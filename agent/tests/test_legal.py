"""Phase 3 legal layer: public /terms and /abuse pages, consent-gated signup,
and the terms gate on scan start (including re-acceptance after a bump)."""

from __future__ import annotations

import json
import re

import pytest

from tests.test_report import _signup


def _csrf(client, path: str) -> str:
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


@pytest.fixture()
def legal_app(tmp_path, monkeypatch):
    """App with an abuse email set and a scan-friendly env."""
    monkeypatch.setenv("SENTINEL_ABUSE_EMAIL", "abuse@sentinel.test")
    monkeypatch.delenv("SENTINEL_PUBLIC_MODE", raising=False)
    monkeypatch.setenv("SENTINEL_DAILY_SCAN_LIMIT", "0")
    monkeypatch.setenv("SENTINEL_CONFIG_DIR", str(tmp_path / "configs"))
    from qaagent.dashboard import create_app

    (tmp_path / "live.json").write_text(json.dumps({"status": "idle"}), encoding="utf-8")
    app = create_app(tmp_path / "live.json", tmp_path, auth_token="tok")
    return app, tmp_path


# --- public legal pages --------------------------------------------------------


def test_terms_page_is_public_and_versioned(legal_app):
    app, _ = legal_app
    anon = app.test_client()
    r = anon.get("/terms")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Terms of Service" in body
    from qaagent.terms import TERMS_VERSION

    assert TERMS_VERSION in body
    assert "Authorized testing only" in body


def test_abuse_page_shows_env_contact(legal_app):
    app, _ = legal_app
    anon = app.test_client()
    body = anon.get("/abuse").get_data(as_text=True)
    assert "abuse@sentinel.test" in body
    assert "mailto:abuse@sentinel.test" in body


def test_abuse_page_without_contact_configured(tmp_path, monkeypatch):
    monkeypatch.delenv("SENTINEL_ABUSE_EMAIL", raising=False)
    monkeypatch.delenv("SENTINEL_ABUSE_URL", raising=False)
    from qaagent.dashboard import create_app

    (tmp_path / "live.json").write_text(json.dumps({"status": "idle"}), encoding="utf-8")
    app = create_app(tmp_path / "live.json", tmp_path, auth_token="tok")
    body = app.test_client().get("/abuse").get_data(as_text=True)
    assert "SENTINEL_ABUSE_EMAIL" in body  # operator hint instead of a dead page


def test_legal_pages_linked_from_dashboard_and_signup(legal_app):
    app, _ = legal_app
    client = app.test_client()
    _signup(client, "owner@example.com", bootstrap_token="tok")
    # Site root routes into the console; legal pages stay directly reachable.
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302 and r.headers["Location"] == "/console/app"
    assert client.get("/terms").status_code == 200
    assert client.get("/abuse").status_code == 200
    signup_html = app.test_client().get("/signup").get_data(as_text=True)
    assert 'href="/terms"' in signup_html and 'name="accept_terms"' in signup_html


# --- signup consent ------------------------------------------------------------


def test_signup_without_consent_refused(legal_app):
    app, _ = legal_app
    client = app.test_client()
    csrf = _csrf(client, "/signup")
    # First user: bootstrap token provided, but no accept_terms checkbox.
    r = client.post("/signup", data={
        "email": "owner@example.com", "password": "supersecret9",
        "csrf_token": csrf, "bootstrap_token": "tok",
        # accept_terms deliberately missing (server must not trust the client)
    })
    assert "must accept the Terms of Service" in r.get_data(as_text=True)


def test_signup_records_acceptance(legal_app):
    from qaagent.terms import TERMS_VERSION

    app, tmp_path = legal_app
    client = app.test_client()
    _signup(client, "owner@example.com", bootstrap_token="tok")  # consent flows through

    from qaagent.auth import UserStore

    users = UserStore(tmp_path / "users.db")
    assert users.terms_accepted_version(1) == TERMS_VERSION


# --- scan gate ------------------------------------------------------------------


def test_token_starter_bypasses_terms_gate(legal_app):
    """Token callers are the operator/CI, not a terms party."""
    app, _ = legal_app
    client = app.test_client()
    r = client.post("/api/scan", data=json.dumps({"config": "example.com", "authorized": True}),
                    content_type="application/json", headers={"X-Sentinel-Token": "tok"})
    assert r.status_code == 200
    from qaagent.dashboard import _scan

    proc = _scan.get("proc")
    if proc is not None and proc.poll() is None:
        proc.kill()
        proc.wait(timeout=10)


def test_scan_gate_blocks_stale_acceptance(legal_app):
    """A logged-in user who accepted an older version gets 403 until re-accept."""
    app, tmp_path = legal_app
    from qaagent.auth import UserStore

    client = app.test_client()
    _signup(client, "owner@example.com", bootstrap_token="tok")

    # Simulate stale acceptance: rewrite the recorded version.
    users = UserStore(tmp_path / "users.db")
    users.accept_terms(1, "0.0.1-old")
    from qaagent.terms import TERMS_VERSION

    assert users.terms_accepted_version(1) != TERMS_VERSION

    r = client.post("/api/scan", data=json.dumps({"config": "example.com", "authorized": True}),
                    content_type="application/json")
    assert r.status_code == 403
    data = r.get_json()
    assert data["code"] == "terms_required" and "terms" in data["error"].lower()

    # Re-accept through the real endpoint (CSRF + next guard).
    csrf = client.get("/api/csrf").get_json()["csrf_token"]
    r2 = client.post("/terms/accept?next=/", data={"csrf_token": csrf})
    assert r2.status_code == 302
    assert users.terms_accepted_version(1) == TERMS_VERSION

    # Now the scan passes the terms gate (target policy still applies; a
    # public example.com target passes in local mode).
    r3 = client.post("/api/scan", data=json.dumps({"config": "example.com", "authorized": True}),
                     content_type="application/json")
    assert r3.status_code == 200
    from qaagent.dashboard import _scan

    proc = _scan.get("proc")
    if proc is not None and proc.poll() is None:
        proc.kill()
        proc.wait(timeout=10)


def test_accept_endpoint_requires_login_and_csrf(legal_app):
    """Anonymous visitors are bounced to login by the auth gate; a CSRF-failed
    accept records nothing."""
    app, tmp_path = legal_app
    anon = app.test_client()
    r = anon.post("/terms/accept", data={"csrf_token": "whatever"})
    # Auth gate: anonymous -> login redirect (never silently "accepts").
    assert r.status_code == 302 and "/login" in r.headers["Location"]

    client = app.test_client()
    _signup(client, "owner@example.com", bootstrap_token="tok")
    bad = client.post("/terms/accept", data={"csrf_token": "nope"})
    assert bad.status_code == 302  # CSRF-failed accept just redirects, records nothing

    from qaagent.terms import TERMS_VERSION
    from qaagent.auth import UserStore

    users = UserStore(tmp_path / "users.db")
    assert users.terms_accepted_version(1) == TERMS_VERSION  # from signup only
