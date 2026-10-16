"""
home.py
=======
Render the Home page (index.html).
"""

from typing import Dict

from .base import (
    render_head, render_header, render_footer, icon, photo_url, SERVICE_ICON_KEYS, VALUE_ICON_KEYS,
)


def _render_hero(ctx: Dict) -> str:
    c = ctx["company"]
    co = ctx["content"]
    layout = ctx["hero_layout"]
    radius = ctx.get("btn_radius", "rounded-lg")
    arrow = icon("arrow_right", "w-4 h-4 inline-block ml-1")
    primary_cta = (
        f'<a href="contact.html" class="inline-flex items-center bg-brand hover:bg-brand-dark text-white font-medium px-7 py-3.5 {radius} transition shadow-sm">\n'
        f'      {co["primary_cta"]} {arrow}\n'
        '    </a>'
    )
    secondary_cta = (
        '<a href="about.html" class="inline-flex items-center text-gray-700 hover:text-brand font-medium px-5 py-3.5 transition">\n'
        '      Learn More &rarr;\n'
        '    </a>'
    )

    if layout == "centered":
        hero_bg = photo_url(ctx, 1920, 1080, "hero_bg")
        return (
            '\n'
            '    <section class="relative overflow-hidden">\n'
            '      <div class="absolute inset-0">\n'
            f'        <img src="{hero_bg}" alt="" class="w-full h-full object-cover">\n'
            '        <div class="absolute inset-0 bg-gradient-to-br from-white/95 via-white/85 to-brand-soft/90"></div>\n'
            '      </div>\n'
            '      <div class="hero-dots absolute inset-0 opacity-30"></div>\n'
            '      <div class="relative max-w-4xl mx-auto px-6 py-24 md:py-32 text-center">\n'
            '        <span data-reveal class="inline-block bg-white/80 backdrop-blur text-brand text-xs font-semibold tracking-wider uppercase px-3 py-1.5 rounded-full mb-6 border border-brand/10 shadow-sm">\n'
            f'          {c["company"]}\n'
            '        </span>\n'
            '        <h1 data-reveal class="font-heading text-4xl md:text-6xl font-bold text-gray-900 mb-6 leading-[1.1]">\n'
            f'          {co["tagline"]}\n'
            '        </h1>\n'
            f'        <p data-reveal class="text-lg md:text-xl text-gray-700 mb-10 max-w-2xl mx-auto leading-relaxed">{co["hero_subtitle"]}</p>\n'
            '        <div data-reveal class="flex flex-wrap items-center justify-center gap-3">\n'
            f'          {primary_cta}\n'
            f'          {secondary_cta}\n'
            '        </div>\n'
            '      </div>\n'
            '    </section>'
        )

    if layout == "minimal":
        return (
            '\n'
            '    <section class="relative bg-gradient-to-br from-brand-soft via-white to-brand-soft/40 overflow-hidden">\n'
            '      <div class="hero-dots absolute inset-0 opacity-25"></div>\n'
            '      <div class="absolute -top-32 -right-32 w-[480px] h-[480px] rounded-full bg-brand/15 blur-3xl"></div>\n'
            '      <div class="absolute -bottom-32 -left-32 w-[480px] h-[480px] rounded-full bg-brand/10 blur-3xl"></div>\n'
            '      <div class="relative max-w-3xl mx-auto px-6 py-28 md:py-36 text-center">\n'
            f'        <span data-reveal class="inline-block bg-white text-brand text-xs font-semibold tracking-[0.2em] uppercase px-4 py-2 {radius} mb-8 border border-brand/15 shadow-sm">\n'
            f'          {c["company"]}\n'
            '        </span>\n'
            '        <h1 data-reveal class="font-heading text-5xl md:text-7xl font-bold text-gray-900 mb-7 leading-[1.05] tracking-tight">\n'
            f'          {co["tagline"]}\n'
            '        </h1>\n'
            f'        <p data-reveal class="text-lg md:text-xl text-gray-600 mb-12 leading-relaxed">{co["hero_subtitle"]}</p>\n'
            '        <div data-reveal class="flex flex-wrap items-center justify-center gap-3">\n'
            f'          {primary_cta}\n'
            f'          {secondary_cta}\n'
            '        </div>\n'
            '      </div>\n'
            '    </section>'
        )

    if layout == "stacked-cards":
        hero_img = photo_url(ctx, 900, 800, "hero")
        return (
            '\n'
            '    <section class="relative bg-gray-50 overflow-hidden">\n'
            '      <div class="hero-dots absolute inset-0 opacity-30"></div>\n'
            '      <div class="relative max-w-6xl mx-auto px-6 py-20 md:py-24 grid md:grid-cols-2 gap-12 items-center">\n'
            '        <div data-reveal>\n'
            f'          <span class="inline-block bg-brand/10 text-brand text-xs font-semibold tracking-wider uppercase px-3 py-1.5 {radius} mb-5">\n'
            f'            {c["company"]}\n'
            '          </span>\n'
            '          <h1 class="font-heading text-4xl md:text-5xl lg:text-6xl font-bold text-gray-900 mb-5 leading-[1.08]">\n'
            f'            {co["tagline"]}\n'
            '          </h1>\n'
            f'          <p class="text-lg text-gray-700 mb-8 leading-relaxed">{co["hero_subtitle"]}</p>\n'
            '          <div class="flex flex-wrap items-center gap-3 mb-10">\n'
            f'            {primary_cta}\n'
            f'            {secondary_cta}\n'
            '          </div>\n'
            # QLBM: removed the “100% / 24/7 / A+” stat row (no source for these claims)
            '        </div>\n'
            '        <div data-reveal class="relative">\n'
            f'          <div class="aspect-[4/5] {radius} overflow-hidden shadow-2xl">\n'
            f'            <img src="{hero_img}" alt="{c["company"]}" class="w-full h-full object-cover">\n'
            '          </div>\n'
            # QLBM: removed the “Trusted Service” floating badge
            '        </div>\n'
            '      </div>\n'
            '    </section>'
        )

    if layout == "image-banner":
        hero_bg = photo_url(ctx, 1920, 1080, "hero_bg")
        return (
            '\n'
            '    <section class="relative overflow-hidden">\n'
            '      <div class="absolute inset-0">\n'
            f'        <img src="{hero_bg}" alt="" class="w-full h-full object-cover">\n'
            '        <div class="absolute inset-0 bg-gradient-to-r from-gray-900/80 via-gray-900/60 to-transparent"></div>\n'
            '      </div>\n'
            '      <div class="relative max-w-6xl mx-auto px-6 py-28 md:py-40">\n'
            '        <div class="max-w-2xl">\n'
            f'          <span data-reveal class="inline-block bg-white/15 backdrop-blur text-white text-xs font-semibold tracking-wider uppercase px-3 py-1.5 {radius} mb-6 border border-white/20">\n'
            f'            {c["company"]}\n'
            '          </span>\n'
            '          <h1 data-reveal class="font-heading text-4xl md:text-6xl font-bold text-white mb-6 leading-[1.08] drop-shadow">\n'
            f'            {co["tagline"]}\n'
            '          </h1>\n'
            f'          <p data-reveal class="text-lg md:text-xl text-white/90 mb-10 leading-relaxed">{co["hero_subtitle"]}</p>\n'
            '          <div data-reveal class="flex flex-wrap items-center gap-3">\n'
            f'            {primary_cta}\n'
            '            <a href="about.html" class="inline-flex items-center text-white hover:text-white/80 font-medium px-5 py-3.5 transition">Learn More &rarr;</a>\n'
            '          </div>\n'
            '        </div>\n'
            '      </div>\n'
            '    </section>'
        )

    # split-left / split-right
    flex_dir = "md:flex-row" if layout == "split-left" else "md:flex-row-reverse"
    hero_img = photo_url(ctx, 900, 700, "hero")
    return (
        '\n'
        '    <section class="relative bg-brand-soft hero-blob overflow-hidden">\n'
        '      <div class="hero-dots absolute inset-0 opacity-50"></div>\n'
        f'      <div class="relative max-w-6xl mx-auto px-6 py-20 md:py-28 flex flex-col {flex_dir} items-center gap-12">\n'
        '        <div class="flex-1" data-reveal>\n'
        f'          <span class="inline-block bg-white/70 backdrop-blur text-brand text-xs font-semibold tracking-wider uppercase px-3 py-1.5 {radius} mb-6 border border-brand/10">\n'
        f'            {c["company"]}\n'
        '          </span>\n'
        '          <h1 class="font-heading text-4xl md:text-5xl lg:text-6xl font-bold text-gray-900 mb-5 leading-[1.1]">\n'
        f'            {co["tagline"]}\n'
        '          </h1>\n'
        f'          <p class="text-lg text-gray-700 mb-8 leading-relaxed">{co["hero_subtitle"]}</p>\n'
        '          <div class="flex flex-wrap items-center gap-3">\n'
        f'            {primary_cta}\n'
        f'            {secondary_cta}\n'
        '          </div>\n'
        '        </div>\n'
        '        <div class="flex-1 w-full" data-reveal>\n'
        '          <div class="relative">\n'
        f'            <div class="absolute -inset-4 bg-brand/15 {radius} blur-2xl"></div>\n'
        f'            <div class="relative aspect-[4/3] {radius} overflow-hidden shadow-2xl border-4 border-white">\n'
        f'              <img src="{hero_img}" alt="{c["company"]}" class="w-full h-full object-cover">\n'
        '            </div>\n'
        # QLBM: removed the “Trusted by / Our customers” badge
        '          </div>\n'
        '        </div>\n'
        '      </div>\n'
        '    </section>'
    )


