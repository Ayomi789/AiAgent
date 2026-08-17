"""Deterministic passive security checks — no LLM required.

Runs at the start of every session: security headers, cookie flags, and the
server banner. These always produce genuine findings regardless of how well
the model performs.
"""

from __future__ import annotations

import httpx

from qaagent.config import CredentialsConfig
from qaagent.models import Evidence, FindingCategory, Severity
from qaagent.report.collector import Collector

_HEADER_CHECKS: list[tuple[str, Severity, str, str]] = [
    (
        "Content-Security-Policy",
        Severity.MEDIUM,
        "Missing Content-Security-Policy header — XSS and injection impact is amplified without it.",
        "Set a Content-Security-Policy appropriate to the site.",
    ),
    (
        "X-Frame-Options",
        Severity.MEDIUM,
        "Missing X-Frame-Options header — the site may be embedded in third-party frames (clickjacking).",
        "Set X-Frame-Options: DENY or use CSP frame-ancestors.",
    ),
    (
        "Strict-Transport-Security",
        Severity.LOW,
        "Missing Strict-Transport-Security header — browsers will allow plain HTTP connections to this host.",
        "Enable HTTPS everywhere and set HSTS (with preload once ready).",
    ),
    (
        "X-Content-Type-Options",
        Severity.LOW,
        "Missing X-Content-Type-Options header — browsers may MIME-sniff responses.",
        "Set X-Content-Type-Options: nosniff.",
    ),
    (
        "Referrer-Policy",
        Severity.INFO,
        "Missing Referrer-Policy header — full URLs may leak to third parties in the Referer header.",
        "Set a strict Referrer-Policy such as same-origin.",
    ),
]


async def run_passive_probe(
    target: str,
    credentials: CredentialsConfig | None,
    collector: Collector,
) -> None:
    """Check headers and cookies on the target root; log in if credentials exist."""
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        try:
            resp = await client.get(target)
        except httpx.HTTPError as exc:
            collector.add(
                title="Target unreachable over HTTP",
                severity=Severity.HIGH,
                category=FindingCategory.BUG,
                description=f"GET {target} failed: {exc}",
                url=target,
            )
            return

        _check_headers(resp, collector, target)
        _check_server_banner(resp, collector, target)

        # Cookie flags: prefer the real session cookie from a login (if
        # credentials exist), otherwise whatever the root page sets.
        set_cookie = resp.headers.get("set-cookie")
        cookie_url = target
        if credentials:
            try:
                login_url = target.rstrip("/") + "/login"
                r = await client.post(
                    login_url,
                    data={"username": credentials.username, "password": credentials.password},
                )
                login_cookie = r.headers.get("set-cookie")
                if login_cookie:
                    set_cookie, cookie_url = login_cookie, login_url
            except httpx.HTTPError:
                pass
        if set_cookie:
            _check_cookie_flags(set_cookie, collector, cookie_url)


def _check_headers(resp: httpx.Response, collector: Collector, url: str) -> None:
    headers = {k.lower(): v for k, v in resp.headers.items()}
    for name, severity, description, remediation in _HEADER_CHECKS:
        if name.lower() not in headers:
            collector.add(
                title=f"Missing {name} header",
                severity=severity,
                category=FindingCategory.SECURITY,
                description=description,
                url=url,
                remediation=remediation,
                evidence=[
                    Evidence(
                        kind="http_response",
                        url=url,
                        detail=f"GET {url} -> {resp.status_code}; header '{name}' absent",
                    )
                ],
            )


def _check_server_banner(resp: httpx.Response, collector: Collector, url: str) -> None:
    for header in ("server", "x-powered-by"):
        value = resp.headers.get(header)
        if value:
            collector.add(
                title=f"Server banner disclosed: {header}: {value}",
                severity=Severity.LOW,
                category=FindingCategory.SECURITY,
                description=f"The {header} response header reveals server technology, useful for targeting exploits.",
                url=url,
                remediation="Remove or obfuscate server banner headers.",
                evidence=[Evidence(kind="http_response", url=url, detail=f"{header}: {value}")],
            )


def _check_cookie_flags(set_cookie: str, collector: Collector, url: str) -> None:
    name = set_cookie.split(";")[0].split("=")[0].strip()
    lowered = set_cookie.lower()
    missing = [flag for flag in ("HttpOnly", "Secure", "SameSite") if flag.lower() not in lowered]
    if missing:
        collector.add(
            title=f"Cookie '{name}' missing {', '.join(missing)}",
            severity=Severity.MEDIUM,
            category=FindingCategory.SECURITY,
            description=(
                f"The '{name}' cookie is set without {', '.join(missing)}. "
                "HttpOnly prevents JavaScript theft, Secure forces HTTPS, SameSite mitigates CSRF."
            ),
            url=url,
            remediation="Set the missing cookie flags.",
            evidence=[Evidence(kind="http_response", url=url, detail=set_cookie)],
        )
