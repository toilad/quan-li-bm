"""The owner's phone number provider — Twilio (REST API 2010-04-01, HTTP basic auth: Account SID + Auth Token).

Read-only and free:   GET  /Accounts/{sid}/IncomingPhoneNumbers.json          numbers the owner already has
                      GET  /Accounts/{sid}/AvailablePhoneNumbers/US/Local.json  numbers on sale in a state (InRegion)
Paid (one number):    POST /Accounts/{sid}/IncomingPhoneNumbers.json  PhoneNumber=+1…  — behind the owner's real-write
                      lock (operation "phone") AND an explicit confirmation of the cost for that very number.

⚠ Not yet checked against a live account (the owner has not configured one): request/answer shapes follow Twilio's
public API reference; the tests mock them. The first live call must be a read (owned numbers) before any purchase.
"""
import httpx

from .. import write_guard
from ..runtime_config import get as cfg
from . import http
from .errors import NotConfigured, Permanent, Transient

BASE = "https://api.twilio.com/2010-04-01"


class PhoneProvider:
    name = "Twilio"

    def __init__(self):
        self.sid, self.token = cfg("TWILIO_ACCOUNT_SID").strip(), cfg("TWILIO_AUTH_TOKEN").strip()
        missing = [k for k, v in (("TWILIO_ACCOUNT_SID", self.sid), ("TWILIO_AUTH_TOKEN", self.token)) if not v]
        if missing:
            raise NotConfigured("nhà cung cấp số điện thoại (Twilio)", missing)

    def _call(self, method: str, path: str, params: dict | None = None, data: dict | None = None) -> dict:
        what = f"Twilio {method} {path.split('/')[-1]}"
        try:
            with http.client(timeout=60, auth=(self.sid, self.token)) as c:
                r = c.request(method, f"{BASE}/Accounts/{self.sid}{path}", params=params, data=data)
        except httpx.TransportError as e:
            raise Transient(f"{what}: lỗi mạng ({type(e).__name__})") from None
        if r.status_code in (401, 403):
            raise NotConfigured("nhà cung cấp số điện thoại (Twilio)", ["TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN đúng (bị từ chối)"])
        if r.status_code == 429 or r.status_code >= 500:
            raise Transient(f"{what}: HTTP {r.status_code}")
        try:
            body = r.json()
        except ValueError:
            raise Permanent(f"{what}: trả về không phải JSON (HTTP {r.status_code})") from None
        if r.status_code >= 400:
            raise Permanent(f"{what}: {body.get('message') or r.status_code}")
        return body

    def owned(self) -> list[dict]:
        """Numbers already in the owner's account (no cost)."""
        body = self._call("GET", "/IncomingPhoneNumbers.json", params={"PageSize": 1000})
        return [{"number": n["phone_number"], "name": n.get("friendly_name") or "", "sid": n.get("sid", "")}
                for n in body.get("incoming_phone_numbers") or []]

    def available(self, state: str, limit: int = 10) -> list[dict]:
        """Local numbers on sale in this state (searching costs nothing; buying does)."""
        body = self._call("GET", "/AvailablePhoneNumbers/US/Local.json",
                          params={"InRegion": state, "VoiceEnabled": "true", "PageSize": limit})
        return [{"number": n["phone_number"], "region": n.get("region") or "", "locality": n.get("locality") or ""}
                for n in body.get("available_phone_numbers") or []]

    def buy(self, number: str, label: str) -> dict:
        """Paid. Only after write_guard allows operation "phone" for this number."""
        write_guard.check("phone", number)
        body = self._call("POST", "/IncomingPhoneNumbers.json", data={"PhoneNumber": number, "FriendlyName": label[:64]})
        return {"number": body.get("phone_number") or number, "sid": body.get("sid", "")}