def _render_trust_strip(ctx: Dict = None) -> str:
    radius = (ctx or {}).get("btn_radius", "rounded-lg") if ctx else "rounded-lg"
    variant = ((ctx or {}).get("variants") or {}).get("trust_strip", "icons")

    if variant == "stats":
        stats = [("100%", "Commitment"), ("24/7", "Always Available"), ("A+", "Quality Standard"), ("On-time", "Every Project")]
        cells = "".join((
            '\n'
            '        <div class="text-center" data-reveal>\n'
            f'          <p class="font-heading text-3xl md:text-4xl font-extrabold text-brand mb-1">{label}</p>\n'
            f'          <p class="text-xs text-gray-500 uppercase tracking-wider font-semibold">{sub}</p>\n'
            '        </div>'
        ) for label, sub in stats)
        return (
            '\n'
            '  <section class="border-y border-gray-100 bg-brand-soft/40">\n'
            f'    <div class="max-w-6xl mx-auto px-6 py-10 grid grid-cols-2 md:grid-cols-4 gap-6">{cells}\n'
            '    </div>\n'
            '  </section>'
        )

    if variant == "logos":
        words = ["Reliable", "Professional", "Responsive", "Trusted", "Quality"]
        cells = "".join((
            f'<span class="font-heading text-gray-400 hover:text-brand transition text-sm md:text-base uppercase tracking-[0.2em] font-semibold" data-reveal>{w}</span>'
        ) for w in words)
        return (
            '\n'
            '  <section class="border-y border-gray-100 bg-white">\n'
            '    <div class="max-w-6xl mx-auto px-6 py-8">\n'
            '      <p class="text-center text-xs uppercase tracking-[0.25em] text-gray-400 mb-5 font-semibold" data-reveal>What we stand for</p>\n'
            f'      <div class="flex flex-wrap items-center justify-center gap-x-10 gap-y-3">{cells}</div>\n'
            '    </div>\n'
            '  </section>'
        )

    items = [
        ("shield", "Professional Service", "Reliable and consistent"),
        ("users", "Customer Focused", "Built around your needs"),
        ("clock", "Responsive", "We reply quickly"),
        ("check", "Quality First", "Standards we stand behind"),
    ]
    cells = ""
    for ikey, title, sub in items:
        cells += (
            '\n'
            '        <div class="flex items-start gap-3" data-reveal>\n'
            f'          <div class="flex-shrink-0 w-10 h-10 {radius} bg-brand-soft text-brand flex items-center justify-center">\n'
            f'            {icon(ikey, "w-5 h-5")}\n'
            '          </div>\n'
            '          <div>\n'
            f'            <p class="font-heading font-semibold text-gray-900 text-sm">{title}</p>\n'
            f'            <p class="text-xs text-gray-500 mt-0.5">{sub}</p>\n'
            '          </div>\n'
            '        </div>'
        )
    return (
        '\n'
        '  <section class="border-y border-gray-100 bg-white">\n'
        f'    <div class="max-w-6xl mx-auto px-6 py-8 grid grid-cols-2 md:grid-cols-4 gap-6">{cells}\n'
        '    </div>\n'
        '  </section>'
    )


