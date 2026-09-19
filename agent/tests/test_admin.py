"""Phase 3 admin console: user list, suspend/unsuspend, running-scan card,
and invite management in one admin-only view."""

from __future__ import annotations

import json
import re

import pytest

from tests.test_report import _signup


def _csrf(client, path: str) -> str:
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


@pytest.fixture()
def admin_app(tmp_path, monkeypatch):
    monkeypatch.delenv("SENTINEL_PUBLIC_MODE", raising=False)
    monkeypatch.setenv("SENTINEL_DAILY_SCAN_LIMIT", "0")
    monkeypatch.setenv("SENTINEL_CONFIG_DIR", str(tmp_path / "configs"))
    from qaagent.dashboard import create_app

    (tmp_path / "live.json").write_text(json.dumps({"status": "idle"}), encoding="utf-8")
    app = create_app(tmp_path / "live.json", tmp_path, auth_token="tok")
    return app, tmp_path


def _seed_accounts(app, tmp_path):
    """Admin + two members through the real signup flow."""
    admin = app.test_client()
    _signup(admin, "admin@example.com", bootstrap_token="tok")
    from qaagent.auth import UserStore

    users = UserStore(tmp_path / "users.db")
    m1 = app.test_client()
    _signup(m1, "one@example.com", invite_code=users.create_invite())
    m2 = app.test_client()
    _signup(m2, "two@example.com", invite_code=users.create_invite())
    return admin, users


def _store(app, tmp_path):
    from qaagent.auth import UserStore

    return UserStore(tmp_path / "users.db")


def test_admin_page_is_admin_only(admin_app):
    app, tmp_path = admin_app
    admin, users = _seed_accounts(app, tmp_path)

    page = admin.get("/admin")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "Admin console" in body
    for email in ("admin@example.com", "one@example.com", "two@example.com"):
        assert email in body

    # Members and anonymous users never see it.
    code = users.create_invite()
    member = app.test_client()
    _signup(member, "member@example.com", invite_code=code)
    assert member.get("/admin").status_code == 302
    assert app.test_client().get("/admin").status_code == 302


def test_suspend_and_reinstate_lifecycle(admin_app):
    app, tmp_path = admin_app
    admin, users = _seed_accounts(app, tmp_path)

    csrf = _csrf(admin, "/admin")
    r = admin.post("/admin/suspend", data={
        "csrf_token": csrf, "user_id": "2", "suspended": "1",
        "reason": "scanned a site they do not own",
    })
    assert r.status_code == 302

    row = users.get(2)
    assert row["suspended"] == 1 and "not own" in row["suspend_reason"]

    # A suspended session dies on the very next request...
    member = app.test_client()
    _signup(member, "fresh@example.com", invite_code=users.create_invite())
    member.get("/")  # establish session works pre-suspension
    fresh_id = users.list_users()[-1]["id"]
    users.set_suspended(fresh_id, True, "x")
    assert member.get("/").status_code == 302  # bounced to login

    # ...and login is refused at the store level.
    assert users.verify("one@example.com", "supersecret9") is None

    # Reinstate restores access.
    users.set_suspended(2, False)
    assert users.verify("one@example.com", "supersecret9") is not None


def test_admin_cannot_suspend_themselves(admin_app):
    app, tmp_path = admin_app
    admin, users = _seed_accounts(app, tmp_path)

    csrf = _csrf(admin, "/admin")
    admin.post("/admin/suspend", data={
        "csrf_token": csrf, "user_id": "1", "suspended": "1", "reason": "oops",
    })
    assert users.get(1)["suspended"] == 0  # self-suspend refused
    # And the admin's session still works.
    assert admin.get("/admin").status_code == 200


def test_suspend_requires_csrf_and_admin(admin_app):
    app, tmp_path = admin_app
    admin, users = _seed_accounts(app, tmp_path)

    # Missing CSRF: redirect, no change.
    r = admin.post("/admin/suspend", data={"user_id": "2", "suspended": "1"})
    assert r.status_code == 302
    assert users.get(2)["suspended"] == 0

    # Malformed user_id: redirect, no change.
    csrf = _csrf(admin, "/admin")
    r = admin.post("/admin/suspend", data={
        "csrf_token": csrf, "user_id": "two", "suspended": "1",
    })
    assert r.status_code == 302
    assert users.get(2)["suspended"] == 0


def test_admin_page_shows_running_scan(admin_app):
    app, tmp_path = admin_app
    admin, users = _seed_accounts(app, tmp_path)

    from qaagent.dashboard import _scan

    saved = dict(_scan)
    try:
        _scan.update(
            proc=None, config="stylesbytiwa.netlify.app",
            started="2026-09-19T00:00:00+00:00", owner_email="one@example.com",
            returncode=0,
        )
        body = admin.get("/admin").get_data(as_text=True)
        assert "stylesbytiwa.netlify.app" in body
        assert "one@example.com" in body
        assert "idle" in body  # proc None -> shown as idle + last exit
    finally:
        _scan.clear()
        _scan.update(saved)


def test_admin_page_includes_invite_management(admin_app):
    app, tmp_path = admin_app
    admin, users = _seed_accounts(app, tmp_path)

    body = admin.get("/admin").get_data(as_text=True)
    assert "Invite codes" in body and "Generate invite code" in body

    # Generate from the console itself; the new code appears.
    csrf = _csrf(admin, "/admin")
    admin.post("/invites", data={"csrf_token": csrf})
    body2 = admin.get("/admin").get_data(as_text=True)
    assert "open" in body2
