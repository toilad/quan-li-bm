"""Build a site with the recovered legacy templates.

Same context as the legacy site_builder._build_context (font pair, accent colour, hero layout, button radius,
section order, section variants, photo seed) — but the random choices are seeded with the domain, so rebuilding
the same site gives the same design, and the chosen business-type template drives the photo keywords.

Owner rules applied on top of the legacy behaviour:
- Home sections limited to about_preview / services / why: the legacy trust strip (stats, “client logo” words),
  placeholder testimonials (5 stars, “Real feedback…”), stock-photo gallery (“A Look at Our Work”) and fixed
  promise steps are not published.
- Business hours are never invented (the legacy prompt asked the AI to make them up).
- The duplicated "<html><!DOCTYPE html>" opening of every legacy page is corrected to "<!DOCTYPE html>".
"""
import random

from .legacy import config_data as cfg
from .legacy.templates import about, contact, faq, home, privacy, terms

SAFE_SECTIONS = ("about_preview", "services", "why")
HOURS_TEXT = "Please contact us for current business hours."

# Variant tables from the legacy site_builder (unchanged).
ABOUT_PREVIEW_VARIANTS = ["left", "right", "stacked", "framed"]
SERVICES_VARIANTS = ["photo", "minimal", "numbered", "alternating"]
CTA_BANNER_VARIANTS = ["solid", "dark", "light", "split"]
GALLERY_VARIANTS = ["asymmetric", "masonry", "bento", "row"]
TRUST_STRIP_VARIANTS = ["icons", "stats", "logos"]
PROCESS_VARIANTS = ["numbered-grid", "timeline", "stepper"]
WHY_VARIANTS = ["side-by-side", "four-col", "list-band"]
HEADER_VARIANTS = ["topbar-left", "topbar-centered", "split-nav"]
FOOTER_VARIANTS = ["dark-3col", "dark-4col", "light-3col", "minimal-band"]
HOME_SECTION_ORDERS = [
    ["trust_strip", "about_preview", "services", "process", "gallery", "testimonials", "why"],
    ["about_preview", "services", "gallery", "why", "process"],
    ["services", "about_preview", "why", "gallery", "testimonials"],
    ["trust_strip", "about_preview", "gallery", "services", "why"],
    ["about_preview", "trust_strip", "services", "process", "why"],
    ["gallery", "about_preview", "services", "testimonials", "why"],
    ["services", "gallery", "about_preview", "process", "trust_strip"],
    ["about_preview", "process", "services", "gallery", "testimonials"],
    ["trust_strip", "services", "gallery", "why", "process", "testimonials"],
    ["about_preview", "why", "gallery", "services", "process"],
    ["services", "why", "gallery", "about_preview"],
    ["about_preview", "gallery", "services", "process", "testimonials", "why"],
]
PAGES = ("index.html", "about.html", "faq.html", "contact.html", "privacy.html", "terms.html")


def theme_name(template_id_or_name: str) -> str:
    """Our template ids (e.g. 'lawyer-legal') → the legacy theme name used for photo keywords."""
    from .templates import BY_ID

    t = BY_ID.get(template_id_or_name)
    name = t.name if t else template_id_or_name
    if name not in cfg.BUSINESS_TYPE_THEMES:
        raise ValueError(f"Unknown template {template_id_or_name}")
    return name


def build_context(company: dict, content: dict, template: str) -> dict:
    rng = random.Random(f"{company['domain'].lower()}|{template}")
    order = [s for s in rng.choice(HOME_SECTION_ORDERS) if s in SAFE_SECTIONS]
    for s in SAFE_SECTIONS:  # every safe section appears once
        if s not in order:
            order.append(s)
    return {
        "company": {**company, "business_type": theme_name(template)},
        "content": {**content, "business_hours": HOURS_TEXT},
        "fonts": rng.choice(cfg.FONT_PAIRS),
        "color": rng.choice(cfg.ACCENT_COLORS),
        "hero_layout": rng.choice(cfg.HERO_LAYOUTS),
        "btn_radius": rng.choice(cfg.BUTTON_RADIUS),
        "fb_app_id": "",
        "sections_order": order,
        "photo_seed": rng.randint(1, 999999),
        "local_photos": {},
        "variants": {
            "about_preview": rng.choice(ABOUT_PREVIEW_VARIANTS), "services": rng.choice(SERVICES_VARIANTS),
            "cta_banner": rng.choice(CTA_BANNER_VARIANTS), "gallery": rng.choice(GALLERY_VARIANTS),
            "trust_strip": rng.choice(TRUST_STRIP_VARIANTS), "process": rng.choice(PROCESS_VARIANTS),
            "why": rng.choice(WHY_VARIANTS), "header": rng.choice(HEADER_VARIANTS), "footer": rng.choice(FOOTER_VARIANTS),
        },
    }


def _fix(html: str) -> str:
    return "<!DOCTYPE html>" + html[len("<html><!DOCTYPE html>"):] if html.startswith("<html><!DOCTYPE html>") else html


def render_site(company: dict, content: dict, template: str) -> dict[str, bytes]:
    """company: {company, domain, phone, email, address}. content: legacy AI fields. → {filename: bytes}."""
    ctx = build_context(company, content, template)
    pages = {
        "index.html": home.render(ctx), "about.html": about.render(ctx), "faq.html": faq.render(ctx),
        "contact.html": contact.render(ctx), "privacy.html": privacy.render(ctx), "terms.html": terms.render(ctx),
    }
    out = {name: _fix(html).encode("utf-8") for name, html in pages.items()}
    domain = company["domain"]
    out["robots.txt"] = f"User-agent: *\nAllow: /\nSitemap: https://{domain}/sitemap.xml\n".encode()
    urls = "".join(f"  <url><loc>https://{domain}/{p}</loc></url>\n" for p in pages)
    out["sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                          f"{urls}</urlset>").encode()
    return out