def _render_about_preview(ctx: Dict) -> str:
    # NOTE: the original function had a docstring; its text is not recoverable from the disassembly.
    co = ctx["content"]
    company = ctx["company"]["company"]
    img = photo_url(ctx, 800, 700, "about_preview")
    variant = (ctx.get("variants") or {}).get("about_preview", "left")
    radius = ctx.get("btn_radius", "rounded-lg")

    if variant == "stacked":
        return (
            '\n'
            '  <section class="relative py-24 overflow-hidden">\n'
            '    <div class="absolute inset-0">\n'
            f'      <img src="{img}" alt="" class="w-full h-full object-cover" loading="lazy">\n'
            '      <div class="absolute inset-0 bg-gradient-to-b from-white via-white/60 to-white"></div>\n'
            '    </div>\n'
            '    <div class="relative max-w-3xl mx-auto px-6 text-center" data-reveal>\n'
            '      <span class="inline-block text-brand text-xs font-semibold tracking-[0.2em] uppercase mb-4">About Our Business</span>\n'
            '      <h2 class="font-heading text-3xl md:text-5xl font-bold text-gray-900 mb-6 leading-[1.1]">A team you can rely on.</h2>\n'
            f'      <p class="text-lg text-gray-700 leading-relaxed mb-5">{co["intro_paragraph"]}</p>\n'
            f'      <p class="text-gray-600 leading-relaxed mb-8">{co["about_short"]}</p>\n'
            f'      <a href="about.html" class="inline-flex items-center bg-brand hover:bg-brand-dark text-white font-medium px-6 py-3 {radius} transition shadow-sm">\n'
            '        Read our full story <span class="ml-2">&rarr;</span>\n'
            '      </a>\n'
            '    </div>\n'
            '  </section>'
        )

    if variant == "framed":
        return (
            '\n'
            '  <section class="py-20 bg-brand-soft/50">\n'
            '    <div class="max-w-6xl mx-auto px-6 grid md:grid-cols-2 gap-10 items-stretch">\n'
            f'      <div data-reveal class="bg-white {radius} shadow-lg overflow-hidden border border-gray-100">\n'
            f'        <img src="{img}" alt="" loading="lazy" class="w-full h-full object-cover aspect-[4/3]">\n'
            '      </div>\n'
            f'      <div data-reveal class="bg-white {radius} shadow-lg border border-gray-100 p-8 md:p-12 flex flex-col justify-center">\n'
            '        <span class="inline-block text-brand text-xs font-semibold tracking-wider uppercase mb-3">About Our Business</span>\n'
            '        <h2 class="font-heading text-3xl md:text-4xl font-bold text-gray-900 mb-5 leading-[1.15]">A team you can rely on.</h2>\n'
            f'        <p class="text-lg text-gray-700 leading-relaxed mb-4">{co["intro_paragraph"]}</p>\n'
            f'        <p class="text-gray-600 leading-relaxed mb-6">{co["about_short"]}</p>\n'
            '        <a href="about.html" class="inline-flex items-center text-brand font-medium hover:text-brand-dark group">\n'
            '          Read our full story\n'
            '          <span class="ml-1 transition group-hover:translate-x-1">&rarr;</span>\n'
            '        </a>\n'
            '      </div>\n'
            '    </div>\n'
            '  </section>'
        )

    flip = "md:flex-row-reverse" if variant == "right" else "md:flex-row"
    badge_corner = "-left-5" if variant == "right" else "-right-5"
    img_block = (
        '\n'
        '        <div data-reveal class="relative flex-1 w-full">\n'
        '          <div class="absolute -inset-3 bg-brand/10 rounded-3xl blur-xl"></div>\n'
        f'          <img src="{img}" alt="" loading="lazy"\n'
        f'               class="relative w-full aspect-[5/4] object-cover {radius} shadow-lg border-4 border-white">\n'
        f'          <div class="absolute -bottom-5 {badge_corner} bg-brand text-white {radius} shadow-xl px-5 py-4 hidden sm:block">\n'
        '            <p class="text-xs uppercase tracking-wider font-semibold text-white/80">About Us</p>\n'
        f'            <p class="font-heading font-bold text-lg">{company[:30]}</p>\n'
        '          </div>\n'
        '        </div>'
    )
    text_block = (
        '\n'
        '        <div data-reveal class="flex-1 w-full">\n'
        '          <span class="inline-block text-brand text-xs font-semibold tracking-wider uppercase mb-3">About Our Business</span>\n'
        '          <h2 class="font-heading text-3xl md:text-4xl font-bold text-gray-900 mb-5 leading-[1.15]">A team you can rely on.</h2>\n'
        f'          <p class="text-lg text-gray-700 leading-relaxed mb-5">{co["intro_paragraph"]}</p>\n'
        f'          <p class="text-gray-600 leading-relaxed mb-7">{co["about_short"]}</p>\n'
        '          <a href="about.html" class="inline-flex items-center text-brand font-medium hover:text-brand-dark group">\n'
        '            Read our full story\n'
        '            <span class="ml-1 transition group-hover:translate-x-1">&rarr;</span>\n'
        '          </a>\n'
        '        </div>'
    )
    return (
        '\n'
        '  <section class="py-20">\n'
        f'    <div class="max-w-6xl mx-auto px-6 flex flex-col {flip} gap-12 items-center">\n'
        f'      {img_block}\n'
        f'      {text_block}\n'
        '    </div>\n'
        '  </section>'
    )


