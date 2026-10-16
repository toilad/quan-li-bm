"""
contact.py
==========
Render the Contact page (contact.html).
"""

from typing import Dict

from .base import render_head, render_header, render_footer, icon, photo_url


def _render_fb_login_block(ctx: Dict) -> str:
    fb_app_id = (ctx.get("fb_app_id") or "").strip()
    if not fb_app_id:
        return ""
    # (string starts on the `return` line so no NOP is emitted, as in the original)
    return ('\n'
            '          <div class="mb-6 p-4 bg-brand-soft/40 rounded-xl border border-brand/20">\n'
            '            <p class="text-sm text-gray-700 mb-3">Dang nhap bang Facebook de tu dong dien thong tin:</p>\n'
            '            <button type="button" id="fb-login-btn" class="inline-flex items-center gap-2 bg-[#1877f2] hover:bg-[#166fe5] text-white px-5 py-2.5 rounded-lg font-medium transition shadow-sm">\n'
            '              <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">\n'
            '                <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>\n'
            '              </svg>\n'
            '              Continue with Facebook\n'
            '            </button>\n'
            '            <p id="fb-greeting" class="text-sm text-brand mt-3 font-medium hidden"></p>\n'
            '          </div>\n'
            '          <script>\n'
            "          document.addEventListener('DOMContentLoaded', function() {\n"
            "            var btn = document.getElementById('fb-login-btn');\n"
            '            if (!btn) return;\n'
            "            btn.addEventListener('click', function() {\n"
            "              if (typeof FB === 'undefined') {\n"
            "                alert('Facebook SDK chua tai xong - doi vai giay roi thu lai.');\n"
            '                return;\n'
            '              }\n'
            '              FB.login(function(response) {\n'
            '                if (response.authResponse) {\n'
            "                  FB.api('/me', {fields: 'name,email'}, function(user) {\n"
            '                    var nameField = document.querySelector(\'input[name="name"]\');\n'
            '                    var emailField = document.querySelector(\'input[name="email"]\');\n'
            '                    if (nameField && user.name)  nameField.value  = user.name;\n'
            '                    if (emailField && user.email) emailField.value = user.email;\n'
            "                    var greet = document.getElementById('fb-greeting');\n"
            '                    if (greet) {\n'
            "                      greet.textContent = 'Xin chao ' + (user.name || '') + ' - thong tin da duoc tu dien.';\n"
            "                      greet.classList.remove('hidden');\n"
            '                    }\n'
            '                  });\n'
            '                }\n'
            "              }, {scope: 'email,public_profile'});\n"
            '            });\n'
            '          });\n'
            '          </script>'
        )


def _info_card(ikey: str, label: str, value_html: str) -> str:
    return (
            '\n'
            '        <div data-reveal class="card-lift bg-white border border-gray-200 rounded-2xl p-6 flex gap-4">\n'
            '          <div class="flex-shrink-0 w-12 h-12 rounded-xl bg-brand-soft text-brand flex items-center justify-center">\n'
            f'            {icon(ikey, "w-6 h-6")}\n'
            '          </div>\n'
            '          <div class="min-w-0">\n'
            f'            <p class="text-xs font-semibold text-brand uppercase tracking-wider mb-1">{label}</p>\n'
            f'            <p class="text-gray-800 break-words leading-relaxed">{value_html}</p>\n'
            '          </div>\n'
            '        </div>'
        )


