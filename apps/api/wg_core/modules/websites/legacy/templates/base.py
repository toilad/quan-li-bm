"""
base.py
=======
Shared HTML fragments: <head>, header (nav), footer, icon library,
and the small scroll-reveal script every page reuses.
"""

from datetime import datetime
from typing import Dict, Optional

from ..config_data import BUSINESS_KEYWORDS, COMPANY_NAME_KEYWORDS, DEFAULT_PHOTO_KEYWORDS

# Inline SVG icon library

ICONS = {
    "gear": (
        '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>'
),
    "shield": (
        '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6" d="M9 12l2 2 4-4M12 3l8 4v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V7l8-4z"/></svg>'
),
    "chart": (
        '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6" d="M9 19V6m6 13V10m6 9V3M3 21h18"/></svg>'
),
    "lightbulb": (
        '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>'
),
    "target": (
        '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" stroke-width="1.6"/><circle cx="12" cy="12" r="5" stroke-width="1.6"/><circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/></svg>'
),
    "headphones": (
        '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6" d="M4 14v-2a8 8 0 0116 0v2m-1 0a2 2 0 012 2v2a2 2 0 01-2 2h-1v-6h1zM5 14H4a2 2 0 00-2 2v2a2 2 0 002 2h1v-6z"/></svg>'
),
    "check": (
        '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>'
),
    "users": (
        '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6" d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-4a4 4 0 11-8 0 4 4 0 018 0zm6 0a4 4 0 11-8 0 4 4 0 018 0z"/></svg>'
),
    "clock": (
        '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" stroke-width="1.6"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6" d="M12 7v5l3 2"/></svg>'
),
    "phone": (
        '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6" d="M3 5a2 2 0 012-2h2.28a2 2 0 011.94 1.515l.84 3.36a2 2 0 01-.45 1.95L8.21 11.79a11 11 0 005 5l1.97-1.4a2 2 0 011.95-.45l3.36.84A2 2 0 0122 17.72V20a2 2 0 01-2 2h-1C9.61 22 2 14.39 2 5V4z"/></svg>'
),
    "mail": (
        '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6" d="M3 8l9 6 9-6M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>'
),
    "pin": (
        '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6" d="M17.657 16.657L13.414 20.9a2 2 0 01-2.828 0l-4.244-4.243a8 8 0 1111.314 0z"/><circle cx="12" cy="11" r="3" stroke-width="1.6"/></svg>'
),
    "arrow_right": (
        '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/></svg>'
),
}

SERVICE_ICON_KEYS = ["gear", "shield", "chart", "lightbulb", "target", "headphones"]
VALUE_ICON_KEYS = ["check", "users", "clock", "shield", "target", "lightbulb"]

LOCAL_PHOTO_SLOT_INDEX = {"hero": 0, "hero_bg": 0, "about_preview": 1, "service_1": 2, "service_2": 3, "service_3": 4, "about_hero": 5, "about_inline": 5, "contact_hero": 5}


def icon(name: str, css_class: str = "w-6 h-6") -> str:
    svg = ICONS.get(name, ICONS["check"])
    return svg.replace("<svg ", f'<svg class="{css_class}" ', 1)


def format_phone_display(phone: str) -> str:
    # NOTE: the original function had a docstring; its text is not recoverable from the disassembly.
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if len(digits) == 10:
        return f'({digits[:3]}) {digits[3:6]}-{digits[6:]}'
    if len(digits) == 11 and digits.startswith("1"):
        return f'+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}'
    return phone


def phone_tel_value(phone: str) -> str:
    s = (phone or "").strip()
    if s and not s.startswith("+"):
        return "+" + "".join(c for c in s if c.isdigit())
    return "".join(c for c in s if c.isdigit() or c == "+")


def _infer_keywords(ctx: Dict) -> str:
    bt = (ctx["company"].get("business_type") or "").strip()
    if bt in BUSINESS_KEYWORDS:
        return BUSINESS_KEYWORDS[bt]
    name = (ctx["company"].get("company") or "").lower()
    for key, kw in COMPANY_NAME_KEYWORDS.items():
        if key in name:
            return kw
    return DEFAULT_PHOTO_KEYWORDS