def _render_services(ctx: Dict) -> str:
    co = ctx["content"]
    variant = (ctx.get("variants") or {}).get("services", "photo")
    radius = ctx.get("btn_radius", "rounded-lg")
    cards = ""

    if variant == "alternating":
        rows = ""
        for i, svc in enumerate(co["services"]):
            photo = photo_url(ctx, 600, 400, f"service_{i + 1}")
            flip = "md:flex-row-reverse" if i % 2 else "md:flex-row"
            rows += (
                '\n'
                f'        <div data-reveal class="flex flex-col {flip} gap-8 md:gap-12 items-center">\n'
                '          <div class="flex-1 w-full">\n'
                f'            <div class="aspect-[5/3] {radius} overflow-hidden shadow-lg">\n'
                f'              <img src="{photo}" alt="" loading="lazy" class="w-full h-full object-cover">\n'
                '            </div>\n'
                '          </div>\n'
                '          <div class="flex-1 w-full">\n'
                f'            <p class="text-brand text-xs font-semibold tracking-wider uppercase mb-2">Service {i + 1:02d}</p>\n'
                f'            <h3 class="font-heading text-2xl md:text-3xl font-bold text-gray-900 mb-3">{svc["title"]}</h3>\n'
                f'            <p class="text-gray-600 leading-relaxed">{svc["description"]}</p>\n'
                '          </div>\n'
                '        </div>'
            )
        return (
            '\n'
            '  <section class="py-20 bg-white">\n'
            '    <div class="max-w-6xl mx-auto px-6">\n'
            '      <div class="text-center max-w-2xl mx-auto mb-14" data-reveal>\n'
            '        <span class="inline-block text-brand text-xs font-semibold tracking-wider uppercase mb-3">What We Offer</span>\n'
            '        <h2 class="font-heading text-3xl md:text-4xl font-bold text-gray-900 mb-4">Services Built Around You</h2>\n'
            '        <p class="text-gray-600">Practical, end-to-end services designed to fit your day-to-day operations.</p>\n'
            '      </div>\n'
            f'      <div class="space-y-16">{rows}\n'
            '      </div>\n'
            '    </div>\n'
            '  </section>'
        )

    for i, svc in enumerate(co["services"]):
        ikey = SERVICE_ICON_KEYS[i % len(SERVICE_ICON_KEYS)]
        if variant == "minimal":
            cards += (
                '\n'
                f'        <div data-reveal class="card-lift bg-white border border-gray-200 {radius} p-8 text-center">\n'
                f'          <div class="w-16 h-16 mx-auto {radius} bg-brand-soft text-brand flex items-center justify-center mb-5">\n'
                f'            {icon(ikey, "w-8 h-8")}\n'
                '          </div>\n'
                f'          <h3 class="font-heading font-semibold text-lg text-gray-900 mb-2">{svc["title"]}</h3>\n'
                f'          <p class="text-gray-600 text-sm leading-relaxed">{svc["description"]}</p>\n'
                '        </div>'
            )
        elif variant == "numbered":
            cards += (
                '\n'
                f'        <div data-reveal class="card-lift bg-white border-l-4 border-brand {radius} shadow-sm p-7">\n'
                f'          <p class="font-heading text-5xl font-extrabold text-brand/20 mb-3">{i + 1:02d}</p>\n'
                f'          <h3 class="font-heading font-semibold text-lg text-gray-900 mb-2">{svc["title"]}</h3>\n'
                f'          <p class="text-gray-600 text-sm leading-relaxed">{svc["description"]}</p>\n'
                '        </div>'
            )
        else:
            photo = photo_url(ctx, 600, 400, f"service_{i + 1}")
            cards += (
                '\n'
                f'        <div data-reveal class="card-lift bg-white border border-gray-200 {radius} overflow-hidden">\n'
                '          <div class="relative aspect-[3/2] bg-gray-100 overflow-hidden">\n'
                f'            <img src="{photo}" alt="" loading="lazy" class="w-full h-full object-cover">\n'
                f'            <div class="absolute bottom-3 left-3 w-11 h-11 {radius} bg-white/95 backdrop-blur text-brand flex items-center justify-center shadow-md">\n'
                f'              {icon(ikey, "w-5 h-5")}\n'
                '            </div>\n'
                '          </div>\n'
                '          <div class="p-6">\n'
                f'            <h3 class="font-heading font-semibold text-lg text-gray-900 mb-2">{svc["title"]}</h3>\n'
                f'            <p class="text-gray-600 text-sm leading-relaxed">{svc["description"]}</p>\n'
                '          </div>\n'
                '        </div>'
            )
    bg = "bg-gray-50" if variant in ("photo", "numbered") else "bg-white"
    return (
        '\n'
        f'  <section class="py-20 {bg}">\n'
        '    <div class="max-w-6xl mx-auto px-6">\n'
        '      <div class="text-center max-w-2xl mx-auto mb-14" data-reveal>\n'
        '        <span class="inline-block text-brand text-xs font-semibold tracking-wider uppercase mb-3">What We Offer</span>\n'
        '        <h2 class="font-heading text-3xl md:text-4xl font-bold text-gray-900 mb-4">Services Built Around You</h2>\n'
        '        <p class="text-gray-600">Practical, end-to-end services designed to fit your day-to-day operations.</p>\n'
        '      </div>\n'
        f'      <div class="grid md:grid-cols-3 gap-6">{cards}\n'
        '      </div>\n'
        '    </div>\n'
        '  </section>'
    )


