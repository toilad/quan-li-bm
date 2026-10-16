"""
faq.py
======
Render the FAQ page (faq.html).

Pulls the AI-generated `faqs` list (8 Q&A pairs) out of the rendering
context and lays them out with a clean accordion-style design. Includes
FAQPage JSON-LD so search engines + AI crawlers can index each question
as a structured Q&A pair (helps with rich snippets and trust signals).
"""

import json
from typing import Dict

from .base import render_head, render_header, render_footer, photo_url


def _faq_jsonld(faqs: list) -> str:
    if not faqs:
        return ""
    entities = [
        {
            "@type": "Question",
            "name": faq.get("q", ""),
            "acceptedAnswer": {"@type": "Answer", "text": faq.get("a", "")},
        }
        for faq in faqs
        if faq.get("q") and faq.get("a")
    ]
    if not entities:
        return ""
    data = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": entities}
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + "</script>"


def _render_hero(ctx: Dict) -> str:
    c = ctx["company"]
    bg = photo_url(ctx, 1920, 720, "contact_hero")
    return (
            '\n'
            '  <section class="relative overflow-hidden">\n'
            '    <div class="absolute inset-0">\n'
            f'      <img src="{bg}" alt="" class="w-full h-full object-cover" loading="lazy">\n'
            '      <div class="absolute inset-0 bg-gradient-to-br from-white/95 via-white/85 to-brand-soft/85"></div>\n'
            '    </div>\n'
            '    <div class="hero-dots absolute inset-0 opacity-30"></div>\n'
            '    <div class="relative max-w-4xl mx-auto px-6 py-20 md:py-28 text-center">\n'
            '      <span data-reveal class="inline-block bg-white/80 text-brand text-xs font-semibold tracking-wider uppercase px-3 py-1.5 rounded-full mb-5 border border-brand/10">FAQ</span>\n'
            '      <h1 data-reveal class="font-heading text-4xl md:text-5xl font-bold text-gray-900 mb-4 leading-[1.1]">\n'
            '        Frequently Asked Questions\n'
            '      </h1>\n'
            '      <p data-reveal class="text-gray-700 text-lg max-w-2xl mx-auto">\n'
            f'        Answers to common questions about {c["company"]}.\n'
            '      </p>\n'
            '    </div>\n'
            '  </section>'
        )


def _render_faq_list(ctx: Dict) -> str:
    faqs = ctx["content"].get("faqs") or []
    if not faqs:
        return ""
    items = []
    for i, faq in enumerate(faqs, 1):
        q = faq.get("q", "").strip()
        a = faq.get("a", "").strip()
        if not q or not a:
            continue
        open_attr = "open" if i == 1 else ""
        items.append((
            '\n'
            f'        <details data-reveal {open_attr} class="group bg-white border border-gray-200 rounded-2xl overflow-hidden hover:border-brand/40 transition">\n'
            '          <summary class="cursor-pointer list-none flex items-start justify-between gap-4 p-5 md:p-6">\n'
            '            <div class="flex items-start gap-4">\n'
            '              <span class="flex-shrink-0 w-9 h-9 rounded-xl bg-brand-soft text-brand flex items-center justify-center font-heading font-bold">\n'
            f'                {i:02d}\n'
            '              </span>\n'
            '              <h3 class="font-heading font-semibold text-gray-900 text-lg leading-snug pt-1">\n'
            f'                {q}\n'
            '              </h3>\n'
            '            </div>\n'
            '            <svg class="flex-shrink-0 w-6 h-6 text-brand transition-transform duration-200 group-open:rotate-45" fill="none" stroke="currentColor" viewBox="0 0 24 24">\n'
            '              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>\n'
            '            </svg>\n'
            '          </summary>\n'
            '          <div class="px-5 md:px-6 pb-6 pl-[68px] md:pl-[76px] text-gray-600 leading-relaxed">\n'
            f'            {a}\n'
            '          </div>\n'
            '        </details>'
        ))
    grid = '\n'.join(items)
    return (
            '\n'
            '  <section class="py-20 bg-gray-50">\n'
            f'    <div class="max-w-3xl mx-auto px-6 space-y-4">{grid}\n'
            '    </div>\n'
            '  </section>'
        )


def _render_cta(ctx: Dict) -> str:
    c = ctx["company"]
    return (
            '\n'
            '  <section class="bg-brand">\n'
            '    <div class="max-w-4xl mx-auto px-6 py-14 text-center">\n'
            '      <h2 data-reveal class="font-heading text-3xl md:text-4xl font-bold text-white mb-3">\n'
            '        Still have questions?\n'
            '      </h2>\n'
            '      <p data-reveal class="text-white/90 text-lg mb-7 max-w-2xl mx-auto">\n'
            f"        Reach out to the {c['company']} team and we'll get back to you promptly.\n"
            '      </p>\n'
            '      <a data-reveal href="contact.html"\n'
            '         class="inline-flex items-center bg-white text-brand hover:bg-gray-50 font-semibold px-7 py-3 rounded-lg transition shadow-sm">\n'
            '        Contact Us\n'
            '      </a>\n'
            '    </div>\n'
            '  </section>'
        )


def render(ctx: Dict) -> str:
    c = ctx["company"]
    co = ctx["content"]
    faqs = co.get("faqs") or []
    title = f'FAQ - {c["company"]}'
    meta_desc = co.get("meta_description_faq") or f'Frequently asked questions about {c["company"]} services.'
    extra_head = _faq_jsonld(faqs)
    return (
            f'<html>{render_head(title, meta_desc, ctx)}\n'
            f'{extra_head}\n'
            '<body class="bg-white text-gray-900 antialiased">\n'
            f'{render_header(ctx, "faq")}\n'
            '<main>\n'
            f'{_render_hero(ctx)}\n'
            f'{_render_faq_list(ctx)}\n'
            f'{_render_cta(ctx)}\n'
            '</main>\n'
            f'{render_footer(ctx)}\n'
            '</body></html>'
        )
