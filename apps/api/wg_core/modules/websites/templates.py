"""The 15 named templates recovered from the legacy WebsiteGenerator (names, palettes, hero layouts,
photo keywords) and the industry detection rules. Same data as apps/web/src/lib/templates.ts."""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    group: str
    primary: str
    accent: str
    hero: str
    photo_keywords: tuple
    industries: tuple


TEMPLATES = [
    Template("corporate-firm", "Corporate Firm", "Doanh nghiệp & Dịch vụ", "#2563eb", "#93c5fd", "split-left", ("office", "corporate", "business", "meeting"), ("consulting", "holding", "group", "partners", "freight", "logistic", "realty", "auto", "motor", "hvac", "plumb", "electric")),
    Template("hr-management", "HR Management", "Doanh nghiệp & Dịch vụ", "#0d9488", "#5eead4", "stacked-cards", ("people", "office", "teamwork", "handshake"), ("hr", "staffing", "recruit", "workforce")),
    Template("misbah-architecture", "Misbah Architecture Blocks", "Xây dựng & Kiến trúc", "#d97706", "#fcd34d", "image-banner", ("architecture", "building", "modern", "interior"), ("construction", "builder", "carpentry", "architecture", "roofing", "concrete")),
    Template("blockskit-digital", "Blockskit Digital Agency Firm", "Công nghệ", "#7c3aed", "#c4b5fd", "split-right", ("technology", "office", "startup", "design"), ("tech", "software", "digital", "data", "systems", "cloud")),
    Template("daily-soap-tv", "Daily SOAP TV", "Truyền thông", "#c026d3", "#f0abfc", "centered", ("studio", "media", "broadcasting", "camera"), ("media", "film", "tv", "broadcast", "production")),
    Template("dermatologist-clinic", "Dermatologist Clinic", "Y tế & Làm đẹp", "#e11d48", "#fda4af", "split-left", ("skincare", "dermatology", "spa", "beauty"), ("dermat", "skin", "salon", "spa", "beauty", "wellness", "clinic", "medic", "health", "pharm")),
    Template("fse-dental", "FSE Dental Clinic", "Y tế & Làm đẹp", "#0284c7", "#7dd3fc", "minimal", ("dental", "dentist", "smile", "teeth"), ("dental", "dds", "dentist", "orthodont")),
    Template("lawyer-legal", "Lawyer Legal Firm", "Pháp lý & Tài chính", "#1e3a8a", "#a5b4fc", "split-right", ("law", "courthouse", "justice", "books"), ("law", "legal", "attorney", "counsel")),
    Template("spike-insurance", "Spike Insurance", "Pháp lý & Tài chính", "#4f46e5", "#a5b4fc", "stacked-cards", ("family", "office", "security", "protection"), ("insurance", "finance", "capital", "invest")),
    Template("wens-academy", "WENS Academy", "Giáo dục", "#0891b2", "#67e8f9", "centered", ("education", "students", "classroom", "learning"), ("academy", "school", "education", "training", "tutor")),
    Template("online-library", "Online Library", "Giáo dục", "#ea580c", "#fdba74", "minimal", ("books", "library", "reading", "knowledge"), ("book", "library", "publish")),
    Template("expert-travel", "Expert Travel Agent", "Du lịch", "#0284c7", "#7dd3fc", "image-banner", ("travel", "beach", "destination", "vacation"), ("travel", "tour", "outfitter", "adventure", "lodge")),
    Template("herbal-shop", "Herbal Products Shop", "Thương mại", "#059669", "#6ee7b7", "split-left", ("herbs", "plants", "wellness", "nature"), ("herbal", "shop", "store", "trading", "coffee", "bakery", "roaster", "goods")),
    Template("waste-management", "Waste Management Firm", "Môi trường & Nông nghiệp", "#65a30d", "#bef264", "split-right", ("environment", "recycling", "green", "nature"), ("waste", "recycl", "environment", "mining", "oil", "gas", "clean")),
    Template("tree-plantation", "Tree Plantation", "Môi trường & Nông nghiệp", "#16a34a", "#86efac", "image-banner", ("forest", "trees", "nature", "green"), ("ranch", "farm", "cattle", "tree", "orchard", "vineyard", "livestock")),
]
BY_ID = {t.id: t for t in TEMPLATES}


def detect(name: str) -> tuple[Template, str | None]:
    """First template whose keyword starts a word of the company name; else Corporate Firm. Never random."""
    words = [w for w in re.split(r"[^a-z0-9]+", name.lower()) if w]
    for t in TEMPLATES:
        if t.id == "corporate-firm":
            continue
        for k in t.industries:
            if any(w.startswith(k) for w in words):
                return t, k
    corp = BY_ID["corporate-firm"]
    k = next((k for k in corp.industries if any(w.startswith(k) for w in words)), None)
    return corp, k


# Brazil: CNAE division (first 2 digits) → template. A PROPOSAL for the owner to review.
CNAE_DIVISION = {
    **{d: "tree-plantation" for d in range(1, 4)}, **{d: "waste-management" for d in range(5, 10)},
    **{d: "waste-management" for d in range(35, 40)}, **{d: "misbah-architecture" for d in range(41, 44)},
    **{d: "herbal-shop" for d in range(45, 48)}, **{d: "daily-soap-tv" for d in (58, 59, 60, 90, 91, 92, 93)},
    **{d: "blockskit-digital" for d in (61, 62, 63, 95)}, **{d: "spike-insurance" for d in (64, 65, 66)},
    69: "lawyer-legal", 78: "hr-management", 79: "expert-travel", 85: "wens-academy",
    **{d: "dermatologist-clinic" for d in (86, 87, 88, 96)},
}


def template_for_cnae(cnae: str) -> Template | None:
    m = re.match(r"(\d{2})\.(\d{2})-\d-(\d{2})", cnae or "")
    if not m:
        return None
    if cnae.startswith("86.30-5-04"):  # atividade odontológica
        return BY_ID["fse-dental"]
    tid = CNAE_DIVISION.get(int(m.group(1)))
    return BY_ID[tid] if tid else BY_ID["corporate-firm"]