def photo_url(
    ctx: Dict,
    width: int,
    height: int,
    slot: str = "",
    keywords: Optional[str] = None,
) -> str:
    local = ctx.get("local_photos") or {}
    idx = LOCAL_PHOTO_SLOT_INDEX.get(slot)
    if idx is not None and idx in local:
        return local[idx]
    kw = keywords or _infer_keywords(ctx)
    kw = ",".join(t.strip() for t in kw.split(",") if t.strip())
    photo_seed = ctx.get("photo_seed") or 0
    seed = abs(hash(f'{photo_seed}|{slot}')) % 999999 + 1
    return f'https://loremflickr.com/{width}/{height}/{kw}?lock={seed}'


def _local_business_jsonld(ctx: Dict, title: str, meta_desc: str) -> str:
    # NOTE: the original function had a docstring; its text is not recoverable from the disassembly.
    import json
    c = ctx["company"]
    data = {
            "@context": 'https://schema.org',
            "@type": 'LocalBusiness',
            "name": c.get("company", ""),
            "url": f'https://{c.get("domain", "")}/',
            "telephone": c.get("phone", ""),
            "email": c.get("email", ""),
            "address": {"@type": "PostalAddress", "streetAddress": c.get("address", "")},
            "description": meta_desc,
        }
    if not data["email"]:
        del data["email"]  # QLBM: no email unless verified
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + "</script>"


def render_head(title: str, meta_desc: str, ctx: Dict) -> str:
    body_font, heading_font = ctx["fonts"]
    fonts_url = "&family=".join(
        [f.replace(" ", "+") + ":wght@400;500;600;700;800" for f in {body_font, heading_font}]
    )
    color = ctx["color"]
    c = ctx["company"]
    jsonld = _local_business_jsonld(ctx, title, meta_desc)
    fb_v = (c.get("fb_verification") or "").strip()
    fb_v_meta = f'<meta name="facebook-domain-verification" content="{fb_v}">' if fb_v else ""
    # QLBM: shown only for a verified business email
    email_meta = (
            f'<meta name="business:contact_data:email" content="{c["email"]}">\n'
    ) if c["email"] else ""
    return (
            '<!DOCTYPE html>\n'
            '<html lang="en">\n'
            '<head>\n'
            '<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f'<meta name="description" content="{meta_desc}">\n'
            f'<meta name="business:contact_data:street_address" content="{c["address"]}">\n'
            f'<meta name="business:contact_data:phone_number" content="{c["phone"]}">\n'
            f'{email_meta}'
            f'<meta property="og:title" content="{title}">\n'
            f'<meta property="og:description" content="{meta_desc}">\n'
            '<meta property="og:type" content="website">\n'
            f'<meta property="og:url" content="https://{c["domain"]}/">\n'
            f'{fb_v_meta}\n'
            f'{jsonld}\n'
            f'<title>{title}</title>\n'
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            f'<link href="https://fonts.googleapis.com/css2?family={fonts_url}&display=swap" rel="stylesheet">\n'
            '<script src="https://cdn.tailwindcss.com"></script>\n'
            '<script>\n'
            '  tailwind.config = {\n'
            '    theme: {\n'
            '      extend: {\n'
            '        fontFamily: {\n'
            f"          sans: ['{body_font}', 'system-ui', 'sans-serif'],\n"
            f"          heading: ['{heading_font}', 'system-ui', 'sans-serif'],\n"
            '        },\n'
            '        colors: {\n'
            f"          brand: '{color['primary']}',\n"
            f"          'brand-dark': '{color['primary_dark']}',\n"
            f"          'brand-soft': '{color['bg_soft']}',\n"
            '        }\n'
            '      }\n'
            '    }\n'
            '  }\n'
            '</script>\n'
            '<style>\n'
            '  html { scroll-behavior: smooth; }\n'
            f"  body {{ font-family: '{body_font}', system-ui, sans-serif; }}\n"
            f"  h1, h2, h3, h4 {{ font-family: '{heading_font}', system-ui, sans-serif; letter-spacing: -0.01em; }}\n"
            '\n'
            '  /* Hero decorative dot pattern */\n'
            '  .hero-dots {\n'
            '    background-image: radial-gradient(circle, rgba(0,0,0,0.05) 1px, transparent 1px);\n'
            '    background-size: 24px 24px;\n'
            '  }\n'
            '\n'
            '  /* Subtle gradient blob behind hero */\n'
            '  .hero-blob::before {\n'
            "    content: '';\n"
            '    position: absolute;\n'
            '    width: 480px; height: 480px;\n'
            f'    background: radial-gradient(circle, {color["primary"]}22 0%, transparent 70%);\n'
            '    top: -120px; right: -120px;\n'
            '    border-radius: 50%;\n'
            '    pointer-events: none;\n'
            '  }\n'
            '\n'
            '  /* Scroll-reveal animation: elements with [data-reveal] fade up when visible */\n'
            '  [data-reveal] {\n'
            '    opacity: 0;\n'
            '    transform: translateY(20px);\n'
            '    transition: opacity 0.7s ease-out, transform 0.7s ease-out;\n'
            '  }\n'
            '  [data-reveal].is-visible {\n'
            '    opacity: 1;\n'
            '    transform: translateY(0);\n'
            '  }\n'
            '\n'
            '  /* Card hover lift */\n'
            '  .card-lift {\n'
            '    transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;\n'
            '  }\n'
            '  .card-lift:hover {\n'
            '    transform: translateY(-4px);\n'
            '    box-shadow: 0 12px 24px -8px rgba(0,0,0,0.10);\n'
            '  }\n'
            '\n'
            '  /* Drop cap for the about page first paragraph */\n'
            '  .dropcap::first-letter {\n'
            '    float: left;\n'
            f"    font-family: '{heading_font}', system-ui, sans-serif;\n"
            '    font-size: 3.5rem;\n'
            '    line-height: 1;\n'
            '    padding-right: 0.5rem;\n'
            '    padding-top: 0.25rem;\n'
            f'    color: {color["primary"]};\n'
            '    font-weight: 700;\n'
            '  }\n'
            '</style>\n'
            '</head>'
        )


