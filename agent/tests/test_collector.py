"""Collector tests: exact + concept-aware deduplication."""

from __future__ import annotations

from qaagent.models import FindingCategory, Severity
from qaagent.report.collector import Collector

T = "http://x.test"


def _add(collector: Collector, title: str, url: str | None = None):
    return collector.add(
        title=title,
        severity=Severity.HIGH,
        category=FindingCategory.SECURITY,
        url=url,
    )


def test_exact_duplicate_merges():
    col = Collector()
    first = _add(col, "Reflected XSS in /search", T + "/search")
    second = _add(col, "Reflected XSS in /search", T + "/search")
    assert first is second
    assert len(col.findings) == 1


def test_llm_admin_variants_merge_into_probe_finding():
    col = Collector()
    probe = _add(col, "Sensitive endpoint exposed: /admin", T + "/admin")
    llm1 = _add(col, "Unauthenticated Admin Panel", T + "/admin")
    llm2 = _add(col, "Broken Access Control", T + "/admin")
    assert probe is llm1 is llm2
    assert len(col.findings) == 1
    notes = [e.detail for e in probe.evidence if e.kind == "note"]
    assert "also reported as: Unauthenticated Admin Panel" in notes


def test_xss_variants_merge():
    col = Collector()
    first = _add(col, "Reflected XSS in /search", T + "/search")
    second = _add(col, "XSS in the search box", T + "/search")
    assert first is second


def test_distinct_findings_stay_distinct():
    col = Collector()
    xss = _add(col, "Reflected XSS in /search", T + "/search")
    sqli = _add(col, "SQL injection in /search", T + "/search")
    ssti = _add(col, "Server-side template injection in /search", T + "/search")
    assert xss is not sqli and sqli is not ssti and xss is not ssti
    assert len(col.findings) == 3


def test_sqli_boolean_and_error_based_merge():
    col = Collector()
    a = _add(col, "SQL injection in /search", T + "/search")
    b = _add(col, "SQL injection (error-based) in /search", T + "/search")
    assert a is b


def test_header_findings_never_fuzzy_merge():
    col = Collector()
    csp = _add(col, "Missing Content-Security-Policy header", T)
    xfo = _add(col, "Missing X-Frame-Options header", T)
    assert csp is not xfo
    assert len(col.findings) == 2


def test_same_title_different_url_stays_distinct():
    col = Collector()
    a = _add(col, "Sensitive endpoint exposed: /admin", T + "/admin")
    b = _add(col, "Sensitive endpoint exposed: /debug", T + "/debug")
    assert a is not b


def test_idor_merges_across_query_params():
    col = Collector()
    a = _add(col, "IDOR: object enumeration at /profile exposing user data", T + "/profile?id=2")
    b = _add(col, "IDOR on the profile page", T + "/profile?id=5")
    assert a is b


def test_cookie_findings_merge():
    col = Collector()
    a = _add(col, "Cookie 'session' missing HttpOnly, Secure, SameSite", T + "/login")
    b = _add(col, "Weak session cookie", T + "/login")
    assert a is b
