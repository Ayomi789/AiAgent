"""Forward-proxy support for targets behind a corporate proxy.

Resolution order: explicit argument > RunConfig.proxy > HTTP_PROXY /
HTTPS_PROXY environment (httpx honors those on its own). Hosts matching the
bypass list (loopback by default) always go direct.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse, urlunparse


def proxy_url_for(server: str, username: str | None = None, password: str | None = None) -> str:
    """Embed optional credentials: http://user:pass@host:port.

    Credentials are percent-encoded (usernames like tester@1423e7 would
    otherwise corrupt the URL authority section).
    """
    from urllib.parse import quote

    parsed = urlparse(server if "://" in server else f"http://{server}")
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    auth = ""
    if username:
        auth = quote(username, safe="") + (f":{quote(password, safe='')}" if password else "") + "@"
    scheme = parsed.scheme or "http"
    return urlunparse((scheme, f"{auth}{host}{port}", "", "", "", ""))


def resolve_proxy(config=None, explicit: str | None = None) -> str | None:
    """Effective proxy URL, or None for a direct connection."""
    if explicit:
        return explicit
    proxy_cfg = getattr(config, "proxy", None)
    if proxy_cfg is not None and getattr(proxy_cfg, "server", None):
        return proxy_url_for(
            proxy_cfg.server,
            getattr(proxy_cfg, "username", None),
            getattr(proxy_cfg, "password", None),
        )
    return os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None


def proxy_auth_headers(proxy_url: str | None) -> dict:
    """Explicit Proxy-Authorization header.

    httpx does not derive proxy credentials from the proxy URL's userinfo,
    so they must be sent as a header or every request gets a 407.
    """
    if not proxy_url:
        return {}
    from urllib.parse import unquote
    import base64

    parsed = urlparse(proxy_url)
    if not parsed.username:
        return {}
    raw = unquote(parsed.username) + ":" + unquote(parsed.password or "")
    token = base64.b64encode(raw.encode()).decode()
    return {"Proxy-Authorization": f"Basic {token}"}


def bypass_hosts(config=None) -> list[str]:
    proxy_cfg = getattr(config, "proxy", None)
    if proxy_cfg is not None and getattr(proxy_cfg, "bypass", None):
        return list(proxy_cfg.bypass)
    extra = os.environ.get("NO_PROXY", "")
    return ["localhost", "127.0.0.1", "::1"] + [
        h.strip().lower().lstrip(".") for h in extra.split(",") if h.strip()
    ]


def should_proxy(url: str, config=None, proxy_url: str | None = None) -> bool:
    """False for bypassed hosts (loopback) or when no proxy is configured."""
    if proxy_url is None:
        proxy_url = resolve_proxy(config)
    if not proxy_url:
        return False
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return True
    return host not in bypass_hosts(config)


def playwright_proxy(config=None, explicit: str | None = None) -> dict | None:
    """Proxy dict for chromium.launch(), or None for direct."""
    proxy_url = resolve_proxy(config, explicit)
    bypass = bypass_hosts(config)
    if not proxy_url:
        return None
    parsed = urlparse(proxy_url)
    out: dict = {"server": f"{parsed.scheme}://{parsed.hostname}{':' + str(parsed.port) if parsed.port else ''}"}
    if parsed.username:
        from urllib.parse import unquote

        out["username"] = unquote(parsed.username)
    if parsed.password:
        from urllib.parse import unquote as _unquote

        out["password"] = _unquote(parsed.password)
    bypass = ",".join(f"*{h}" if not h.startswith("*") else h for h in bypass)
    if bypass:
        out["bypass"] = bypass
    return out