def _render_gallery(ctx: Dict) -> str:
    photos = [photo_url(ctx, 600, 600, f"gallery_{i + 1}") for i in range(6)]
    variant = (ctx.get("variants") or {}).get("gallery", "asymmetric")
    radius = ctx.get("btn_radius", "rounded-lg")
    header = (
        '\n'
        '      <div class="text-center max-w-2xl mx-auto mb-14" data-reveal>\n'
        '        <span class="inline-block text-brand text-xs font-semibold tracking-wider uppercase mb-3">Gallery</span>\n'
        '        <h2 class="font-heading text-3xl md:text-4xl font-bold text-gray-900 mb-4">A Look at Our Work</h2>\n'
        '        <p class="text-gray-600">A few moments from our day-to-day operations.</p>\n'
        '      </div>'
    )

    if variant == "masonry":
        cols = ["", "", ""]
        aspects = ["aspect-[4/5]", "aspect-square", "aspect-[3/4]", "aspect-square", "aspect-[4/5]", "aspect-[3/4]"]
        for i, p in enumerate(photos):
            cols[i % 3] += (
                '\n'
                f'        <div data-reveal class="{aspects[i]} overflow-hidden {radius}">\n'
                f'          <img src="{p}" alt="" loading="lazy" class="w-full h-full object-cover hover:scale-105 transition-transform duration-500">\n'
                '        </div>'
            )
        col_html = "".join(f'<div class="space-y-4">{c}</div>' for c in cols)
        return (
            '\n'
            '  <section class="py-20 bg-white">\n'
            f'    <div class="max-w-6xl mx-auto px-6">{header}\n'
            f'      <div class="grid grid-cols-2 md:grid-cols-3 gap-4">{col_html}\n'
            '      </div>\n'
            '    </div>\n'
            '  </section>'
        )

    if variant == "bento":
        return (
            '\n'
            '  <section class="py-20 bg-gray-50">\n'
            f'    <div class="max-w-6xl mx-auto px-6">{header}\n'
            '      <div class="grid grid-cols-4 grid-rows-3 gap-3 md:gap-4 h-[520px]">\n'
            f'        <div data-reveal class="col-span-2 row-span-2 overflow-hidden {radius}">\n'
            f'          <img src="{photos[0]}" alt="" loading="lazy" class="w-full h-full object-cover hover:scale-105 transition-transform duration-500">\n'
            '        </div>\n'
            f'        <div data-reveal class="col-span-2 row-span-1 overflow-hidden {radius}">\n'
            f'          <img src="{photos[1]}" alt="" loading="lazy" class="w-full h-full object-cover hover:scale-105 transition-transform duration-500">\n'
            '        </div>\n'
            f'        <div data-reveal class="overflow-hidden {radius}">\n'
            f'          <img src="{photos[2]}" alt="" loading="lazy" class="w-full h-full object-cover hover:scale-105 transition-transform duration-500">\n'
            '        </div>\n'
            f'        <div data-reveal class="overflow-hidden {radius}">\n'
            f'          <img src="{photos[3]}" alt="" loading="lazy" class="w-full h-full object-cover hover:scale-105 transition-transform duration-500">\n'
            '        </div>\n'
            f'        <div data-reveal class="col-span-2 overflow-hidden {radius}">\n'
            f'          <img src="{photos[4]}" alt="" loading="lazy" class="w-full h-full object-cover hover:scale-105 transition-transform duration-500">\n'
            '        </div>\n'
            '      </div>\n'
            '    </div>\n'
            '  </section>'
        )

    if variant == "row":
        cells = "".join((
            '\n'
            f'        <div data-reveal class="flex-shrink-0 w-72 aspect-[4/5] overflow-hidden {radius} snap-start">\n'
            f'          <img src="{p}" alt="" loading="lazy" class="w-full h-full object-cover hover:scale-105 transition-transform duration-500">\n'
            '        </div>'
        ) for p in photos)
        return (
            '\n'
            '  <section class="py-20 bg-white">\n'
            f'    <div class="max-w-6xl mx-auto px-6">{header}\n'
            f'      <div class="flex gap-4 overflow-x-auto snap-x pb-4 -mx-6 px-6">{cells}\n'
            '      </div>\n'
            '    </div>\n'
            '  </section>'
        )

    return (
        '\n'
        '  <section class="py-20 bg-white">\n'
        f'    <div class="max-w-6xl mx-auto px-6">{header}\n'
        '      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">\n'
        f'        <div data-reveal class="md:col-span-2 md:row-span-2 aspect-square md:aspect-auto overflow-hidden {radius}">\n'
        f'          <img src="{photos[0]}" alt="" loading="lazy" class="w-full h-full object-cover hover:scale-105 transition-transform duration-500">\n'
        '        </div>\n'
        f'        <div data-reveal class="aspect-square overflow-hidden {radius}">\n'
        f'          <img src="{photos[1]}" alt="" loading="lazy" class="w-full h-full object-cover hover:scale-105 transition-transform duration-500">\n'
        '        </div>\n'
        f'        <div data-reveal class="aspect-square overflow-hidden {radius}">\n'
        f'          <img src="{photos[2]}" alt="" loading="lazy" class="w-full h-full object-cover hover:scale-105 transition-transform duration-500">\n'
        '        </div>\n'
        f'        <div data-reveal class="aspect-square overflow-hidden {radius}">\n'
        f'          <img src="{photos[3]}" alt="" loading="lazy" class="w-full h-full object-cover hover:scale-105 transition-transform duration-500">\n'
        '        </div>\n'
        f'        <div data-reveal class="aspect-square overflow-hidden {radius}">\n'
        f'          <img src="{photos[4]}" alt="" loading="lazy" class="w-full h-full object-cover hover:scale-105 transition-transform duration-500">\n'
        '        </div>\n'
        '      </div>\n'
        '    </div>\n'
        '  </section>'
    )


