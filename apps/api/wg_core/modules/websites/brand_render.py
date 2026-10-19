"""Website renderer for the 15 templates in the "brand" style the owner chose (2026-10-17 reference): soft gradient hero
with a curved colour shape and a framed photo, floating fact cards, "who we are" block with a ringed photo, full-width
photo band with an overlapping card, gradient service cards, a contact band and a dark footer.

Every word on the page comes from the Sheet (company, phone, address), the owner-verified email, or the checked AI copy.
Not published, whatever the reference shows: follower / subscriber counts, star ratings, testimonials, skill
percentages, "verified by" badges, like / heart bubbles, a video button without a video, invented opening hours,
a map pin that is not the company's address. Without a verified email there is no email link and no form.

Each template has its own gradient, heading font and hero style; within a template the layout details (photo side,
shapes, section order, card style) are picked from the domain, so the same site always rebuilds the same way.
"""
import hashlib
import json
import random
from datetime import date
from html import escape
from urllib.parse import quote_plus

from .legacy import config_data as legacy_cfg
from .templates import BY_ID

HOURS_TEXT = "Please contact us for current business hours."
PAGES = ("index.html", "about.html", "faq.html", "contact.html", "privacy.html", "terms.html")

# template id → (gradient start, gradient end, soft background, heading font)
STYLE = {
    "corporate-firm": ("#2563eb", "#7c3aed", "#eef2ff", "Source Sans 3"),
    "hr-management": ("#0d9488", "#2563eb", "#ecfdf5", "Poppins"),
    "misbah-architecture": ("#d97706", "#c2410c", "#fffbeb", "Montserrat"),
    "blockskit-digital": ("#7c3aed", "#db2777", "#f5f3ff", "Space Grotesk"),
    "daily-soap-tv": ("#ff4d1c", "#e0457b", "#fff1ec", "Source Sans 3"),
    "dermatologist-clinic": ("#e11d48", "#f472b6", "#fff1f2", "DM Serif Display"),
    "fse-dental": ("#0284c7", "#06b6d4", "#f0f9ff", "Poppins"),
    "lawyer-legal": ("#1e3a8a", "#6d28d9", "#eef2ff", "Playfair Display"),
    "spike-insurance": ("#4f46e5", "#0ea5e9", "#eef2ff", "Poppins"),
    "wens-academy": ("#0891b2", "#4f46e5", "#ecfeff", "Nunito"),
    "online-library": ("#ea580c", "#dc2626", "#fff7ed", "Merriweather"),
    "expert-travel": ("#0284c7", "#14b8a6", "#f0fdfa", "Montserrat"),
    "herbal-shop": ("#059669", "#65a30d", "#ecfdf5", "Nunito"),
    "waste-management": ("#65a30d", "#0d9488", "#f7fee7", "Poppins"),
    "tree-plantation": ("#16a34a", "#0f766e", "#f0fdf4", "Montserrat"),
}
# Home sections between the hero and the contact band (the reference order first, then close variations).
SECTION_ORDERS = (
    ("who", "band", "why", "services", "faq"),
    ("who", "services", "band", "why", "faq"),
    ("services", "who", "band", "why", "faq"),
    ("who", "band", "services", "faq", "why"),
)
HERO_OF = {"split-left": "split", "split-right": "split", "stacked-cards": "split", "image-banner": "banner",
           "centered": "centered", "minimal": "centered"}

ICONS = {
    "phone": '<path d="M3 5a2 2 0 012-2h2.3a1 1 0 01.95.68l1.1 3.3a1 1 0 01-.5 1.2L7.2 9.3a11 11 0 005.5 5.5l1.1-1.65a1 1 0 011.2-.5l3.3 1.1a1 1 0 01.68.95V19a2 2 0 01-2 2h-1C9.7 21 3 14.3 3 6V5z"/>',
    "pin": '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0119 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
    "mail": '<path d="M3 7l9 6 9-6M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "briefcase": '<path d="M4 8h16v11H4zM9 8V5h6v3M4 13h16"/>',
    "spark": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6"/>',
    "shield": '<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/><path d="M9 12l2 2 4-4"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "layers": '<path d="M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "map": '<path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
}
SERVICE_ICONS = ("briefcase", "spark", "shield", "layers")


def icon(name: str, cls: str = "w-5 h-5") -> str:
    return (f'<svg class="{cls}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>')


def _rng(domain: str, template: str) -> random.Random:
    seed = int(hashlib.sha256(f"{domain.lower()}|{template}".encode()).hexdigest()[:12], 16)
    return random.Random(seed)


def design(company: dict, template: str) -> dict:
    """Template style + domain-seeded layout choices (stable for a given domain and template)."""
    t = BY_ID[template]
    c1, c2, soft, heading = STYLE[template]
    r = _rng(company["domain"], template)
    middle = list(r.choice(SECTION_ORDERS))
    return {
        "template": t, "c1": c1, "c2": c2, "soft": soft, "heading": heading,
        "hero": HERO_OF.get(t.hero, "split"),
        "photo_right": (t.hero != "split-left") if r.random() < 0.75 else (t.hero == "split-left"),
        "shape": r.choice(["blob", "arc", "slant"]),
        "frame": r.choice(["tilt", "arch", "round"]),
        "about_photo": r.choice(["circle", "arch"]),
        "cards": r.choice(["alternate", "gradient", "outline"]),
        "middle": middle,
        "keywords": legacy_cfg.BUSINESS_KEYWORDS[t.name],
        "seed": r.randint(1, 999999),
    }


SLOT_ICONS = {"hero": "briefcase", "about": "shield", "band": "layers", "why": "spark", "faq": "check", "contact": "phone",
              "about-page": "shield"}


