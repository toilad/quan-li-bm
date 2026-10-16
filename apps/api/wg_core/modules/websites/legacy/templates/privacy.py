"""
privacy.py
==========
Render the Privacy Policy page (privacy.html).
Uses standard legal boilerplate with the company's specific info injected.
"""

from datetime import datetime
from typing import Dict

from .base import render_head, render_header, render_footer


def render(ctx: Dict) -> str:
    c = ctx["company"]
    today = datetime.now().strftime("%B %d, %Y")
    title = f'Privacy Policy - {c["company"]}'
    meta_desc = f'Privacy policy for {c["company"]}'
    # QLBM: shown only for a verified business email
    contact_line = (
        f'      Questions about this Privacy Policy may be sent to <a href="mailto:{c["email"]}" class="text-brand hover:underline">{c["email"]}</a> or mailed to {c["address"]}.\n'
    ) if c["email"] else f'      Questions about this Privacy Policy may be mailed to {c["address"]}.\n'
    return (
        f'<html>{render_head(title, meta_desc, ctx)}\n'
        '<body class="bg-white text-gray-900 antialiased">\n'
        f'{render_header(ctx, "")}\n'
        '<main>\n'
        '  <section class="relative bg-brand-soft hero-blob overflow-hidden">\n'
        '    <div class="hero-dots absolute inset-0 opacity-40"></div>\n'
        '    <div class="relative max-w-3xl mx-auto px-6 py-16 md:py-20">\n'
        '      <span class="inline-block bg-white/70 backdrop-blur text-brand text-xs font-semibold tracking-wider uppercase px-3 py-1.5 rounded-full mb-4 border border-brand/10">Legal</span>\n'
        '      <h1 class="font-heading text-4xl md:text-5xl font-bold text-gray-900 mb-3 leading-[1.1]">Privacy Policy</h1>\n'
        f'      <p class="text-sm text-gray-500">Last updated: {today}</p>\n'
        '    </div>\n'
        '  </section>\n'
        '  <article class="max-w-3xl mx-auto px-6 py-16 prose">\n'
        '\n'
        '    <p class="text-gray-700 leading-relaxed mb-5">\n'
        f'      This Privacy Policy describes how {c["company"]} ("we", "our", or "us") collects, uses, and shares information about you when you visit our website at {c["domain"]} or interact with our services.\n'
        '    </p>\n'
        '\n'
        '    <h2 class="font-heading text-2xl font-semibold mt-8 mb-3">Information We Collect</h2>\n'
        '    <p class="text-gray-700 leading-relaxed mb-5">\n'
        '      We collect information you provide directly, such as your name, email address, phone number, and any details included in messages you send us. We may also collect automatically generated information when you visit our website, including IP address, browser type, referring pages, and pages visited.\n'
        '    </p>\n'
        '\n'
        '    <h2 class="font-heading text-2xl font-semibold mt-8 mb-3">How We Use Your Information</h2>\n'
        '    <p class="text-gray-700 leading-relaxed mb-5">\n'
        '      We use the information we collect to respond to inquiries, deliver our services, improve our website, and communicate with you about updates or offers when you have requested them. We do not sell your personal information to third parties.\n'
        '    </p>\n'
        '\n'
        '    <h2 class="font-heading text-2xl font-semibold mt-8 mb-3">Cookies</h2>\n'
        '    <p class="text-gray-700 leading-relaxed mb-5">\n'
        '      Our website may use cookies and similar technologies to remember preferences and analyze traffic. You can adjust your browser settings to refuse cookies, although some site features may not function properly as a result.\n'
        '    </p>\n'
        '\n'
        '    <h2 class="font-heading text-2xl font-semibold mt-8 mb-3">Sharing of Information</h2>\n'
        '    <p class="text-gray-700 leading-relaxed mb-5">\n'
        '      We may share information with trusted service providers who assist us in operating our website or conducting our business, provided they agree to keep this information confidential. We may also disclose information when required by law.\n'
        '    </p>\n'
        '\n'
        '    <h2 class="font-heading text-2xl font-semibold mt-8 mb-3">Data Security</h2>\n'
        '    <p class="text-gray-700 leading-relaxed mb-5">\n'
        '      We take reasonable measures to protect your information from unauthorized access, alteration, or disclosure. However, no method of transmission over the internet is fully secure, and we cannot guarantee absolute security.\n'
        '    </p>\n'
        '\n'
        '    <h2 class="font-heading text-2xl font-semibold mt-8 mb-3">Your Rights</h2>\n'
        '    <p class="text-gray-700 leading-relaxed mb-5">\n'
        '      You may request access to, correction of, or deletion of personal information we hold about you by contacting us using the details below.\n'
        '    </p>\n'
        '\n'
        '    <h2 class="font-heading text-2xl font-semibold mt-8 mb-3">Contact</h2>\n'
        '    <p class="text-gray-700 leading-relaxed mb-5">\n'
        f'{contact_line}'
        '    </p>\n'
        '  </article>\n'
        '</main>\n'
        f'{render_footer(ctx)}\n'
        '</body></html>'
    )
