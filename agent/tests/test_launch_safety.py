"""Phase 3 launch-safety tests: signup policy, invites, scan authorization,
private-target blocking, and the daily quota."""

from __future__ import annotations

import json
import re

import pytest

from tests.test_report import _signup


# --- netpolicy: private-network detection -------------------------------------


class TestHostIsPrivate:
    def test_ip_literals(self):
        from qaagent.netpolicy import host_is_private

        for host in ("127.0.0.1", "10.1.2.3", "192.168.0.9", "172.16.5.4",
                     "169.254.169.254", "::1", "0.0.0.0", "fe80::1", "fc00::1"):
            assert host_is_private(host), host
        for host in ("8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:4700::1"):
            assert not host_is_private(host), host

    def test_bracketed_ipv6(self):
        from qaagent.netpolicy import host_is_private

        assert host_is_private("[::1]")
        assert not host_is_private("[2606:4700::1]")

    def test_resolving_names(self, monkeypatch):
        import socket

        from qaagent import netpolicy

        # A name that resolves private -> blocked; public -> allowed;
        # unresolvable -> allowed here (the scan fails on its own).
        monkeypatch.setattr(
            socket, "getaddrinfo",
            lambda h, p, proto: [(socket.AF_INET, None, None, "", ("10.0.0.5", 0))],
        )
        assert netpolicy.host_is_private("internal.example")
        monkeypatch.setattr(
            socket, "getaddrinfo",
            lambda h, p, proto: [(socket.AF_INET, None, None, "", ("93.184.216.34", 0))],
        )
        assert not netpolicy.host_is_private("site.example")
        monkeypatch.setattr(
            socket, "getaddrinfo",
            lambda *a, **k: (_ for _ in ()).throw(socket.gaierror(1, "nope")),
        )
        assert not netpolicy.host_is_private("gone.example")

    def test_dns_rebinding_guard_checks_all_addresses(self, monkeypatch):
        """A rebinding name (public + private mix) must be blocked."""
        import socket

        from qaagent import netpolicy

        def _mixed(h, p, proto):
            return [
                (socket.AF_INET, None, None, "", ("93.184.216.34", 0)),
                (socket.AF_INET, None, None, "", ("192.168.1.10", 0)),
            ]

        monkeypatch.setattr(socket, "getaddrinfo", _mixed)
        assert netpolicy.host_is_private("rebind.example")


class TestTargetIsAllowed:
    def test_local_mode_allows_private(self):
        from qaagent.netpolicy import target_is_allowed

        ok, why = target_is_allowed("http://127.0.0.1:5001", public_mode=False)
        assert ok and why == ""

    def test_public_mode_blocks_private(self):
        from qaagent.netpolicy import target_is_allowed

        for url in ("http://127.0.0.1:5001", "http://10.0.0.1/",
                    "http://[::1]/", "http://169.254.169.254/latest/meta-data"):
            ok, why = target_is_allowed(url, public_mode=True)
            assert not ok, url
            assert "private" in why

    def test_public_mode_allows_public(self):
        from qaagent.netpolicy import target_is_allowed

        ok, why = target_is_allowed("https://example.com", public_mode=True)
        assert ok and why == ""

    def test_bad_scheme_and_empty_host(self):
        from qaagent.netpolicy import target_is_allowed

        ok, why = target_is_allowed("ftp://example.com", public_mode=False)
        assert not ok and "scheme" in why
        ok, why = target_is_allowed("http://", public_mode=False)
        assert not ok


# --- signup policy ------------------------------------------------------------


def test_signup_policy_states(monkeypatch):
    from qaagent.auth import signup_policy

    monkeypatch.delenv("SENTINEL_OPEN_SIGNUP", raising=False)
    assert signup_policy(0) == "bootstrap"
    assert signup_policy(3) == "invite"
    monkeypatch.setenv("SENTINEL_OPEN_SIGNUP", "1")
    # Even with open signup, the FIRST account needs the bootstrap token:
    # a stranger must never be able to claim admin on a fresh instance.
    assert signup_policy(0) == "bootstrap"
    assert signup_policy(2) == "open"