def media(d: dict, w: int, h: int, slot: str, cls: str, alt: str = "") -> str:
    """A photo only when one was supplied for this slot (files shipped with the site, never a hot-linked random
    image service — loremflickr, used by the legacy app, returns HTTP 500). Otherwise a gradient panel with an icon,
    so a page never shows a broken image."""
    ph = (d.get("photos") or {}).get(slot)
    if ph:
        src, alt = (ph, alt) if isinstance(ph, str) else (ph["src"], ph.get("alt") or alt)
        return f'<img src="{escape(src)}" alt="{escape(alt)}" width="{w}" height="{h}" class="{cls}" loading="lazy">'
    art_cls = cls.replace("object-cover", "").strip()
    background = "absolute" in art_cls  # behind text: no icon, the text is the subject
    if not background:
        art_cls += " relative"
    mark = "" if background else (f'<span class="absolute inset-0 grid place-items-center text-white/85">'
                                  f'{icon(SLOT_ICONS.get(slot, "spark"), "w-1/4 h-1/4 max-w-[7rem] max-h-[7rem]")}</span>')
    return (f'<div class="{art_cls} grad overflow-hidden" role="presentation">'
            '<div class="dots-w absolute inset-0"></div>'
            '<div class="absolute -right-10 -bottom-10 w-2/3 aspect-square rounded-full bg-white/10"></div>'
            '<div class="absolute -left-8 -top-8 w-1/3 aspect-square rounded-full bg-white/10"></div>'
            f'{mark}</div>')


def _tel(phone: str) -> str:
    first = phone.split("/")[0]
    digits = "".join(ch for ch in first if ch.isdigit() or ch == "+")
    return digits


def _city(address: str) -> str:
    parts = [p.strip() for p in address.split(",") if p.strip()]
    return ", ".join(parts[-2:]) if len(parts) >= 2 else (parts[0] if parts else "")


def maps_link(address: str) -> str:
    """Google Maps URLs (documented, no key): opens a search for the printed address — never a guessed pin."""
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(address)}"


# ───────── shared page parts ─────────

def head(c: dict, d: dict, title: str, desc: str, page: str) -> str:
    data = {"@context": "https://schema.org", "@type": "LocalBusiness", "name": c["company"], "url": f"https://{c['domain']}/",
            "description": desc}
    if c.get("phone"):
        data["telephone"] = c["phone"]
    if c.get("address"):
        data["address"] = {"@type": "PostalAddress", "streetAddress": c["address"]}
    if c.get("email"):
        data["email"] = c["email"]
    if c.get("reg_id"):
        data["taxID"] = c["reg_id"]
    fonts = "family=Barlow:wght@400;500;600;700&family=" + d["heading"].replace(" ", "+") + ":wght@600;700;800"
    if d["heading"] in ("DM Serif Display",):
        fonts = "family=Barlow:wght@400;500;600;700&family=DM+Serif+Display"
    canonical = f"https://{c['domain']}/" + ("" if page == "index.html" else page)
    ld = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"UTF-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        f"<title>{escape(title)}</title>\n<meta name=\"description\" content=\"{escape(desc)}\">\n"
        f"<link rel=\"canonical\" href=\"{escape(canonical)}\">\n"
        f"<meta property=\"og:title\" content=\"{escape(title)}\">\n<meta property=\"og:description\" content=\"{escape(desc)}\">\n"
        f"<meta property=\"og:type\" content=\"website\">\n<meta property=\"og:url\" content=\"{escape(canonical)}\">\n"
        f"<script type=\"application/ld+json\">{ld}</script>\n"
        "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\"><link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>\n"
        f"<link href=\"https://fonts.googleapis.com/css2?{fonts}&display=swap\" rel=\"stylesheet\">\n"
        "<script src=\"https://cdn.tailwindcss.com\"></script>\n"
        "<script>tailwind.config={theme:{extend:{colors:{brand:'" + d["c1"] + "',brand2:'" + d["c2"] + "',soft:'" + d["soft"] + "'},"
        "fontFamily:{sans:['Barlow','system-ui','sans-serif'],heading:['" + d["heading"] + "','Barlow','sans-serif']}}}}</script>\n"
        "<style>\n"
        f".grad{{background-image:linear-gradient(135deg,{d['c1']},{d['c2']})}}\n"
        f".grad-v{{background-image:linear-gradient(180deg,{d['c1']},{d['c2']})}}\n"
        f".hero-bg{{background-image:linear-gradient(180deg,{d['soft']},#ffffff)}}\n"
        f".dots{{background-image:radial-gradient({d['c1']}33 2.2px,transparent 2.4px);background-size:22px 22px}}\n"
        ".dots-w{background-image:radial-gradient(rgba(255,255,255,.28) 2px,transparent 2.3px);background-size:24px 24px}\n"
        ".float-card{box-shadow:0 18px 40px -18px rgba(15,23,42,.35)}\n"
        "details>summary{list-style:none}details>summary::-webkit-details-marker{display:none}\n"
        "details[open] .plus{transform:rotate(45deg)}\n"
        "</style>\n</head>\n"
    )