def _render_topbar(ctx: Dict) -> str:
    c = ctx["company"]
    phone_display = format_phone_display(c["phone"])
    phone_tel = phone_tel_value(c["phone"])
    phone_icon = icon("phone", "w-4 h-4")
    mail_icon = icon("mail", "w-4 h-4")
    pin_icon = icon("pin", "w-4 h-4")
    # QLBM: shown only for a verified business email
    email_link = (
            f'      <a href="mailto:{c["email"]}" class="hidden sm:flex items-center gap-2 font-medium hover:text-white/80 transition" itemprop="email">\n'
            f'        {mail_icon}<span>{c["email"]}</span>\n'
            '      </a>\n'
    ) if c["email"] else ""
    return (
            '<div class="bg-brand text-white text-sm" itemscope itemtype="https://schema.org/LocalBusiness">\n'
            f'  <meta itemprop="name" content="{c["company"]}">\n'
            f'  <meta itemprop="url" content="https://{c["domain"]}/">\n'
            '  <div class="max-w-6xl mx-auto px-6 py-3 flex flex-wrap items-center justify-between gap-3">\n'
            '    <div class="flex flex-wrap items-center gap-x-6 gap-y-1.5">\n'
            f'      <a href="tel:{phone_tel}" class="flex items-center gap-2 font-medium hover:text-white/80 transition" itemprop="telephone" content="{c["phone"]}">\n'
            f'        {phone_icon}<span>{phone_display}</span>\n'
            '      </a>\n'
            f'{email_link}'
            '    </div>\n'
            '    <div class="hidden md:flex items-center gap-2 text-white/90" itemprop="address" itemscope itemtype="https://schema.org/PostalAddress">\n'
            f'      {pin_icon}<span class="truncate max-w-[440px]" itemprop="streetAddress">{c["address"]}</span>\n'
            '    </div>\n'
            '  </div>\n'
            '</div>'
        )