# --- invites store ------------------------------------------------------------


def test_invite_lifecycle(tmp_path):
    from qaagent.auth import UserStore

    store = UserStore(tmp_path / "users.db")
    assert store.list_invites() == []

    code = store.create_invite(created_by=1)
    assert code and len(code) >= 12
    assert [(r["code"], r["used_by"]) for r in store.list_invites()] == [(code, None)]

    assert store.use_invite(code) is True
    # Single-use: the second consumption fails.
    assert store.use_invite(code) is False
    assert store.use_invite("never-existed") is False
    assert store.use_invite("") is False
    rows = store.list_invites()
    assert rows[0]["used_by"] is not None and rows[0]["used_at"]


# --- dashboard signup gating --------------------------------------------------


def _csrf(client, path: str) -> str:
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def test_first_signup_requires_bootstrap_token(tmp_path, monkeypatch):
    monkeypatch.delenv("SENTINEL_OPEN_SIGNUP", raising=False)
    from qaagent.dashboard import create_app

    (tmp_path / "live.json").write_text(json.dumps({"status": "idle"}), encoding="utf-8")
    app = create_app(tmp_path / "live.json", tmp_path, auth_token="tok")
    client = app.test_client()

    # Signup form shows the access-token field.
    page = client.get("/signup").get_data(as_text=True)
    assert 'name="bootstrap_token"' in page

    # Wrong or missing token -> refused, no user created.
    csrf = _csrf(client, "/signup")
    bad = client.post("/signup", data={
        "email": "hacker@example.com", "password": "supersecret9",
        "csrf_token": csrf, "bootstrap_token": "WRONG",
    })
    assert "reserved for the server operator" in bad.get_data(as_text=True)

    # Correct token -> admin account created.
    csrf = _csrf(client, "/signup")
    ok = client.post("/signup", data={
        "email": "owner@example.com", "password": "supersecret9",
        "csrf_token": csrf, "bootstrap_token": "tok", "accept_terms": "1",
    }, follow_redirects=True)
    assert "Run scan" in ok.get_data(as_text=True)


def test_later_signup_requires_invite_code(tmp_path, monkeypatch):
    monkeypatch.delenv("SENTINEL_OPEN_SIGNUP", raising=False)
    from qaagent.auth import UserStore
    from qaagent.dashboard import create_app

    (tmp_path / "live.json").write_text(json.dumps({"status": "idle"}), encoding="utf-8")
    app = create_app(tmp_path / "live.json", tmp_path, auth_token="tok")
    users = UserStore(tmp_path / "users.db")

    owner = app.test_client()
    _signup(owner, "owner@example.com", bootstrap_token="tok")

    # Signup form now shows the invite field.
    client = app.test_client()
    assert 'name="invite_code"' in client.get("/signup").get_data(as_text=True)

    # No/garbage code -> refused.
    csrf = _csrf(client, "/signup")
    bad = client.post("/signup", data={
        "email": "friend@example.com", "password": "supersecret9",
        "csrf_token": csrf, "invite_code": "GARBAGE", "accept_terms": "1",
    })
    assert "not valid" in bad.get_data(as_text=True)

    # A real code (single-use) works.
    code = users.create_invite(created_by=1)
    csrf = _csrf(client, "/signup")
    ok = client.post("/signup", data={
        "email": "friend@example.com", "password": "supersecret9",
        "csrf_token": csrf, "invite_code": code, "accept_terms": "1",
    }, follow_redirects=True)
    assert ok.status_code == 200
    assert users.count() == 2

    # The used code cannot create a second account.
    other = app.test_client()
    csrf = _csrf(other, "/signup")
    again = other.post("/signup", data={
        "email": "stranger@example.com", "password": "supersecret9",
        "csrf_token": csrf, "invite_code": code, "accept_terms": "1",
    })
    assert "not valid" in again.get_data(as_text=True)