def reg_label(reg_id: str) -> str:
    """Brazilian CNPJ (00.000.000/0000-00) or the US state filing number the Sheet calls control id (column J)."""
    import re

    return "CNPJ" if re.fullmatch(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", reg_id.strip()) else "Control ID"


def topbar(c: dict) -> str:
    """Company facts at the very top of every page, straight from the Sheet: legal name, full address, phone and the
    registration number (column J). Nothing is shown that the Sheet does not have."""
    items = [f'<span class="font-semibold text-white">{escape(c["company"])}</span>']
    if c.get("reg_id"):
        items.append(f'<span>{reg_label(c["reg_id"])}: <span class="font-semibold text-white">{escape(c["reg_id"])}</span></span>')
    if c.get("address"):
        items.append(f'<a href="{maps_link(c["address"])}" target="_blank" rel="noopener" class="inline-flex items-center gap-1.5 hover:text-white">'
                     f'{icon("pin", "w-4 h-4")}{escape(c["address"])}</a>')
    if c.get("phone"):
        items.append(f'<a href="tel:{_tel(c["phone"])}" class="inline-flex items-center gap-1.5 hover:text-white">'
                     f'{icon("phone", "w-4 h-4")}{escape(c["phone"])}</a>')
    return ('  <div class="bg-slate-900 text-slate-300 text-[13px]">\n'
            '    <div class="max-w-6xl mx-auto px-6 py-2.5 flex flex-wrap items-center gap-x-6 gap-y-1.5">'
            + "".join(items) + '</div>\n  </div>\n')


def header(c: dict, d: dict, active: str) -> str:
    links = [("index.html", "Home"), ("about.html", "About Us"), ("index.html#services", "Our Services"), ("faq.html", "FAQ"),
             ("contact.html", "Contact Us")]
    nav = "".join(
        f'<a href="{h}" class="text-[13px] font-semibold uppercase tracking-wide {"text-brand" if h == active else "text-slate-700 hover:text-brand"} transition">{t}</a>'
        for h, t in links)
    mobile = "".join(f'<a href="{h}" class="block py-2 font-semibold text-slate-700">{t}</a>' for h, t in links)
    call = (f'<a href="tel:{_tel(c["phone"])}" class="hidden lg:inline-flex items-center gap-2 grad text-white text-sm font-semibold '
            f'px-5 py-2.5 rounded-md shadow-lg">{icon("phone", "w-4 h-4")}{escape(c["phone"].split("/")[0].strip())}</a>') if c.get("phone") else ""
    return (
        '<header class="sticky top-0 z-30 bg-white/90 backdrop-blur border-b border-slate-100">\n'
        + topbar(c) +
        '  <div class="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between gap-6">\n'
        f'    <a href="index.html" class="font-heading text-xl font-extrabold text-slate-900 leading-tight max-w-[16rem]">{escape(c["company"])}</a>\n'
        f'    <nav class="hidden md:flex items-center gap-8">{nav}</nav>\n'
        f'    {call}\n'
        '    <button class="md:hidden text-slate-800" aria-label="Menu" onclick="document.getElementById(\'m\').classList.toggle(\'hidden\')">'
        f'{icon("menu", "w-7 h-7")}</button>\n'
        '  </div>\n'
        f'  <div id="m" class="hidden md:hidden mx-6 rounded-xl bg-white p-4 shadow-xl">{mobile}</div>\n'
        '</header>\n'
    )


def fact_cards(c: dict, content: dict) -> list[tuple[str, str, str]]:
    """Small floating cards: only real facts (never likes, hearts or counters)."""
    out = []
    if c.get("phone"):
        out.append(("phone", "Call us", c["phone"].split("/")[0].strip()))
    if c.get("address"):
        out.append(("pin", "Find us", _city(c["address"])))
    if content.get("services"):
        out.append(("briefcase", "What we do", content["services"][0]["title"]))
    return out


def _float(card: tuple[str, str, str], pos: str) -> str:
    ic, label, value = card
    return (f'<div class="float-card absolute {pos} hidden sm:flex items-center gap-3 rounded-2xl bg-white px-4 py-3 max-w-[15rem]">'
            f'<span class="grid place-items-center w-10 h-10 rounded-full grad text-white shrink-0">{icon(ic, "w-5 h-5")}</span>'
            f'<span class="min-w-0"><span class="block text-[11px] uppercase tracking-wider text-slate-500">{escape(label)}</span>'
            f'<span class="block text-sm font-semibold text-slate-900 truncate">{escape(value)}</span></span></div>')


def _buttons(c: dict, content: dict, light: bool = False) -> str:
    primary = (f'<a href="contact.html" class="inline-flex items-center gap-2 {"bg-white text-brand" if light else "grad text-white"} '
               f'font-bold uppercase tracking-wide text-sm px-7 py-3.5 rounded-md shadow-lg hover:brightness-110 transition">'
               f'{escape(content["primary_cta"])}{icon("arrow", "w-4 h-4")}</a>')
    second = ""
    if c.get("phone"):
        second = (f'<a href="tel:{_tel(c["phone"])}" class="inline-flex items-center gap-2 font-semibold text-sm px-5 py-3.5 rounded-md '
                  f'{"text-white border border-white/60 hover:bg-white/10" if light else "text-slate-800 hover:text-brand"} transition">'
                  f'{icon("phone", "w-4 h-4")}{escape(c["phone"].split("/")[0].strip())}</a>')
    return f'<div class="flex flex-wrap items-center gap-3">{primary}{second}</div>'


def _shape(d: dict) -> str:
    side = "right-0" if d["photo_right"] else "left-0"
    if d["shape"] == "blob":
        radius = "rounded-bl-[55%] rounded-tl-[40%]" if d["photo_right"] else "rounded-br-[55%] rounded-tr-[40%]"
        return f'<div class="absolute top-0 {side} h-[88%] w-[46%] grad {radius} opacity-95"></div>'
    if d["shape"] == "arc":
        pos = "-right-40" if d["photo_right"] else "-left-40"
        return f'<div class="absolute top-16 {pos} w-[44rem] h-[44rem] rounded-full grad opacity-90"></div>'
    clip = "polygon(25% 0,100% 0,100% 100%,0 100%)" if d["photo_right"] else "polygon(0 0,75% 0,100% 100%,0 100%)"
    return f'<div class="absolute top-0 {side} h-full w-[48%] grad" style="clip-path:{clip}"></div>'


def _frame(d: dict, alt: str) -> str:
    cls = {"tilt": "rounded-[3rem] -rotate-3", "arch": "rounded-t-full rounded-b-[2.5rem]", "round": "rounded-[2.5rem]"}[d["frame"]]
    inner = {"tilt": "rotate-3 scale-110", "arch": "", "round": ""}[d["frame"]]
    return (f'<div class="relative overflow-hidden {cls} bg-white shadow-2xl aspect-[4/5] w-full max-w-md mx-auto">'
            f'{media(d, 900, 1100, "hero", f"w-full h-full object-cover {inner}", alt)}</div>')


def hero(c: dict, d: dict, content: dict) -> str:
    cards = fact_cards(c, content)
    eyebrow = f'<span class="inline-block text-brand font-semibold uppercase tracking-[.2em] text-sm mb-4">{escape(c["company"])}</span>'
    title = f'<h1 class="font-heading text-4xl md:text-6xl font-extrabold text-slate-900 leading-[1.05] mb-6">{escape(content["tagline"])}</h1>'
    sub = f'<p class="text-lg text-slate-600 leading-relaxed mb-8 max-w-xl">{escape(content["hero_subtitle"])}</p>'
    if d["hero"] == "banner":
        return (
            '<section class="relative min-h-[92vh] flex items-center overflow-hidden">\n'
            f'  {media(d, 1920, 1100, "hero", "absolute inset-0 w-full h-full object-cover")}\n'
            '  <div class="absolute inset-0 grad opacity-80"></div>\n'
            '  <div class="relative max-w-6xl mx-auto px-6 pt-20 pb-24 w-full">\n'
            '    <div class="max-w-2xl text-white">\n'
            f'      <span class="inline-block font-semibold uppercase tracking-[.2em] text-sm mb-4 text-white/90">{escape(c["company"])}</span>\n'
            f'      <h1 class="font-heading text-4xl md:text-6xl font-extrabold leading-[1.05] mb-6">{escape(content["tagline"])}</h1>\n'
            f'      <p class="text-lg text-white/90 leading-relaxed mb-8">{escape(content["hero_subtitle"])}</p>\n'
            f'      {_buttons(c, content, light=True)}\n'
            '    </div>\n'
            '    <div class="mt-12 flex flex-wrap gap-4">' + "".join(
                f'<div class="float-card flex items-center gap-3 rounded-2xl bg-white px-4 py-3">'
                f'<span class="grid place-items-center w-10 h-10 rounded-full grad text-white">{icon(i, "w-5 h-5")}</span>'
                f'<span><span class="block text-[11px] uppercase tracking-wider text-slate-500">{escape(lab)}</span>'
                f'<span class="block text-sm font-semibold text-slate-900">{escape(v)}</span></span></div>' for i, lab, v in cards) + '</div>\n'
            '  </div>\n</section>\n')
    if d["hero"] == "centered":
        return (
            '<section class="relative hero-bg overflow-hidden pt-16 pb-20">\n'
            '  <div class="dots absolute top-28 left-6 w-40 h-40 opacity-70"></div><div class="dots absolute bottom-24 right-6 w-40 h-40 opacity-70"></div>\n'
            '  <div class="relative max-w-4xl mx-auto px-6 text-center">\n'
            f'    {eyebrow}\n    {title}\n'
            f'    <p class="text-lg text-slate-600 leading-relaxed mb-8 max-w-2xl mx-auto">{escape(content["hero_subtitle"])}</p>\n'
            f'    <div class="flex justify-center">{_buttons(c, content)}</div>\n'
            '  </div>\n'
            '  <div class="relative max-w-5xl mx-auto px-6 mt-14">\n'
            f'    <div class="rounded-[2.5rem] overflow-hidden shadow-2xl aspect-[16/7] grad p-2">{media(d, 1600, 700, "hero", "w-full h-full object-cover rounded-[2.2rem]")}</div>\n'
            + (_float(cards[0], "-top-6 left-10") if cards else "") + (_float(cards[-1], "-bottom-6 right-10") if len(cards) > 1 else "") +
            '\n  </div>\n</section>\n')
    text_order = "md:order-1" if d["photo_right"] else "md:order-2"
    photo_order = "md:order-2" if d["photo_right"] else "md:order-1"
    floats = ""
    for card, pos in zip(cards, ("top-10 -left-4", "top-1/2 -right-6", "bottom-6 left-6")):
        floats += _float(card, pos)
    return (
        '<section class="relative hero-bg overflow-hidden">\n'
        f'  {_shape(d)}\n'
        '  <div class="relative max-w-6xl mx-auto px-6 pt-16 pb-24 grid md:grid-cols-2 gap-14 items-center">\n'
        f'    <div class="relative {text_order}"><div class="dots absolute -top-8 -left-10 w-36 h-48 opacity-70"></div>\n'
        f'      <div class="relative">{eyebrow}{title}{sub}{_buttons(c, content)}</div></div>\n'
        f'    <div class="relative {photo_order}">{_frame(d, c["company"])}{floats}</div>\n'
        '  </div>\n</section>\n')


# ───────── home sections ─────────

def sec_who(c: dict, d: dict, content: dict) -> str:
    items = [s["title"] for s in content.get("services", [])] + [w["title"] for w in content.get("why_choose_us", [])]
    checks = "".join(f'<li class="flex items-start gap-2 text-slate-700">{icon("check", "w-5 h-5 text-brand shrink-0 mt-0.5")}'
                     f'<span>{escape(t)}</span></li>' for t in items[:6])
    shape = "rounded-full" if d["about_photo"] == "circle" else "rounded-t-full rounded-b-3xl"
    return (
        '<section class="py-24 relative overflow-hidden">\n'
        '  <div class="max-w-6xl mx-auto px-6 grid md:grid-cols-2 gap-16 items-center">\n'
        '    <div class="relative max-w-sm mx-auto w-full">\n'
        f'      <div class="absolute -inset-4 {shape} border-2 border-brand/60"></div>\n'
        f'      <div class="relative {shape} overflow-hidden aspect-square shadow-xl">{media(d, 800, 800, "about", "w-full h-full object-cover")}</div>\n'
        '    </div>\n'
        '    <div>\n'
        '      <span class="text-brand font-medium uppercase tracking-[.15em] text-lg">Who we are</span>\n'
        f'      <h2 class="font-heading text-4xl md:text-5xl font-extrabold text-slate-900 leading-tight mt-3 mb-6">{escape(c["company"])}</h2>\n'
        f'      <p class="text-slate-600 leading-relaxed mb-6">{escape(content["about_short"])}</p>\n'
        f'      <ul class="grid sm:grid-cols-2 gap-x-6 gap-y-3 mb-8">{checks}</ul>\n'
        '      <a href="about.html" class="inline-flex items-center gap-2 grad text-white font-bold uppercase tracking-wide text-sm px-7 py-3.5 rounded-md shadow-lg">'
        f'Discover more{icon("arrow", "w-4 h-4")}</a>\n'
        '    </div>\n  </div>\n</section>\n')


def info_strip(c: dict, content: dict) -> str:
    cells = []
    if c.get("phone"):
        cells.append(("phone", "Phone", f'<a href="tel:{_tel(c["phone"])}" class="hover:text-brand">{escape(c["phone"])}</a>'))
    if c.get("address"):
        cells.append(("pin", "Address", f'<a href="{maps_link(c["address"])}" target="_blank" rel="noopener" class="hover:text-brand">{escape(c["address"])}</a>'))
    cells.append(("briefcase", "Services", escape(", ".join(s["title"] for s in content.get("services", [])[:3]))))
    cells.append(("clock", "Hours", escape(HOURS_TEXT)))
    cols = {2: "sm:grid-cols-2", 3: "sm:grid-cols-3", 4: "sm:grid-cols-2 lg:grid-cols-4"}[len(cells)]
    return (f'<div class="grid {cols} divide-y sm:divide-y-0 sm:divide-x divide-slate-200 bg-white rounded-xl shadow-2xl">' + "".join(
        f'<div class="p-6 text-center"><span class="inline-grid place-items-center w-12 h-12 rounded-full grad text-white mb-3">{icon(i, "w-6 h-6")}</span>'
        f'<div class="font-heading text-lg font-bold text-slate-900">{lab}</div><div class="text-sm text-slate-600 mt-1 break-words">{v}</div></div>'
        for i, lab, v in cells) + "</div>")


def sec_band(c: dict, d: dict, content: dict) -> str:
    return (
        '<section class="relative mt-10 mb-20">\n'
        '  <div class="relative h-[30rem] overflow-hidden">\n'
        f'    {media(d, 1920, 900, "band", "absolute inset-0 w-full h-full object-cover")}\n'
        '    <div class="absolute inset-0 grad opacity-75"></div>\n'
        '    <div class="relative max-w-4xl mx-auto px-6 h-full flex flex-col items-center justify-center text-center text-white pb-16">\n'
        '      <h2 class="font-heading text-4xl md:text-5xl font-extrabold mb-5">How we can help</h2>\n'
        f'      <p class="text-white/90 leading-relaxed max-w-3xl">{escape(content["intro_paragraph"])}</p>\n'
        '    </div>\n  </div>\n'
        f'  <div class="relative max-w-5xl mx-auto px-6 -mt-24">{info_strip(c, content)}</div>\n'
        '</section>\n')


def sec_services(c: dict, d: dict, content: dict) -> str:
    cards = ""
    for k, s in enumerate(content.get("services", [])):
        style = d["cards"]
        hot = style == "gradient" or (style == "alternate" and k % 2 == 0)
        lift = "md:mt-16" if style == "alternate" and k % 2 == 1 else ""
        box = "grad text-white" if hot else "bg-white text-slate-900 border border-slate-100"
        ring = "bg-white/25 text-white" if hot else "grad text-white"
        body = "text-white/90" if hot else "text-slate-600"
        cards += (f'<div class="{box} {lift} rounded-xl shadow-xl p-8 text-center">'
                  f'<span class="inline-grid place-items-center w-16 h-16 rounded-full {ring} mb-5">{icon(SERVICE_ICONS[k % 4], "w-7 h-7")}</span>'
                  f'<h3 class="font-heading text-2xl font-bold mb-3">{escape(s["title"])}</h3>'
                  f'<p class="{body} leading-relaxed">{escape(s["description"])}</p></div>')
    return (
        '<section id="services" class="relative py-24 overflow-hidden">\n'
        '  <div class="absolute left-1/2 top-10 -translate-x-1/2 w-[34rem] h-[34rem] rounded-full bg-soft"></div>\n'
        '  <div class="relative max-w-6xl mx-auto px-6">\n'
        '    <div class="text-center mb-14"><span class="text-brand font-medium uppercase tracking-[.15em] text-lg">What we do</span>\n'
        f'      <h2 class="font-heading text-4xl md:text-5xl font-extrabold text-slate-900 mt-3">Our Services</h2></div>\n'
        f'    <div class="grid md:grid-cols-3 gap-8 items-start">{cards}</div>\n'
        '  </div>\n</section>\n')


def sec_why(c: dict, d: dict, content: dict) -> str:
    items = "".join(f'<li class="flex items-start gap-3"><span class="grid place-items-center w-8 h-8 rounded-full bg-white/25 shrink-0">'
                    f'{icon("check", "w-4 h-4")}</span><span><span class="block font-heading text-lg font-bold">{escape(w["title"])}</span>'
                    f'<span class="block text-white/85 text-sm leading-relaxed">{escape(w["description"])}</span></span></li>'
                    for w in content.get("why_choose_us", []))
    text_first = "md:order-1" if d["photo_right"] else "md:order-2"
    media_side = "md:order-2" if d["photo_right"] else "md:order-1"
    return (
        '<section class="py-24">\n'
        '  <div class="max-w-6xl mx-auto px-6 grid md:grid-cols-2 gap-14 items-center">\n'
        f'    <div class="relative {text_first}"><div class="dots absolute -left-6 top-24 w-32 h-56 opacity-70"></div><div class="relative">\n'
        '      <span class="text-brand font-medium uppercase tracking-[.15em] text-lg">Why choose us</span>\n'
        f'      <h2 class="font-heading text-4xl md:text-5xl font-extrabold text-slate-900 leading-tight mt-3 mb-6">Why work with {escape(c["company"])}</h2>\n'
        f'      <p class="text-slate-600 leading-relaxed mb-8">{escape(content["about_full"].split(chr(10) * 2)[0].strip())}</p>\n'
        f'      {_buttons(c, content)}\n'
        '    </div></div>\n'
        f'    <div class="relative {media_side} grid grid-cols-5 items-center">\n'
        f'      <div class="col-span-3 col-start-1 row-start-1 rounded-xl overflow-hidden shadow-xl aspect-[3/4]">{media(d, 700, 900, "why", "w-full h-full object-cover")}</div>\n'
        f'      <div class="col-span-3 col-start-3 row-start-1 grad-v text-white rounded-xl shadow-2xl p-8 mt-24 relative"><ul class="space-y-5">{items}</ul></div>\n'
        '    </div>\n  </div>\n</section>\n')


def faq_items(content: dict, limit: int | None = None) -> str:
    out = ""
    for f in content.get("faqs", [])[:limit]:
        out += ('<details class="group rounded-xl bg-white border border-slate-200 shadow-sm">'
                f'<summary class="flex items-center justify-between gap-4 cursor-pointer p-5 font-heading text-lg font-bold text-slate-900">{escape(f["q"])}'
                '<span class="plus grid place-items-center w-8 h-8 rounded-full grad text-white text-xl leading-none transition shrink-0">+</span></summary>'
                f'<p class="px-5 pb-5 text-slate-600 leading-relaxed">{escape(f["a"])}</p></details>')
    return out


def sec_faq(c: dict, d: dict, content: dict) -> str:
    return (
        '<section class="py-24 overflow-hidden">\n'
        '  <div class="max-w-6xl mx-auto px-6 grid md:grid-cols-2 gap-14 items-center">\n'
        '    <div>\n'
        '      <span class="text-brand font-medium uppercase tracking-[.15em] text-lg">FAQ</span>\n'
        '      <h2 class="font-heading text-4xl md:text-5xl font-extrabold text-slate-900 leading-tight mt-3 mb-8">Questions and answers</h2>\n'
        f'      <div class="space-y-3">{faq_items(content, 3)}</div>\n'
        '      <a href="faq.html" class="inline-flex items-center gap-2 mt-6 font-semibold text-brand">All questions'
        f'{icon("arrow", "w-4 h-4")}</a>\n'
        '    </div>\n'
        '    <div class="relative max-w-md mx-auto w-full">\n'
        '      <div class="absolute inset-0 rounded-full grad opacity-80 scale-110"></div>\n'
        f'      <div class="relative rounded-t-full rounded-b-[3rem] overflow-hidden aspect-[4/5] shadow-2xl border-8 border-white">{media(d, 800, 1000, "faq", "w-full h-full object-cover")}</div>\n'
        '    </div>\n  </div>\n</section>\n')


def contact_form(c: dict, light: bool) -> str:
    """Only with an owner-verified email (static site: a mailto form, as before). Otherwise no form at all."""
    if not c.get("email"):
        return ""
    field = ("w-full rounded-md px-4 py-3 bg-transparent border border-white/80 text-white placeholder-white/80 focus:outline-none focus:border-white"
             if light else "w-full rounded-md px-4 py-3 border border-slate-300 focus:outline-none focus:border-brand")
    btn = "bg-white text-brand" if light else "grad text-white"
    return (
        f'<form action="mailto:{escape(c["email"])}" method="post" enctype="text/plain" class="space-y-4 max-w-md">'
        f'<input name="name" required placeholder="Full Name" class="{field}">'
        f'<input name="email" type="email" required placeholder="Email" class="{field}">'
        f'<textarea name="message" rows="4" required placeholder="Message" class="{field}"></textarea>'
        f'<button type="submit" class="{btn} font-bold uppercase tracking-wide text-sm px-8 py-3.5 rounded-md shadow-lg">Send Message</button></form>')


def contact_band(c: dict, d: dict, content: dict) -> str:
    rows = ""
    if c.get("phone"):
        rows += (f'<a href="tel:{_tel(c["phone"])}" class="flex items-center gap-3 text-white/95 hover:text-white">'
                 f'{icon("phone", "w-5 h-5")}<span>{escape(c["phone"])}</span></a>')
    if c.get("address"):
        rows += (f'<a href="{maps_link(c["address"])}" target="_blank" rel="noopener" class="flex items-center gap-3 text-white/95 hover:text-white">'
                 f'{icon("pin", "w-5 h-5")}<span>{escape(c["address"])}</span></a>')
    if c.get("email"):
        rows += (f'<a href="mailto:{escape(c["email"])}" class="flex items-center gap-3 text-white/95 hover:text-white">'
                 f'{icon("mail", "w-5 h-5")}<span>{escape(c["email"])}</span></a>')
    return (
        '<section class="relative grad overflow-hidden">\n'
        '  <div class="absolute -bottom-40 right-0 w-[36rem] h-[36rem] rounded-full border-[3rem] border-white/10"></div>\n'
        '  <div class="absolute -bottom-20 right-24 w-[22rem] h-[22rem] rounded-full border-[2rem] border-white/10"></div>\n'
        '  <div class="relative max-w-6xl mx-auto px-6 py-20 grid md:grid-cols-2 gap-12 items-center">\n'
        '    <div class="text-white">\n'
        '      <h2 class="font-heading text-4xl md:text-5xl font-extrabold mb-5">Get in touch</h2>\n'
        f'      <p class="text-white/90 leading-relaxed mb-8">{escape(content["contact_intro"])}</p>\n'
        f'      <div class="space-y-3 mb-8">{rows}</div>\n'
        f'      {contact_form(c, light=True)}\n'
        '    </div>\n'
        f'    <div class="hidden md:block"><div class="rounded-[2.5rem] overflow-hidden shadow-2xl aspect-[4/3] border-8 border-white/30">'
        f'{media(d, 900, 700, "contact", "w-full h-full object-cover")}</div></div>\n'
        '  </div>\n</section>\n')


def photo_credit(d: dict) -> str:
    """Show where the photos come from and credit the photographers (asked by both Pexels and Pixabay)."""
    if not d.get("credits"):
        return ""
    names = ", ".join(f'<a href="{escape(x["url"])}" target="_blank" rel="noopener" class="hover:text-white underline">{escape(x["name"])}</a>'
                      for x in d["credits"])
    source, source_url = d["credits"][0].get("source", "Pixabay"), d["credits"][0].get("source_url", "https://pixabay.com/")
    return (f'<div>Photos by {names} on '
            f'<a href="{escape(source_url)}" target="_blank" rel="noopener" class="hover:text-white underline">{escape(source)}</a></div>')


def footer(c: dict, d: dict, content: dict) -> str:
    lines = ""
    if c.get("address"):
        lines += (f'<li class="flex items-start gap-2">{icon("pin", "w-4 h-4 mt-1 shrink-0")}'
                  f'<a href="{maps_link(c["address"])}" target="_blank" rel="noopener" class="hover:text-white">{escape(c["address"])}</a></li>')
    if c.get("phone"):
        lines += f'<li class="flex items-center gap-2">{icon("phone", "w-4 h-4")}<a href="tel:{_tel(c["phone"])}" class="hover:text-white">{escape(c["phone"])}</a></li>'
    if c.get("email"):
        lines += f'<li class="flex items-center gap-2">{icon("mail", "w-4 h-4")}<a href="mailto:{escape(c["email"])}" class="hover:text-white">{escape(c["email"])}</a></li>'
    find = (f'<a href="{maps_link(c["address"])}" target="_blank" rel="noopener" class="inline-flex items-center gap-2 mt-4 rounded-md border border-white/30 px-4 py-2 text-sm text-white hover:bg-white/10">'
            f'{icon("map", "w-4 h-4")}Open in Google Maps</a>') if c.get("address") else ""
    links = "".join(f'<li><a href="{h}" class="hover:text-white">{t}</a></li>' for h, t in
                    (("index.html", "Home"), ("about.html", "About Us"), ("faq.html", "FAQ"), ("contact.html", "Contact Us"),
                     ("privacy.html", "Privacy Policy"), ("terms.html", "Terms of Service")))
    return (
        '<footer class="bg-black text-slate-400">\n'
        '  <div class="max-w-6xl mx-auto px-6 py-16 grid md:grid-cols-3 gap-12">\n'
        f'    <div><div class="font-heading text-2xl font-extrabold text-white mb-3">{escape(c["company"])}</div>'
        f'<p class="text-sm leading-relaxed">{escape(content["footer_blurb"])}</p></div>\n'
        f'    <div><h4 class="font-heading text-lg font-bold text-white mb-4">Contact</h4><ul class="space-y-3 text-sm">{lines}</ul>{find}</div>\n'
        f'    <div><h4 class="font-heading text-lg font-bold text-white mb-4">Quick Links</h4><ul class="space-y-2 text-sm">{links}</ul></div>\n'
        '  </div>\n'
        f'  <div class="border-t border-white/10 py-6 text-center text-xs space-y-1"><div>&copy; {date.today().year} {escape(c["company"])}. All rights reserved.</div>{photo_credit(d)}</div>\n'
        '</footer>\n</body>\n</html>\n')


def page_hero(c: dict, d: dict, eyebrow: str, title: str, text: str = "") -> str:
    return (
        '<section class="relative hero-bg overflow-hidden pt-16 pb-16">\n'
        '  <div class="absolute -top-24 -right-24 w-96 h-96 rounded-full grad opacity-90"></div>\n'
        '  <div class="dots absolute bottom-6 left-6 w-40 h-32 opacity-70"></div>\n'
        '  <div class="relative max-w-6xl mx-auto px-6">\n'
        f'    <span class="text-brand font-medium uppercase tracking-[.15em]">{escape(eyebrow)}</span>\n'
        f'    <h1 class="font-heading text-4xl md:text-6xl font-extrabold text-slate-900 mt-3 mb-4 max-w-3xl">{escape(title)}</h1>\n'
        + (f'    <p class="text-lg text-slate-600 max-w-2xl leading-relaxed">{escape(text)}</p>\n' if text else "") +
        '  </div>\n</section>\n')


# ───────── pages ─────────

def page_home(c: dict, d: dict, content: dict) -> str:
    sections = {"who": sec_who, "band": sec_band, "services": sec_services, "why": sec_why, "faq": sec_faq}
    body = "".join(sections[k](c, d, content) for k in d["middle"])
    return (head(c, d, c["company"] + " — " + content["tagline"], content["meta_description_home"], "index.html")
            + '<body class="font-sans text-slate-800 antialiased bg-white">\n' + header(c, d, "index.html")
            + "<main>\n" + hero(c, d, content) + body + contact_band(c, d, content) + "</main>\n" + footer(c, d, content))


def page_about(c: dict, d: dict, content: dict) -> str:
    paras = "".join(f'<p class="text-slate-600 leading-relaxed mb-5">{escape(p.strip())}</p>' for p in content["about_full"].split("\n\n") if p.strip())
    return (head(c, d, f'About - {c["company"]}', content["meta_description_about"], "about.html")
            + '<body class="font-sans text-slate-800 antialiased bg-white">\n' + header(c, d, "about.html") + "<main>\n"
            + page_hero(c, d, "About us", c["company"], content["about_short"])
            + '<section class="py-20"><div class="max-w-6xl mx-auto px-6 grid md:grid-cols-2 gap-14 items-start">'
            + f'<div>{paras}</div>'
            + f'<div class="relative"><div class="absolute -inset-4 rounded-[2.5rem] border-2 border-brand/50"></div>'
              f'<div class="relative rounded-[2.5rem] overflow-hidden shadow-xl aspect-[4/5]">{media(d, 800, 1000, "about-page", "w-full h-full object-cover")}</div></div>'
            + "</div></section>\n" + sec_services(c, d, content) + sec_why(c, d, content) + contact_band(c, d, content)
            + "</main>\n" + footer(c, d, content))


def page_faq(c: dict, d: dict, content: dict) -> str:
    return (head(c, d, f'FAQ - {c["company"]}', content["meta_description_faq"], "faq.html")
            + '<body class="font-sans text-slate-800 antialiased bg-white">\n' + header(c, d, "faq.html") + "<main>\n"
            + page_hero(c, d, "FAQ", "Frequently asked questions")
            + f'<section class="py-16"><div class="max-w-3xl mx-auto px-6 space-y-3">{faq_items(content)}</div></section>\n'
            + contact_band(c, d, content) + "</main>\n" + footer(c, d, content))


def page_contact(c: dict, d: dict, content: dict) -> str:
    cards = ""
    if c.get("address"):
        cards += (f'<div class="rounded-xl bg-white shadow-xl p-6 flex gap-4"><span class="grid place-items-center w-12 h-12 rounded-full grad text-white shrink-0">{icon("pin")}</span>'
                  f'<div><div class="font-heading font-bold text-slate-900">Address</div><div class="text-slate-600">{escape(c["address"])}</div>'
                  f'<a href="{maps_link(c["address"])}" target="_blank" rel="noopener" class="inline-flex items-center gap-1 text-sm font-semibold text-brand mt-1">Open in Google Maps{icon("arrow", "w-4 h-4")}</a></div></div>')
    if c.get("phone"):
        cards += (f'<div class="rounded-xl bg-white shadow-xl p-6 flex gap-4"><span class="grid place-items-center w-12 h-12 rounded-full grad text-white shrink-0">{icon("phone")}</span>'
                  f'<div><div class="font-heading font-bold text-slate-900">Phone</div><a href="tel:{_tel(c["phone"])}" class="text-slate-600 hover:text-brand">{escape(c["phone"])}</a></div></div>')
    if c.get("email"):
        cards += (f'<div class="rounded-xl bg-white shadow-xl p-6 flex gap-4"><span class="grid place-items-center w-12 h-12 rounded-full grad text-white shrink-0">{icon("mail")}</span>'
                  f'<div><div class="font-heading font-bold text-slate-900">Email</div><a href="mailto:{escape(c["email"])}" class="text-slate-600 hover:text-brand">{escape(c["email"])}</a></div></div>')
    cards += (f'<div class="rounded-xl bg-white shadow-xl p-6 flex gap-4"><span class="grid place-items-center w-12 h-12 rounded-full grad text-white shrink-0">{icon("clock")}</span>'
              f'<div><div class="font-heading font-bold text-slate-900">Business Hours</div><div class="text-slate-600">{escape(HOURS_TEXT)}</div></div></div>')
    form = contact_form(c, light=False)
    right = (f'<div class="rounded-2xl bg-soft p-8"><h2 class="font-heading text-2xl font-extrabold text-slate-900 mb-5">Send Us a Message</h2>{form}</div>'
             if form else
             f'<div class="rounded-2xl grad text-white p-8"><h2 class="font-heading text-2xl font-extrabold mb-3">Talk With Us</h2>'
             f'<p class="text-white/90 leading-relaxed mb-6">{escape(content["contact_intro"])}</p>{_buttons(c, content, light=True) if c.get("phone") else ""}</div>')
    return (head(c, d, f'Contact - {c["company"]}', content["meta_description_contact"], "contact.html")
            + '<body class="font-sans text-slate-800 antialiased bg-white">\n' + header(c, d, "contact.html") + "<main>\n"
            + page_hero(c, d, "Contact us", "Get in touch", content["contact_intro"])
            + f'<section class="py-16"><div class="max-w-6xl mx-auto px-6 grid lg:grid-cols-2 gap-10 items-start"><div class="space-y-5">{cards}</div>{right}</div></section>\n'
            + "</main>\n" + footer(c, d, content))


def _legal(c: dict, d: dict, content: dict, page: str, title: str, blocks: list[tuple[str, str]]) -> str:
    body = "".join(f'<h2 class="font-heading text-2xl font-bold text-slate-900 mt-10 mb-3">{escape(h)}</h2>'
                   f'<p class="text-slate-600 leading-relaxed">{t}</p>' for h, t in blocks)
    return (head(c, d, f'{title} - {c["company"]}', f'{title} for {c["company"]}', page)
            + '<body class="font-sans text-slate-800 antialiased bg-white">\n' + header(c, d, page) + "<main>\n"
            + page_hero(c, d, "Legal", title, f"Last updated: {date.today().strftime('%B %d, %Y')}")
            + f'<section class="py-12"><article class="max-w-3xl mx-auto px-6">{body}</article></section>\n'
            + "</main>\n" + footer(c, d, content))


def _contact_sentence(c: dict, what: str) -> str:
    if c.get("email"):
        return (f'Questions about {what} may be sent to <a href="mailto:{escape(c["email"])}" class="text-brand hover:underline">'
                f'{escape(c["email"])}</a>' + (f' or mailed to {escape(c["address"])}.' if c.get("address") else "."))
    if c.get("address"):
        return f"Questions about {what} may be mailed to {escape(c['address'])}."
    return f"Questions about {what} may be raised with us by phone."


def page_privacy(c: dict, d: dict, content: dict) -> str:
    n = escape(c["company"])
    return _legal(c, d, content, "privacy.html", "Privacy Policy", [
        ("Information we collect", f"{n} collects information you choose to give us, such as your name, phone number or message, "
                                   "and basic technical data sent by your browser when you visit this website."),
        ("How we use it", "We use this information to answer your questions and provide our services. We do not sell personal information."),
        ("Sharing", "We may share information with service providers who help us run this website or our business, and when the law requires it."),
        ("Your rights", "You may ask us to access, correct or delete personal information we hold about you."),
        ("Contact", _contact_sentence(c, "this Privacy Policy")),
    ])


def page_terms(c: dict, d: dict, content: dict) -> str:
    n = escape(c["company"])
    return _legal(c, d, content, "terms.html", "Terms of Service", [
        ("Use of this website", f"By using this website you agree to these terms. The content is provided by {n} for general information."),
        ("Services", "Any service is provided under the terms agreed with you directly. Information on this site is not an offer."),
        ("Liability", f"{n} is not liable for indirect damages arising from the use of this website, to the extent permitted by law."),
        ("Changes", "We may update these terms; the date above shows the latest version."),
        ("Contact", _contact_sentence(c, "these Terms")),
    ])


def render_site(company: dict, content: dict, template: str, photos: dict | None = None,
                credits: list[dict] | None = None) -> dict[str, bytes]:
    """company: {company, domain, phone, email (verified only), address}. content: the checked AI copy.
    photos: optional {slot: file path or {src, alt}} (files shipped with the site; URLs only in the in-app preview).
    credits: [{name, url}] of the photographers (shown in the footer). → {filename: bytes}."""
    if template not in BY_ID:
        raise ValueError(f"Unknown template {template}")
    c = dict(company)
    d = {**design(company, template), "photos": photos or {}, "credits": credits or []}
    content = {**content, "business_hours": HOURS_TEXT}
    pages = {"index.html": page_home(c, d, content), "about.html": page_about(c, d, content), "faq.html": page_faq(c, d, content),
             "contact.html": page_contact(c, d, content), "privacy.html": page_privacy(c, d, content), "terms.html": page_terms(c, d, content)}
    out = {name: html.encode("utf-8") for name, html in pages.items()}
    domain = company["domain"]
    out["robots.txt"] = f"User-agent: *\nAllow: /\nSitemap: https://{domain}/sitemap.xml\n".encode()
    urls = "".join(f"  <url><loc>https://{domain}/{p}</loc></url>\n" for p in pages)
    out["sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                          f"{urls}</urlset>").encode()
    return out

