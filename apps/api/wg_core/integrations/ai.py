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
    "properties": {
        "doc_type": {"type": "string", "enum": ["ca", "wy", "br", "unknown"]},
        "evidence": {"type": "string"},
        **{k: _FIELD for k in ("A", "D", "F", "G", "H", "I", "J")},
    },
    "required": ["doc_type", "evidence", "A", "D", "F", "G", "H", "I", "J"],
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
of page 1. F = item 3a initial street address (street line). G, H, I = city, state, ZIP of item 3a. D = phone (LLC-1 has none).
Fields for wy: A = name of the LLC. J = the Original ID / filing ID. F, G, H, I = the company's mailing or principal address
(street, city, state, ZIP). D = the company's phone if printed.
Fields for br: A = NOME EMPRESARIAL. J = NÚMERO DE INSCRIÇÃO (as printed, 00.000.000/0000-00). F = LOGRADOURO, NÚMERO,
COMPLEMENTO - BAIRRO (skip boxes printed as asterisks). G = MUNICÍPIO. H = UF. I = CEP as printed. D = TELEFONE.
For unknown: return found=false for every field."""


def read_scanned_pdf(pdf: bytes) -> dict:
    """Classify + transcribe a scanned registration document. Every value comes back marked as read by AI."""
    content = [
        {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                        "data": base64.standard_b64encode(pdf).decode()}},
        {"type": "text", "text": PDF_PROMPT},
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


def check_model() -> dict:
    """Ask the Models API whether the configured model exists for this key (no tokens spent)."""
    client = _client()
    try:
        m = client.models.retrieve(settings().ai_model)
    except anthropic.NotFoundError as e:
        raise Permanent(f"Model {settings().ai_model} không có với khoá này") from e
    except anthropic.AuthenticationError as e:
        raise NotConfigured("AI (Anthropic)", ["ANTHROPIC_API_KEY hợp lệ"]) from e
    except anthropic.APIConnectionError as e:
        raise Transient("AI: lỗi mạng") from e
    return {"id": m.id, "display_name": getattr(m, "display_name", None), "max_input_tokens": getattr(m, "max_input_tokens", None),
            "max_tokens": getattr(m, "max_tokens", None), "sdk": anthropic.__version__}