def test_open_signup_env_bypasses_invite_but_not_bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTINEL_OPEN_SIGNUP", "1")
    from qaagent.dashboard import create_app

    (tmp_path / "live.json").write_text(json.dumps({"status": "idle"}), encoding="utf-8")
    app = create_app(tmp_path / "live.json", tmp_path, auth_token="tok")

    first = app.test_client()
    _signup(first, "owner@example.com", bootstrap_token="tok")

    second = app.test_client()
    assert 'name="invite_code"' not in second.get("/signup").get_data(as_text=True)
    _signup(second, "anyone@example.com")


def test_invites_page_admin_only(tmp_path, monkeypatch):
    monkeypatch.delenv("SENTINEL_OPEN_SIGNUP", raising=False)
    from qaagent.dashboard import create_app

    (tmp_path / "live.json").write_text(json.dumps({"status": "idle"}), encoding="utf-8")
    app = create_app(tmp_path / "live.json", tmp_path, auth_token="tok")

    owner = app.test_client()
    _signup(owner, "owner@example.com", bootstrap_token="tok")

    page = owner.get("/invites")
    assert page.status_code == 200 and "Invite codes" in page.get_data(as_text=True)

    # Generate one via the form (CSRF-protected).
    csrf = _csrf(owner, "/invites")
    owner.post("/invites", data={"csrf_token": csrf})
    body = owner.get("/invites").get_data(as_text=True)
    assert "open" in body  # the new code is listed as open

    # Members get redirected away; anonymous -> login.
    member = app.test_client()
    _signup(member, "member@example.com")
    assert member.get("/invites").status_code == 302
    anon = app.test_client()
    assert anon.get("/invites").status_code == 302


# --- scan-start gate ----------------------------------------------------------


@pytest.fixture()
def scan_env(tmp_path, monkeypatch):
    """Dashboard app with public-mode + quota env pinned; returns (app, tmp_path)."""
    monkeypatch.setenv("SENTINEL_PUBLIC_MODE", "1")
    monkeypatch.setenv("SENTINEL_DAILY_SCAN_LIMIT", "2")
    monkeypatch.setenv("SENTINEL_CONFIG_DIR", str(tmp_path / "configs"))
    from qaagent.dashboard import create_app

    (tmp_path / "live.json").write_text(json.dumps({"status": "idle"}), encoding="utf-8")
    app = create_app(tmp_path / "live.json", tmp_path, auth_token="tok")
    return app, tmp_path


def _scan_post(client, config: str, *, authorized=True):
    # X-Sentinel-Token authenticates anonymous clients as the operator/API;
    # logged-in clients are unaffected by it (their session still applies).
    return client.post(
        "/api/scan",
        data=json.dumps({"config": config, "authorized": authorized}),
        content_type="application/json",
        headers={"X-Sentinel-Token": "tok"},
    )


def test_scan_requires_authorization(scan_env, monkeypatch):
    """No authorized flag -> 403, before any target resolution or spawn."""
    app, _ = scan_env
    client = app.test_client()

    # Unauthenticated callers hit the auth gate first (401)...
    r = client.post("/api/scan", data=json.dumps({"config": "example.com"}),
                    content_type="application/json")
    assert r.status_code == 401

    # ...and an authenticated caller without the declaration gets 403.
    r = client.post(
        "/api/scan",
        data=json.dumps({"config": "example.com"}),
        content_type="application/json",
        headers={"X-Sentinel-Token": "tok"},
    )
    assert r.status_code == 403
    assert "authorization required" in r.get_json()["error"]

    r = _scan_post(client, "example.com", authorized=False)
    assert r.status_code == 403

    # Declared + public target: passes the gate, config auto-created, spawn
    # attempted (the child fails fast on an unreachable target - harmless).
    r = _scan_post(client, "example.com")
    assert r.status_code == 200
    body = r.get_json()
    assert body["started"] is True and body["created"] is True

    # The started process belongs to the test run - reap it so it cannot
    # outlive the test or leak a python child.
    from qaagent.dashboard import _scan

    proc = _scan.get("proc")
    if proc is not None and proc.poll() is None:
        proc.kill()
        proc.wait(timeout=10)


