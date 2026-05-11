"""
Trusted-proxy IP resolution (audit C-1).

Behind Replit's edge (and any L7 proxy) `request.client.host` collapses to
the proxy address, which makes per-IP rate limiting and per-IP audit
attribution useless. Naively trusting `X-Forwarded-For` is *worse* — it's
client-controlled, so an attacker can rotate it freely to bypass limits.

This module honours `X-Forwarded-For` only when the immediate peer
(`request.client.host`) is itself in a configured trusted-proxy CIDR
allow-list, sourced from the env var `TRUSTED_PROXY_CIDRS` (comma-
separated). Outside that list, the limiter falls back to the peer
address (the safe default — no spoofing vector).

Configuration is read once at process start and cached. To change the
allow-list, set the env var and restart the workers.
"""
from __future__ import annotations

import ipaddress
import logging
import os
from functools import lru_cache
from typing import Tuple

logger = logging.getLogger("nassaq.trusted_proxy")


@lru_cache(maxsize=1)
def trusted_networks() -> Tuple[ipaddress._BaseNetwork, ...]:
    raw = (os.environ.get("TRUSTED_PROXY_CIDRS") or "").strip()
    if not raw:
        return tuple()
    nets = []
    for cidr in raw.split(","):
        cidr = cidr.strip()
        if not cidr:
            continue
        try:
            nets.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid TRUSTED_PROXY_CIDRS entry: %r", cidr)
    return tuple(nets)


def is_trusted_peer(peer: str) -> bool:
    nets = trusted_networks()
    if not nets or not peer or peer == "unknown":
        return False
    try:
        ip = ipaddress.ip_address(peer)
    except ValueError:
        return False
    return any(ip in n for n in nets)


def extract_client_ip(request) -> str:
    """Return the best-effort *real* client IP for `request`.

    - If the immediate peer is not in the trusted-proxy allow-list, returns
      the peer (cannot be spoofed by anyone except that peer).
    - If it IS trusted, honours the leftmost `X-Forwarded-For` entry, then
      `X-Real-IP`. Falls back to the peer if neither is present.
    """
    peer = request.client.host if request.client else "unknown"
    if not is_trusted_peer(peer):
        return peer
    xff = request.headers.get("x-forwarded-for")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return peer


__all__ = ["extract_client_ip", "is_trusted_peer", "trusted_networks"]
