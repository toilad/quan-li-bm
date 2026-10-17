"""Photos for a generated website, from Pexels (used when its key is set) or Pixabay.

One search per orientation needed (at most 3 API requests per site). Which photos a site gets is decided by the
domain (stable seed), so two companies on the same template do not get the same pictures and a rebuild gets the
same ones. The images are downloaded and shipped with the site as photo-<slot>.jpg — the pages never hot-link.
"""
import hashlib
import random

from ...integrations import pexels, pixabay
from ...integrations.errors import NotConfigured
from ...runtime_config import get as cfg
from .templates import BY_ID

PROVIDERS = {"pexels": pexels, "pixabay": pixabay}
KEYS = {"pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY"}


def provider_name() -> str | None:
    """Pexels first when its key is set, otherwise Pixabay; None when neither is configured."""
    return next((name for name, key in KEYS.items() if cfg(key)), None)


def slots(d: dict) -> dict[str, str]:
    """slot → orientation for the layout of this site (see brand_render.design)."""
    return {"hero": "portrait" if d["hero"] == "split" else "landscape", "about": "square", "band": "landscape",
            "why": "portrait", "faq": "portrait", "contact": "landscape", "about-page": "portrait"}


def query_for(template_id: str, rng: random.Random) -> str:
    kw = list(BY_ID[template_id].photo_keywords)
    second = rng.choice(kw[1:]) if len(kw) > 1 else ""
    return f"{kw[0]} {second}".strip()


def choose(domain: str, template_id: str, d: dict) -> list[dict]:
    """[{slot, id, src, file, alt, photographer, photographer_url, url, provider}] — the photos this site will use."""
    name = provider_name()
    if not name:
        raise NotConfigured("Ảnh cho website", ["PEXELS_API_KEY hoặc PIXABAY_API_KEY"])
    api = PROVIDERS[name]
    rng = random.Random(int(hashlib.sha256(f"photos|{domain.lower()}|{template_id}".encode()).hexdigest()[:12], 16))
    query = query_for(template_id, rng)
    need: dict[str, list[str]] = {}
    for slot, orient in slots(d).items():
        need.setdefault(orient, []).append(slot)
    out, used = [], set()
    for orient, slot_list in need.items():
        found = api.search(query, orient, per_page=30, page=rng.randint(1, 3))["photos"]
        if len(found) < len(slot_list):  # small result set → first page
            found = api.search(query, orient, per_page=30, page=1)["photos"]
        pool = [p for p in found if p["id"] not in used and p["src"]]
        rng.shuffle(pool)
        for slot, p in zip(slot_list, pool):
            used.add(p["id"])
            out.append({**p, "slot": slot, "file": f"photo-{slot}.jpg", "provider": name})
    return out


def download(p: dict) -> bytes:
    return PROVIDERS[p.get("provider", "pixabay")].download(p["src"])


def credits(chosen: list[dict]) -> list[dict]:
    """[{name, url, source, source_url}] — photographers plus where the photos come from (both providers ask for it)."""
    seen, out = set(), []
    for p in chosen:
        api = PROVIDERS[p.get("provider", "pixabay")]
        if p["photographer"] and p["photographer"] not in seen:
            seen.add(p["photographer"])
            out.append({"name": p["photographer"], "url": p["photographer_url"] or p["url"], "source": api.NAME, "source_url": api.SITE})
    return out
