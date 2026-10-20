"""Claude via the official Anthropic SDK: structured JSON output (output_config.format = json_schema).

- read_scanned_pdf(): the PDF is sent as a base64 `document` block (Claude reads scanned pages).
- write_site_copy(): website text for one company, facts only from the Sheet.
Server-side refusal fallback is enabled (`fallbacks: "default"`, beta server-side-fallback-2026-07-01).
"""
import base64
import json

import anthropic

from ..config import settings
from ..runtime_config import get as cfg
from .errors import NotConfigured, Permanent, Transient

FALLBACK_BETA = "server-side-fallback-2026-07-01"


def model_id() -> str:
    return cfg("AI_MODEL", settings().ai_model)


def _client() -> anthropic.Anthropic:
    key = cfg("ANTHROPIC_API_KEY")
    if not key:
        raise NotConfigured("AI (Anthropic)", ["ANTHROPIC_API_KEY"])
    import httpx2

    from .http import local_address

    # IPv4 like every other integration (integrations/http.py); the SDK runs on httpx2.
    http_client = anthropic.DefaultHttpxClient(transport=httpx2.HTTPTransport(local_address=local_address()))
    return anthropic.Anthropic(api_key=key, max_retries=2, timeout=300, http_client=http_client)


def _json_call(content: list, schema: dict, system: str, effort: str, max_tokens: int = 16000) -> dict:
    client = _client()
    try:
        resp = client.beta.messages.create(
            model=model_id(),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.RateLimitError as e:
        ra = e.response.headers.get("retry-after")
        raise Transient("AI: vượt giới hạn tốc độ", float(ra) if ra and ra.isdigit() else 60) from e
    except anthropic.AuthenticationError as e:
        raise NotConfigured("AI (Anthropic)", ["ANTHROPIC_API_KEY hợp lệ"]) from e
    except anthropic.PermissionDeniedError as e:
        raise NotConfigured("AI (Anthropic)", ["quyền dùng model " + model_id()]) from e
    except anthropic.BadRequestError as e:
        raise Permanent(f"AI: yêu cầu không hợp lệ — {e.message}") from e
    except anthropic.APIStatusError as e:
        if e.status_code >= 500:
            raise Transient(f"AI: lỗi máy chủ {e.status_code}") from e
        raise Permanent(f"AI: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise Transient("AI: lỗi mạng") from e

    if resp.stop_reason == "refusal":
        raise Permanent("AI từ chối xử lý yêu cầu này")
    if resp.stop_reason == "max_tokens":
        raise Transient("AI: kết quả bị cắt (max_tokens) — thử lại")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except ValueError as e:
        raise Transient("AI trả về JSON không hợp lệ — thử lại") from e


# ── PDF (scanned) ──

_FIELD = {"type": "object", "properties": {"value": {"type": "string"}, "found": {"type": "boolean"}},
          "required": ["value", "found"], "additionalProperties": False}
PDF_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": {"type": "string", "enum": ["ca", "wy", "br", "unknown"]},
        "evidence": {"type": "string"},
        **{k: _FIELD for k in ("A", "D", "F", "G", "H", "I", "J", "A_repeat", "J_repeat")},
    },
    "required": ["doc_type", "evidence", "A", "D", "F", "G", "H", "I", "J", "A_repeat", "J_repeat"],
    "additionalProperties": False,
}

PDF_PROMPT = """Identify this company registration document, then transcribe its fields.
Read exactly what is printed. Do not guess, do not complete missing characters. A field that is not on the document:
found=false and an empty value. Never use a registered agent's / service-of-process address as the company address.

doc_type:
- "ca": California Secretary of State form LLC-1, Articles of Organization (often a scan, stamped FILED, Secretary of State, State of California).
- "wy": State of Wyoming, Articles of Organization (Wyoming Secretary of State).
- "br": Brazil, Receita Federal "Comprovante de Inscrição e de Situação Cadastral" (CNPJ).
- "unknown": anything else, or not sure. evidence = the printed words that decided it.

Fields for ca: A = item 1 LLC name as written (keep punctuation and suffix). J = the 12-digit filing number at the top right
of page 1. F = the FULL item 3a initial street address: street, suite, city, state ZIP (e.g. "100 Main St., Ste. 2, Los
Angeles, CA 90049"). G, H, I = city, state, ZIP of item 3a. D = phone (LLC-1 has none).
Fields for wy: A = name of the LLC. J = the Original ID / filing ID. F, G, H, I = the company's mailing or principal address
— F = the FULL address (street, suite, city, state ZIP), G, H, I = city, state, ZIP. D = the company's phone if printed.
Fields for br: A = NOME EMPRESARIAL. J = NÚMERO DE INSCRIÇÃO (as printed, 00.000.000/0000-00). F = the FULL address:
LOGRADOURO, NÚMERO, COMPLEMENTO, BAIRRO, MUNICÍPIO, UF CEP (skip boxes printed as asterisks). G = MUNICÍPIO. H = UF.
I = CEP as printed. D = TELEFONE.
For unknown: return found=false for every field.

Cross-check (ca only; for wy, br and unknown return found=false): the filing number and the LLC name are often printed
again on a later page (e.g. the top right of an "Attachment to Articles of Organization" page). Read them there on their
own, without copying from page 1: J_repeat = the filing number printed on a later page, A_repeat = the LLC name printed on
a later page. Not printed again: found=false."""


