"""Public DNS lookup (DNS-over-HTTPS JSON APIs of Cloudflare and Google) and HTTPS checks."""
import html

import httpx

from . import http

from .errors import Transient

DOH = "https://cloudflare-dns.com/dns-query"  # https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/
GOOGLE_DOH = "https://dns.google/resolve"  # https://developers.google.com/speed/public-dns/docs/doh/json


def _ask(url: str, name: str) -> list[str] | None:
    try:
        with http.client(timeout=20) as c:
            r = c.get(url, params={"name": name, "type": "A"}, headers={"accept": "application/dns-json"})
    except httpx.TransportError:
        return None
    if r.status_code != 200:
        return None
    return [a["data"] for a in r.json().get("Answer", []) if a.get("type") == 1]


def _system(name: str) -> list[str] | None:
    """The machine's own resolver, IPv4 answers only. [] when the name does not exist, None when it cannot answer."""
    import socket

    try:
        return sorted({ai[4][0] for ai in socket.getaddrinfo(name, None, socket.AF_INET, socket.SOCK_STREAM)})
    except socket.gaierror as e:
        return [] if e.errno in (socket.EAI_NONAME, getattr(socket, "EAI_NODATA", -5), 11001, 11004) else None


system_resolve = _system  # tests replace this (no real DNS lookups in tests)


def resolve_a(name: str) -> list[str]:
    """A records seen by any resolver (union): Cloudflare and Google DNS-over-HTTPS, plus the system resolver because
    some networks block DoH. One resolver's cached "no such name" — common right after a record is added, because
    the preview asked before it existed — does not hide the new record."""
    answers = [a for a in (_ask(DOH, name), _ask(GOOGLE_DOH, name), system_resolve(name)) if a is not None]
    if not answers:
        raise Transient(f"DNS {name}: không hỏi được resolver nào")
    return sorted({ip for a in answers for ip in a})


def https_ok(domain: str, must_contain: str) -> tuple[bool, str]:
    """GET https://domain with certificate verification. OK = 200 + expected text in the page."""
    try:
        with http.client(timeout=30, follow_redirects=True, verify=True) as c:
            r = c.get(f"https://{domain}/")
    except httpx.ConnectError as e:
        return False, f"không kết nối HTTPS được ({e.__class__.__name__}: chứng chỉ chưa có hoặc chưa hợp lệ?)"
    except httpx.TransportError as e:
        return False, f"lỗi mạng: {e}"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    if html.unescape(must_contain).lower() not in html.unescape(r.text).lower():  # "Silva &amp; Cia" == "Silva & Cia"
        return False, "trang trả về không phải website vừa dựng (thiếu tên doanh nghiệp)"
    return True, "HTTP 200 · chứng chỉ hợp lệ · đúng nội dung"
