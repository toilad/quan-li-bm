"""Pixabay API (https://pixabay.com/api/docs/, checked 2026-10-17) — photos for the generated websites.

- GET https://pixabay.com/api/?key=&q= (≤ 100 chars) &image_type=photo &orientation=all|horizontal|vertical
  &safesearch=true &per_page (3–200) &page → {total, totalHits, hits: [{id, pageURL, tags, webformatURL (≤ 640 px,
  valid 24 h), largeImageURL (≤ 1280 px), imageWidth, imageHeight, user_id, user, …}]}
- Limits: 100 requests / 60 s per key (429 "API rate limit exceeded"; X-RateLimit-Reset = seconds to wait).
  Search results must be cached for 24 hours.
- Rules: no permanent hotlinking — download the images to your own server (the build ships them with the site);
  no systematic mass downloads (7 photos per site); show where the images come from (credit in the site footer).
The key travels in the query string, so request URLs are never logged or put in error messages.
"""
import httpx

from ..runtime_config import get as cfg
from .errors import NotConfigured, Permanent, Transient

API = "https://pixabay.com/api/"
IMAGE_HOSTS = ("pixabay.com", "cdn.pixabay.com")
ORIENTATION = {"portrait": "vertical", "landscape": "horizontal", "square": "all"}
NAME, SITE = "Pixabay", "https://pixabay.com/"


def _key() -> str:
    key = cfg("PIXABAY_API_KEY")
    if not key:
        raise NotConfigured("Pixabay (ảnh cho website)", ["PIXABAY_API_KEY"])
    return key


def _check(r: httpx.Response, what: str):
    if r.status_code == 429:
        wait = r.headers.get("X-RateLimit-Reset")
        raise Transient("Pixabay: vượt giới hạn 100 yêu cầu/phút — chờ rồi thử lại", float(wait) if wait and wait.isdigit() else 60)
    if r.status_code in (400, 401, 403) and what == "search":
        raise NotConfigured("Pixabay", [f"khoá API hợp lệ (HTTP {r.status_code}: {r.text[:120]})"])
    if r.status_code >= 500:
        raise Transient(f"Pixabay {what}: HTTP {r.status_code}")
    if r.status_code >= 400:
        raise Permanent(f"Pixabay {what}: HTTP {r.status_code}")


def _photo(hit: dict) -> dict:
    """Normalised: {id, src, alt, photographer, photographer_url, url}."""
    user, uid = hit.get("user") or "", hit.get("user_id")
    return {"id": hit.get("id"), "src": hit.get("largeImageURL") or hit.get("webformatURL") or "",
            "alt": (hit.get("tags") or "").replace(",", ", ").replace("  ", " ").strip(),
            "photographer": user, "photographer_url": f"{SITE}users/{user}-{uid}/" if user and uid else "",
            "url": hit.get("pageURL") or ""}


def search(query: str, orientation: str, per_page: int = 30, page: int = 1) -> dict:
    """orientation: portrait | landscape | square. Returns {"photos": [normalised], "remaining": header or None}."""
    params = {"key": _key(), "q": query[:100], "image_type": "photo", "orientation": ORIENTATION[orientation],
              "safesearch": "true", "per_page": max(3, min(per_page, 200)), "page": page}
    try:
        with httpx.Client(timeout=30) as c:
            r = c.get(API, params=params)
    except httpx.TransportError as e:
        raise Transient(f"Pixabay search: lỗi mạng ({type(e).__name__})") from None
    _check(r, "search")
    hits = r.json().get("hits") or []
    return {"photos": [_photo(h) for h in hits if h.get("largeImageURL") or h.get("webformatURL")],
            "remaining": r.headers.get("X-RateLimit-Remaining")}


def download(url: str) -> bytes:
    """An image URL from a search result (Pixabay hosts only), saved on our side as the rules require."""
    if httpx.URL(url).host not in IMAGE_HOSTS:
        raise Permanent(f"Pixabay: địa chỉ ảnh không thuộc Pixabay ({httpx.URL(url).host})")
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as c:
            r = c.get(url)
    except httpx.TransportError as e:
        raise Transient(f"Pixabay ảnh: lỗi mạng ({type(e).__name__})") from None
    _check(r, "ảnh")
    if not r.headers.get("content-type", "").startswith("image/"):
        raise Permanent(f"Pixabay: không phải file ảnh ({r.headers.get('content-type')})")
    return r.content
