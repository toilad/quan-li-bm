"""
terms.py
========
Render the Terms of Service page (terms.html).
Uses standard legal boilerplate with the company's specific info injected.
"""

from datetime import datetime
from typing import Dict

from .base import render_head, render_header, render_footer


def render(ctx: Dict) -> str:
    c = ctx["company"]
    today = datetime.now().strftime("%B %d, %Y")
    title = f'Terms of Service - {c["company"]}'
    meta_desc = f'Terms of service for {c["company"]}'
    return (
        f'<html>{render_head(title, meta_desc, ctx)}\n'
        '<body class="bg-white text-gray-900 antialiased">\n'
        f'{render_header(ctx, "")}\n'
        '<main>\n'
        '  <section class="relative bg-brand-soft hero-blob overflow-hidden">\n'
        '    <div class="hero-dots absolute inset-0 opacity-40"></div>\n'
        '    <div class="relative max-w-3xl mx-auto px-6 py-16 md:py-20">\n'
        '      <span class="inline-block bg-white/70 backdrop-blur text-brand text-xs font-semibold tracking-wider uppercase px-3 py-1.5 rounded-full mb-4 border border-brand/10">Legal</span>\n'
        '      <h1 class="font-heading text-4xl md:text-5xl font-bold text-gray-900 mb-3 leading-[1.1]">Terms of Service</h1>\n'
        f'      <p class="text-sm text-gray-500">Last updated: {today}</p>\n'
        '    </div>\n'
        '  </section>\n'
        '  <article class="max-w-3xl mx-auto px-6 py-16">\n'
        '\n'
        '    <p class="text-gray-700 leading-relaxed mb-5">\n'
        f'      Welcome to {c["company"]}. These Terms of Service ("Terms") govern your access to and use of our website at {c["domain"]} and any related services. By using our website, you agree to be bound by these Terms.\n'
        '    </p>\n'
        '\n'
        '    <h2 class="font-heading text-2xl font-semibold mt-8 mb-3">Use of the Website</h2>\n'
        '    <p class="text-gray-700 leading-relaxed mb-5">\n'
        "      You agree to use the website only for lawful purposes and in a way that does not infringe upon the rights of others. You may not use the site in a manner that could damage, disable, overburden, or impair the site or interfere with any other party's use of it.\n"
        '    </p>\n'
        '\n'
        '    <h2 class="font-heading text-2xl font-semibold mt-8 mb-3">Intellectual Property</h2>\n'
        '    <p class="text-gray-700 leading-relaxed mb-5">\n'
        f'      All content on this website, including text, graphics, logos, and images, is the property of {c["company"]} or its licensors and is protected by applicable copyright and trademark laws. You may not reproduce, distribute, or create derivative works without our prior written consent.\n'
        '    </p>\n'
        '\n'
        '    <h2 class="font-heading text-2xl font-semibold mt-8 mb-3">Disclaimer of Warranties</h2>\n'
        '    <p class="text-gray-700 leading-relaxed mb-5">\n'
        '      The website and its content are provided on an "as is" and "as available" basis. We make no warranties, express or implied, regarding the accuracy, reliability, or availability of the website or the information it contains.\n'
        '    </p>\n'
        '\n'
        '    <h2 class="font-heading text-2xl font-semibold mt-8 mb-3">Limitation of Liability</h2>\n'
        '    <p class="text-gray-700 leading-relaxed mb-5">\n'
        f'      To the maximum extent permitted by law, {c["company"]} shall not be liable for any indirect, incidental, special, or consequential damages arising out of or relating to your use of the website.\n'
        '    </p>\n'
        '\n'
        '    <h2 class="font-heading text-2xl font-semibold mt-8 mb-3">Third-Party Links</h2>\n'
        '    <p class="text-gray-700 leading-relaxed mb-5">\n'
        '      Our website may contain links to third-party websites. We are not responsible for the content or practices of any third-party sites and encourage you to review their terms and privacy policies.\n'
        '    </p>\n'
        '\n'
        '    <h2 class="font-heading text-2xl font-semibold mt-8 mb-3">Changes to These Terms</h2>\n'
        '    <p class="text-gray-700 leading-relaxed mb-5">\n'
        '      We may update these Terms from time to time. Continued use of the website after changes are posted constitutes acceptance of the revised Terms.\n'
        '    </p>\n'
        '\n'
        '    <h2 class="font-heading text-2xl font-semibold mt-8 mb-3">Contact</h2>\n'
        '    <p class="text-gray-700 leading-relaxed mb-5">\n'
        f'      Questions about these Terms may be sent to <a href="mailto:{c["email"]}" class="text-brand hover:underline">{c["email"]}</a> or mailed to {c["address"]}.\n'
        '    </p>\n'
        '  </article>\n'
        '</main>\n'
        f'{render_footer(ctx)}\n'
        '</body></html>'
    )
