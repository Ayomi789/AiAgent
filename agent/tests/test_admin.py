"""Phase 3 admin console (JSON API): user list, suspend/unsuspend, running-scan
state, and invite management in one admin-only surface."""

from __future__ import annotations

import json

import pytest

from tests.test_report import _signup


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


def _csrf(client) -> str:
    return client.get("/api/csrf").get_json()["csrf_token"]


def test_admin_overview_is_admin_only(admin_app):
    app, tmp_path = admin_app
    admin, users = _seed_accounts(app, tmp_path)

    r = admin.get("/api/admin/overview")
    assert r.status_code == 200
    emails = [u["email"] for u in r.get_json()["users"]]
    for email in ("admin@example.com", "one@example.com", "two@example.com"):
        assert email in emails

    # Members get 403; anonymous gets 401 from the gate.
    code = users.create_invite()
    member = app.test_client()
    _signup(member, "member@example.com", invite_code=code)
    assert member.get("/api/admin/overview").status_code == 403
    assert app.test_client().get("/api/admin/overview").status_code == 401


def test_suspend_and_reinstate_lifecycle(admin_app):
    app, tmp_path = admin_app
    admin, users = _seed_accounts(app, tmp_path)

    r = admin.post("/api/admin/suspend", json={
        "csrf_token": _csrf(admin), "user_id": 2, "suspended": True,
        "reason": "scanned a site they do not own",
    })
    assert r.status_code == 200 and r.get_json() == {"ok": True}

    row = users.get(2)
    assert row["suspended"] == 1 and "not own" in row["suspend_reason"]

    # A suspended session dies on the very next request...
    member = app.test_client()
    _signup(member, "fresh@example.com", invite_code=users.create_invite())
    member.get("/")  # establish session works pre-suspension
    fresh_id = users.list_users()[-1]["id"]
    users.set_suspended(fresh_id, True, "x")
    assert member.get("/").status_code == 302  # bounced away

    # ...and login is refused at the store level.
    assert users.verify("one@example.com", "supersecret9") is None

    # Reinstate through the API restores access.
    r = admin.post("/api/admin/suspend", json={
        "csrf_token": _csrf(admin), "user_id": 2, "suspended": False,
    })
    assert r.status_code == 200
    assert users.verify("one@example.com", "supersecret9") is not None


def test_admin_cannot_suspend_themselves(admin_app):
    app, tmp_path = admin_app
    admin, users = _seed_accounts(app, tmp_path)

    r = admin.post("/api/admin/suspend", json={
        "csrf_token": _csrf(admin), "user_id": 1, "suspended": True, "reason": "oops",
    })
    assert r.status_code == 400
    assert users.get(1)["suspended"] == 0  # self-suspend refused
    # And the admin's session still works.
    assert admin.get("/api/admin/overview").status_code == 200


def test_suspend_requires_csrf_and_admin(admin_app):
    app, tmp_path = admin_app
    admin, users = _seed_accounts(app, tmp_path)

    # Missing CSRF: 400, no change.
    r = admin.post("/api/admin/suspend", json={"user_id": 2, "suspended": True})
    assert r.status_code == 400
    assert users.get(2)["suspended"] == 0

    # Malformed user_id: 400, no change.
    r = admin.post("/api/admin/suspend", json={
        "csrf_token": _csrf(admin), "user_id": "two", "suspended": True,
    })
    assert r.status_code == 400
    assert users.get(2)["suspended"] == 0

    # Non-admins are refused even with a valid token.
    member = app.test_client()
    _signup(member, "member@example.com", invite_code=users.create_invite())
    r = member.post("/api/admin/suspend", json={
        "csrf_token": _csrf(member), "user_id": 2, "suspended": True,
    })
    assert r.status_code == 403
    assert users.get(2)["suspended"] == 0


def test_admin_overview_shows_running_scan(admin_app):
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
        scan = admin.get("/api/admin/overview").get_json()["scan"]
        assert scan["config"] == "stylesbytiwa.netlify.app"
        assert scan["owner_email"] == "one@example.com"
        assert scan["running"] is False
        assert scan["returncode"] == 0
    finally:
        _scan.clear()
        _scan.update(saved)


def test_admin_invite_management(admin_app):
    app, tmp_path = admin_app
    admin, users = _seed_accounts(app, tmp_path)

    before = admin.get("/api/admin/overview").get_json()["invites"]

    # Mint from the console itself; the new code appears.
    r = admin.post("/api/admin/invites", json={"csrf_token": _csrf(admin)})
    assert r.status_code == 200 and r.get_json()["code"]
    invites = admin.get("/api/admin/overview").get_json()["invites"]
    assert len(invites) == len(before) + 1
    fresh = [i for i in invites if i["used"] is False]
    assert len(fresh) == 1

    # The minted code actually works for signup.
    member = app.test_client()
    _signup(member, "new@example.com", invite_code=fresh[0]["code"])
    invites = admin.get("/api/admin/overview").get_json()["invites"]
    assert [i for i in invites if i["code"] == fresh[0]["code"]][0]["used"] is True