def _render_process(ctx: Dict = None) -> str:
    variant = ((ctx or {}).get("variants") or {}).get("process", "numbered-grid")
    radius = (ctx or {}).get("btn_radius", "rounded-lg") if ctx else "rounded-lg"
    steps = [
        ("01", "Reach Out", "Send us a message or give us a call to start the conversation."),
        ("02", "Discuss Your Needs", "We listen carefully and ask the right questions to understand the work."),
        ("03", "Delivery", "Our team handles the work professionally and keeps you informed along the way."),
        ("04", "Ongoing Support", "We stay available after the work is done to answer questions and help."),
    ]
    header = (
        '\n'
        '      <div class="text-center max-w-2xl mx-auto mb-14" data-reveal>\n'
        '        <span class="inline-block text-brand text-xs font-semibold tracking-wider uppercase mb-3">How We Work</span>\n'
        '        <h2 class="font-heading text-3xl md:text-4xl font-bold text-gray-900 mb-4">A Straightforward Process</h2>\n'
        '        <p class="text-gray-600">No surprises - just a clear path from first contact to ongoing support.</p>\n'
        '      </div>'
    )

    if variant == "timeline":
        rows = ""
        for num, title, desc in steps:
            rows += (
                '\n'
                '        <div data-reveal class="relative pl-14 pb-10 last:pb-0">\n'
                f'          <div class="absolute left-0 top-0 w-11 h-11 {radius} bg-brand text-white flex items-center justify-center font-heading font-bold">{num}</div>\n'
                '          <div class="absolute left-[21px] top-11 bottom-0 w-px bg-gray-200"></div>\n'
                f'          <h4 class="font-heading font-semibold text-gray-900 text-lg mb-2">{title}</h4>\n'
                f'          <p class="text-gray-600 leading-relaxed max-w-xl">{desc}</p>\n'
                '        </div>'
            )
        return (
            '\n'
            '  <section class="py-20">\n'
            f'    <div class="max-w-3xl mx-auto px-6">{header}\n'
            f'      <div class="relative">{rows}\n'
            '      </div>\n'
            '    </div>\n'
            '  </section>'
        )

    if variant == "stepper":
        cells = ""
        for i, (num, title, desc) in enumerate(steps):
            cells += (
                '\n'
                '        <div data-reveal class="relative flex-1">\n'
                '          <div class="flex items-center mb-4">\n'
                f'            <div class="w-12 h-12 {radius} bg-brand text-white flex items-center justify-center font-heading font-bold text-lg shadow-md z-10">{num}</div>\n'
                f'            {"<div class='flex-1 h-px bg-gray-200 hidden md:block'></div>" if i < 3 else ""}\n'
                '          </div>\n'
                f'          <h4 class="font-heading font-semibold text-gray-900 mb-2">{title}</h4>\n'
                f'          <p class="text-gray-600 text-sm leading-relaxed">{desc}</p>\n'
                '        </div>'
            )
        return (
            '\n'
            '  <section class="py-20 bg-gray-50">\n'
            f'    <div class="max-w-6xl mx-auto px-6">{header}\n'
            f'      <div class="flex flex-col md:flex-row gap-8 md:gap-0">{cells}\n'
            '      </div>\n'
            '    </div>\n'
            '  </section>'
        )

    cells = ""
    for num, title, desc in steps:
        cells += (
            '\n'
            '        <div data-reveal class="relative">\n'
            f'          <div class="text-5xl font-heading font-extrabold text-brand/15 mb-2">{num}</div>\n'
            f'          <h4 class="font-heading font-semibold text-gray-900 text-lg mb-2">{title}</h4>\n'
            f'          <p class="text-gray-600 text-sm leading-relaxed">{desc}</p>\n'
            '        </div>'
        )
    return (
        '\n'
        '  <section class="py-20">\n'
        f'    <div class="max-w-6xl mx-auto px-6">{header}\n'
        f'      <div class="grid md:grid-cols-4 gap-8">{cells}\n'
        '      </div>\n'
        '    </div>\n'
        '  </section>'
    )


def _render_why(ctx: Dict) -> str:
    co = ctx["content"]
    variant = (ctx.get("variants") or {}).get("why", "side-by-side")
    radius = ctx.get("btn_radius", "rounded-lg")

    if variant == "four-col":
        cells = ""
        for i, r in enumerate(co["why_choose_us"]):
            ikey = VALUE_ICON_KEYS[i % len(VALUE_ICON_KEYS)]
            cells += (
                '\n'
                '        <div data-reveal class="text-center p-6">\n'
                f'          <div class="w-14 h-14 mx-auto {radius} bg-brand-soft text-brand flex items-center justify-center mb-4">\n'
                f'            {icon(ikey, "w-7 h-7")}\n'
                '          </div>\n'
                f'          <h4 class="font-heading font-semibold text-gray-900 mb-2">{r["title"]}</h4>\n'
                f'          <p class="text-gray-600 text-sm leading-relaxed">{r["description"]}</p>\n'
                '        </div>'
            )
        return (
            '\n'
            '  <section class="py-20 bg-gray-50">\n'
            '    <div class="max-w-6xl mx-auto px-6">\n'
            '      <div class="text-center max-w-2xl mx-auto mb-12" data-reveal>\n'
            '        <span class="inline-block text-brand text-xs font-semibold tracking-wider uppercase mb-3">Why Choose Us</span>\n'
            '        <h2 class="font-heading text-3xl md:text-4xl font-bold text-gray-900 mb-4">The values behind our work</h2>\n'
            f'        <p class="text-gray-600 leading-relaxed">{co["about_short"]}</p>\n'
            '      </div>\n'
            f'      <div class="grid md:grid-cols-2 lg:grid-cols-4 gap-4">{cells}\n'
            '      </div>\n'
            '    </div>\n'
            '  </section>'
        )

    if variant == "list-band":
        cells = ""
        for i, r in enumerate(co["why_choose_us"]):
            ikey = VALUE_ICON_KEYS[i % len(VALUE_ICON_KEYS)]
            cells += (
                '\n'
                '        <div data-reveal class="flex gap-3 items-start">\n'
                f'          <div class="flex-shrink-0 w-10 h-10 {radius} bg-white/15 text-white flex items-center justify-center backdrop-blur">\n'
                f'            {icon(ikey, "w-5 h-5")}\n'
                '          </div>\n'
                '          <div>\n'
                f'            <h4 class="font-heading font-semibold text-white mb-1">{r["title"]}</h4>\n'
                f'            <p class="text-white/80 text-sm leading-relaxed">{r["description"]}</p>\n'
                '          </div>\n'
                '        </div>'
            )
        return (
            '\n'
            '  <section class="py-20 bg-brand relative overflow-hidden">\n'
            '    <div class="hero-dots absolute inset-0 opacity-10"></div>\n'
            '    <div class="relative max-w-6xl mx-auto px-6">\n'
            '      <div class="text-center max-w-2xl mx-auto mb-12" data-reveal>\n'
            '        <span class="inline-block text-white/80 text-xs font-semibold tracking-wider uppercase mb-3">Why Choose Us</span>\n'
            '        <h2 class="font-heading text-3xl md:text-4xl font-bold text-white mb-4">The values behind our work</h2>\n'
            f'        <p class="text-white/85 leading-relaxed">{co["about_short"]}</p>\n'
            '      </div>\n'
            f'      <div class="grid md:grid-cols-2 lg:grid-cols-4 gap-6">{cells}\n'
            '      </div>\n'
            '    </div>\n'
            '  </section>'
        )

    rows = ""
    for i, r in enumerate(co["why_choose_us"]):
        ikey = VALUE_ICON_KEYS[i % len(VALUE_ICON_KEYS)]
        rows += (
            '\n'
            f'        <div data-reveal class="flex gap-4 p-5 {radius} hover:bg-brand-soft/40 transition">\n'
            f'          <div class="flex-shrink-0 w-11 h-11 {radius} bg-brand text-white flex items-center justify-center">\n'
            f'            {icon(ikey, "w-5 h-5")}\n'
            '          </div>\n'
            '          <div>\n'
            f'            <h4 class="font-heading font-semibold text-gray-900 mb-1">{r["title"]}</h4>\n'
            f'            <p class="text-gray-600 text-sm leading-relaxed">{r["description"]}</p>\n'
            '          </div>\n'
            '        </div>'
        )
    return (
        '\n'
        '  <section class="py-20 bg-gray-50">\n'
        '    <div class="max-w-6xl mx-auto px-6 grid md:grid-cols-2 gap-14 items-start">\n'
        '      <div data-reveal>\n'
        '        <span class="inline-block text-brand text-xs font-semibold tracking-wider uppercase mb-3">Why Choose Us</span>\n'
        '        <h2 class="font-heading text-3xl md:text-4xl font-bold text-gray-900 mb-5">The values behind our work</h2>\n'
        f'        <p class="text-gray-700 leading-relaxed mb-7">{co["about_short"]}</p>\n'
        '        <a href="about.html" class="inline-flex items-center text-brand font-medium hover:text-brand-dark group">\n'
        '          Learn more about us\n'
        '          <span class="ml-1 transition group-hover:translate-x-1">&rarr;</span>\n'
        '        </a>\n'
        '      </div>\n'
        f'      <div class="space-y-2">{rows}\n'
        '      </div>\n'
        '    </div>\n'
        '  </section>'
    )


