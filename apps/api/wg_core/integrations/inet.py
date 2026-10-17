"""iNET public API (developers.inet.vn). Base https://developers.inet.vn/api/gateway/v1, Bearer key.

Every call below is in the official API reference (https://developers.inet.vn/api-reference, checked 2026-10-17):
- GET   /domain?name=&page=&pageSize=  → {content: [{id, name, status, …}], totalPages, …}
- GET   /domain/{domainId}              → {id, name, nsList: [{id, hostname}], …}
- GET   /domain/{domainId}/record       → {id, name, recordList: [{id, name, type, data, ttl, …}]}  (ns1/ns2.inet.vn only)
- PATCH /domain/{domainId}/record       body {recordList: [{domainId, name, type, data, ttl, action}]}
                                        → {id, name, status, recordList: [... after the update]}

Meaning of PATCH (official description): "Thêm hoặc xóa DNS records" — every item of recordList is ONE operation:
ACTION_ADD adds a record (no id), ACTION_DELETE removes the record with that id, an edit is DELETE + ADD.
So sending one ACTION_ADD item adds one record; it is not a replacement of the whole zone. This is also checked on
every call: the records returned after the PATCH must still contain every record that existed before.

This module only ever sends ACTION_ADD. It never deletes or edits a record.
Rate limit 60/min (429 + Retry-After).
"""
from typing import Callable

import httpx

from . import http

from ..config import env_secret
from .errors import Conflict, NotAvailable, NotConfigured, Permanent, Transient

BASE = "https://developers.inet.vn/api/gateway/v1"
INET_NS = {"ns1.inet.vn", "ns2.inet.vn"}

Log = Callable[[str, str], None]


def dns_provider(ns: set[str]) -> str:
    """inet | cloudflare | other | unknown — from the nameservers iNET reports for the domain."""
    if not ns:
        return "unknown"
    if ns & INET_NS:
        return "inet" if all(n.endswith(".inet.vn") for n in ns) else "mixed"
    if all(n.endswith(".ns.cloudflare.com") for n in ns):
        return "cloudflare"
    return "other"


def record_label(name: str, domain: str) -> str:
    """The record's label relative to the domain. The docs show "@, www, _dmarc"; a full name ("acme.example.vn" or
    "acme.example.vn.") is reduced the same way, so an existing record is never missed and added twice."""
    n, d = (name or "").strip().rstrip(".").lower(), domain.strip().rstrip(".").lower()
    if n in ("", "@", d):
        return "@"
    return n[: -len(d) - 1] if n.endswith("." + d) else n


def _same(r: dict, name: str, rtype: str, data: str, domain: str) -> bool:
    return (record_label(r.get("name"), domain) == name.lower() and (r.get("type") or "").upper() == rtype
            and (r.get("data") or "").strip().rstrip(".") == data)


