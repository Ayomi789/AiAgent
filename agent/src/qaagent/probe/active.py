"""Deterministic active probes: injection payloads against discovered forms.

Runs alongside the passive checks, before the LLM loop, so reflected XSS,
SSTI, SQL injection, login auth bypass, and exposed endpoints are found on
every run regardless of how well the model explores. Uses only plain HTTP —
no LLM calls, no browser.

Every request stays on the target's origin (scope guard).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from difflib import SequenceMatcher
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse

import httpx

from qaagent.config import RunConfig
from qaagent.models import Evidence, FindingCategory, Severity
from qaagent.report.collector import Collector

_XSS = "<script>alert(1)</script>"
_SSTI = "{{7*37}}"  # evaluates to 259 if the template engine renders it
_SSTI_MARK = "259"
_SQLI_TRUE = "x' OR 1=1-- "
_SQLI_FALSE = "x' AND 1=2-- "
_SQLI_ERR = "'"
_LOGIN_BYPASS = "admin' -- "
_TEXT_TYPES = ("text", "search", "email", "number", "tel", "url", "")

# Query params that typically reference a database object by id.
_ID_PARAM_NAMES = (
    "id", "user_id", "uid", "account", "user", "item", "product", "record", "post",
)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")

# Query params that commonly control a redirect destination.
_REDIRECT_PARAMS = (
    "next", "redirect", "url", "return", "return_to", "returnTo", "continue",
    "dest", "destination", "redirect_uri", "goto", "target", "ref", "path",
)
_OFF_ORIGIN_MARKER = "https://evil.example/"


def _is_off_origin(url: str, target: str) -> bool:
    """True if url points to a different origin than target (or is
    protocol-relative to one)."""
    a, b = urlparse(url), urlparse(target)
    if not a.netloc:
        return False  # relative destination
    return a.scheme != b.scheme or a.netloc.lower() != b.netloc.lower()


async def _probe_open_redirect(
    client: httpx.AsyncClient,
    links: list[str],
    target: str,
    collector: Collector,
) -> None:
    """Open-redirect probe: inject an off-origin marker into redirect params.

    For every link carrying a redirect-style query param, rebuild the URL with
    the param set to an attacker-controlled marker and follow the response
    headers. A 3xx to an off-origin destination proves the redirect target is
    user-controlled — an open redirect.
    """
    candidates: set[tuple[str, str]] = set()
    for link in links:
        if not _same_origin(link, target):
            continue
        parsed = urlparse(link)
        params = parse_qs(parsed.query, keep_blank_values=True)
        for name in _REDIRECT_PARAMS:
            if name in params:
                base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                candidates.add((base, name))

    for base, name in candidates:
        probe_url = f"{base}?{name}={quote(_OFF_ORIGIN_MARKER, safe='')}"
        try:
            r = await client.get(probe_url, follow_redirects=False)
        except httpx.HTTPError:
            continue
        location = r.headers.get("location", "")
        if 300 <= r.status_code < 400 and location and _is_off_origin(location, target):
            collector.add(
                title=f"Open redirect in {base}",
                severity=Severity.MEDIUM,
                category=FindingCategory.SECURITY,
                description=(
                    f"GET {base}?{name}=<attacker-url> returns a redirect to an "
                    f"off-origin destination ({location}) — the redirect target "
                    "is taken from user input without validation."
                ),
                url=probe_url,
                remediation=(
                    "Validate redirect targets against an allowlist of internal "
                    "paths; never trust the raw parameter."
                ),
                evidence=[
                    Evidence(
                        kind="http_response",
                        url=probe_url,
                        detail=f"{r.status_code} Location: {location}",
                    )
                ],
            )


async def _probe_idor(
    client: httpx.AsyncClient,
    links: list[str],
    target: str,
    collector: Collector,
) -> None:
    """Object-enumeration (IDOR) probe on id-parameter links found in the crawl.

    Fetches id=1, id=2, and a bogus id. If ids 1 and 2 return distinct real
    objects (and differ from the not-found response) without authentication,
    per-object data is enumerable — an insecure direct object reference.
    """
    candidates: set[tuple[str, str]] = set()
    for link in links:
        if not _same_origin(link, target):
            continue
        parsed = urlparse(link)
        params = parse_qs(parsed.query)
        for name in _ID_PARAM_NAMES:
            if name in params:
                base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                candidates.add((base, name))

    for base, name in candidates:
        url_for = lambda v: f"{base}?{name}={v}"
        try:
            r1 = await client.get(url_for(1))
            r2 = await client.get(url_for(2))
            rn = await client.get(url_for(99999))
        except httpx.HTTPError:
            continue
        if r1.status_code != 200 or r2.status_code != 200:
            continue
        norm = lambda s: " ".join(s.split())[:5000]
        b1, b2, bn = norm(r1.text), norm(r2.text), norm(rn.text)
        if b1 == b2 or b1 == bn:
            continue  # not per-object data, or bogus id indistinguishable
        path = urlparse(base).path or base
        has_emails = bool(_EMAIL_RE.search(b1)) or bool(_EMAIL_RE.search(b2))
        severity = Severity.HIGH if has_emails else Severity.MEDIUM
        title = (
            f"IDOR: object enumeration at {path} exposing user data"
            if has_emails
            else f"IDOR: object enumeration at {path}"
        )
        collector.add(
            title=title,
            severity=severity,
            category=FindingCategory.SECURITY,
            description=(
                f"{base} returns distinct per-object data for sequential ids "
                f"(id=1 and id=2 differ, {len(b1)} vs {len(b2)} chars) without "
                "any authentication — object references are enumerable and "
                "authorization is not enforced on individual objects."
                + (" Responses contain email addresses." if has_emails else "")
            ),
            url=url_for(2),
            remediation="Enforce authorization checks on every object access; do not rely on unguessable ids.",
            evidence=[
                Evidence(kind="http_response", url=url_for(1), detail=f"id=1 -> {r1.status_code} ({len(b1)} chars)"),
                Evidence(kind="http_response", url=url_for(2), detail=f"id=2 -> {r2.status_code} ({len(b2)} chars)"),
                Evidence(kind="http_response", url=url_for(99999), detail=f"id=99999 (bogus) -> {rn.status_code} ({len(bn)} chars)"),
            ],
        )

# Entries are (path, severity, description, remediation, kind). The `kind`
# drives response validation (see _probe_sensitive_paths): HTML panels must
# differ from the site's own homepage (an SPA catch-all serves the same
# index.html for any path — not evidence), while text artifacts (git config,
# .env) must actually match their content type.
_SENSITIVE_PATHS: list[tuple[str, Severity, str, str, str]] = [
    (
        "/admin",
        Severity.HIGH,
        "Admin panel reachable without authentication.",
        "Require authentication and authorization on the admin panel.",
        "panel",
    ),
    (
        "/debug",
        Severity.HIGH,
        "Debug endpoint reachable without authentication (may disclose internals).",
        "Remove debug endpoints in production and require auth.",
        "panel",
    ),
    (
        "/.git/config",
        Severity.HIGH,
        "Version-control metadata exposed.",
        "Block access to .git and other dot-directories.",
        "git",
    ),
    (
        "/.env",
        Severity.HIGH,
        "Environment file exposed (may contain secrets).",
        "Block .env and config files from the web root.",
        "env",
    ),
    (
        "/server-status",
        Severity.MEDIUM,
        "Server status page reachable by unauthenticated users.",
        "Restrict server status pages to administrators.",
        "panel",
    ),
    (
        "/robots.txt",
        Severity.INFO,
        "robots.txt present (may disclose internal paths).",
        "Ensure robots.txt does not leak sensitive paths.",
        "text",
    ),
]


def _same_origin(url: str, target: str) -> bool:
    a, b = urlparse(url), urlparse(target)
    return a.scheme == b.scheme and a.netloc == b.netloc


class _FormParser(HTMLParser):
    """Extract forms (action/method/inputs) and links from a page."""

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.forms: list[dict] = []
        self.links: list[str] = []
        self._current: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs = {k: (v or "") for k, v in attrs}
        if tag == "form":
            self._current = {
                "action": urljoin(self.base_url, attrs.get("action", "")),
                "method": attrs.get("method", "get").lower(),
                "inputs": [],
            }
        elif tag == "input" and self._current is not None:
            self._current["inputs"].append(
                {
                    "name": attrs.get("name", ""),
                    "type": attrs.get("type", "text"),
                }
            )
        elif tag == "a":
            href = attrs.get("href")
            if href:
                self.links.append(urljoin(self.base_url, href))

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._current is not None:
            self.forms.append(self._current)
            self._current = None


def _form_key(form: dict) -> tuple:
    return (
        form["action"],
        form["method"],
        tuple((i["name"], i["type"]) for i in form["inputs"]),
    )


def _first_text_input(form: dict) -> dict | None:
    for inp in form["inputs"]:
        if inp["type"] in _TEXT_TYPES and inp["name"]:
            return inp
    return None


def _path_of(url: str) -> str:
    path = urlparse(url).path or "/"
    return path if len(path) <= 60 else path[:57] + "..."


async def _probe_get_form(
    client: httpx.AsyncClient, form: dict, collector: Collector
) -> None:
    """XSS / SSTI / SQLi probes on a GET form (search-like endpoint)."""
    inp = _first_text_input(form)
    if not inp:
        return
    action = form["action"]
    other = {i["name"]: "" for i in form["inputs"] if i["name"] and i is not inp}

    def url_for(value: str) -> str:
        params = {**other, inp["name"]: value}
        sep = "&" if "?" in action else "?"
        return action + sep + urlencode(params)

    path = _path_of(action)

    # Reflected XSS.
    try:
        r = await client.get(url_for(_XSS))
        if r.status_code < 400 and _XSS in r.text:
            collector.add(
                title=f"Reflected XSS in {path}",
                severity=Severity.HIGH,
                category=FindingCategory.SECURITY,
                description=(
                    f"Payload {_XSS!r} is echoed back unescaped in the response, "
                    "so script payloads will execute in victims' browsers."
                ),
                url=url_for(_XSS),
                remediation="Escape all user input when rendering, and add a Content-Security-Policy.",
                evidence=[Evidence(kind="http_response", url=url_for(_XSS), detail=f"payload reflected in {r.status_code} response")],
            )
    except httpx.HTTPError:
        pass

    # Server-side template injection.
    try:
        r = await client.get(url_for(_SSTI))
        if r.status_code < 400 and _SSTI_MARK in r.text:
            collector.add(
                title=f"Server-side template injection in {path}",
                severity=Severity.HIGH,
                category=FindingCategory.SECURITY,
                description=(
                    f"Payload {_SSTI!r} was evaluated by the template engine "
                    f"(result '{_SSTI_MARK}' appears in the response) — arbitrary "
                    "template code may be executable."
                ),
                url=url_for(_SSTI),
                remediation="Treat user input as data: never interpolate it into templates.",
                evidence=[Evidence(kind="http_response", url=url_for(_SSTI), detail=f"payload evaluated -> {_SSTI_MARK}")],
            )
    except httpx.HTTPError:
        pass

    # SQL injection via differential response (true vs false condition).
    try:
        r_true = await client.get(url_for(_SQLI_TRUE))
        r_false = await client.get(url_for(_SQLI_FALSE))
        if (
            r_true.status_code < 400
            and r_false.status_code < 400
            and len(r_true.text) > len(r_false.text) * 1.15
        ):
            collector.add(
                title=f"SQL injection in {path}",
                severity=Severity.HIGH,
                category=FindingCategory.SECURITY,
                description=(
                    f"Boolean-based SQL injection: {_SQLI_TRUE!r} returns "
                    "significantly more content than a false condition, meaning "
                    "the query string is concatenated into SQL."
                ),
                url=url_for(_SQLI_TRUE),
                remediation="Use parameterized queries; never build SQL from user input.",
                evidence=[Evidence(kind="http_response", url=url_for(_SQLI_TRUE), detail=f"true={len(r_true.text)}B vs false={len(r_false.text)}B")],
            )
    except httpx.HTTPError:
        pass

    # SQL injection via error (single quote breaks the query).
    try:
        r = await client.get(url_for(_SQLI_ERR))
        if r.status_code >= 500:
            collector.add(
                title=f"SQL injection (error-based) in {path}",
                severity=Severity.MEDIUM,
                category=FindingCategory.SECURITY,
                description=(
                    f"A single quote ({_SQLI_ERR!r}) breaks the query and produces "
                    f"an HTTP {r.status_code}, indicating string-built SQL."
                ),
                url=url_for(_SQLI_ERR),
                remediation="Use parameterized queries; never build SQL from user input.",
                evidence=[Evidence(kind="http_response", url=url_for(_SQLI_ERR), detail=f"single quote -> {r.status_code}")],
            )
    except httpx.HTTPError:
        pass


async def _probe_login_form(
    client: httpx.AsyncClient, form: dict, collector: Collector
) -> None:
    """Auth-bypass probe on a POST form with a password field."""
    if not any(i["type"] == "password" for i in form["inputs"]):
        return
    user_field = next(
        (i["name"] for i in form["inputs"] if i["type"] in ("text", "email", "username", "") and i["name"]),
        None,
    )
    pass_field = next((i["name"] for i in form["inputs"] if i["type"] == "password"), None)
    if not user_field or not pass_field:
        return
    action = form["action"]
    data = {user_field: _LOGIN_BYPASS, pass_field: "x"}
    try:
        r = await client.post(action, data=data, follow_redirects=False)
        location = r.headers.get("location", "")
        if 300 <= r.status_code < 400:
            collector.add(
                title="SQL injection in login form (authentication bypass)",
                severity=Severity.CRITICAL,
                category=FindingCategory.SECURITY,
                description=(
                    f"Logging in with username {_LOGIN_BYPASS!r} and any password "
                    "succeeds and redirects, meaning the auth query is built from "
                    "unvalidated input."
                ),
                url=action,
                remediation="Use parameterized queries and never build the auth query from user input.",
                evidence=[Evidence(kind="http_response", url=action, detail=f"POST -> {r.status_code} Location: {location}")],
            )
    except httpx.HTTPError:
        pass


# Common backup/database/config files that should never be web-accessible.
# Unlike _SENSITIVE_PATHS (fixed endpoints), these catch *newly shipped*
# regressions — a file that suddenly appears at the web root — which is exactly
# what a release-to-release baseline comparison is meant to detect.
# Common backup/database/config files that should never be web-accessible.
# Entries are (path, kind, description). Unlike _SENSITIVE_PATHS (fixed
# endpoints), these catch *newly shipped* regressions — a file that suddenly
# appears at the web root — which is exactly what a release-to-release
# baseline comparison is meant to detect.
#
# The `kind` drives content validation (see _content_matches): a plain 200 is
# NOT enough, because many apps serve index.html for any path (SPA fallback).
# A finding only fires when the response body actually looks like the expected
# file type (magic bytes / SQL markers / env-var pairs / PEM header) and the
# MIME type isn't HTML.
_SENSITIVE_FILES: list[tuple[str, str, str]] = [
    # SQL dumps.
    ("/backup.sql", "sql", "Database backup exposed (may contain credentials and user data)."),
    ("/dump.sql", "sql", "Database dump exposed."),
    ("/backup-db.sql", "sql", "Database backup exposed."),
    ("/db.sql", "sql", "Database dump exposed."),
    ("/database.sql", "sql", "Database dump exposed."),
    ("/db-dump.sql", "sql", "Database dump exposed."),
    ("/database-backup.sql", "sql", "Database backup exposed."),
    ("/mysql.sql", "sql", "MySQL dump exposed."),
    ("/backup-2024.sql", "sql", "Database backup exposed."),
    ("/backup-2025.sql", "sql", "Database backup exposed."),
    ("/backup-2026.sql", "sql", "Database backup exposed."),
    # SQLite / database files.
    ("/db.sqlite3", "sqlite", "SQLite database file exposed."),
    ("/db.sqlite", "sqlite", "SQLite database file exposed."),
    ("/database.sqlite", "sqlite", "SQLite database file exposed."),
    ("/database.sqlite3", "sqlite", "SQLite database file exposed."),
    ("/data.db", "sqlite", "Database file exposed."),
    ("/app.db", "sqlite", "Database file exposed."),
    ("/site.db", "sqlite", "Database file exposed."),
    ("/users.db", "sqlite", "Database file exposed (may contain user credentials)."),
    ("/sqlite.db", "sqlite", "Database file exposed."),
    ("/backup.db", "sqlite", "Database file exposed."),
    ("/backup.sqlite3", "sqlite", "Database file exposed."),
    # Archives (zip / tar / gzip / rar / 7z).
    ("/backup.zip", "archive", "Archive backup exposed."),
    ("/backup.tar.gz", "archive", "Archive backup exposed."),
    ("/backup.tgz", "archive", "Archive backup exposed."),
    ("/backup.tar", "archive", "Archive backup exposed."),
    ("/backup.rar", "archive", "Archive backup exposed."),
    ("/backup.7z", "archive", "Archive backup exposed."),
    ("/site.zip", "archive", "Site archive (source/database) exposed."),
    ("/site.tar.gz", "archive", "Site archive (source/database) exposed."),
    ("/dump.zip", "archive", "Archive dump exposed."),
    ("/dump.tar.gz", "archive", "Archive dump exposed."),
    ("/db.zip", "archive", "Database archive exposed."),
    ("/db-backup.zip", "archive", "Database archive exposed."),
    ("/web.zip", "archive", "Site archive exposed."),
    ("/www.zip", "archive", "Site archive exposed."),
    ("/htdocs.zip", "archive", "Site archive exposed."),
    ("/public_html.zip", "archive", "Site archive exposed."),
    # Config / source backups (text).
    ("/app.bak", "text", "Backup of application source exposed."),
    ("/config.bak", "text", "Backup of configuration exposed."),
    ("/config.php.bak", "text", "Backup of configuration/source exposed."),
    ("/wp-config.php.bak", "text", "Backup of WordPress configuration exposed."),
    ("/web.config.bak", "text", "Backup of web configuration exposed."),
    ("/application.bak", "text", "Backup of application source exposed."),
    ("/config.old", "text", "Old configuration file exposed."),
    ("/config.save", "text", "Saved configuration file exposed."),
    ("/config.txt", "text", "Configuration file exposed."),
    ("/settings.py.bak", "text", "Backup of application settings exposed."),
    ("/.htaccess.bak", "text", "Backup of server configuration exposed."),
    ("/.htpasswd", "text", "HTTP basic-auth credential file exposed."),
    # Env / secret files.
    ("/.env.bak", "env", "Backup of environment file (may contain secrets)."),
    ("/.env.old", "env", "Old environment file (may contain secrets)."),
    ("/.env.save", "env", "Saved environment file (may contain secrets)."),
    ("/.env.backup", "env", "Backup of environment file (may contain secrets)."),
    ("/.env.production", "env", "Production environment file exposed (may contain secrets)."),
    ("/env.js", "env", "Environment configuration exposed (may contain secrets)."),
    ("/credentials.txt", "text", "Credential file exposed."),
    ("/passwords.txt", "text", "Password file exposed."),
    ("/secret.txt", "text", "Secret file exposed."),
    ("/secrets.json", "text", "Secrets file exposed."),
    ("/keys.json", "text", "Keys file exposed."),
    # Private keys.
    ("/private_key.pem", "key", "Private key exposed."),
    ("/server.key", "key", "TLS/private key exposed."),
    ("/id_rsa", "key", "SSH private key exposed."),
]

# Fallback descriptions for config-supplied artifact names (the built-in
# wordlist above carries its own per-file descriptions).
_KIND_DESCRIPTIONS = {
    "sql": "Database backup exposed (may contain credentials and user data).",
    "sqlite": "Database file exposed.",
    "archive": "Archive backup exposed.",
    "env": "Environment file exposed (may contain secrets).",
    "key": "Private key exposed.",
    "git": "Version-control metadata exposed.",
    "text": "Sensitive file exposed.",
}


def _sensitive_files_for(config: RunConfig) -> list[tuple[str, str, str]]:
    """Built-in wordlist plus any names the config adds (path, kind, description)."""
    files = list(_SENSITIVE_FILES)
    for path, kind in config.sensitive_files.items():
        files.append((path, kind, _KIND_DESCRIPTIONS.get(kind, "Sensitive file exposed.")))
    return files


# Content signatures used to confirm a response is really the expected kind.
_SQLITE_MAGIC = b"SQLite format 3\x00"
_ARCHIVE_MAGICS = (b"PK\x03\x04", b"\x1f\x8b", b"Rar!\x1a\x07", b"7z\xbc\xaf\x27\x1c")
_SQL_MARKERS = (
    b"create table",
    b"insert into",
    b"drop table",
    b"pragma ",
    b"begin transaction",
    b"-- mysql dump",
    b"-- sql dump",
    b"postgresql database dump",
    b"pg_dump",
    b"backup database",
)
_SENSITIVE_ENV_KEYS = (
    "secret",
    "password",
    "api_key",
    "apikey",
    "token",
    "database_url",
    "private_key",
    "access_key",
    "client_secret",
)
_GIT_MARKERS = (
    b"[core]",
    b"[remote",
    b"[branch",
    b"[user]",
    b"repositoryformatversion",
    b"[http]",
)
_MAX_PROBE_BYTES = 65536  # never download a whole multi-MB backup to sniff it


def _is_html(head: bytes) -> bool:
    low = head[:4096].lstrip().lower()
    return low.startswith(b"<!doctype html") or b"<html" in low[:512]


def _content_matches(kind: str, head: bytes, content_type: str) -> bool:
    """True if the response body looks like the expected file kind.

    Ground truth is the content signature (magic bytes / markers), not the
    Content-Type header alone (servers mislabel types). HTML bodies never
    match — that is the SPA-fallback false-positive case.
    """
    ct = content_type.lower()
    if kind == "sqlite":
        return head.startswith(_SQLITE_MAGIC)
    if kind == "archive":
        return head.startswith(_ARCHIVE_MAGICS) or head[257:262] == b"ustar"
    if kind == "sql":
        if _is_html(head):
            return False
        return any(m in head.lower() for m in _SQL_MARKERS) or "sql" in ct
    if kind == "env":
        if _is_html(head):
            return False
        lines = head.decode("utf-8", "ignore").splitlines()
        kv = [ln for ln in lines if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*=", ln)]
        return len(kv) >= 2 and any(
            ln.split("=", 1)[0].strip().lower() in _SENSITIVE_ENV_KEYS for ln in kv
        )
    if kind == "key":
        return b"-----BEGIN" in head
    if kind == "git":
        if _is_html(head):
            return False
        return any(m in head.lower() for m in _GIT_MARKERS)
    if kind == "text":
        if _is_html(head):
            return False
        return bool(head.strip())  # non-trivial non-HTML content
    return True

_PASSWORD_INPUT_RE = re.compile(
    r"<input[^>]*type=['\"]password['\"]", re.IGNORECASE
)


def _is_login_page(html: str) -> bool:
    """True if the page is an authentication form (a password input).

    A sensitive path that returns 200 but is merely a login form is the
    *expected* state (the endpoint exists but is gated), not an exposed
    panel — skipping it avoids false positives on real sites.
    """
    return bool(_PASSWORD_INPUT_RE.search(html))


def _normalize_html(text: str) -> str:
    return " ".join(text.split()).lower()[:20000]


def _is_spa_fallback(body_norm: str, home_norm: str) -> bool:
    """True if a 200 body looks like the site's own index page.

    Single-page apps serve the same index.html for any path, so a 200 on
    /admin that is ~identical to the homepage is a catch-all fallback, not an
    exposed panel. Requires both to be non-empty to avoid matching on "" == "".
    """
    if not body_norm or not home_norm:
        return False
    if body_norm == home_norm:
        return True
    return SequenceMatcher(None, body_norm[:8000], home_norm[:8000]).ratio() >= 0.9


async def _fetch_home_norm(client: httpx.AsyncClient, target: str) -> str:
    """Normalized homepage body, used to recognize SPA catch-all fallbacks."""
    try:
        hr = await client.get(target)
        if hr.status_code < 400:
            return _normalize_html(hr.text)
    except httpx.HTTPError:
        pass
    return ""


async def _add_sensitive_url(
    client: httpx.AsyncClient,
    collector: Collector,
    url: str,
    path: str,
    severity: Severity,
    description: str,
    remediation: str,
    kind: str,
    home_norm: str,
) -> bool:
    """Validate one sensitive URL and record it if genuinely exposed.

    Shared by the root path probe and the subdirectory probe so both apply
    the same rules: empty/login/SPA-fallback bodies never fire, and text
    artifacts must match their content kind.
    """
    try:
        r = await client.get(url)
    except httpx.HTTPError:
        return False
    if r.status_code != 200:
        return False
    text = r.text
    if not text.strip():
        return False  # empty body is not evidence of exposure
    if _is_login_page(text):
        return False  # gated behind a login form — expected, not exposed
    if kind in ("git", "env"):
        if not _content_matches(kind, r.content, r.headers.get("content-type", "")):
            return False
    elif kind == "text":
        if _is_html(r.content):
            return False
    else:  # panel: HTML admin/debug/status pages
        if _is_spa_fallback(_normalize_html(text), home_norm):
            return False
    collector.add(
        title=f"Sensitive endpoint exposed: {path}",
        severity=severity,
        category=FindingCategory.SECURITY,
        description=description,
        url=url,
        remediation=remediation,
        content_type=r.headers.get("content-type") or None,
        evidence=[
            Evidence(
                kind="http_response",
                url=url,
                detail=(
                    f"GET {path} -> 200, Content-Type: "
                    f"{r.headers.get('content-type', 'n/a')}, "
                    f"{len(text)} chars, kind: {kind}"
                ),
            )
        ],
    )
    return True


async def _probe_sensitive_paths(
    client: httpx.AsyncClient,
    target: str,
    collector: Collector,
    home_norm: str | None = None,
) -> None:
    """Probe the fixed sensitive endpoints at the web root."""
    if home_norm is None:
        home_norm = await _fetch_home_norm(client, target)
    for path, severity, description, remediation, kind in _SENSITIVE_PATHS:
        await _add_sensitive_url(
            client, collector, urljoin(target, path), path, severity,
            description, remediation, kind, home_norm,
        )


async def _probe_sensitive_files(
    client: httpx.AsyncClient,
    target: str,
    collector: Collector,
    files: list[tuple[str, str, str]] | None = None,
    bases: tuple[str, ...] = ("/",),
    subdir_names: set[str] | None = None,
) -> None:
    """Probe for backup/database/config files under the given base paths.

    A plain 200 is not enough: many apps serve index.html for any path (SPA
    fallback). A finding only fires when the response content matches the
    expected kind (magic bytes / markers / MIME type) — so a misconfigured
    catch-all route is ignored, while a real exposed backup is confirmed.
    Bodies are capped at 64 KiB so large backups are never downloaded whole.
    `subdir_names` narrows the wordlist when probing subdirectories (a
    focused, high-value subset instead of every name under every directory).
    """
    for path, kind, description in files or _SENSITIVE_FILES:
        name = path.lstrip("/")
        for base in bases:
            if subdir_names is not None and name not in subdir_names:
                continue
            full = (base + name) if base != "/" else path
            url = urljoin(target, full)
            head = b""
            content_type = ""
            status = 0
            try:
                async with client.stream("GET", url) as r:
                    status = r.status_code
                    content_type = r.headers.get("content-type", "")
                    async for chunk in r.aiter_bytes():
                        head += chunk
                        if len(head) >= _MAX_PROBE_BYTES:
                            break
            except httpx.HTTPError:
                continue
            if status == 200 and _content_matches(kind, head, content_type):
                collector.add(
                    title=f"Sensitive file exposed: {full}",
                    severity=Severity.MEDIUM,
                    category=FindingCategory.SECURITY,
                    description=(
                        description
                        + f" Content verified as {kind} (Content-Type: {content_type or 'n/a'})."
                    ),
                    content_type=content_type or None,
                    url=url,
                    remediation="Remove backups from the web root; store them privately and rotate any exposed secrets.",
                    evidence=[
                        Evidence(
                            kind="http_response",
                            url=url,
                            detail=(
                                f"GET {full} -> 200, Content-Type: {content_type or 'n/a'}, "
                                f"{len(head)}+ bytes, kind: {kind}"
                            ),
                        )
                    ],
                )


def _discover_directories(
    urls: Iterable[str], limit: int = 6, max_depth: int = 2
) -> list[str]:
    """Directory prefixes (up to max_depth levels) of the crawled pages.

    /blog/post/1 -> /blog/ and /blog/post/. Root-level pages yield nothing,
    and results are sorted + capped so subdirectory probing stays bounded.
    """
    dirs: set[str] = set()
    for u in urls:
        segments = [s for s in urlparse(u).path.split("/") if s]
        for depth in range(1, min(len(segments), max_depth) + 1):
            dirs.add("/" + "/".join(segments[:depth]) + "/")
    return sorted(dirs)[:limit]


# Focused, high-value artifact names probed under *discovered subdirectories*
# (the full ~60-name wordlist would be hundreds of requests per directory).
_SUBDIR_FILES: tuple[tuple[str, str], ...] = (
    (".env", "env"),
    (".env.bak", "env"),
    (".env.old", "env"),
    (".git/config", "git"),
    ("backup.sql", "sql"),
    ("dump.sql", "sql"),
    ("db.sqlite3", "sqlite"),
    ("data.db", "sqlite"),
    ("backup.zip", "archive"),
    ("credentials.txt", "text"),
    ("private_key.pem", "key"),
    ("server.key", "key"),
    ("config.php.bak", "text"),
)


async def _probe_subdirectories(
    client: httpx.AsyncClient,
    target: str,
    collector: Collector,
    dirs: list[str],
    files: list[tuple[str, str, str]],
    home_norm: str,
) -> None:
    """Probe discovered subdirectories for exposed artifacts and panels.

    Runs the focused file wordlist (plus any config-supplied names) under
    each discovered directory, and checks for admin/debug panels the same
    way the root probe does (homepage-diff rejects SPA fallbacks).
    """
    if not dirs:
        return
    # Subdir wordlist = focused built-ins + config-supplied names (the main
    # wordlist lacks plain .env / .git/config / dump.sql, which are probed at
    # the root via _SENSITIVE_PATHS but belong under subdirectories too).
    entries: dict[str, str] = dict(_SUBDIR_FILES)  # name -> kind
    for p, k, _ in files:
        entries.setdefault(p.lstrip("/"), k)
    sub_files = [
        (name, kind, _KIND_DESCRIPTIONS.get(kind, "Sensitive file exposed."))
        for name, kind in entries.items()
    ]
    await _probe_sensitive_files(
        client, target, collector, sub_files, bases=tuple(dirs)
    )
    for base in dirs:
        for name, severity, description, remediation in (
            (
                "admin",
                Severity.HIGH,
                "Admin panel reachable without authentication.",
                "Require authentication and authorization on the admin panel.",
            ),
            (
                "debug",
                Severity.HIGH,
                "Debug endpoint reachable without authentication (may disclose internals).",
                "Remove debug endpoints in production and require auth.",
            ),
        ):
            await _add_sensitive_url(
                client, collector, urljoin(target, base + name), base + name,
                severity, description, remediation, "panel", home_norm,
            )


async def run_active_probe(config: RunConfig, collector: Collector) -> None:
    """Crawl the target, discover forms, and fire the payload probes."""
    target = config.target
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        # 1. Crawl: home page, then a handful of same-origin links, collecting
        #    forms (which reveals search/login pages without hardcoding paths)
        #    and links (for the IDOR probe).
        forms: list[dict] = []
        all_links: set[str] = set()
        seen_urls: set[str] = set()
        ok_urls: set[str] = set()
        try:
            resp = await client.get(target)
            if resp.status_code >= 400:
                return
            parser = _FormParser(target)
            parser.feed(resp.text)
            forms.extend(parser.forms)
            all_links.update(u for u in parser.links if _same_origin(u, target))
            seen_urls.add(target)
            ok_urls.add(target)
            for link in sorted(all_links)[:8]:
                if link in seen_urls:
                    continue
                seen_urls.add(link)
                try:
                    r = await client.get(link)
                    if r.status_code < 400:
                        ok_urls.add(link)
                        p = _FormParser(link)
                        p.feed(r.text)
                        forms.extend(p.forms)
                        all_links.update(u for u in p.links if _same_origin(u, target))
                except httpx.HTTPError:
                    pass
        except httpx.HTTPError:
            return

        # 2. Probe each unique form (GET = search-like, POST = login-like).
        seen_forms: set[tuple] = set()
        for form in forms:
            if not _same_origin(form["action"], target):
                continue
            key = _form_key(form)
            if key in seen_forms:
                continue
            seen_forms.add(key)
            if form["method"] == "get":
                await _probe_get_form(client, form, collector)
            elif form["method"] == "post":
                await _probe_login_form(client, form, collector)

        # 3. Sensitive endpoints and backup files on the target origin.
        files = _sensitive_files_for(config)
        home_norm = await _fetch_home_norm(client, target)
        await _probe_sensitive_paths(client, target, collector, home_norm=home_norm)
        await _probe_sensitive_files(client, target, collector, files)

        # 3b. Discovered subdirectories: probe the same artifact classes there.
        dirs = _discover_directories(ok_urls)
        await _probe_subdirectories(
            client, target, collector, dirs, files, home_norm
        )

        # 4. IDOR / object enumeration on id-parameter links.
        await _probe_idor(client, sorted(all_links), target, collector)

        # 5. Open redirect on redirect-parameter links.
        await _probe_open_redirect(client, sorted(all_links), target, collector)
