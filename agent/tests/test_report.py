"""Report generator and live-state tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from qaagent.live import LiveState
from qaagent.models import Evidence, Finding, FindingCategory, Report, Severity
from qaagent.report.generator import (
    render_html,
    render_markdown,
    render_testio_bug,
    save_report,
    save_report_csv,
    save_report_html,
    save_report_json,
    save_report_testio,
    save_summary,
)


def _report() -> Report:
    now = datetime.now(timezone.utc)
    report = Report(
        target="http://x.test",
        started_at=now,
        finished_at=now,
        findings=[
            Finding(title="Low thing", severity=Severity.LOW, category=FindingCategory.SECURITY),
            Finding(title="Critical thing", severity=Severity.CRITICAL, category=FindingCategory.SECURITY),
        ],
    )
    report.summary = report.build_summary()
    return report


def _testio_report() -> Report:
    now = datetime.now(timezone.utc)
    finding = Finding(
        title="Reflected XSS in /search",
        severity=Severity.HIGH,
        category=FindingCategory.SECURITY,
        description="Payload '<script>alert(1)</script>' is echoed back unescaped.",
        url="http://x.test/search?q=<script>",
        remediation="Escape all user input when rendering.",
        evidence=[
            Evidence(kind="http_response", detail="payload reflected in 200 response"),
            Evidence(kind="screenshot", file="shot.png"),
        ],
        detected_at=now,
    )
    report = Report(target="http://x.test", started_at=now, finished_at=now, findings=[finding])
    report.summary = report.build_summary()
    return report


def test_testio_bug_has_all_required_fields():
    text = render_testio_bug(_testio_report(), _testio_report().findings[0])
    for field in (
        "**Feature:**",
        "**Severity:** High",
        "**Title:**",
        "**URL:**",
        "## Steps to reproduce",
        "## Actual result",
        "## Expected result",
        "## Attachment",
        "## Used environment",
    ):
        assert field in text, f"missing {field!r}"


def test_testio_bug_step1_opens_target():
    """Test IO requires step 1 to be opening the site root."""
    report = _testio_report()
    text = render_testio_bug(report, report.findings[0])
    assert "1. Open http://x.test" in text


def test_testio_severity_mapping():
    """Only Low/High/Critical exist in Test IO; info/medium/low map to Low."""
    from qaagent.report.generator import _TESTIO_SEVERITY

    assert _TESTIO_SEVERITY["critical"] == "Critical"
    assert _TESTIO_SEVERITY["high"] == "High"
    assert _TESTIO_SEVERITY["medium"] == "Low"
    assert _TESTIO_SEVERITY["info"] == "Low"


def test_save_report_testio_writes_per_finding_files():
    import tempfile
    from pathlib import Path

    report = _testio_report()
    with tempfile.TemporaryDirectory() as tmp:
        bug_dir = save_report_testio(report, tmp)
        files = sorted(Path(bug_dir).glob("*.md"))
        # one per finding + the index
        assert len(files) == 2
        assert (Path(bug_dir) / "00-INDEX.md").exists()
        per_finding = [f for f in files if f.name != "00-INDEX.md"][0]
        content = per_finding.read_text(encoding="utf-8")
        assert "Test IO format" in content
        assert "high" in per_finding.name  # severity in the filename


def test_redaction_masks_session_cookie_in_saved_reports():
    """Evidence with a real session cookie must never reach a saved report."""
    import tempfile
    from pathlib import Path

    from qaagent.models import Evidence, Finding, FindingCategory, Report, Severity
    from qaagent.report.generator import (
        save_report,
        save_report_csv,
        save_report_html,
        save_report_json,
        save_report_testio,
    )

    cookie = "session=.eJyrVirKz0lVslIqLU4tUtIBU_GZKUpWhhB2XmIuSDYxJzM5VakW.aoO9_Q.Ckjrr6Nk46A1jUjmgwWfPIP0g1E; Path=/"
    finding = Finding(
        title="Cookie flags",
        severity=Severity.MEDIUM,
        category=FindingCategory.SECURITY,
        description="Cookie set without HttpOnly.",
        evidence=[Evidence(kind="http_response", detail=cookie)],
    )
    report = Report(target="http://x.test", findings=[finding])
    report.summary = report.build_summary()
    with tempfile.TemporaryDirectory() as tmp:
        save_report(report, tmp)
        save_report_json(report, tmp)
        save_report_html(report, tmp)
        save_report_csv(report, tmp)
        save_report_testio(report, tmp)
        for artifact in sorted(Path(tmp).rglob("*")):
            if artifact.is_file():
                content = artifact.read_text(encoding="utf-8")
                assert "eJyrVirKz0lVslIqLU4tUtIBU" not in content, f"leak in {artifact.name}"
                # CSV rows and the Test IO index carry no evidence, so only
                # the leak-check applies; other artifacts must show the marker.
                if artifact.suffix != ".csv" and artifact.name != "00-INDEX.md":
                    # HTML escapes the marker, so accept either form.
                    assert (
                        "<redacted>" in content
                        or "&lt;redacted&gt;" in content
                        or "<jwt-redacted>" in content
                        or "&lt;jwt-redacted&gt;" in content
                    ), f"no redaction marker in {artifact.name}"


def test_redaction_masks_jwt_and_bearer():
    from qaagent.report.generator import redact

    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9Pj-_sq5FgWMw"
    out = redact(f"Authorization: Bearer abc123def456789 {jwt}")
    assert "abc123def456789" not in out
    assert "eyJhbGciOiJIUzI1NiIs" not in out
    assert "Bearer<redacted>" in out or "Bearer <redacted>" in out or "<jwt-redacted>" in out


def test_dashboard_api_requires_token(tmp_path):
    """The dashboard gates everything: token for APIs, login page for humans."""
    from qaagent.dashboard import create_app

    app = create_app(
        tmp_path / "live.json", tmp_path, auth_token="test-token-123"
    )
    client = app.test_client()

    # No token anywhere -> 401 on API, console landing on the page.
    assert client.get("/api/state").status_code == 401
    assert client.get("/").status_code == 302
    assert client.get("/").headers.get("Location", "") == "/console/"
    # Wrong token -> 401.
    assert client.get("/api/state?token=wrong").status_code == 401
    # Header token -> 200.
    assert (
        client.get("/api/state", headers={"X-Sentinel-Token": "test-token-123"}).status_code
        == 200
    )
    # Query token -> 302 into the console, and sets the cookie for later plain requests.
    resp = client.get("/?token=test-token-123")
    assert resp.status_code == 302
    assert resp.headers.get("Location", "") == "/console/"
    assert "sentinel_token" in resp.headers.get("Set-Cookie", "")
    assert client.get("/api/state").status_code == 200  # cookie carried it


def test_dashboard_account_flow(tmp_path):
    """Signup (first user = admin), login, logout, and CSRF enforcement."""
    from qaagent.dashboard import create_app

    app = create_app(tmp_path / "live.json", tmp_path, auth_token="tok")
    app.config["WTF_CSRF_ENABLED"] = False  # not flask-wtf; placeholder no-op
    client = app.test_client()

    # First-time visitor: redirected to login; login page links to signup.
    page = client.get("/login")
    assert page.status_code == 200 and "Sign in" in page.get_data(as_text=True)

    # Fetch the signup form to get a CSRF token.
    import re

    signup_page = client.get("/signup").get_data(as_text=True)
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', signup_page).group(1)

    # Signup the first user (becomes admin), then land on the dashboard.
    # Closed signup: the first account must present the bootstrap token.
    resp = client.post(
        "/signup",
        data={
            "email": "owner@example.com",
            "password": "supersecret9",
            "csrf_token": csrf,
            "bootstrap_token": "tok",
            "accept_terms": "1",
        },
        follow_redirects=True,
    )
    body = resp.get_data(as_text=True)
    assert "Sentinel Console" in body
    assert client.get("/api/me").get_json()["email"] == "owner@example.com"

    # Logout (CSRF-protected POST), then the dashboard redirects to login again.
    csrf2 = client.get("/api/csrf").get_json()["csrf_token"]
    client.post("/logout", data={"csrf_token": csrf2})
    assert client.get("/api/state").status_code == 401

    # Login again with the same credentials.
    login_html = client.get("/login").get_data(as_text=True)
    csrf3 = re.search(r'name="csrf_token" value="([^"]+)"', login_html).group(1)
    resp = client.post(
        "/login",
        data={"email": "owner@example.com", "password": "supersecret9", "csrf_token": csrf3},
        follow_redirects=True,
    )
    assert "Sentinel Console" in resp.get_data(as_text=True)

    # Wrong password is rejected (and counts toward rate limiting).
    client2 = app.test_client()
    html = client2.get("/login").get_data(as_text=True)
    csrf4 = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    bad = client2.post(
        "/login",
        data={"email": "owner@example.com", "password": "wrong-pass-1", "csrf_token": csrf4},
    )
    assert "Wrong email or password" in bad.get_data(as_text=True)


def test_dashboard_signup_requires_csrf(tmp_path):
    """Posting the signup form without a CSRF token must fail."""
    from qaagent.dashboard import create_app

    app = create_app(tmp_path / "live.json", tmp_path, auth_token="tok")
    client = app.test_client()
    resp = client.post(
        "/signup",
        data={"email": "x@example.com", "password": "supersecret9"},
    )
    assert resp.status_code == 400


def test_dashboard_login_rate_limited(tmp_path):
    """Six bad logins from one IP -> the 6th is throttled."""
    import re

    from qaagent.dashboard import create_app

    app = create_app(tmp_path / "live.json", tmp_path, auth_token="tok")
    client = app.test_client()

    def attempt(pwd: str):
        html = client.get("/login").get_data(as_text=True)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        return client.post(
            "/login",
            data={"email": "nobody@example.com", "password": pwd, "csrf_token": csrf},
        ).get_data(as_text=True)

    for _ in range(5):
        assert "Too many attempts" not in attempt("bad-pass-99")
    assert "Too many attempts" in attempt("bad-pass-99")  # 6th blocked


def test_dashboard_token_persists(tmp_path):
    """Restarting the dashboard must reuse the same token."""
    from qaagent.dashboard import create_app, load_or_create_token

    t1 = load_or_create_token(tmp_path)
    t2 = load_or_create_token(tmp_path)
    assert t1 == t2 and len(t1) >= 24
    app = create_app(tmp_path / "live.json", tmp_path)  # no explicit token
    client = app.test_client()
    assert client.get("/api/state?token=" + t1).status_code == 200


def test_render_html_ranks_by_severity():
    html = render_html(_report())
    assert html.index("CRITICAL") < html.index("LOW")
    assert "<html" in html
    assert "No findings" not in html


def test_render_html_empty():
    report = Report(target="http://x.test")
    assert "No findings" in render_html(report)


def test_render_html_shows_content_type():
    report = Report(
        target="http://x.test",
        findings=[
            Finding(
                title="Sensitive file",
                severity=Severity.MEDIUM,
                category=FindingCategory.SECURITY,
                content_type="application/sql",
            )
        ],
    )
    html = render_html(report)
    assert "application/sql" in html


def test_render_html_escapes_special_chars():
    report = Report(
        target="http://x.test",
        findings=[
            Finding(
                title="XSS <script>alert(1)</script>",
                severity=Severity.HIGH,
                category=FindingCategory.SECURITY,
                description="Uses \"quotes\" and <tags>",
            )
        ],
    )
    html = render_html(report)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_save_html_and_csv(tmp_path):
    report = _report()
    html_path = save_report_html(report, tmp_path)
    csv_path = save_report_csv(report, tmp_path)
    assert html_path.exists()
    assert csv_path.exists()
    assert html_path.suffix == ".html"
    assert csv_path.suffix == ".csv"
    assert html_path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    non_empty = [l for l in lines if l.strip()]
    assert len(non_empty) == 3  # header + 2 findings
    assert non_empty[0].startswith("id,severity")


def test_csv_content_type_present(tmp_path):
    report = Report(
        target="http://x.test",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        findings=[
            Finding(
                title="Sensitive file",
                severity=Severity.MEDIUM,
                category=FindingCategory.SECURITY,
                content_type="application/json",
            )
        ],
    )
    report.summary = report.build_summary()
    csv_path = save_report_csv(report, tmp_path)
    text = csv_path.read_text(encoding="utf-8")
    assert "application/json" in text


def test_render_markdown_ranks_by_severity():
    md = render_markdown(_report())
    assert md.index("### critical") < md.index("### low")
    assert "No findings" not in md


def test_render_markdown_empty():
    report = Report(target="http://x.test")
    assert "No findings" in render_markdown(report)


def test_save_artifacts(tmp_path):
    report = _report()
    md = save_report(report, tmp_path)
    js = save_report_json(report, tmp_path)
    summary = save_summary(report, tmp_path, md, js)
    assert md.exists() and js.exists() and summary.exists()

    data = json.loads(summary.read_text(encoding="utf-8"))
    assert data["findings_total"] == 2
    assert data["by_severity"]["critical"] == 1
    assert data["report_json"] == str(js)
    assert data["report_markdown"] == str(md)
    assert len(data["findings"]) == 2

    full = json.loads(js.read_text(encoding="utf-8"))
    assert len(full["findings"]) == 2


def test_content_type_roundtrips_through_artifacts(tmp_path):
    now = datetime.now(timezone.utc)
    report = Report(
        target="http://x.test",
        started_at=now,
        finished_at=now,
        findings=[
            Finding(
                title="Sensitive file exposed: /backup.sql",
                severity=Severity.MEDIUM,
                category=FindingCategory.SECURITY,
                content_type="application/sql",
            )
        ],
    )
    report.summary = report.build_summary()

    js = save_report_json(report, tmp_path)
    full = json.loads(js.read_text(encoding="utf-8"))
    assert full["findings"][0]["content_type"] == "application/sql"

    # Old reports without the field still parse (backward compatible).
    js.write_text(
        json.dumps({"target": "http://x.test", "findings": [{"title": "t", "severity": "low", "category": "security"}]}),
        encoding="utf-8",
    )
    from qaagent.report.diff import load_report_files

    loaded = load_report_files(tmp_path)
    assert loaded and loaded[-1]["findings"][0].get("content_type") is None


def test_live_state_roundtrip(tmp_path):
    live = LiveState(tmp_path / "live.json")
    live.update(status="running", stage="Probes", target="http://x.test")
    live.push_action("click Login")
    live.finish("completed", report_path="reports/x.md")
    data = json.loads((tmp_path / "live.json").read_text(encoding="utf-8"))
    assert data["status"] == "completed"
    assert data["stage"] == "Finished"
    assert data["recent_actions"] == ["click Login"]
    assert data["target"] == "http://x.test"
    assert data["report_path"] == "reports/x.md"


def _signup(client, email: str, *, bootstrap_token: str | None = None, invite_code: str | None = None) -> None:
    """Create an account through the real signup form (CSRF + policy included)."""
    import re

    html = client.get("/signup").get_data(as_text=True)
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    data = {
        "email": email,
        "password": "supersecret9",
        "csrf_token": csrf,
        "accept_terms": "1",  # legal consent is part of every real signup
    }
    if bootstrap_token is not None:
        data["bootstrap_token"] = bootstrap_token
    if invite_code is not None:
        data["invite_code"] = invite_code
    resp = client.post(
        "/signup",
        data=data,
        follow_redirects=True,
    )
    assert resp.status_code == 200


def test_phase1_healthz_cookies_proxyfix(tmp_path):
    """Production posture: public healthz, secure-aware cookies, ProxyFix on."""
    from qaagent.dashboard import create_app

    (tmp_path / "live.json").write_text(json.dumps({"status": "idle"}), encoding="utf-8")
    app = create_app(tmp_path / "live.json", tmp_path, auth_token="tok")
    client = app.test_client()

    # /healthz is public and JSON-ok.
    r = client.get("/healthz")
    assert r.status_code == 200 and r.get_json() == {"ok": True}

    # Everything else stays gated.
    assert client.get("/").status_code == 302
    assert client.get("/api/state").status_code == 401

    # Session cookies carry the production posture.
    cfg = app.config
    assert cfg["SESSION_COOKIE_SECURE"] is True
    assert cfg["SESSION_COOKIE_HTTPONLY"] is True
    assert cfg["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert cfg["SESSION_COOKIE_NAME"] == "sentinel_session"

    # Token cookie honors the scheme: Secure on https, not on http.
    cookie_name = "sentinel_token"
    https = app.test_client()
    https.get("/healthz", base_url="https://localhost")
    https.get("/?token=tok", base_url="https://localhost")
    cookie = https.get_cookie(cookie_name)
    assert cookie is not None and cookie.secure is True
    http = app.test_client()
    http.get("/?token=tok")  # default http base
    cookie2 = http.get_cookie(cookie_name)
    assert cookie2 is not None and cookie2.secure is False

    # ProxyFix is installed (X-Forwarded-Proto drives request.scheme).
    from werkzeug.middleware.proxy_fix import ProxyFix

    assert isinstance(app.wsgi_app, ProxyFix)
    behind = app.test_client()
    behind.get("/?token=tok", headers={"X-Forwarded-Proto": "https"})
    cookie3 = behind.get_cookie(cookie_name)
    assert cookie3 is not None and cookie3.secure is True


def test_reports_isolated_between_accounts(tmp_path):
    """Each account sees only its own scans; admins and tokens see everything."""
    from qaagent.dashboard import _scan, create_app

    # Seed: a member-owned report and an ownerless one (CLI/pre-accounts runs).
    # Pairs of .md + .json, matching what a real run writes to disk.
    for name, owner in (
        ("20260101-000001", {"owner_id": 2, "owner_email": "member@example.com"}),
        ("20260101-000002", {}),
    ):
        (tmp_path / f"report-{name}.md").write_text("# report", encoding="utf-8")
        (tmp_path / f"report-{name}.json").write_text(
            json.dumps(
                {
                    "target": "http://x.test",
                    "started_at": f"{name[:4]}-{name[4:6]}-{name[6:8]}T00:00:00+00:00",
                    "findings": [],
                    **owner,
                }
            ),
            encoding="utf-8",
        )
    (tmp_path / "live.json").write_text(
        json.dumps({"status": "running", "stage": "Exploring", "findings": []}),
        encoding="utf-8",
    )

    app = create_app(tmp_path / "live.json", tmp_path, auth_token="tok")
    saved_owner = (_scan.get("owner_id"), _scan.get("owner_email"))
    _scan.update(owner_id=1, owner_email="admin@example.com")
    try:
        admin = app.test_client()
        _signup(admin, "admin@example.com", bootstrap_token="tok")  # first user becomes admin

        # Admin sees everything: the newest report (ownerless) is visible.
        rep = json.loads(admin.get("/api/report").get_data(as_text=True))
        assert rep["path"] is not None and "000002" in rep["path"]
        # Admin sees the real live state.
        st = json.loads(admin.get("/api/state").get_data(as_text=True))
        assert st["status"] == "running"

        # Second user -> regular; closed signup requires an invite code.
        from qaagent.auth import UserStore

        users = UserStore(tmp_path / "users.db")
        member = app.test_client()
        _signup(member, "member@example.com", invite_code=users.create_invite(created_by=1))

        # Member sees only their own report (the ownerless one is hidden).
        rep2 = json.loads(member.get("/api/report").get_data(as_text=True))
        assert rep2["path"] is not None and "000001" in rep2["path"]
        # Live state: admin's running scan is invisible to the member...
        st2 = json.loads(member.get("/api/state").get_data(as_text=True))
        assert st2["status"] == "idle"
        # ...but visible once the member owns the running scan.
        _scan.update(owner_id=2, owner_email="member@example.com")
        st3 = json.loads(member.get("/api/state").get_data(as_text=True))
        assert st3["status"] == "running"
        _scan.update(owner_id=1, owner_email="admin@example.com")

        # A third account starts completely clean.
        third = app.test_client()
        _signup(third, "third@example.com", invite_code=users.create_invite(created_by=1))
        rep3 = json.loads(third.get("/api/report").get_data(as_text=True))
        assert rep3["path"] is None
        st4 = json.loads(third.get("/api/state").get_data(as_text=True))
        assert st4["status"] == "idle"

        # The bootstrap token still sees everything (admin/API mechanism).
        tok = app.test_client()
        rep4 = json.loads(tok.get("/api/report?token=tok").get_data(as_text=True))
        assert rep4["path"] is not None and "000002" in rep4["path"]
    finally:
        _scan.update(owner_id=saved_owner[0], owner_email=saved_owner[1])


def test_report_downloads_and_history(tmp_path):
    """Downloads and history are served per-run, ownership-checked, traversal-safe."""
    import io
    import zipfile

    from qaagent.dashboard import _scan, create_app

    stamp = "20260101-000000"  # matches started_at 2026-01-01T00:00:00
    (tmp_path / f"report-{stamp}.json").write_text(
        json.dumps(
            {
                "target": "http://x.test",
                "started_at": "2026-01-01T00:00:00+00:00",
                "owner_id": 2,
                "owner_email": "member@example.com",
                "findings": [{"title": "T", "severity": "low", "url": "http://x.test"}],
                "summary": {
                    "total": 1,
                    "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 1, "info": 0},
                    "by_category": {},
                },
            }
        ),
        encoding="utf-8",
    )
    for ext, body in (("md", "# report"), ("csv", "a,b\n1,2"), ("html", "<h1>r</h1>")):
        (tmp_path / f"report-{stamp}.{ext}").write_text(body, encoding="utf-8")
    bug_dir = tmp_path / f"testio-{stamp}"
    bug_dir.mkdir()
    (bug_dir / "00-INDEX.md").write_text("# index", encoding="utf-8")
    (tmp_path / "live.json").write_text(json.dumps({"status": "idle"}), encoding="utf-8")

    app = create_app(tmp_path / "live.json", tmp_path, auth_token="tok")
    saved_owner = (_scan.get("owner_id"), _scan.get("owner_email"))
    _scan.update(owner_id=1, owner_email="admin@example.com")
    try:
        admin = app.test_client()
        _signup(admin, "admin@example.com", bootstrap_token="tok")  # first user becomes admin

        # History lists the run with a Test IO flag + severity summary.
        hist = json.loads(admin.get("/api/history").get_data(as_text=True))
        assert len(hist["runs"]) == 1
        run = hist["runs"][0]
        assert run["stamp"] == stamp and run["has_testio"] is True
        assert run["summary"]["by_severity"]["low"] == 1

        # All four file downloads work for the owner (admin sees all).
        for fmt, marker in (("md", b"# report"), ("csv", b"a,b"), ("html", b"<h1>"), ("json", b"x.test")):
            r = admin.get(f"/api/report/{stamp}/{fmt}")
            assert r.status_code == 200, fmt
            assert marker in r.data
        # Zip contains the Test IO bundle.
        z = admin.get(f"/api/report/{stamp}/testio")
        assert z.status_code == 200 and z.data[:2] == b"PK"
        names = zipfile.ZipFile(io.BytesIO(z.data)).namelist()
        assert "00-INDEX.md" in names

        # The owning member can download their own run's artifacts.
        from qaagent.auth import UserStore

        users = UserStore(tmp_path / "users.db")
        member = app.test_client()
        _signup(member, "member@example.com", invite_code=users.create_invite(created_by=1))
        r = member.get(f"/api/report/{stamp}/md")
        assert r.status_code == 200 and b"# report" in r.data
        hist2 = json.loads(member.get("/api/history").get_data(as_text=True))
        assert len(hist2["runs"]) == 1

        # A non-owner is blocked on every artifact.
        third = app.test_client()
        _signup(third, "third@example.com", invite_code=users.create_invite(created_by=1))
        for fmt in ("md", "csv", "html", "json", "testio"):
            r = third.get(f"/api/report/{stamp}/{fmt}")
            assert r.status_code == 403, fmt
        # ...and history shows them nothing.
        hist3 = json.loads(third.get("/api/history").get_data(as_text=True))
        assert hist3["runs"] == []

        # Path traversal and malformed ids are rejected before touching disk.
        for bad in ("..%2F..%2Fetc", "../../etc", "x/y", "", "zzzz"):
            r = admin.get(f"/api/report/{bad}/md")
            assert r.status_code in (400, 404), bad

        # Unknown format -> 404.
        assert admin.get(f"/api/report/{stamp}/exe").status_code == 404
        # Missing artifact -> 404 (owner would pass the ownership check).
        missing = admin.get("/api/report/19990101-000000/md")
        assert missing.status_code == 404
    finally:
        _scan.update(owner_id=saved_owner[0], owner_email=saved_owner[1])
