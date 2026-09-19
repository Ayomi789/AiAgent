"""Scan-target policy: authorization gates for a publicly hosted Sentinel.

A public testing tool is one misuse away from becoming an attack tool. Two
controls keep it legitimate:

1. **Private-network blocking** — a Sentinel running in the cloud can reach
   the hosting provider's internal network (link-local metadata services,
   RFC1918 ranges, container networks). Scanning those is never legitimate
   from the outside and is the classic SSRF pivot. Public mode blocks them.
2. **Ownership declaration** — the operator of a scan asserts, and the run
   permanently records, that they are authorized to test the target. Same
   rule Test IO enforces with invite-only cycles; here it becomes the legal
   foundation for report isolation and per-site scanning.

Local development is unaffected: public mode is opt-in via
SENTINEL_PUBLIC_MODE=1 (set in compose for hosted deployments).
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

# Everything that must never be a scan target from a public host:
# - loopback: the server itself and anything co-hosted on it
# - private/RFC1918 + link-local: cloud metadata (169.254.169.254), LAN pivots
# - unspecified (0.0.0.0/::), reserved, multicast: never legit targets
_BLOCKED_NETS = [
    *(ipaddress.ip_network(n) for n in (
        "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
        "169.254.0.0/16", "172.16.0.0/12", "192.0.0.0/24", "192.0.2.0/24",
        "192.168.0.0/16", "198.18.0.0/15", "198.51.100.0/24",
        "203.0.113.0/24", "224.0.0.0/4", "240.0.0.0/4",
        "::/128", "::1/128", "fc00::/7", "fe80::/10", "ff00::/8",
    )),
]


def _all_ips(hostname: str) -> list[str]:
    """Resolve a hostname to every address it maps to (empty on failure)."""
    try:
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OSError):
        return []
    return sorted({info[4][0] for info in infos})


def host_is_private(hostname: str) -> bool:
    """True if the host is an IP literal or resolves into a blocked range.

    Names that do not resolve return False here (the scan itself will fail
    with a connection error); the decision to block is about reachable
    *internal* addresses, not unreachable names.
    """
    host = (hostname or "").strip().strip("[]").lower()
    if not host:
        return True
    # IP literal (fast path, no DNS).
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return any(addr in net for net in _BLOCKED_NETS)
    return any(
        ipaddress.ip_address(ip) in net
        for ip in _all_ips(host)
        for net in _BLOCKED_NETS
    )


def target_is_allowed(url: str, *, public_mode: bool) -> tuple[bool, str]:
    """Policy check for a scan target.

    Returns (allowed, reason). Local mode allows everything except
    non-http(s) schemes; public mode additionally blocks private networks.
    """
    try:
        parts = urlsplit(url if "://" in url else f"https://{url}")
    except ValueError:
        return False, "unparseable target URL"
    if parts.scheme not in ("http", "https", ""):
        return False, f"scheme {parts.scheme!r} is not scannable"
    host = parts.hostname or ""
    if not host:
        return False, "target has no hostname"
    if public_mode and host_is_private(host):
        return (
            False,
            "refusing to scan a private/loopback/metadata address "
            "(public deployments may only test internet-facing sites)",
        )
    return True, ""
