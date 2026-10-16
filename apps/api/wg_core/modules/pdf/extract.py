"""Detect the document type and extract Sheet fields from the PDF text layer.

- Brazil Comprovante CNPJ: column-aware parsing (word x positions under each printed label).
- California LLC-1: scanned (no text) → read by AI (integrations.ai), every field marked source=ai.
- Wyoming Articles of Organization: label-based parsing of the text layer.
  ⚠ No real Wyoming sample yet: fields not found stay empty for review; nothing is guessed.
"""
import io
import re
from dataclasses import dataclass, field as dfield

import pdfplumber

from .fields import field, short_name, strip_accents


@dataclass
class Detection:
    doc_type: str  # wy|ca|br|unknown
    confidence: float
    reason: str


@dataclass
class PdfText:
    pages: int
    text: str
    lines: list = dfield(default_factory=list)  # [(top, [(x0, word), ...])] page 1


def read_pdf(data: bytes) -> PdfText:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        lines = []
        if pdf.pages:
            rows: dict[int, list] = {}
            for w in pdf.pages[0].extract_words(keep_blank_chars=False):
                rows.setdefault(round(w["top"]), []).append((w["x0"], w["text"]))
            # merge rows whose tops differ by ≤2pt (same printed line)
            merged: list[tuple[int, list]] = []
            for top in sorted(rows):
                if merged and top - merged[-1][0] <= 2:
                    merged[-1][1].extend(rows[top])
                else:
                    merged.append((top, list(rows[top])))
            lines = [(t, sorted(ws)) for t, ws in merged]
        return PdfText(pages=len(pdf.pages), text=text, lines=lines)


def _norm(s: str) -> str:
    return strip_accents(s).upper()


def detect(t: PdfText) -> Detection:
    n = _norm(t.text)
    if "CADASTRO NACIONAL DA PESSOA JURIDICA" in n and "COMPROVANTE DE INSCRICAO" in n:
        return Detection("br", 0.99, "Có “CADASTRO NACIONAL DA PESSOA JURÍDICA” + “COMPROVANTE DE INSCRIÇÃO”")
    if "STATE OF WYOMING" in n and "ARTICLES OF ORGANIZATION" in n:
        return Detection("wy", 0.95, "Có “STATE OF WYOMING” + “Articles of Organization”")
    if "LLC-1" in n and "CALIFORNIA" in n:
        return Detection("ca", 0.9, "Có “LLC-1” + “California” trong lớp chữ")
    if len(n.strip()) < 20:
        # Scanned, no text layer. The only scanned form we handle is California LLC-1 → confirm by AI read.
        return Detection("unknown", 0.0, "PDF là bản scan, không có lớp chữ — chọn loại phôi (vd California LLC-1) để AI đọc")
    return Detection("unknown", 0.0, "Không khớp mẫu phôi nào đã biết — không đoán")


# ───────────────────────── Brazil ─────────────────────────

BR_HEADERS = {
    "NUMERO DE INSCRICAO": ["NUMERO", "DATA"],
    "NOME EMPRESARIAL": ["NOME"],
    "TITULO DO ESTABELECIMENTO": ["TITULO", "PORTE"],
    "CODIGO E DESCRICAO DA ATIVIDADE ECONOMICA PRINCIPAL": ["CODIGO"],
    "CODIGO E DESCRICAO DAS ATIVIDADES ECONOMICAS SECUNDARIAS": ["CODIGO"],
    "CODIGO E DESCRICAO DA NATUREZA JURIDICA": ["CODIGO"],
    "LOGRADOURO": ["LOGRADOURO", "NUMERO", "COMPLEMENTO"],
    "CEP": ["CEP", "BAIRRO/DISTRITO", "MUNICIPIO", "UF"],
    "ENDERECO ELETRONICO": ["ENDERECO", "TELEFONE"],
    "SITUACAO CADASTRAL": ["SITUACAO", "DATA"],
}
# Printed headers we do not read; they only end the block above them.
BR_STOP = ("ENTE FEDERATIVO", "MOTIVO DE SITUACAO", "SITUACAO ESPECIAL", "APROVADO PELA", "EMITIDO NO DIA")


def _br_blocks(t: PdfText) -> dict[str, dict[str, str]]:
    """For each known header line: {column label: value text}, value lines = lines until the next header."""
    lines = [(top, ws, _norm(" ".join(w for _, w in ws))) for top, ws in t.lines]
    header_idx = []
    for i, (_, ws, txt) in enumerate(lines):
        if txt.startswith(BR_STOP):
            header_idx.append((i, None))
            continue
        for key in BR_HEADERS:
            if txt.startswith(key):
                header_idx.append((i, key))
                break
    out: dict[str, dict[str, str]] = {}
    for n, (i, key) in enumerate(header_idx):
        if key is None:
            continue
        end = header_idx[n + 1][0] if n + 1 < len(header_idx) else len(lines)
        hdr_words = lines[i][1]
        cols = []
        for label in BR_HEADERS[key]:
            x = next((x for x, w in hdr_words if _norm(w) == label), None)
            if x is not None:
                cols.append((x, label))
        cols.sort()
        vals = {label: [] for _, label in cols}
        for top, ws, txt in lines[i + 1:end]:
            if txt.startswith(("COMPROVANTE", "CADASTRAL", "MATRIZ", "FILIAL", "APROVADO", "EMITIDO", "ABOUT:BLANK")) and key != "NOME EMPRESARIAL":
                continue
            for x, w in ws:
                label = cols[0][1]
                for cx, cl in cols:
                    if x >= cx - 2:
                        label = cl
                vals[label].append(w)
        out[key] = {k: " ".join(v).strip() for k, v in vals.items()}
    return out