def test_scan_blocks_private_targets_in_public_mode(scan_env):
    app, _ = scan_env
    client = app.test_client()
    # Bare IP-literal domains (config names cannot contain ':' or '/';
    # bracketed IPv6 is covered at the netpolicy unit level).
    for target in ("127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254"):
        r = _scan_post(client, target)
        assert r.status_code == 403, target
        assert "refusing to scan a private" in r.get_json()["error"]
    # A private target hidden inside an existing config file is caught too.
    import pathlib

    cfg_dir = pathlib.Path(app.config["SENTINEL_CONFIG_DIR"]) if "SENTINEL_CONFIG_DIR" in app.config else None
    # SENTINEL_CONFIG_DIR was set by the fixture env; _config_dir reads env.
    import os

    cfg_dir = pathlib.Path(os.environ["SENTINEL_CONFIG_DIR"])
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.internal.yml").write_text(
        "target: http://10.9.9.9\n", encoding="utf-8"
    )
    r = _scan_post(client, "internal")
    assert r.status_code == 403
    assert "refusing to scan a private" in r.get_json()["error"]


def test_scan_allows_private_targets_in_local_mode(tmp_path, monkeypatch):
    """Local mode keeps scanning the localhost test app - that's the point."""
    monkeypatch.delenv("SENTINEL_PUBLIC_MODE", raising=False)
    monkeypatch.setenv("SENTINEL_DAILY_SCAN_LIMIT", "0")
    monkeypatch.setenv("SENTINEL_CONFIG_DIR", str(tmp_path / "configs"))
    from qaagent.dashboard import create_app

    (tmp_path / "live.json").write_text(json.dumps({"status": "idle"}), encoding="utf-8")
    app = create_app(tmp_path / "live.json", tmp_path, auth_token="tok")
    r = _scan_post(app.test_client(), "127.0.0.1")
    assert r.status_code == 200
    from qaagent.dashboard import _scan

    proc = _scan.get("proc")
    if proc is not None and proc.poll() is None:
        proc.kill()
        proc.wait(timeout=10)


def test_daily_quota_enforced(scan_env):
    """The starter's 3rd scan today is refused at the daily limit of 2."""
    from datetime import datetime, timezone

    app, tmp_path = scan_env

    # The quota applies to logged-in starters - sign one up.
    owner = app.test_client()
    _signup(owner, "quota@example.com", bootstrap_token="tok")

    # Seed two runs owned by that user, dated today (as if already scanned).
    today = datetime.now(timezone.utc).date().isoformat()
    for i in (1, 2):
        (tmp_path / f"report-2026010{i}-000000.json").write_text(
            json.dumps(
                {
                    "target": "http://x.test",
                    "started_at": f"{today}T00:00:0{i}+00:00",
                    "owner_id": 1,
                    "owner_email": "quota@example.com",
                    "findings": [],
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / f"report-2026010{i}-000000.md").write_text("# r", encoding="utf-8")

    r = _scan_post(owner, "example.com")
    assert r.status_code == 429
    assert "daily scan limit reached (2/day)" in r.get_json()["error"]


def test_token_starter_bypasses_quota(scan_env):
    """Bootstrap-token callers are the operator/API - quota does not apply."""
    app, _ = scan_env
    client = app.test_client()
    r = _scan_post(client, "example.com")
    assert r.status_code == 200
    from qaagent.dashboard import _scan

    proc = _scan.get("proc")
    if proc is not None and proc.poll() is None:
        proc.kill()
        proc.wait(timeout=10)
