"""iNET public API (developers.inet.vn). Base https://developers.inet.vn/api/gateway/v1, Bearer key.

Documented: GET /domain (list), GET /domain/{id}/record, PATCH /domain/{id}/record, rate limit 60/min (429 + Retry-After).
NOT documented: the response shape of GET /domain and the request body of PATCH /record.
→ Listing returns the raw JSON for the owner to check; creating an A record is BLOCKED until iNET
  publishes (or confirms) the PATCH body. No guessing.
"""
import httpx

from ..config import env_secret
from .errors import NotAvailable, NotConfigured, Permanent, Transient

BASE = "https://developers.inet.vn/api/gateway/v1"


class Inet:
    def __init__(self, nick_id: str):
        self.key = env_secret(f"INET_API_KEY_{nick_id.upper()}")
        if not self.key:
            raise NotConfigured(f"iNET {nick_id}", [f"INET_API_KEY_{nick_id.upper()}"])

    def _get(self, path: str):
        try:
            with httpx.Client(timeout=60) as c:
                r = c.get(BASE + path, headers={"Authorization": f"Bearer {self.key}"})
        except httpx.TransportError as e:
            raise Transient(f"iNET {path}: {e}") from e
        if r.status_code == 429:
            ra = r.headers.get("Retry-After")
            raise Transient("iNET: vượt giới hạn 60 yêu cầu/phút", float(ra) if ra and ra.isdigit() else 60)
        if r.status_code >= 500:
            raise Transient(f"iNET {path}: HTTP {r.status_code}")
        if r.status_code in (401, 403):
            raise NotConfigured("iNET", [f"khoá API hợp lệ / quyền (HTTP {r.status_code})"])
        if r.status_code >= 400:
            raise Permanent(f"iNET {path}: HTTP {r.status_code}")
        return r.json()

    def list_domains_raw(self):
        """GET /domain — raw response (shape not documented; parsed only after checking a real reply)."""
        return self._get("/domain")

    def create_a_record(self, domain: str, label: str, ip: str):
        raise NotAvailable("iNET DNS", "tài liệu chính thức chưa có cấu trúc dữ liệu gửi lên cho PATCH /domain/{id}/record — "
                                       "cần iNET cung cấp (hoặc bản Postman chính thức) trước khi tạo bản ghi A")
