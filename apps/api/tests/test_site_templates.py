"""The 15 templates in the owner's chosen "brand" style, rendered for many domains."""
import re

import pytest

from tests.test_legacy_templates import CONTENT, NEVER
from wg_core.modules.websites.brand_render import STYLE, design, render_site
from wg_core.modules.websites.templates import TEMPLATES

# What the reference site showed and must never be published here.
REFERENCE_FAKES = ("Subscribers", "Followers", "Verified by", "★", "Lorem ipsum", "Singing", "Business Manage", "loremflickr",
                   "play-button", "Testimonial", "%</")


def visible(html: str) -> str:
    """Text a visitor reads (no tags, CSS or scripts) — claims are checked here."""
    html = re.sub(r"<(style|script).*?</>", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


def company(domain, **kw):
    return {"company": "Acme Example LLC", "domain": domain, "phone": "(307) 555-0101", "email": "",
            "address": "1 Main St, Cheyenne, WY 82001", **kw}


@pytest.mark.parametrize("t", TEMPLATES, ids=lambda t: t.id)
def test_every_template_renders_six_pages_with_no_unverifiable_content(t):
    seen = set()
    for k in range(10):
        c = company(f"site{k}.example.com")
        files = render_site(c, CONTENT, t.id)
        assert set(files) == {"index.html", "about.html", "faq.html", "contact.html", "privacy.html", "terms.html", "robots.txt", "sitemap.xml"}
        for name, data in files.items():
            if not name.endswith(".html"):
                continue
            html = data.decode()
            assert html.startswith("<!DOCTYPE html>") and html.count("<html") == 1 and html.rstrip().endswith("</html>"), name
            assert "Acme Example LLC" in html and STYLE[t.id][0] in html  # the template's own gradient
            text = visible(html)
            for bad in NEVER + REFERENCE_FAKES:
                assert bad not in text, (t.id, name, bad)
            assert "loremflickr" not in html
            assert "<img" not in html and "<iframe" not in html  # no hot-linked photos, no guessed map pin
            for url in re.findall(r'href="(https?://[^"]+)"', html):
                assert url.startswith(("https://www.google.com/maps/search/?api=1&query=", "https://fonts.", f"https://{c['domain']}/")), url
        assert "Please contact us for current business hours." in files["contact.html"].decode()
        d = design(c, t.id)
        seen.add((d["shape"], d["frame"], d["cards"], d["photo_right"], tuple(d["middle"])))
    assert len(seen) >= 4  # domains of the same template do not all look the same


def test_the_15_templates_have_their_own_colours():
    assert set(STYLE) == {t.id for t in TEMPLATES}
    assert len({(s[0], s[1]) for s in STYLE.values()}) == 15


def test_same_site_same_design():
    assert design(company("a.example.com"), "lawyer-legal") == design(company("a.example.com"), "lawyer-legal")
    a = render_site(company("a.example.com"), CONTENT, "lawyer-legal")["index.html"]
    b = render_site(company("a.example.com"), CONTENT, "lawyer-legal")["index.html"]
    assert a == b


def test_no_verified_email_means_no_email_anywhere_and_no_form():
    for t in TEMPLATES:
        files = render_site(company(f"m.{t.id}.example.com"), CONTENT, t.id)
        for name, data in files.items():
            html = data.decode()
            for bad in ("mailto:", "<form", '"email":', "Send Us a Message"):
                assert bad not in html, (t.id, name, bad)
        assert "Talk With Us" in files["contact.html"].decode()
        assert "may be mailed to 1 Main St" in files["privacy.html"].decode()


def test_verified_email_shows_the_contact_form():
    files = render_site(company("v.example.com", email="hello@acme.example"), CONTENT, "corporate-firm")
    contact = files["contact.html"].decode()
    assert '<form action="mailto:hello@acme.example"' in contact and "Send Us a Message" in contact
    assert 'href="mailto:hello@acme.example"' in files["privacy.html"].decode()
    assert '"email": "hello@acme.example"' in files["index.html"].decode()


def test_text_from_the_sheet_or_ai_is_escaped():
    c = company("x.example.com", company='Bad <script>alert(1)</script> & Co "LLC"')
    copy = {**CONTENT, "tagline": "<img src=x onerror=alert(1)>"}
    for name, data in render_site(c, copy, "fse-dental").items():
        html = data.decode()
        assert "<script>alert(1)</script>" not in html and "<img src=x" not in html, name
    assert "Bad &lt;script&gt;" in render_site(c, copy, "fse-dental")["index.html"].decode()


def test_missing_phone_or_address_leaves_no_empty_links():
    files = render_site(company("p.example.com", phone="", address=""), CONTENT, "herbal-shop")
    for name, data in files.items():
        html = data.decode()
        assert 'href="tel:"' not in html and "maps/search" not in html, name


def test_photos_are_used_only_when_shipped_with_the_site():
    files = render_site(company("ph.example.com"), CONTENT, "expert-travel", photos={"hero": "img/hero.jpg"})
    assert '<img src="img/hero.jpg"' in files["index.html"].decode()