def render_header(ctx: Dict, active: str) -> str:
    # NOTE: the original function had a docstring; its text is not recoverable from the disassembly.
    company = ctx["company"]["company"]
    variant = (ctx.get("variants") or {}).get("header", "topbar-left")
    radius = ctx.get("btn_radius", "rounded-lg")
    nav_items = [("Home", "index.html"), ("About", "about.html"), ("FAQ", "faq.html"), ("Contact", "contact.html")]

    def _link(label, href):
        is_active = active == label.lower()
        cls = "text-brand font-semibold" if is_active else "text-gray-700 hover:text-brand"
        return f'<a href="{href}" class="{cls} transition">{label}</a>'

    nav_html = "\n      ".join(_link(label, href) for label, href in nav_items)
    initials = "".join(w[0].upper() for w in company.split()[:3] if w[0].isalpha())
    logo = (
            '<a href="index.html" class="flex items-center gap-3">\n'
            f'      <div class="w-10 h-10 {radius} bg-brand text-white flex items-center justify-center font-heading font-bold text-sm shadow-sm">\n'
            f'        {initials}\n'
            '      </div>\n'
            f'      <span class="font-heading font-semibold text-gray-900 text-lg">{company}</span>\n'
            '    </a>'
        )
    quote_btn = (
            f'<a href="contact.html" class="bg-brand hover:bg-brand-dark text-white px-4 py-2 {radius} transition shadow-sm">Get a Quote</a>'
        )
    mobile_btn = (
            '<button id="mobile-menu-btn" class="md:hidden text-gray-700" aria-label="Menu">\n'
            '      <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24">\n'
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>\n'
            '      </svg>\n'
            '    </button>'
        )
    mobile_menu = (
            '<div id="mobile-menu" class="hidden md:hidden border-t border-gray-100 bg-white">\n'
            '    <div class="px-6 py-3 flex flex-col gap-3 text-sm">\n'
            f'      {nav_html}\n'
            f'      <a href="contact.html" class="bg-brand text-white px-4 py-2 {radius} text-center">Get a Quote</a>\n'
            '    </div>\n'
            '  </div>'
        )
    topbar = _render_topbar(ctx) if variant != "no-topbar" else ""
    if variant == "topbar-centered":
        return (
            f'{topbar}\n'
            '<header id="site-header" class="bg-white/95 backdrop-blur border-b border-gray-100 sticky top-0 z-50 transition-shadow">\n'
            '  <div class="max-w-6xl mx-auto px-6 py-5 flex flex-col items-center gap-4">\n'
            f'    {logo}\n'
            '    <nav class="hidden md:flex items-center gap-8 text-sm">\n'
            f'      {nav_html}\n'
            f'      {quote_btn}\n'
            '    </nav>\n'
            '  </div>\n'
            '  <div class="md:hidden border-t border-gray-100">\n'
            f'    <div class="max-w-6xl mx-auto px-6 py-3 flex justify-end">{mobile_btn}</div>\n'
            '  </div>\n'
            f'  {mobile_menu}\n'
            '</header>'
        )
    if variant == "split-nav":
        return (
            f'{topbar}\n'
            '<header id="site-header" class="bg-white/95 backdrop-blur border-b border-gray-100 sticky top-0 z-50 transition-shadow">\n'
            '  <div class="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">\n'
            '    <nav class="hidden md:flex items-center gap-8 text-sm flex-1 justify-start">\n'
            f'      {_link("Home", "index.html")}\n'
            f'      {_link("About", "about.html")}\n'
            '    </nav>\n'
            f'    {logo}\n'
            '    <nav class="hidden md:flex items-center gap-8 text-sm flex-1 justify-end">\n'
            f'      {_link("FAQ", "faq.html")}\n'
            f'      {_link("Contact", "contact.html")}\n'
            f'      {quote_btn}\n'
            '    </nav>\n'
            f'    {mobile_btn}\n'
            '  </div>\n'
            f'  {mobile_menu}\n'
            '</header>'
        )
    return (
            f'{topbar}\n'
            '<header id="site-header" class="bg-white/95 backdrop-blur border-b border-gray-100 sticky top-0 z-50 transition-shadow">\n'
            '  <div class="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">\n'
            f'    {logo}\n'
            '    <nav class="hidden md:flex items-center gap-8 text-sm">\n'
            f'      {nav_html}\n'
            f'      {quote_btn}\n'
            '    </nav>\n'
            f'    {mobile_btn}\n'
            '  </div>\n'
            f'  {mobile_menu}\n'
            '</header>'
        )


