"""Claude via the official Anthropic SDK: structured JSON output (output_config.format = json_schema).

- read_scanned_pdf(): the PDF is sent as a base64 `document` block (Claude reads scanned pages).
- write_site_copy(): website text for one company, facts only from the Sheet.
Server-side refusal fallback is enabled (`fallbacks: "default"`, beta server-side-fallback-2026-07-01).
"""
import base64
import json

import anthropic

from ..config import settings
from .errors import NotConfigured, Permanent, Transient

FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _client() -> anthropic.Anthropic:
    key = settings().anthropic_api_key
    if not key:
        raise NotConfigured("AI (Anthropic)", ["ANTHROPIC_API_KEY"])
    return anthropic.Anthropic(api_key=key, max_retries=2, timeout=300)


def _json_call(content: list, schema: dict, system: str, effort: str, max_tokens: int = 16000) -> dict:
    client = _client()
    try:
        resp = client.beta.messages.create(
            model=settings().ai_model,
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
        raise NotConfigured("AI (Anthropic)", ["quyền dùng model " + settings().ai_model]) from e
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
    "properties": {k: _FIELD for k in ("A", "D", "F", "G", "H", "I", "J")},
    "required": ["A", "D", "F", "G", "H", "I", "J"],
    "additionalProperties": False,
}

CA_PROMPT = """This is a California Secretary of State form LLC-1 (Articles of Organization), possibly scanned.
Read exactly what is printed. Do not guess, do not complete missing characters. If a field is not on the form, return found=false and an empty value.
A = item 1, the LLC name, exactly as written (keep punctuation and suffix).
J = the 12-digit filing number printed at the top right of page 1 (digits only, as printed).
F = item 3a Initial Street Address of the LLC (street line only). Never use the agent's address (item 4).
G = city of item 3a. H = state of item 3a as printed. I = ZIP of item 3a.
D = phone number: the LLC-1 has no phone field, so return found=false unless a phone of the LLC is clearly printed."""


def read_scanned_pdf(pdf: bytes, doc_type: str) -> dict:
    if doc_type != "ca":
        raise Permanent(f"Chưa có hướng dẫn AI cho loại phôi {doc_type}")
    content = [
        {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                        "data": base64.standard_b64encode(pdf).decode()}},
        {"type": "text", "text": CA_PROMPT},
    ]
    return _json_call(content, PDF_SCHEMA, "You transcribe government forms. Accuracy over completeness.", effort="high")


# ── Website copy ──

SITE_SCHEMA = {
    "type": "object",
    "properties": {
        "tagline": {"type": "string"},
        "intro": {"type": "string"},
        "about": {"type": "array", "items": {"type": "string"}},
        "services": {"type": "array", "items": {"type": "object", "properties": {
            "title": {"type": "string"}, "description": {"type": "string"}},
            "required": ["title", "description"], "additionalProperties": False}},
        "faq": {"type": "array", "items": {"type": "object", "properties": {
            "question": {"type": "string"}, "answer": {"type": "string"}},
            "required": ["question", "answer"], "additionalProperties": False}},
    },
    "required": ["tagline", "intro", "about", "services", "faq"],
    "additionalProperties": False,
}

SITE_SYSTEM = """You write plain, factual small-business website copy in English.
Hard rules:
- Use only the facts given. Never invent awards, certifications, clients, partners, years in business, founding dates,
  team size, prices, statistics, ratings, testimonials or guarantees. Do not write any number that is not in the facts.
- Describe services generically for the industry; no promises of results; no superlatives like "best" or "#1".
- 1 tagline, 1 intro (2-3 sentences), 2-3 about paragraphs, exactly 3 services, 4-5 FAQ items."""


def write_site_copy(facts: dict, industry: str, template_name: str, feedback: str = "") -> dict:
    text = (f"Company facts (from the registration sheet):\n{json.dumps(facts, ensure_ascii=False, indent=2)}\n"
            f"Industry: {industry}\nWebsite template: {template_name}\n")
    if feedback:
        text += f"\nYour previous draft was rejected: {feedback}\nRewrite it following the rules."
    return _json_call([{"type": "text", "text": text}], SITE_SCHEMA, SITE_SYSTEM, effort="medium")