def _render_testimonials() -> str:
    star_svg = '<svg fill="currentColor" viewBox="0 0 20 20" class="w-4 h-4"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.286 3.957a1 1 0 00.95.69h4.162c.969 0 1.371 1.24.588 1.81l-3.37 2.447a1 1 0 00-.363 1.118l1.287 3.957c.3.92-.755 1.688-1.54 1.118l-3.37-2.447a1 1 0 00-1.176 0l-3.37 2.447c-.784.57-1.838-.197-1.539-1.118l1.287-3.957a1 1 0 00-.363-1.118L2.05 9.384c-.783-.57-.38-1.81.588-1.81h4.162a1 1 0 00.95-.69l1.286-3.957z"/></svg>'
    stars = star_svg * 5
    cards = ""
    for i in range(3):
        cards += (
            '\n'
            '        <div data-reveal class="bg-white border-2 border-dashed border-brand/30 rounded-2xl p-6 relative">\n'
            '          <span class="absolute top-2 right-3 text-[10px] uppercase tracking-wider text-brand/60 font-semibold">Edit me</span>\n'
            f'          <div class="flex gap-1 mb-4 text-amber-500">{stars}</div>\n'
            '          <p class="text-gray-600 italic leading-relaxed mb-5">"Replace this placeholder with a real customer quote. Do not invent reviews - paste a real one a client gave you."</p>\n'
            '          <div class="flex items-center gap-3 pt-4 border-t border-gray-100">\n'
            '            <div class="w-10 h-10 rounded-full bg-brand-soft text-brand flex items-center justify-center font-heading font-bold">?</div>\n'
            '            <div>\n'
            '              <p class="text-sm font-semibold text-gray-900">Customer Name</p>\n'
            '              <p class="text-xs text-gray-500">Their role or company</p>\n'
            '            </div>\n'
            '          </div>\n'
            '        </div>'
        )
    return (
        '\n'
        '  <!-- TESTIMONIAL SECTION - EDIT ME\n'
        '       To turn this into a real-looking section:\n'
        '       1. Replace the placeholder quote in each card with a REAL customer quote.\n'
        "       2. Replace 'Customer Name' / 'Their role or company' with real attribution.\n"
        "       3. Replace the '?' with the customer's initials.\n"
        "       4. Remove the 'border-dashed border-brand/30' classes and the 'Edit me' span.\n"
        '       Do NOT invent quotes - use feedback you have actually received. -->\n'
        '  <section class="py-20 bg-gray-50">\n'
        '    <div class="max-w-6xl mx-auto px-6">\n'
        '      <div class="text-center max-w-2xl mx-auto mb-14" data-reveal>\n'
        '        <span class="inline-block text-brand text-xs font-semibold tracking-wider uppercase mb-3">Testimonials</span>\n'
        '        <h2 class="font-heading text-3xl md:text-4xl font-bold text-gray-900 mb-4">What Our Customers Say</h2>\n'
        '        <p class="text-gray-600">Real feedback from people we have worked with.</p>\n'
        '      </div>\n'
        f'      <div class="grid md:grid-cols-3 gap-6">{cards}\n'
        '      </div>\n'
        '    </div>\n'
        '  </section>'
    )


