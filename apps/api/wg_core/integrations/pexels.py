"""Pexels API (https://www.pexels.com/api/documentation/, checked 2026-10-17) — photos for the generated websites.

- Auth: header `Authorization: <key>` (never in the URL).
- GET https://api.pexels.com/v1/search?query=&orientation=landscape|portrait|square&per_page (≤ 80)&page
  → {photos: [{id, url, photographer, photographer_url, alt, src: {original, large2x, large, medium, small,
  portrait (800×1200), landscape (1200×627), tiny}}], …}
- Limits: 200 requests / hour, 20 000 / month (429 when exceeded). X-Ratelimit-* headers on 2xx only.
- Guidelines: show a prominent link to Pexels and credit the photographers (done in the site footer).
The images are downloaded once and uploaded with the site — the published pages do not hot-link them.
Same normalised output as pixabay.py, so the photo picker works with either.
"""
import httpx

from . import http

from ..runtime_config import get as cfg
from .errors import NotConfigured, Permanent, Transient

NAME, SITE = "Pexels", "https://www.pexels.com/"
API = "https://api.pexels.com/v1"
IMAGE_HOSTS = ("images.pexels.com",)
SRC = {"portrait": "portrait", "landscape": "landscape", "square": "large"}


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


def _photo(p: dict, orientation: str) -> dict:
    return {"id": p.get("id"), "src": (p.get("src") or {}).get(SRC[orientation]) or "", "alt": p.get("alt") or "",
            "photographer": p.get("photographer") or "", "photographer_url": p.get("photographer_url") or "",
            "url": p.get("url") or ""}


def search(query: str, orientation: str, per_page: int = 30, page: int = 1) -> dict:
    """orientation: portrait | landscape | square. Returns {"photos": [normalised], "remaining": header or None}."""
    params = {"query": query, "orientation": orientation, "per_page": min(per_page, 80), "page": page}
    try:
        with http.client(timeout=30) as c:
            r = c.get(f"{API}/search", params=params, headers={"Authorization": _key()})
    except httpx.TransportError as e:
        raise Transient(f"Pexels search: lỗi mạng ({type(e).__name__})") from None
    _check(r, "search")
    photos = [_photo(p, orientation) for p in r.json().get("photos") or []]
    return {"photos": [p for p in photos if p["src"]], "remaining": r.headers.get("X-Ratelimit-Remaining")}


def download(url: str) -> bytes:
    """One of the `src` URLs of a search result (images.pexels.com only)."""
    if httpx.URL(url).host not in IMAGE_HOSTS:
        raise Permanent(f"Pexels: địa chỉ ảnh không thuộc Pexels ({httpx.URL(url).host})")
    try:
        with http.client(timeout=60, follow_redirects=True) as c:
            r = c.get(url)
    except httpx.TransportError as e:
        raise Transient(f"Pexels ảnh: lỗi mạng ({type(e).__name__})") from None
    _check(r, "ảnh")
    if not r.headers.get("content-type", "").startswith("image/"):
        raise Permanent(f"Pexels: không phải file ảnh ({r.headers.get('content-type')})")
    return r.content