def _star(v: str) -> str:
    return "" if not v or set(v.replace(" ", "")) <= {"*"} else v


def extract_br(t: PdfText) -> tuple[dict, dict]:
    b = _br_blocks(t)
    g = lambda k, c: _star(b.get(k, {}).get(c, ""))  # noqa: E731
    cnpj = (g("NUMERO DE INSCRICAO", "NUMERO").split() or [""])[0]
    name = g("NOME EMPRESARIAL", "NOME")
    lograd, numero, compl = g("LOGRADOURO", "LOGRADOURO"), g("LOGRADOURO", "NUMERO"), g("LOGRADOURO", "COMPLEMENTO")
    bairro = g("CEP", "BAIRRO/DISTRITO")
    street = lograd
    if numero and not re.search(rf"\b{re.escape(numero)}$", lograd):
        street = f"{lograd}, {numero}" if lograd else numero
    parts = [street] + ([compl] if compl else [])
    address = ", ".join(p for p in parts if p) + (f" - {bairro}" if bairro else "")
    phone = g("ENDERECO ELETRONICO", "TELEFONE")
    fields = {
        "A": field(name, "text"),
        "D": field(phone, "text", "Có nhiều số — giữ nguyên như phôi" if "/" in phone else None),
        "F": field(address, "text", "LOGRADOURO, NÚMERO, COMPLEMENTO - BAIRRO (bỏ ô ********)"),
        "G": field(g("CEP", "MUNICIPIO"), "text"),
        "H": field(g("CEP", "UF"), "text"),
        "I": field(g("CEP", "CEP"), "text"),
        "J": field(cnpj, "text"),
    }
    fields["E"] = field(short_name(name), "auto", "Tự sinh từ A")
    cnae = g("CODIGO E DESCRICAO DA ATIVIDADE ECONOMICA PRINCIPAL", "CODIGO")
    situ = g("SITUACAO CADASTRAL", "SITUACAO")
    extra = {
        "data_abertura": (g("NUMERO DE INSCRICAO", "DATA").split() or [""])[0],
        "nome_fantasia": g("TITULO DO ESTABELECIMENTO", "TITULO"),
        "porte": g("TITULO DO ESTABELECIMENTO", "PORTE"),
        "cnae_principal": cnae,
        "cnae_secundarias": g("CODIGO E DESCRICAO DAS ATIVIDADES ECONOMICAS SECUNDARIAS", "CODIGO"),
        "natureza_juridica": g("CODIGO E DESCRICAO DA NATUREZA JURIDICA", "CODIGO"),
        "email": g("ENDERECO ELETRONICO", "ENDERECO"),
        "situacao_cadastral": situ,
        "data_situacao": g("SITUACAO CADASTRAL", "DATA"),
    }
    if situ and situ.upper() != "ATIVA":
        extra["warning"] = f"Situação cadastral: {situ} (không phải ATIVA)"
    return fields, extra


# ───────────────────────── Wyoming (text layer) ─────────────────────────

def _after(label_rx: str, text: str) -> str:
    m = re.search(label_rx + r"\s*[:\-]?\s*(.+)", text, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def extract_wy(t: PdfText) -> tuple[dict, dict]:
    txt = t.text
    name = _after(r"Name of the (?:Limited Liability Company|LLC)", txt)
    oid = _after(r"Original ID", txt).split()[0] if _after(r"Original ID", txt) else ""
    fields = {
        "A": field(name, "text"),
        "D": field(_after(r"(?:Daytime )?Phone", txt), "text"),
        "F": field("", "missing"), "G": field("", "missing"), "H": field("", "missing"), "I": field("", "missing"),
        "J": field(oid, "text"),
    }
    m = re.search(r"Mailing Address\s*[:\-]?\s*(.+?),\s*([A-Za-z .]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)", txt, re.IGNORECASE)
    if m:
        fields["F"], fields["G"] = field(m.group(1), "text"), field(m.group(2), "text")
        fields["H"], fields["I"] = field(m.group(3).upper(), "text"), field(m.group(4), "text")
    fields["E"] = field(short_name(fields["A"]["value"]), "auto", "Tự sinh từ A")
    return fields, {"note": "Bộ đọc Wyoming chưa được kiểm trên phôi thật — kiểm tra kỹ từng ô"}


# ───────────────────────── California (AI result) ─────────────────────────

def fields_from_ai(ai: dict, doc_type: str) -> dict:
    out = {}
    for k in ("A", "D", "F", "G", "H", "I", "J"):
        f = ai.get(k) or {}
        out[k] = field(f.get("value", "") if f.get("found") else "", "ai")
    h = out["H"]["value"]
    if h.upper() in ("CALIFORNIA", "CALIF.", "CALIF"):
        out["H"] = field("CA", "ai", f"Chuẩn hoá “{h}” → CA")
    out["E"] = field(short_name(out["A"]["value"]), "auto", "Tự sinh từ A")
    return out