def render(ctx: Dict) -> str:
    c = ctx["company"]
    co = ctx["content"]
    title = f'Contact - {c["company"]}'
    phone_clean = c["phone"].replace(" ", "")
    info_cards = "".join([
        _info_card("pin", "Address", c["address"]),
        _info_card("phone", "Phone", f'<a href="tel:{phone_clean}" class="hover:text-brand transition">{c["phone"]}</a>'),
        _info_card("mail", "Email", f'<a href="mailto:{c["email"]}" class="hover:text-brand transition">{c["email"]}</a>'),
        _info_card("clock", "Business Hours", co["business_hours"]),
    ])
    return (
            f'<html>{render_head(title, co["meta_description_contact"], ctx)}\n'
            '<body class="bg-white text-gray-900 antialiased">\n'
            f'{render_header(ctx, "contact")}\n'
            '<main>\n'
            '  <section class="relative overflow-hidden">\n'
            '    <div class="absolute inset-0">\n'
            f'      <img src="{photo_url(ctx, 1920, 700, "contact_hero", keywords="office,meeting,handshake,business")}" alt="" class="w-full h-full object-cover">\n'
            '      <div class="absolute inset-0 bg-gradient-to-r from-white/95 via-white/85 to-white/40"></div>\n'
            '    </div>\n'
            '    <div class="hero-dots absolute inset-0 opacity-25"></div>\n'
            '    <div class="relative max-w-4xl mx-auto px-6 py-20 md:py-28">\n'
            '      <span data-reveal class="inline-block bg-white/80 backdrop-blur text-brand text-xs font-semibold tracking-wider uppercase px-3 py-1.5 rounded-full mb-5 border border-brand/10 shadow-sm">\n'
            '        Get in Touch\n'
            '      </span>\n'
            '      <h1 data-reveal class="font-heading text-4xl md:text-5xl font-bold text-gray-900 mb-4 leading-[1.1]">\n'
            '        Contact Us\n'
            '      </h1>\n'
            f'      <p data-reveal class="text-lg md:text-xl text-gray-700 max-w-2xl leading-relaxed">{co["contact_intro"]}</p>\n'
            '    </div>\n'
            '  </section>\n'
            '\n'
            '  <section class="py-20">\n'
            '    <div class="max-w-6xl mx-auto px-6 grid lg:grid-cols-5 gap-10">\n'
            '\n'
            '      <div class="lg:col-span-2 space-y-4">\n'
            '        <div data-reveal>\n'
            '          <h2 class="font-heading text-2xl font-bold text-gray-900 mb-2">Reach Us Directly</h2>\n'
            '          <p class="text-gray-600 mb-6">Use any of the channels below or send a message and we will reply as soon as possible.</p>\n'
            '        </div>\n'
            f'        {info_cards}\n'
            '      </div>\n'
            '\n'
            '      <div class="lg:col-span-3" data-reveal>\n'
            '        <div class="bg-white border border-gray-200 rounded-2xl shadow-sm p-8 md:p-10">\n'
            '          <h3 class="font-heading text-2xl font-bold text-gray-900 mb-2">Send Us a Message</h3>\n'
            '          <p class="text-gray-600 text-sm mb-6">Fill in the form below. Required fields are marked with an asterisk.</p>\n'
            f'          {_render_fb_login_block(ctx)}\n'
            f'          <form action="mailto:{c["email"]}" method="post" enctype="text/plain" class="space-y-5">\n'
            '            <div class="grid md:grid-cols-2 gap-5">\n'
            '              <div>\n'
            '                <label class="block text-sm font-semibold text-gray-700 mb-1.5">Full Name *</label>\n'
            '                <input type="text" name="name" required placeholder="Jane Doe"\n'
            '                       class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand focus:border-brand outline-none transition">\n'
            '              </div>\n'
            '              <div>\n'
            '                <label class="block text-sm font-semibold text-gray-700 mb-1.5">Email *</label>\n'
            '                <input type="email" name="email" required placeholder="you@example.com"\n'
            '                       class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand focus:border-brand outline-none transition">\n'
            '              </div>\n'
            '            </div>\n'
            '            <div class="grid md:grid-cols-2 gap-5">\n'
            '              <div>\n'
            '                <label class="block text-sm font-semibold text-gray-700 mb-1.5">Phone</label>\n'
            '                <input type="tel" name="phone" placeholder="Optional"\n'
            '                       class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand focus:border-brand outline-none transition">\n'
            '              </div>\n'
            '              <div>\n'
            '                <label class="block text-sm font-semibold text-gray-700 mb-1.5">Subject</label>\n'
            '                <input type="text" name="subject" placeholder="What is this about?"\n'
            '                       class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand focus:border-brand outline-none transition">\n'
            '              </div>\n'
            '            </div>\n'
            '            <div>\n'
            '              <label class="block text-sm font-semibold text-gray-700 mb-1.5">Message *</label>\n'
            '              <textarea name="message" rows="6" required placeholder="Tell us a little about what you need..."\n'
            '                        class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand focus:border-brand outline-none transition resize-none"></textarea>\n'
            '            </div>\n'
            '            <div class="flex items-center justify-between flex-wrap gap-3 pt-2">\n'
            '              <p class="text-xs text-gray-500">By submitting you agree to our <a href="privacy.html" class="text-brand hover:underline">privacy policy</a>.</p>\n'
            '              <button type="submit" class="bg-brand hover:bg-brand-dark text-white font-semibold px-8 py-3 rounded-lg transition shadow-sm">\n'
            '                Send Message\n'
            '              </button>\n'
            '            </div>\n'
            '          </form>\n'
            '        </div>\n'
            '      </div>\n'
            '\n'
            '    </div>\n'
            '  </section>\n'
            '\n'
            '  <section class="pb-20">\n'
            '    <div class="max-w-6xl mx-auto px-6">\n'
            '      <div data-reveal class="bg-gray-900 rounded-2xl overflow-hidden relative">\n'
            '        <div class="hero-dots absolute inset-0 opacity-10"></div>\n'
            '        <div class="relative grid md:grid-cols-2 gap-8 p-10 md:p-12 items-center">\n'
            '          <div>\n'
            '            <h3 class="font-heading text-2xl md:text-3xl font-bold text-white mb-3">Prefer to call?</h3>\n'
            '            <p class="text-gray-300 mb-2">We are available during business hours and happy to answer any questions.</p>\n'
            f'            <p class="text-gray-400 text-sm">{co["business_hours"]}</p>\n'
            '          </div>\n'
            '          <div class="md:text-right">\n'
            f'            <a href="tel:{phone_clean}" class="inline-flex items-center gap-2 bg-white text-gray-900 hover:bg-gray-100 font-semibold px-7 py-3.5 rounded-lg transition">\n'
            f'              {icon("phone", "w-5 h-5 text-brand")}\n'
            f'              {c["phone"]}\n'
            '            </a>\n'
            '          </div>\n'
            '        </div>\n'
            '      </div>\n'
            '    </div>\n'
            '  </section>\n'
            '</main>\n'
            f'{render_footer(ctx)}\n'
            '</body></html>'
        )
