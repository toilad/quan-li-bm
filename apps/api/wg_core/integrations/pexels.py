"""Pexels API (https://www.pexels.com/api/documentation/, checked 2026-10-17) — photos for the generated websites.

- Auth: header `Authorization: <key>`.
- GET https://api.pexels.com/v1/search?query=&orientation=landscape|portrait|square&per_page (≤ 80)&page
  → {photos: [{id, url, photographer, photographer_url, alt, src: {original, large2x, large, medium, small,
  portrait (800×1200), landscape (1200×627), tiny}}], …}
- Limits: 200 requests / hour, 20 000 / month (429 when exceeded). X-Ratelimit-* headers on 2xx only.
- Guidelines: show a prominent link to Pexels and credit the photographers (done in the site footer).
The images are downloaded once and uploaded with the site — the published pages do not hot-link them.
"""
import httpx

from ..runtime_config import get as cfg
from .errors import NotConfigured, Permanent, Transient

API = "https://api.pexels.com/v1"
IMAGE_HOSTS = ("images.pexels.com",)


def _key() -> str:
    key = cfg("PEXELS_API_KEY")
    if not key:
        raise NotConfigured("Pexels (ảnh cho website)", ["PEXELS_API_KEY"])
    return key


def _check(r: httpx.Response, what: str):
    if r.status_code == 429:
        raise Transient("Pexels: vượt giới hạn 200 yêu cầu/giờ — chờ rồi thử lại", 900)
    if r.status_code in (401, 403):
        raise NotConfigured("Pexels", [f"khoá API hợp lệ (HTTP {r.status_code})"])
    if r.status_code >= 500:
        raise Transient(f"Pexels {what}: HTTP {r.status_code}")
    if r.status_code >= 400:
        raise Permanent(f"Pexels {what}: HTTP {r.status_code}")


def search(query: str, orientation: str, per_page: int = 30, page: int = 1) -> dict:
    """Returns {"photos": [...], "remaining": X-Ratelimit-Remaining or None}."""
    params = {"query": query, "orientation": orientation, "per_page": min(per_page, 80), "page": page}
    try:
        with httpx.Client(timeout=30) as c:
            r = c.get(f"{API}/search", params=params, headers={"Authorization": _key()})
    except httpx.TransportError as e:
        raise Transient(f"Pexels search: {e}") from e
    _check(r, "search")
    body = r.json()
    return {"photos": body.get("photos") or [], "remaining": r.headers.get("X-Ratelimit-Remaining")}


def download(url: str) -> bytes:
    """One of the `src` URLs of a search result (images.pexels.com only)."""
    if httpx.URL(url).host not in IMAGE_HOSTS:
        raise Permanent(f"Pexels: địa chỉ ảnh không thuộc Pexels ({url})")
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as c:
            r = c.get(url)
    except httpx.TransportError as e:
        raise Transient(f"Pexels ảnh: {e}") from e
    _check(r, "ảnh")
    if not r.headers.get("content-type", "").startswith("image/"):
        raise Permanent(f"Pexels: không phải file ảnh ({r.headers.get('content-type')})")
    return r.content
