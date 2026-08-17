"""Probe tests: run the deterministic probes against the vulnerable demo app."""

from __future__ import annotations

from qaagent.config import CredentialsConfig, RunConfig, ScopeConfig
from qaagent.probe.active import (
    _content_matches,
    _discover_directories,
    _is_login_page,
    _is_spa_fallback,
    _sensitive_files_for,
    run_active_probe,
)
from qaagent.probe.passive import run_passive_probe
from qaagent.report.collector import Collector


def _cfg(target: str) -> RunConfig:
    return RunConfig(
        target=target,
        scope=ScopeConfig(allowed_origins=[target]),
        credentials=CredentialsConfig(username="alice", password="alice123"),
    )


def test_sensitive_files_for_merges_builtin_and_custom():
    cfg = _cfg("http://x.test")
    cfg = RunConfig.model_validate(
        {**cfg.model_dump(), "sensitive_files": {"/custom.sql": "sql", "/deploy.key": "key"}}
    )
    files = _sensitive_files_for(cfg)
    paths = {f[0] for f in files}
    assert "/backup.sql" in paths  # built-in still present
    assert "/custom.sql" in paths
    assert "/deploy.key" in paths
    kinds = {f[0]: f[1] for f in files}
    assert kinds["/custom.sql"] == "sql"
    assert kinds["/deploy.key"] == "key"


async def test_custom_sensitive_file_is_probed(target):
    # The app's /healthz returns 200 with JSON (non-HTML) — pointing a custom
    # entry at it proves config-supplied names are really probed end-to-end.
    cfg = RunConfig.model_validate(
        {**_cfg(target).model_dump(), "sensitive_files": {"/healthz": "text"}}
    )
    collector = Collector()
    await run_active_probe(cfg, collector)
    titles = {f.title for f in collector.findings}
    assert "Sensitive file exposed: /healthz" in titles
    hit = next(f for f in collector.findings if f.title == "Sensitive file exposed: /healthz")
    assert hit.content_type == "application/json"


async def test_passive_probe_finds_header_and_cookie_issues(target):
    cfg = _cfg(target)
    collector = Collector()
    await run_passive_probe(target, cfg.credentials, collector)
    titles = {f.title for f in collector.findings}
    assert "Missing Content-Security-Policy header" in titles
    assert "Missing X-Frame-Options header" in titles
    assert "Cookie 'session' missing HttpOnly, Secure, SameSite" in titles
    assert any("Server banner" in t for t in titles)


async def test_active_probe_finds_injection_and_access_flaws(target):
    collector = Collector()
    await run_active_probe(_cfg(target), collector)
    titles = {f.title for f in collector.findings}
    assert "Reflected XSS in /search" in titles
    assert "Server-side template injection in /search" in titles
    assert "SQL injection in /search" in titles
    assert "SQL injection in login form (authentication bypass)" in titles
    assert "Sensitive endpoint exposed: /admin" in titles
    assert "Sensitive endpoint exposed: /debug" in titles
    assert any("IDOR" in t for t in titles)
    assert any("Open redirect" in t for t in titles)


def test_sensitive_file_content_matches():
    # Real signatures confirm the expected kind.
    assert _content_matches("sqlite", b"SQLite format 3\x00rest", "application/octet-stream")
    assert _content_matches("archive", b"PK\x03\x04rest", "application/zip")
    assert _content_matches("archive", b"\x1f\x8b\x08rest", "application/x-gzip")
    assert _content_matches("key", b"-----BEGIN OPENSSH PRIVATE KEY-----\nabc", "text/plain")
    assert _content_matches(
        "sql", b"-- SQL dump --\nCREATE TABLE users (id int);\nINSERT INTO users VALUES (1);", "text/plain"
    )
    assert _content_matches(
        "env", b"DATABASE_URL=postgres://x\nAPI_KEY=abc123\nSECRET=xyz", "text/plain"
    )
    assert _content_matches("text", b"<?php $db = new PDO(...); ?>", "text/plain")

    # A 200 that is really the SPA fallback index.html must NOT fire.
    html = b"<!doctype html><html><head><title>app</title></head><body>home</body></html>"
    assert not _content_matches("sql", html, "text/html")
    assert not _content_matches("env", html, "text/html")
    assert not _content_matches("text", html, "text/html")
    assert not _content_matches("sqlite", html, "text/html")
    assert not _content_matches("archive", html, "text/html")

    # A bare 200 with the wrong content is not evidence of anything.
    assert not _content_matches("sql", b"<html><body>not found page</body></html>", "text/plain")
    assert not _content_matches("env", b"username=alice\nrole=admin", "text/plain")


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()[:20000]


def test_spa_fallback_discrimination():
    home = _norm("<html><head><title>Home</title></head><body>Welcome to my site</body></html>")
    # Same page served for another path -> SPA fallback.
    assert _is_spa_fallback(home, home)
    assert _is_spa_fallback(_norm("<html><head><title>Home</title></head><body>Welcome to my site!</body></html>"), home)
    # A genuinely different page is not a fallback.
    assert not _is_spa_fallback(
        _norm("<html><head><title>Admin</title></head><body>user table</body></html>"), home
    )
    # Empty bodies are never "fallbacks" (guards against "" == "" matches).
    assert not _is_spa_fallback("", "")
    assert not _is_spa_fallback("", home)


def test_discover_directories():
    urls = [
        "http://x.test/",
        "http://x.test/blog",
        "http://x.test/blog/post/1",
        "http://x.test/api/users",
        "http://x.test/search",
    ]
    dirs = _discover_directories(urls)
    assert "/blog/" in dirs
    assert "/blog/post/" in dirs
    assert "/api/" in dirs
    assert "/search/" in dirs
    assert "/" not in dirs  # root is probed separately
    # Deterministic order and bounded size.
    assert dirs == sorted(dirs)
    assert len(_discover_directories(["http://x.test/a/b/c/d" for _ in range(20)])) <= 6


def test_git_config_content_matches():
    assert _content_matches(
        "git", b"[core]\n\trepositoryformatversion = 0\n[remote \"origin\"]\n\turl = https://github.com/x/y.git", "text/plain"
    )
    # HTML fallback serving index.html for /.git/config must not match.
    html = b"<!doctype html><html><body>home</body></html>"
    assert not _content_matches("git", html, "text/html")


def test_login_page_discrimination():
    # A password input makes a page a login form (expected, not exposed).
    assert _is_login_page("<form><input type='password' name='pw'></form>")
    assert _is_login_page('<input type="password" name="pw">')
    # Panel/dashboard content without a password input is not a login page.
    assert not _is_login_page("<table><tr><td>admin panel</td></tr></table>")
    assert not _is_login_page("")


async def test_probes_find_expected_severity_span(target):
    collector = Collector()
    await run_active_probe(_cfg(target), collector)
    severities = {f.severity for f in collector.findings}
    assert severities  # at least one finding
    assert any(f.severity.value == "critical" for f in collector.findings)