def _render_cta_banner(ctx: Dict) -> str:
    c = ctx["company"]
    co = ctx["content"]
    arrow = icon("arrow_right", "w-4 h-4 inline-block ml-1")
    variant = (ctx.get("variants") or {}).get("cta_banner", "solid")
    radius = ctx.get("btn_radius", "rounded-lg")

    if variant == "dark":
        return (
            '\n'
            '  <section class="relative bg-gradient-to-br from-gray-900 via-gray-900 to-brand-dark overflow-hidden">\n'
            '    <div class="hero-dots absolute inset-0 opacity-10"></div>\n'
            '    <div class="relative max-w-4xl mx-auto px-6 py-16 md:py-20 text-center">\n'
            f'      <span class="inline-block bg-white/10 backdrop-blur text-white/90 text-xs font-semibold tracking-wider uppercase px-3 py-1.5 {radius} mb-5 border border-white/10">Get in touch</span>\n'
            '      <h2 data-reveal class="font-heading text-3xl md:text-4xl font-bold text-white mb-4">Ready to get started?</h2>\n'
            '      <p data-reveal class="text-gray-300 text-lg mb-8 max-w-2xl mx-auto">Get in touch and let us know how we can help. We respond promptly and look forward to hearing about your project.</p>\n'
            f'      <a data-reveal href="contact.html" class="inline-flex items-center bg-brand hover:bg-brand-dark text-white font-semibold px-8 py-3.5 {radius} transition shadow-lg">\n'
            f'        {co["primary_cta"]} {arrow}\n'
            '      </a>\n'
            '    </div>\n'
            '  </section>'
        )

    if variant == "light":
        return (
            '\n'
            '  <section class="relative bg-white border-y border-gray-100 overflow-hidden">\n'
            '    <div class="absolute -top-32 -right-32 w-[480px] h-[480px] rounded-full bg-brand/10 blur-3xl"></div>\n'
            '    <div class="relative max-w-4xl mx-auto px-6 py-20 md:py-24 text-center">\n'
            f'      <span class="inline-block bg-brand-soft text-brand text-xs font-semibold tracking-[0.2em] uppercase px-3 py-1.5 {radius} mb-5">Get in touch</span>\n'
            '      <h2 data-reveal class="font-heading text-3xl md:text-5xl font-bold text-gray-900 mb-5 leading-[1.1]">Ready to <span class="text-brand">get started?</span></h2>\n'
            '      <p data-reveal class="text-gray-600 text-lg mb-8 max-w-2xl mx-auto leading-relaxed">Get in touch and let us know how we can help. We respond promptly and look forward to hearing about your project.</p>\n'
            f'      <a data-reveal href="contact.html" class="inline-flex items-center bg-brand hover:bg-brand-dark text-white font-semibold px-8 py-3.5 {radius} transition shadow-sm">\n'
            f'        {co["primary_cta"]} {arrow}\n'
            '      </a>\n'
            '    </div>\n'
            '  </section>'
        )

    if variant == "split":
        img = photo_url(ctx, 800, 600, "about_inline")
        return (
            '\n'
            '  <section class="relative bg-brand-soft/60 overflow-hidden">\n'
            '    <div class="max-w-6xl mx-auto px-6 py-16 md:py-20 grid md:grid-cols-2 gap-12 items-center">\n'
            '      <div data-reveal>\n'
            '        <span class="inline-block text-brand text-xs font-semibold tracking-wider uppercase mb-3">Get in touch</span>\n'
            '        <h2 class="font-heading text-3xl md:text-4xl font-bold text-gray-900 mb-5 leading-[1.1]">Let us know how we can help.</h2>\n'
            '        <p class="text-gray-700 text-lg mb-8 leading-relaxed">Send us a message or give us a call. We respond promptly and would love to hear about your project.</p>\n'
            f'        <a href="contact.html" class="inline-flex items-center bg-brand hover:bg-brand-dark text-white font-semibold px-8 py-3.5 {radius} transition shadow-sm">\n'
            f'          {co["primary_cta"]} {arrow}\n'
            '        </a>\n'
            '      </div>\n'
            '      <div data-reveal class="relative">\n'
            f'        <div class="absolute -inset-3 bg-brand/15 {radius} blur-2xl"></div>\n'
            f'        <div class="relative aspect-[4/3] {radius} overflow-hidden shadow-xl border-4 border-white">\n'
            f'          <img src="{img}" alt="{c["company"]}" loading="lazy" class="w-full h-full object-cover">\n'
            '        </div>\n'
            '      </div>\n'
            '    </div>\n'
            '  </section>'
        )

    return (
        '\n'
        '  <section class="relative bg-brand overflow-hidden">\n'
        '    <div class="hero-dots absolute inset-0 opacity-10"></div>\n'
        '    <div class="relative max-w-4xl mx-auto px-6 py-16 md:py-20 text-center">\n'
        '      <h2 data-reveal class="font-heading text-3xl md:text-4xl font-bold text-white mb-4">Ready to get started?</h2>\n'
        '      <p data-reveal class="text-white/90 text-lg mb-8 max-w-2xl mx-auto">Get in touch and let us know how we can help. We respond promptly and look forward to hearing about your project.</p>\n'
        f'      <a data-reveal href="contact.html" class="inline-flex items-center bg-white text-brand hover:bg-gray-50 font-semibold px-8 py-3.5 {radius} transition shadow-sm">\n'
        f'        {co["primary_cta"]} {arrow}\n'
        '      </a>\n'
        '    </div>\n'
        '  </section>'
    )


def _section_dispatcher():
    return {
        "trust_strip": _render_trust_strip,
        "about_preview": _render_about_preview,
        "services": _render_services,
        "process": _render_process,
        "gallery": _render_gallery,
        "testimonials": lambda ctx: _render_testimonials(),
        "why": _render_why,
    }


def render(ctx: Dict) -> str:
    c = ctx["company"]
    co = ctx["content"]
    title = f'{c["company"]} - {co["tagline"]}'
    order = ctx.get("sections_order") or [
        "trust_strip", "about_preview", "services", "process", "gallery", "testimonials", "why",
    ]
    dispatch = _section_dispatcher()
    middle_html = "\n".join(dispatch[name](ctx) for name in order if name in dispatch)
    return (
        f'<html>{render_head(title, co["meta_description_home"], ctx)}\n'
        '<body class="bg-white text-gray-900 antialiased">\n'
        f'{render_header(ctx, "home")}\n'
        '<main>\n'
        f'{_render_hero(ctx)}\n'
        f'{middle_html}\n'
        f'{_render_cta_banner(ctx)}\n'
        '</main>\n'
        f'{render_footer(ctx)}\n'
        '</body></html>'
    )
