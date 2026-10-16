"""
about.py
========
Render the About Us page (about.html).
"""

from typing import Dict

from .base import render_head, render_header, render_footer, icon, photo_url, VALUE_ICON_KEYS


def _render_story(ctx: Dict) -> str:
    co = ctx["content"]
    paragraphs = [p.strip() for p in co["about_full"].split("\n\n") if p.strip()]
    inline_img = photo_url(ctx, 1200, 700, "about_inline")
    parts = []
    for i, p in enumerate(paragraphs):
        cls = "dropcap text-gray-700 leading-[1.8] mb-6 text-lg" if i == 0 else "text-gray-700 leading-[1.8] mb-6"
        parts.append(f'<p data-reveal class="{cls}">{p}</p>')
        if i == 1:
            parts.append((
            '\n'
            '            <figure data-reveal class="my-10 -mx-6 md:-mx-12">\n'
            f'              <img src="{inline_img}" alt="" loading="lazy"\n'
            '                   class="w-full aspect-[16/9] object-cover rounded-2xl shadow-md">\n'
            '            </figure>'
        ))
    return (
            '\n'
            '  <section class="py-20">\n'
            '    <div class="max-w-3xl mx-auto px-6">\n'
            f'      {"".join(parts)}\n'
            '    </div>\n'
            '  </section>'
        )


def _render_values(ctx: Dict) -> str:
    co = ctx["content"]
    cards = ""
    for i, r in enumerate(co["why_choose_us"]):
        ikey = VALUE_ICON_KEYS[i % len(VALUE_ICON_KEYS)]
        cards += (
            '\n'
            '        <div data-reveal class="card-lift bg-white border border-gray-200 rounded-2xl p-7 text-center">\n'
            '          <div class="w-14 h-14 mx-auto rounded-2xl bg-brand-soft text-brand flex items-center justify-center mb-5">\n'
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
            '      <div class="text-center max-w-2xl mx-auto mb-14" data-reveal>\n'
            '        <span class="inline-block text-brand text-xs font-semibold tracking-wider uppercase mb-3">Our Values</span>\n'
            '        <h2 class="font-heading text-3xl md:text-4xl font-bold text-gray-900">What We Stand For</h2>\n'
            '      </div>\n'
            f'      <div class="grid md:grid-cols-3 gap-6">{cards}\n'
            '      </div>\n'
            '    </div>\n'
            '  </section>'
        )


def _render_quote(ctx: Dict) -> str:
    co = ctx["content"]
    return (
            '\n'
            '  <section class="py-16">\n'
            '    <div class="max-w-3xl mx-auto px-6">\n'
            '      <div data-reveal class="relative bg-brand-soft border-l-4 border-brand rounded-r-2xl p-8 md:p-10">\n'
            '        <svg class="w-10 h-10 text-brand/40 mb-3" fill="currentColor" viewBox="0 0 24 24">\n'
            '          <path d="M6.5 10c-1.93 0-3.5 1.57-3.5 3.5S4.57 17 6.5 17c1.93 0 3.5-1.57 3.5-3.5C10 11.57 8.43 10 6.5 10zm10.5 0c-1.93 0-3.5 1.57-3.5 3.5s1.57 3.5 3.5 3.5 3.5-1.57 3.5-3.5c0-1.93-1.57-3.5-3.5-3.5z"/>\n'
            '          <path d="M3.5 13.5C3.5 9.91 6.41 7 10 7V4c-5.25 0-9.5 4.25-9.5 9.5h3zm10.5 0C14 9.91 16.91 7 20.5 7V4c-5.25 0-9.5 4.25-9.5 9.5h3z"/>\n'
            '        </svg>\n'
            f'        <p class="font-heading text-xl md:text-2xl text-gray-800 leading-relaxed italic">{co["about_short"]}</p>\n'
            '      </div>\n'
            '    </div>\n'
            '  </section>'
        )


def render(ctx: Dict) -> str:
    c = ctx["company"]
    co = ctx["content"]
    title = f'About - {c["company"]}'
    return (
            f'<html>{render_head(title, co["meta_description_about"], ctx)}\n'
            '<body class="bg-white text-gray-900 antialiased">\n'
            f'{render_header(ctx, "about")}\n'
            '<main>\n'
            '  <section class="relative overflow-hidden">\n'
            '    <div class="absolute inset-0">\n'
            f'      <img src="{photo_url(ctx, 1920, 700, "about_hero")}" alt="" class="w-full h-full object-cover">\n'
            '      <div class="absolute inset-0 bg-gradient-to-r from-white/95 via-white/85 to-white/40"></div>\n'
            '    </div>\n'
            '    <div class="hero-dots absolute inset-0 opacity-25"></div>\n'
            '    <div class="relative max-w-4xl mx-auto px-6 py-20 md:py-28">\n'
            '      <span data-reveal class="inline-block bg-white/80 backdrop-blur text-brand text-xs font-semibold tracking-wider uppercase px-3 py-1.5 rounded-full mb-5 border border-brand/10 shadow-sm">\n'
            '        About Us\n'
            '      </span>\n'
            '      <h1 data-reveal class="font-heading text-4xl md:text-5xl font-bold text-gray-900 mb-4 leading-[1.1]">\n'
            f'        About {c["company"]}\n'
            '      </h1>\n'
            '      <p data-reveal class="text-lg md:text-xl text-gray-700 max-w-2xl leading-relaxed">\n'
            '        Learn who we are, what we do, and the principles that guide our work.\n'
            '      </p>\n'
            '    </div>\n'
            '  </section>\n'
            '\n'
            f'{_render_story(ctx)}\n'
            f'{_render_quote(ctx)}\n'
            f'{_render_values(ctx)}\n'
            '\n'
            '  <section class="py-16">\n'
            '    <div class="max-w-3xl mx-auto px-6">\n'
            '      <div data-reveal class="bg-gray-900 rounded-2xl p-10 md:p-12 text-center text-white relative overflow-hidden">\n'
            '        <div class="hero-dots absolute inset-0 opacity-10"></div>\n'
            '        <div class="relative">\n'
            '          <h3 class="font-heading text-2xl md:text-3xl font-bold mb-3">Visit or Get in Touch</h3>\n'
            f'          <p class="text-gray-300 mb-6">We are based at {c["address"]}.</p>\n'
            '          <a href="contact.html" class="inline-flex items-center bg-white text-gray-900 hover:bg-gray-100 font-semibold px-7 py-3 rounded-lg transition">\n'
            '            Contact Us &rarr;\n'
            '          </a>\n'
            '        </div>\n'
            '      </div>\n'
            '    </div>\n'
            '  </section>\n'
            '</main>\n'
            f'{render_footer(ctx)}\n'
            '</body></html>'
        )