def read_scanned_pdf(pdf: bytes) -> dict:
    """Classify + transcribe a scanned registration document. Every value comes back marked as read by AI."""
    content = [
        {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                        "data": base64.standard_b64encode(pdf).decode()}},
        {"type": "text", "text": PDF_PROMPT},
    ]
    return _json_call(content, PDF_SCHEMA, "You transcribe government forms. Accuracy over completeness.", effort="high")


# ── Website copy ──

_ITEM = {"type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}},
         "required": ["title", "description"], "additionalProperties": False}
_TEXT = ("tagline", "hero_subtitle", "primary_cta", "intro_paragraph", "about_short", "about_full", "contact_intro",
         "footer_blurb", "meta_description_home", "meta_description_about", "meta_description_contact", "meta_description_faq")
# Field names and lengths follow the legacy generator (src/ai_generator.py) so the recovered templates render unchanged.
SITE_SCHEMA = {
    "type": "object",
    "properties": {
        **{k: {"type": "string"} for k in _TEXT},
        "services": {"type": "array", "items": _ITEM},
        "why_choose_us": {"type": "array", "items": _ITEM},
        "faqs": {"type": "array", "items": {"type": "object", "properties": {"q": {"type": "string"}, "a": {"type": "string"}},
                                            "required": ["q", "a"], "additionalProperties": False}},
    },
    "required": [*_TEXT, "services", "why_choose_us", "faqs"],
    "additionalProperties": False,
}

SITE_SYSTEM = """You write website copy for a small business, in clear, professional English (US business style).
Sound like a real, established small/medium business — plain-spoken, factual, specific to the business type; no generic
AI marketing fluff and no cliches ("cutting-edge solutions", "leverage synergies", "we are passionate about").
Hard rules (the site is published under the company's name):
- Use only the facts given. Never invent awards, certifications, licences, clients, partners, reviews, ratings,
  years in business, founding dates, team size, prices, statistics, guarantees or opening hours.
- Do not write any number that is not in the facts.
- Describe services generically for the business type; no promises of specific results.
Lengths: tagline 6-10 words; hero_subtitle ~25 words; primary_cta 2-3 words; intro_paragraph ~50 words;
exactly 3 services (title 2-4 words, description ~25 words); exactly 3 why_choose_us (title 3-5 words, description ~18 words);
about_short ~60 words; about_full 3-4 paragraphs (~250 words) separated by blank lines (background, mission, approach,
commitment to customers — without invented facts); contact_intro ~40 words; footer_blurb ~15 words;
5 faqs a prospect would ask (how to request a quote, service area — say to contact the company, how to get started,
what is included, how the process works), each answer 1-2 sentences, no invented credentials or guarantees;
meta descriptions ~150 characters each."""


def write_site_copy(facts: dict, business_type: str, template_name: str, feedback: str = "") -> dict:
    text = (f"Company facts (from the registration sheet):\n{json.dumps(facts, ensure_ascii=False, indent=2)}\n"
            f"Business type: {business_type}\nWebsite template: {template_name}\n")
    if feedback:
        text += f"\nYour previous draft was rejected: {feedback}\nRewrite it following the rules."
    return _json_call([{"type": "text", "text": text}], SITE_SCHEMA, SITE_SYSTEM, effort="medium")


def check_model() -> dict:
    """Ask the Models API whether the configured model exists for this key (no tokens spent)."""
    client = _client()
    try:
        m = client.models.retrieve(model_id())
    except anthropic.NotFoundError as e:
        raise Permanent(f"Model {model_id()} không có với khoá này") from e
    except anthropic.AuthenticationError as e:
        raise NotConfigured("AI (Anthropic)", ["ANTHROPIC_API_KEY hợp lệ"]) from e
    except anthropic.APIConnectionError as e:
        raise Transient("AI: lỗi mạng") from e
    return {"id": m.id, "display_name": getattr(m, "display_name", None), "max_input_tokens": getattr(m, "max_input_tokens", None),
            "max_tokens": getattr(m, "max_tokens", None), "sdk": anthropic.__version__}