class Inet:
    def __init__(self, nick_id: str, log: Log | None = None):
        self.nick_id = nick_id
        self.key = env_secret(f"INET_API_KEY_{nick_id.upper()}")
        if not self.key:
            raise NotConfigured(f"iNET {nick_id}", [f"INET_API_KEY_{nick_id.upper()}"])
        self.log = log or (lambda msg, level="info": None)

    def _call(self, method: str, path: str, params: dict | None = None, json: dict | None = None, note: str = ""):
        shown = path + ("?" + "&".join(f"{k}={v}" for k, v in params.items()) if params else "")
        try:
            with http.client(timeout=60) as c:
                r = c.request(method, BASE + path, params=params, json=json, headers={"Authorization": f"Bearer {self.key}"})
        except httpx.TransportError as e:
            self.log(f"iNET {method} {shown} → lỗi mạng: {e}", "warn")
            raise Transient(f"iNET {path}: {e}") from e
        self.log(f"iNET {method} {shown}{note} → HTTP {r.status_code}", "info" if r.status_code < 400 else "warn")
        if r.status_code == 429:
            ra = r.headers.get("Retry-After")
            raise Transient("iNET: vượt giới hạn 60 yêu cầu/phút", float(ra) if ra and ra.isdigit() else 60)
        if r.status_code >= 500:
            raise Transient(f"iNET {path}: HTTP {r.status_code}")
        if r.status_code in (401, 403):
            scope = "read" if method == "GET" else "write"
            raise NotConfigured("iNET", [f"khoá API hợp lệ có quyền {scope} (HTTP {r.status_code})"])
        if r.status_code >= 400:
            raise Permanent(f"iNET {method} {path}: HTTP {r.status_code} — {r.text[:300]}")
        try:
            return r.json()
        except ValueError as e:
            raise Permanent(f"iNET {method} {path}: trả về không phải JSON") from e

    def _get(self, path: str, params: dict | None = None):
        return self._call("GET", path, params=params)

    # ── read ──
    def list_domains(self) -> list[dict]:
        """GET /domain, every page."""
        out, page = [], 1
        while True:
            r = self._get("/domain", {"page": page, "pageSize": 100})
            out += r.get("content") or []
            if page >= int(r.get("totalPages") or 1):
                return out
            page += 1

    def find_domain(self, domain: str) -> dict | None:
        r = self._get("/domain", {"name": domain})
        hits = [d for d in r.get("content") or [] if (d.get("name") or "").lower() == domain.lower()]
        return hits[0] if hits else None

    def nameservers(self, domain_id: int) -> set[str]:
        d = self._get(f"/domain/{domain_id}")
        return {(n.get("hostname") or "").lower().rstrip(".") for n in d.get("nsList") or [] if n.get("hostname")}

    def records(self, domain_id: int) -> list[dict]:
        return self._get(f"/domain/{domain_id}/record").get("recordList") or []

    def inspect(self, domain: str, label: str) -> dict:
        """Read-only picture before any write: the domain in THIS nick's iNET account, its nameservers / DNS provider,
        and every record already using `label`."""
        d = self.find_domain(domain)
        if not d:
            return {"in_account": False}
        did = int(d["id"])
        ns = self.nameservers(did)
        prov = dns_provider(ns)
        out = {"in_account": True, "domain_id": did, "status": d.get("status"), "nameservers": sorted(ns), "provider": prov}
        if prov == "inet":
            out["same_name"] = [{"id": r.get("id"), "type": r.get("type"), "data": r.get("data"), "ttl": r.get("ttl")}
                                for r in self.records(did) if record_label(r.get("name"), domain) == label.lower()]
        return out

    # ── write (ACTION_ADD only) ──
    def create_a_record(self, domain: str, label: str, ip: str, expect_domain_id: int | None = None, ttl: int = 300) -> dict:
        """Add `label.domain A ip`. Returns {"result": "created"|"exists", "domain_id", "record_id"}.
        Any other record already using that name → Conflict: nothing is overwritten, edited or deleted."""
        from .. import write_guard

        write_guard.check("dns", f"{label}.{domain}")
        d = self.find_domain(domain)
        if not d:
            raise Permanent(f"Miền {domain} không có trong tài khoản iNET của nick {self.nick_id}")
        did = int(d["id"])
        if expect_domain_id is not None and did != expect_domain_id:
            raise Permanent(f"ID miền {domain} trên iNET ({did}) khác lúc xem trước ({expect_domain_id}) — dừng, xem trước lại")
        ns = self.nameservers(did)
        if dns_provider(ns) != "inet":
            raise NotAvailable("iNET DNS", f"{domain} không dùng ns1/ns2.inet.vn (đang: {', '.join(sorted(ns)) or 'không rõ'}) — không gọi API bản ghi của iNET")
        before = self.records(did)
        same = [r for r in before if record_label(r.get("name"), domain) == label.lower()]
        mine = [r for r in same if _same(r, label, "A", ip, domain)]
        if mine:
            self.log(f"Bản ghi {label} A {ip} đã có (id {mine[0].get('id')}) — không gửi lại", "ok")
            return {"result": "exists", "domain_id": did, "record_id": mine[0].get("id")}
        if same:
            found = ", ".join(f"{r.get('type')} {r.get('data')} (id {r.get('id')})" for r in same)
            raise Conflict(f"{label}.{domain} đã có bản ghi {found} trên iNET — không ghi đè, không sửa, không xoá")
        item = {"domainId": did, "name": label, "type": "A", "data": ip, "ttl": str(ttl), "action": "ACTION_ADD"}
        r = self._call("PATCH", f"/domain/{did}/record", json={"recordList": [item]}, note=f" [ACTION_ADD {label} A {ip} ttl {ttl}]")
        after = r.get("recordList") if isinstance(r, dict) else None
        if after is None:  # response without the list → read it back
            after = self.records(did)
        new = [x for x in after if _same(x, label, "A", ip, domain)]
        if not new:
            raise Permanent(f"iNET không xác nhận bản ghi {label} A {ip} sau khi thêm — kiểm tra trên iNET trước khi chạy lại")
        ids_after = {x.get("id") for x in after}
        lost = [x for x in before if x.get("id") not in ids_after]
        if lost:
            lost_s = ", ".join(f"{x.get('name')} {x.get('type')} {x.get('data')}" for x in lost)
            self.log(f"CẢNH BÁO: sau khi thêm, iNET không còn trả về {len(lost)} bản ghi cũ: {lost_s}", "err")
            raise Permanent(f"Sau ACTION_ADD, {len(lost)} bản ghi cũ không còn trong danh sách iNET ({lost_s}) — dừng mọi việc, kiểm tra DNS ngay")
        self.log(f"Đã thêm {label}.{domain} A {ip} (id {new[0].get('id')}); {len(before)} bản ghi cũ giữ nguyên", "ok")
        return {"result": "created", "domain_id": did, "record_id": new[0].get("id")}
