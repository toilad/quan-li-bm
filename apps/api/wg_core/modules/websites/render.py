"""Static site renderer: 6 pages in the chosen template's palette and hero layout.

NOTE: the legacy app's original HTML is not recovered yet (compiled bytecode). This renderer rebuilds each
template from its recovered name, palette, hero layout and photo keywords; it is replaced once the legacy
HTML is restored. Facts come only from the Sheet; generic legal pages are fixed text, not AI.
"""
from html import escape

from .templates import Template

PAGES = [("index.html", "Home"), ("about.html", "About"), ("contact.html", "Contact"), ("faq.html", "FAQ"),
         ("privacy.html", "Privacy Policy"), ("terms.html", "Terms of Service")]


def _css(t: Template) -> str:
    return f"""*{{box-sizing:border-box}}body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#1e293b;line-height:1.6}}
a{{color:{t.primary}}}header{{display:flex;justify-content:space-between;align-items:center;padding:18px 6vw;border-bottom:1px solid #e2e8f0;flex-wrap:wrap;gap:12px}}
.brand{{font-weight:700;color:{t.primary};text-decoration:none;font-size:1.1rem}}nav a{{margin-left:18px;color:#475569;text-decoration:none;font-size:.95rem}}
nav a.on{{color:{t.primary};font-weight:600}}main{{min-height:50vh}}section{{padding:56px 6vw}}h1{{font-size:2.4rem;line-height:1.15;margin:.2em 0}}
.kicker{{color:{t.primary};font-weight:600;letter-spacing:.08em;text-transform:uppercase;font-size:.8rem}}
.btn{{display:inline-block;background:{t.primary};color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:600}}
.photo{{background:linear-gradient(135deg,{t.primary},{t.accent});border-radius:18px;min-height:260px}}
.grid{{display:grid;gap:20px;grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}}.card{{border:1px solid #e2e8f0;border-radius:14px;padding:22px}}
.card b{{display:block;margin-bottom:6px}}.split{{display:grid;gap:40px;grid-template-columns:1fr 1fr;align-items:center}}
.hero-centered{{text-align:center;background:linear-gradient(180deg,{t.primary},{t.accent});color:#fff}}.hero-centered .kicker,.hero-centered h1{{color:#fff}}
.hero-centered .btn{{background:#fff;color:{t.primary}}}.hero-minimal h1{{font-weight:300;font-size:2.8rem}}.bar{{width:64px;height:4px;background:{t.primary};border-radius:4px}}
.hero-banner{{position:relative;padding:0}}.hero-banner .photo{{border-radius:0;min-height:340px}}.hero-banner .over{{position:absolute;left:6vw;bottom:40px;color:#fff}}
.hero-banner h1{{color:#fff;text-shadow:0 2px 12px rgba(0,0,0,.35)}}.hero-stacked{{background:{t.accent}22}}.stack{{position:relative}}
.stack:before{{content:"";position:absolute;inset:14px -14px -14px 14px;background:{t.accent};opacity:.5;border-radius:18px;transform:rotate(3deg)}}.stack .photo{{position:relative}}
footer{{background:#f8fafc;border-top:1px solid #e2e8f0;padding:28px 6vw;font-size:.9rem;color:#475569;display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}}
@media(max-width:760px){{.split{{grid-template-columns:1fr}}nav a{{margin:0 14px 0 0}}h1{{font-size:1.9rem}}}}"""


def _hero(t: Template, name: str, copy: dict) -> str:
    n, tag, intro = escape(name), escape(copy["tagline"]), escape(copy["intro"])
    cta = '<a class="btn" href="contact.html">Contact us</a>'
    text = f'<div><div class="kicker">{escape(tag)}</div><h1>{n}</h1><p>{intro}</p>{cta}</div>'
    photo = '<div class="photo" role="img" aria-label="{}"></div>'.format(escape(", ".join(t.photo_keywords)))
    if t.hero == "centered":
        return f'<section class="hero-centered"><div class="kicker">{tag}</div><h1>{n}</h1><p>{intro}</p>{cta}</section>'
    if t.hero == "minimal":
        return f'<section class="hero-minimal"><h1>{n}</h1><div class="bar"></div><p>{intro}</p>{cta}</section>'
    if t.hero == "image-banner":
        return f'<section class="hero-banner">{photo}<div class="over"><h1>{n}</h1><p>{tag}</p></div></section><section><p>{intro}</p>{cta}</section>'
    if t.hero == "stacked-cards":
        return f'<section class="hero-stacked split">{text}<div class="stack">{photo}</div></section>'
    if t.hero == "split-right":
        return f'<section class="split">{photo}{text}</section>'
    return f'<section class="split">{text}{photo}</section>'  # split-left


def _page(t: Template, name: str, facts: dict, current: str, title: str, body: str) -> str:
    nav = "".join(f'<a href="{f}"{" class=on" if f == current else ""}>{escape(lbl)}</a>' for f, lbl in PAGES[:4])
    foot = "".join(f"<div><b>{escape(k)}</b><br>{escape(v)}</div>" for k, v in facts.items() if v)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{escape(title)} — {escape(name)}</title><style>{_css(t)}</style></head><body>"
            f'<header><a class="brand" href="index.html">{escape(name)}</a><nav>{nav}</nav></header><main>{body}</main>'
            f'<footer>{foot}<div><a href="privacy.html">Privacy Policy</a> · <a href="terms.html">Terms of Service</a></div></footer></body></html>')


def render_site(t: Template, name: str, facts: dict, copy: dict) -> dict[str, bytes]:
    services = "".join(f'<div class="card"><b>{escape(s["title"])}</b>{escape(s["description"])}</div>' for s in copy["services"])
    faq = "".join(f'<div class="card"><b>{escape(f["question"])}</b>{escape(f["answer"])}</div>' for f in copy["faq"])
    about = "".join(f"<p>{escape(p)}</p>" for p in copy["about"])
    contact = "".join(f"<p><b>{escape(k)}:</b> {escape(v)}</p>" for k, v in facts.items() if v)
    legal = lambda what: (f"<section><h1>{what}</h1><p>This {what.lower()} applies to the website of {escape(name)}. "  # noqa: E731
                          "We only collect the information you choose to send us through the contact details on this site, "
                          "and we use it solely to respond to you. Questions can be sent using the contact page.</p></section>")
    bodies = {
        "index.html": _hero(t, name, copy) + f'<section><h2>Services</h2><div class="grid">{services}</div></section>',
        "about.html": f"<section><h1>About {escape(name)}</h1>{about}</section>",
        "contact.html": f"<section><h1>Contact</h1>{contact}</section>",
        "faq.html": f'<section><h1>Frequently asked questions</h1><div class="grid">{faq}</div></section>',
        "privacy.html": legal("Privacy Policy"),
        "terms.html": legal("Terms of Service"),
    }
    return {f: _page(t, name, facts, f, lbl, bodies[f]).encode("utf-8") for f, lbl in PAGES}
