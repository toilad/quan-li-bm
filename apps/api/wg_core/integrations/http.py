"""Outbound HTTP for every integration (Google, iNET, cPanel, DNS checks, Pexels/Pixabay, Anthropic).

IPv4 only by default: on the owner's network IPv6 does not route out, and httpx — unlike curl and browsers, which
fall back to IPv4 at once — waits for the IPv6 connection to time out, so every call hung. Set QLBM_IPV6=1 on a
machine where IPv6 works. Certificates are always verified.
"""
import os

import httpx


def local_address() -> str | None:
    return None if os.environ.get("QLBM_IPV6") == "1" else "0.0.0.0"


def transport(**kw) -> httpx.HTTPTransport:
    return httpx.HTTPTransport(local_address=local_address(), **kw)


def client(**kw) -> httpx.Client:
    kw.setdefault("transport", transport())
    return httpx.Client(**kw)
