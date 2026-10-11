"""Proxy resolution: config > env, loopback bypass, Playwright mapping."""

from __future__ import annotations

from qaagent.config import ProxyConfig, RunConfig
from qaagent import netproxy


def _cfg(**kw):
    base = {
        "target": "https://x.test",
        "scope": {"allowed_origins": ["https://x.test"]},
    }
    base.update(kw)
    return RunConfig.model_validate(base)


def test_no_proxy_by_default(monkeypatch):
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    assert netproxy.resolve_proxy(_cfg()) is None
    assert netproxy.playwright_proxy(_cfg()) is None


def test_config_proxy_with_auth():
    cfg = _cfg(proxy={"server": "http://fwd.test.io:3128", "username": "u", "password": "p"})
    assert isinstance(cfg.proxy, ProxyConfig)
    assert netproxy.resolve_proxy(cfg) == "http://u:p@fwd.test.io:3128"
    pw = netproxy.playwright_proxy(cfg)
    assert pw["server"] == "http://fwd.test.io:3128"
    assert pw["username"] == "u" and pw["password"] == "p"
    assert "127.0.0.1" in pw["bypass"]


def test_loopback_bypasses_proxy():
    cfg = _cfg(proxy={"server": "http://fwd.test.io:3128"})
    url = netproxy.resolve_proxy(cfg)
    assert netproxy.should_proxy("http://127.0.0.1:5001/", cfg, url) is False
    assert netproxy.should_proxy("https://x.test/", cfg, url) is True


def test_env_fallback(monkeypatch):
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://env-proxy:8080")
    assert netproxy.resolve_proxy(_cfg()) == "http://env-proxy:8080"


def test_at_sign_in_username_is_encoded():
    cfg = _cfg(proxy={"server": "fwd.test.io:3128", "username": "tester@1423e7", "password": "pw."})
    url = netproxy.resolve_proxy(cfg)
    assert url == "http://tester%401423e7:pw.@fwd.test.io:3128"
    pw = netproxy.playwright_proxy(cfg)
    assert pw["server"] == "http://fwd.test.io:3128"
    assert pw["username"] == "tester@1423e7" and pw["password"] == "pw."


def test_proxy_auth_header_decodes_credentials():
    headers = netproxy.proxy_auth_headers("http://tester%401423e7:pw.@fwd.test.io:3128")
    import base64

    assert headers == {
        "Proxy-Authorization": "Basic " + base64.b64encode(b"tester@1423e7:pw.").decode()
    }
    assert netproxy.proxy_auth_headers(None) == {}
    assert netproxy.proxy_auth_headers("http://fwd.test.io:3128") == {}