_FOOTER_SCRIPT = (
    '\n'
    '<script>\n'
    '  // Mobile menu toggle\n'
    '  (function() {\n'
    "    var btn = document.getElementById('mobile-menu-btn');\n"
    "    var menu = document.getElementById('mobile-menu');\n"
    '    if (btn && menu) {\n'
    "      btn.addEventListener('click', function() { menu.classList.toggle('hidden'); });\n"
    '    }\n'
    '  })();\n'
    '\n'
    '  // Header shadow on scroll\n'
    '  (function() {\n'
    "    var header = document.getElementById('site-header');\n"
    '    if (!header) return;\n'
    '    var onScroll = function() {\n'
    "      if (window.scrollY > 8) header.classList.add('shadow-sm');\n"
    "      else header.classList.remove('shadow-sm');\n"
    '    };\n'
    "    window.addEventListener('scroll', onScroll, { passive: true });\n"
    '    onScroll();\n'
    '  })();\n'
    '\n'
    '  // Scroll-reveal: fade elements in when they enter the viewport\n'
    '  (function() {\n'
    "    var els = document.querySelectorAll('[data-reveal]');\n"
    "    if (!('IntersectionObserver' in window) || !els.length) {\n"
    "      els.forEach(function(el) { el.classList.add('is-visible'); });\n"
    '      return;\n'
    '    }\n'
    '    var io = new IntersectionObserver(function(entries) {\n'
    '      entries.forEach(function(entry) {\n'
    '        if (entry.isIntersecting) {\n'
    "          entry.target.classList.add('is-visible');\n"
    '          io.unobserve(entry.target);\n'
    '        }\n'
    '      });\n'
    '    }, { threshold: 0.12 });\n'
    '    els.forEach(function(el) { io.observe(el); });\n'
    '  })();\n'
    '</script>'
)


