"""Photos for a generated website, from the Pexels API.

One search per orientation needed (at most 3 API requests per site, well under 200 / hour). Which photos a site
gets is decided by the domain (stable seed), so two companies on the same template do not get the same pictures
and a rebuild gets the same ones. The images are downloaded and shipped with the site as photo-<slot>.jpg.
"""
import hashlib
import random

from ...integrations import pexels
from .templates import BY_ID

# slot → which design value decides the orientation, and the Pexels `src` size used for it
SRC = {"portrait": "portrait", "landscape": "landscape", "square": "large"}


def slots(d: dict) -> dict[str, str]:
    """slot → orientation for the layout of this site (see brand_render.design)."""
    return {"hero": "portrait" if d["hero"] == "split" else "landscape", "about": "square", "band": "landscape",
            "why": "portrait", "faq": "portrait", "contact": "landscape", "about-page": "portrait"}


def query_for(template_id: str, rng: random.Random) -> str:
    kw = list(BY_ID[template_id].photo_keywords)
    first = kw[0]
    second = rng.choice(kw[1:]) if len(kw) > 1 else ""
    return f"{first} {second}".strip()


def choose(domain: str, template_id: str, d: dict) -> list[dict]:
    """[{slot, id, src, file, alt, photographer, photographer_url, url}] — the photos this site will use."""
    rng = random.Random(int(hashlib.sha256(f"photos|{domain.lower()}|{template_id}".encode()).hexdigest()[:12], 16))
    query = query_for(template_id, rng)
    need: dict[str, list[str]] = {}
    for slot, orient in slots(d).items():
        need.setdefault(orient, []).append(slot)
    out, used = [], set()
    for orient, slot_list in need.items():
        found = pexels.search(query, orient, per_page=30, page=rng.randint(1, 3))["photos"]
        if len(found) < len(slot_list):  # small result set → first page
            found = pexels.search(query, orient, per_page=30, page=1)["photos"]
        pool = [p for p in found if p.get("id") not in used and (p.get("src") or {}).get(SRC[orient])]
        rng.shuffle(pool)
        for slot, p in zip(slot_list, pool):
            used.add(p["id"])
            out.append({"slot": slot, "id": p["id"], "src": p["src"][SRC[orient]], "file": f"photo-{slot}.jpg",
                        "alt": p.get("alt") or "", "photographer": p.get("photographer") or "",
                        "photographer_url": p.get("photographer_url") or "", "url": p.get("url") or ""})
    return out


def credits(chosen: list[dict]) -> list[dict]:
    seen, out = set(), []
    for p in chosen:
        if p["photographer"] and p["photographer"] not in seen:
            seen.add(p["photographer"])
            out.append({"name": p["photographer"], "url": p["photographer_url"] or p["url"]})
    return out
