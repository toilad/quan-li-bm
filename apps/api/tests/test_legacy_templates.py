"""The recovered legacy templates, rendered for all 15 themes and many domains (= many legacy design variants)."""
import re

import pytest

from wg_core.modules.websites.legacy import config_data as cfg
from wg_core.modules.websites.legacy_render import build_context, render_site
from wg_core.modules.websites.templates import TEMPLATES

CONTENT = {
    "tagline": "Plain tagline", "hero_subtitle": "Sub", "primary_cta": "Get a Quote", "intro_paragraph": "Intro.",
    "about_short": "About.", "about_full": "One.\n\nTwo.\n\nThree.", "contact_intro": "Write to us.", "footer_blurb": "Blurb.",
    "meta_description_home": "Home.", "meta_description_about": "About.", "meta_description_contact": "Contact.",
    "meta_description_faq": "FAQ.",
    "services": [{"title": f"S{i}", "description": "D."} for i in range(3)],
    "why_choose_us": [{"title": f"W{i}", "description": "D."} for i in range(3)],
    "faqs": [{"q": f"Q{i}?", "a": "A."} for i in range(5)],
}
NEVER = ("What Our Customers Say", "Real feedback", "Edit me", "Trusted by", "Our customers", "Trusted Service", "100%",
         "24/7", "A+", "On-time", "A Look at Our Work", "hears most often")


def company(domain):
    return {"company": "Acme Example LLC", "domain": domain, "phone": "(307) 555-0101", "email": "", "address": "1 Main St, Cheyenne, WY 82001"}


def test_the_15_templates_are_the_legacy_themes():
    assert [t.name for t in TEMPLATES] == sorted(cfg.BUSINESS_TYPE_THEMES, key=[t.name for t in TEMPLATES].index)
    assert {t.name for t in TEMPLATES} == set(cfg.BUSINESS_TYPE_THEMES)


@pytest.mark.parametrize("t", TEMPLATES, ids=lambda t: t.id)
def test_every_template_renders_six_pages_without_unverifiable_claims(t):
    seen_layouts = set()
    for k in range(12):  # different domains → different legacy design variants
        files = render_site(company(f"site{k}.example.com"), CONTENT, t.id)
        assert set(files) == {"index.html", "about.html", "faq.html", "contact.html", "privacy.html", "terms.html", "robots.txt", "sitemap.xml"}
        for name, data in files.items():
            if not name.endswith(".html"):
                continue
            html = data.decode()
            assert html.startswith("<!DOCTYPE html>") and html.count("<html") == 1, name
            assert "Acme Example LLC" in html
            for claim in NEVER:
                assert claim not in html, (t.id, name, claim)
        assert "Please contact us for current business hours." in files["contact.html"].decode()
        keywords = cfg.BUSINESS_KEYWORDS[t.name]
        assert keywords in files["index.html"].decode()  # the chosen theme decides the photo keywords
        seen_layouts.add(build_context(company(f"site{k}.example.com"), CONTENT, t.id)["hero_layout"])
    assert len(seen_layouts) >= 3  # the legacy variety of hero layouts is kept


def test_same_site_same_design():
    a = build_context(company("a.example.com"), CONTENT, "lawyer-legal")
    b = build_context(company("a.example.com"), CONTENT, "lawyer-legal")
    assert a["color"] == b["color"] and a["fonts"] == b["fonts"] and a["sections_order"] == b["sections_order"]
    assert set(a["sections_order"]) == {"about_preview", "services", "why"}


def test_no_verified_email_means_no_email_anywhere_and_no_form():
    for t in TEMPLATES:
        for k in range(6):
            files = render_site(company(f"m{k}.example.com"), CONTENT, t.id)
            for name, data in files.items():
                html = data.decode()
                for bad in ("mailto:", "<form", 'itemprop="email"', "contact_data:email", '"email":', "Send Us a Message"):
                    assert bad not in html, (t.id, name, bad)
            contact = files["contact.html"].decode()
            assert "Talk With Us" in contact and "tel:" in contact and "1 Main St, Cheyenne, WY 82001" in contact
            assert "may be mailed to 1 Main St" in files["privacy.html"].decode()


def test_verified_email_keeps_the_legacy_contact_form():
    c = {**company("v.example.com"), "email": "hello@acme.example"}
    files = render_site(c, CONTENT, "corporate-firm")
    contact = files["contact.html"].decode()
    assert '<form action="mailto:hello@acme.example"' in contact and "Send Us a Message" in contact
    assert 'href="mailto:hello@acme.example"' in files["privacy.html"].decode()
    assert '"email": "hello@acme.example"' in files["index.html"].decode()