def render_footer(ctx: Dict) -> str:
    # NOTE: the original function had a docstring; its text is not recoverable from the disassembly.
    c = ctx["company"]
    content = ctx["content"]
    year = datetime.now().year
    phone_display = format_phone_display(c["phone"])
    phone_tel = phone_tel_value(c["phone"])
    variant = (ctx.get("variants") or {}).get("footer", "dark-3col")
    fb_app_id = (ctx.get("fb_app_id") or "").strip()
    fb_sdk = ""
    if fb_app_id:
        fb_sdk = (
            '\n'
            '<div id="fb-root"></div>\n'
            '<script async defer crossorigin="anonymous" src="https://connect.facebook.net/en_US/sdk.js"></script>\n'
            '<script>\n'
            '  window.fbAsyncInit = function() {\n'
            f"    FB.init({{ appId: '{fb_app_id}', cookie: true, xfbml: true, version: 'v18.0' }});\n"
            '  };\n'
            '</script>'
        )
    if variant == "minimal-band":
        phone_icon = icon("phone", "w-4 h-4 text-brand")
        mail_icon = icon("mail", "w-4 h-4 text-brand")
        pin_icon = icon("pin", "w-4 h-4 text-brand")
        # QLBM: shown only for a verified business email
        email_link = (
            f'        <a href="mailto:{c["email"]}" class="flex items-center gap-2 hover:text-white" itemprop="email">{mail_icon}<span>{c["email"]}</span></a>\n'
        ) if c["email"] else ""
        return (
            f'{fb_sdk}\n'
            '<footer class="bg-gray-900 text-gray-300 mt-24" itemscope itemtype="https://schema.org/LocalBusiness">\n'
            f'  <meta itemprop="name" content="{c["company"]}">\n'
            f'  <meta itemprop="url" content="https://{c["domain"]}/">\n'
            '  <div class="max-w-6xl mx-auto px-6 py-10 grid md:grid-cols-2 gap-6 items-start">\n'
            '    <div>\n'
            f'      <h3 class="font-heading font-semibold text-white text-lg mb-2">{c["company"]}</h3>\n'
            f'      <p class="text-xs text-gray-500 mb-4">{c["domain"]}</p>\n'
            '      <div class="space-y-2 text-sm">\n'
            f'        <div class="flex items-start gap-2" itemprop="address" itemscope itemtype="https://schema.org/PostalAddress">{pin_icon}<span itemprop="streetAddress">{c["address"]}</span></div>\n'
            f'        <a href="tel:{phone_tel}" class="flex items-center gap-2 hover:text-white" itemprop="telephone" content="{c["phone"]}">{phone_icon}<span>{phone_display}</span></a>\n'
            f'{email_link}'
            '      </div>\n'
            '    </div>\n'
            '    <nav class="flex flex-wrap gap-4 text-xs uppercase tracking-wider text-gray-400 md:justify-end">\n'
            '      <a href="index.html" class="hover:text-white">Home</a>\n'
            '      <a href="about.html" class="hover:text-white">About</a>\n'
            '      <a href="faq.html" class="hover:text-white">FAQ</a>\n'
            '      <a href="contact.html" class="hover:text-white">Contact</a>\n'
            '      <a href="privacy.html" class="hover:text-white">Privacy</a>\n'
            '      <a href="terms.html" class="hover:text-white">Terms</a>\n'
            '    </nav>\n'
            '  </div>\n'
            f'  <div class="border-t border-gray-800 text-xs text-gray-500 text-center py-4">&copy; {year} {c["company"]}. All rights reserved.</div>\n'
            '</footer>\n'
            f'{_FOOTER_SCRIPT}'
        )
    if variant == "light-3col":
        phone_icon = icon("phone", "w-4 h-4 text-brand")
        mail_icon = icon("mail", "w-4 h-4 text-brand")
        pin_icon = icon("pin", "w-4 h-4 text-brand mt-0.5")
        # QLBM: shown only for a verified business email
        email_li = (
            f'        <li class="flex items-center gap-2">{mail_icon}<a href="mailto:{c["email"]}" class="hover:text-brand" itemprop="email">{c["email"]}</a></li>\n'
        ) if c["email"] else ""
        return (
            f'{fb_sdk}\n'
            '<footer class="bg-gray-50 text-gray-700 border-t border-gray-200 mt-24" itemscope itemtype="https://schema.org/LocalBusiness">\n'
            f'  <meta itemprop="name" content="{c["company"]}">\n'
            f'  <meta itemprop="url" content="https://{c["domain"]}/">\n'
            '  <div class="max-w-6xl mx-auto px-6 py-14 grid md:grid-cols-3 gap-10">\n'
            '    <div>\n'
            f'      <h3 class="font-heading font-semibold text-gray-900 text-lg mb-3">{c["company"]}</h3>\n'
            f'      <p class="text-sm text-gray-600 leading-relaxed mb-4">{content["footer_blurb"]}</p>\n'
            f'      <p class="text-xs text-gray-500">{c["domain"]}</p>\n'
            '    </div>\n'
            '    <div>\n'
            '      <h4 class="font-heading font-semibold text-gray-900 mb-4 text-sm uppercase tracking-wider">Contact</h4>\n'
            '      <ul class="text-sm space-y-3">\n'
            f'        <li class="flex items-start gap-2" itemprop="address" itemscope itemtype="https://schema.org/PostalAddress">{pin_icon}<span itemprop="streetAddress">{c["address"]}</span></li>\n'
            f'        <li class="flex items-center gap-2">{phone_icon}<a href="tel:{phone_tel}" class="hover:text-brand" itemprop="telephone" content="{c["phone"]}">{phone_display}</a></li>\n'
            f'{email_li}'
            '      </ul>\n'
            '    </div>\n'
            '    <div>\n'
            '      <h4 class="font-heading font-semibold text-gray-900 mb-4 text-sm uppercase tracking-wider">Quick Links</h4>\n'
            '      <ul class="text-sm space-y-2">\n'
            '        <li><a href="index.html" class="hover:text-brand">Home</a></li>\n'
            '        <li><a href="about.html" class="hover:text-brand">About Us</a></li>\n'
            '        <li><a href="faq.html" class="hover:text-brand">FAQ</a></li>\n'
            '        <li><a href="contact.html" class="hover:text-brand">Contact</a></li>\n'
            '        <li><a href="privacy.html" class="hover:text-brand">Privacy Policy</a></li>\n'
            '        <li><a href="terms.html" class="hover:text-brand">Terms of Service</a></li>\n'
            '      </ul>\n'
            '    </div>\n'
            '  </div>\n'
            '  <div class="border-t border-gray-200">\n'
            '    <div class="max-w-6xl mx-auto px-6 py-5 text-xs text-gray-500 flex flex-col md:flex-row justify-between gap-2">\n'
            f'      <span>&copy; {year} {c["company"]}. All rights reserved.</span>\n'
            f'      <span>{c["domain"]}</span>\n'
            '    </div>\n'
            '  </div>\n'
            '</footer>\n'
            f'{_FOOTER_SCRIPT}'
        )
    phone_icon = icon("phone", "w-4 h-4 text-brand")
    mail_icon = icon("mail", "w-4 h-4 text-brand")
    pin_icon = icon("pin", "w-4 h-4 text-brand mt-0.5")
    services_col = ""
    if variant == "dark-4col":
        service_titles = [s["title"] for s in (content.get("services") or [])][:5]
        if service_titles:
            items = "".join(f'<li class="hover:text-white transition cursor-default">{t}</li>' for t in service_titles)
            services_col = (
            '\n'
            '    <div>\n'
            '      <h4 class="font-heading font-semibold text-white mb-4 text-sm uppercase tracking-wider">Services</h4>\n'
            '      <ul class="text-sm space-y-2 text-gray-400">\n'
            f'        {items}\n'
            '      </ul>\n'
            '    </div>'
        )
    grid_cols = "md:grid-cols-4" if services_col else "md:grid-cols-3"
    # QLBM: shown only for a verified business email
    email_li = (
            '        <li class="flex items-center gap-2">\n'
            f'          {mail_icon}<a href="mailto:{c["email"]}" class="hover:text-white" itemprop="email">{c["email"]}</a>\n'
            '        </li>\n'
    ) if c["email"] else ""
    return (
            f'{fb_sdk}\n'
            '<footer class="bg-gray-900 text-gray-300 mt-24" itemscope itemtype="https://schema.org/LocalBusiness">\n'
            f'  <meta itemprop="name" content="{c["company"]}">\n'
            f'  <meta itemprop="url" content="https://{c["domain"]}/">\n'
            f'  <div class="max-w-6xl mx-auto px-6 py-14 grid {grid_cols} gap-10">\n'
            '    <div>\n'
            f'      <h3 class="font-heading font-semibold text-white text-lg mb-3">{c["company"]}</h3>\n'
            f'      <p class="text-sm text-gray-400 leading-relaxed mb-4">{content["footer_blurb"]}</p>\n'
            f'      <p class="text-xs text-gray-500">{c["domain"]}</p>\n'
            '    </div>\n'
            '    <div>\n'
            '      <h4 class="font-heading font-semibold text-white mb-4 text-sm uppercase tracking-wider">Contact</h4>\n'
            '      <ul class="text-sm space-y-3 text-gray-400">\n'
            '        <li class="flex items-start gap-2" itemprop="address" itemscope itemtype="https://schema.org/PostalAddress">\n'
            f'          {pin_icon}<span itemprop="streetAddress">{c["address"]}</span>\n'
            '        </li>\n'
            '        <li class="flex items-center gap-2">\n'
            f'          {phone_icon}<a href="tel:{phone_tel}" class="hover:text-white" itemprop="telephone" content="{c["phone"]}">{phone_display}</a>\n'
            '        </li>\n'
            f'{email_li}'
            '      </ul>\n'
            f'    </div>{services_col}\n'
            '    <div>\n'
            '      <h4 class="font-heading font-semibold text-white mb-4 text-sm uppercase tracking-wider">Quick Links</h4>\n'
            '      <ul class="text-sm space-y-2 text-gray-400">\n'
            '        <li><a href="index.html" class="hover:text-white">Home</a></li>\n'
            '        <li><a href="about.html" class="hover:text-white">About Us</a></li>\n'
            '        <li><a href="faq.html" class="hover:text-white">FAQ</a></li>\n'
            '        <li><a href="contact.html" class="hover:text-white">Contact</a></li>\n'
            '        <li><a href="privacy.html" class="hover:text-white">Privacy Policy</a></li>\n'
            '        <li><a href="terms.html" class="hover:text-white">Terms of Service</a></li>\n'
            '      </ul>\n'
            '    </div>\n'
            '  </div>\n'
            '  <div class="border-t border-gray-800">\n'
            '    <div class="max-w-6xl mx-auto px-6 py-5 text-xs text-gray-500 flex flex-col md:flex-row justify-between gap-2">\n'
            f'      <span>&copy; {year} {c["company"]}. All rights reserved.</span>\n'
            f'      <span>{c["domain"]}</span>\n'
            '    </div>\n'
            '  </div>\n'
            '</footer>\n'
            f'{_FOOTER_SCRIPT}'
        )
