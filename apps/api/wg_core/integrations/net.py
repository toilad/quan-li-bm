"""Public DNS lookup (Cloudflare DNS-over-HTTPS JSON API) and HTTPS checks."""
import httpx

from .errors import Transient

DOH = "https://cloudflare-dns.com/dns-query"


def resolve_a(name: str) -> list[str]:
    try:
        with httpx.Client(timeout=20) as c:
            r = c.get(DOH, params={"name": name, "type": "A"}, headers={"accept": "application/dns-json"})
    except httpx.TransportError as e:
        raise Transient(f"DNS {name}: {e}") from e
    if r.status_code != 200:
        raise Transient(f"DNS {name}: HTTP {r.status_code}")
    return [a["data"] for a in r.json().get("Answer", []) if a.get("type") == 1]


def https_ok(domain: str, must_contain: str) -> tuple[bool, str]:
    """GET https://domain with certificate verification. OK = 200 + expected text in the page."""
    try:
        with httpx.Client(timeout=30, follow_redirects=True, verify=True) as c:
            r = c.get(f"https://{domain}/")
    except httpx.ConnectError as e:
        return False, f"không kết nối HTTPS được ({e.__class__.__name__}: chứng chỉ chưa có hoặc chưa hợp lệ?)"
    except httpx.TransportError as e:
        return False, f"lỗi mạng: {e}"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    if must_contain.lower() not in r.text.lower():
        return False, "trang trả về không phải website vừa dựng (thiếu tên doanh nghiệp)"
    return True, "HTTP 200 · chứng chỉ hợp lệ · đúng nội dung"
