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
    if "FICHA CADASTRAL DE EMPRESA" in n and "RECEITA FEDERAL" in n and "CNPJ" in n:
        return Detection("br", 0.95, "Có “FICHA CADASTRAL DE EMPRESA” (dữ liệu mở Receita Federal) — không phải Comprovante chính thức")
    if "SECRETARY OF STATE" in n and "STATE OF WASHINGTON" in n and "UBI" in n:
        return Detection("wa", 0.97, "Có “Secretary of State · State of Washington” + số UBI")
    if "STATE OF WYOMING" in n and "ARTICLES OF ORGANIZATION" in n:
        return Detection("wy", 0.95, "Có “STATE OF WYOMING” + “Articles of Organization”")
    if "LLC-1" in n and "CALIFORNIA" in n:
        return Detection("ca", 0.9, "Có “LLC-1” + “California” trong lớp chữ")
    if len(n.strip()) < 20:
        # Scanned, no text layer. The only scanned form we handle is California LLC-1 → confirm by AI read.
        return Detection("unknown", 0.0, "PDF là bản scan, không có lớp chữ — chọn loại phôi (vd California LLC-1) để AI đọc")
    return Detection("unknown", 0.0, "Không khớp mẫu phôi nào đã biết — không đoán")


def extract_text_layer(t: PdfText, doc_type: str) -> tuple[dict, dict] | None:
    """Fields from the text layer for the forms that have a reader; None = this form needs the AI (scan) or a person."""
    if doc_type == "br":
        return extract_ficha(t) if "FICHA CADASTRAL DE EMPRESA" in _norm(t.text) else extract_br(t)
    if doc_type == "wa":
        return extract_wa(t)
    if doc_type == "wy":
        return extract_wy(t)
    return None


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
    city, uf, cep = g("CEP", "MUNICIPIO"), g("CEP", "UF"), re.sub(r"\D", "", g("CEP", "CEP"))
    # The owner's Sheet (checked on 16 rows, 2026-10-19): F = "LOGRADOURO, NÚMERO, COMPLEMENTO, BAIRRO, MUNICÍPIO, UF CEP",
    # I = the CEP digits, D = the first number printed.
    address = us_style_address(", ".join(p for p in (street, compl, bairro) if p), city, uf, cep)
    phone = g("ENDERECO ELETRONICO", "TELEFONE")
    fields = {
        "A": field(name, "text"),
        "D": field(first_phone(phone), "text", f"Phôi có nhiều số: {phone}" if "/" in phone else None),
        "F": field(address, "text", "LOGRADOURO, NÚMERO, COMPLEMENTO, BAIRRO, MUNICÍPIO, UF CEP (bỏ ô ********)"),
        "G": field(city, "text"),
        "H": field(uf, "text"),
        "I": field(cep, "text", "CEP chỉ gồm chữ số"),
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
        # raw boxes as printed (shown next to the composed address for checking)
        "logradouro": lograd, "numero": numero, "complemento": compl, "bairro": bairro,
        "cep": g("CEP", "CEP"), "municipio": g("CEP", "MUNICIPIO"), "uf": g("CEP", "UF"), "telefone": phone,
        "data_situacao": g("SITUACAO CADASTRAL", "DATA"),
    }
    if situ and situ.upper() != "ATIVA":
        extra["warning"] = f"Situação cadastral: {situ} (không phải ATIVA)"
    return fields, extra


# ───────────────────────── Brazil "Ficha cadastral de empresa" (text layer) ─────────────────────────
# A one-page summary generated from Receita Federal open data (not the official comprovante), e.g.
#   "… dados abertos CNPJ <NAME> Nome fantasia: <X> CNPJ: 00.001.441/0001-08 ATIVA … CNAE principal 8211300 - … Endereco
#    RUA RUI BARBOSA · 661 · B. DAS JANGADAS · PERUIBE, SP · CEP 11750000 Municipio / UF PERUIBE / SP CEP 11750000
#    Telefone +55 (11) 44321746 E-mail …"

def _flat(t: PdfText) -> str:
    return " ".join(t.text.split())


def _m(rx: str, s: str, group: int = 1) -> str:
    found = re.search(rx, s)
    return (found.group(group) or "").strip() if found else ""


def first_phone(phone: str) -> str:
    """The owner keeps one number in D (the first printed)."""
    return phone.split("/")[0].strip()


def us_style_address(street: str, city: str, state: str, code: str) -> str:
    """F as the owner writes it: "STREET, CITY, ST CODE" (the full line, also used on the website)."""
    tail = " ".join(x for x in (state, code) if x)
    return ", ".join(x for x in (street, city, tail) if x)


def extract_ficha(t: PdfText) -> tuple[dict, dict]:
    s = _flat(t)
    name = _m(r"dados abertos CNPJ (.+?) (?:Nome fantasia:|CNPJ:)", s)
    cnpj = _m(r"CNPJ: (\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", s)
    city, uf = _m(r"Munic[ií]pio / UF (.+?) / ([A-Z]{2})\b", s), _m(r"Munic[ií]pio / UF (.+?) / ([A-Z]{2})\b", s, 2)
    cep = _m(r"Munic[ií]pio / UF .+? CEP (\d{8})", s)
    raw = _m(r"Endere[cç]o (.+?) Munic[ií]pio / UF", s)
    parts = [p.strip() for p in raw.split("·") if p.strip()]
    parts = [p for p in parts if not p.startswith("CEP ") and p != f"{city}, {uf}"]  # city / UF / CEP go at the end
    phone = _m(r"Telefone (\+?[\d(][\d() ./-]{6,}\d)", s)
    fields = {
        "A": field(name, "text"),
        "D": field(first_phone(phone), "text", f"Phôi có nhiều số: {phone}" if "/" in phone else None),
        "F": field(us_style_address(", ".join(parts), city, uf, cep), "text", "Endereço, MUNICÍPIO, UF CEP"),
        "G": field(city, "text"), "H": field(uf, "text"), "I": field(cep, "text"), "J": field(cnpj, "text"),
    }
    fields["E"] = field(short_name(name), "auto", "Tự sinh từ A")
    situ = _m(r"Situa[cç][aã]o cadastral (\w+)", s)
    extra = {"form": "ficha", "nome_fantasia": _m(r"Nome fantasia: (.+?) CNPJ:", s), "situacao_cadastral": situ,
             "cnae_principal": _m(r"CNAE principal (.+?) Endere[cç]o", s), "email": _m(r"E-mail (\S+@\S+)", s).lower(),
             "data_abertura": _m(r"Data in[ií]cio atividade (\d{2}/\d{2}/\d{4})", s), "telefone": phone, "endereco": raw,
             "note": "Ficha cadastral (dữ liệu mở Receita Federal) — không phải Comprovante chính thức"}
    if situ and situ.upper() != "ATIVA":
        extra["warning"] = f"Situação cadastral: {situ} (không phải ATIVA)"
    return fields, extra


# ───────────────────────── Washington Secretary of State (text layer) ─────────────────────────
# Certificate of Formation / Articles of Incorporation / Foreign Registration / Annual Report: "Filed Secretary of State
# State of Washington … UBI #: 604 704 009 …". Principal office: "Principal Office Street Address: …" (annual report) or
# "PRINCIPAL OFFICE Phone: … Street Address: …". Without a principal office: the registered agent's street address.

WA_ADDR = r"(\d[^,]*?(?:,\s*(?:STE|SUITE|UNIT|APT|#|BLDG|FL|PMB)[^,]*)?),\s*([A-Z][A-Z .'-]+?),\s*([A-Z]{2}),\s*(\d{5}(?:-\d{4})?)"
COUNTRY_END = re.compile(r",\s*(UNITED STATES|USA|U\.S\.A\.|CANADA|MEXICO|[A-Z][A-Z ]{2,30})\s*$")


def split_address(line: str) -> tuple[str, str, str, str] | None:
    """"95 THIRD STREET, 2ND FLOOR, SAN FRANCISCO, CA, 94103, UNITED STATES" → (street, city, state, postal code),
    read from the end: [country], postal code, state, city; everything before is the street (kept as printed)."""
    line = re.sub(r"(\d{5}-)\s+(\d{4})", r"\1\2", " ".join(line.split())).strip(" ,")
    parts = [p.strip() for p in line.split(",") if p.strip()]
    if parts and not re.search(r"\d", parts[-1]):
        parts = parts[:-1]  # country
    if len(parts) < 4 or not re.fullmatch(r"[A-Z0-9][A-Z0-9 -]{2,10}", parts[-1]) or not re.search(r"\d", parts[-1]):
        return None
    code, state, city = parts[-1], parts[-2], parts[-3]
    return ", ".join(parts[:-3]), city, state, code


def _wa_agent_street(t: PdfText) -> tuple | None:
    return _wa_agent(t)[0]


def _wa_agent(t: PdfText) -> tuple[tuple | None, str]:
    """Registered agent block, laid out in columns (Name | Street Address | Mailing Address): (street address read from the
    words under the "Street Address" column only, the agent's name from the column left of it), from page 1 positions."""
    lines = [(top, ws, _norm(" ".join(w for _, w in ws))) for top, ws in t.lines]
    start = next((i for i, (_, ws, txt) in enumerate(lines) if txt.startswith("REGISTERED AGENT") and "CONSENT" not in txt), None)
    if start is None:
        return None, ""
    hdr = next((i for i in range(start, min(start + 4, len(lines))) if "STREET" in lines[i][2] and "MAILING" in lines[i][2]), None)
    if hdr is None:
        return None, ""
    xs = {_norm(w): x for x, w in lines[hdr][1]}
    x_street, x_mail = xs.get("STREET"), xs.get("MAILING")
    if x_street is None or x_mail is None:
        return None, ""
    words, name = [], []
    for _, ws, txt in lines[hdr + 1:hdr + 6]:
        if txt.startswith(("REGISTERED AGENT CONSENT", "DURATION", "EFFECTIVE DATE", "PRINCIPAL OFFICE")):
            break
        words += [w for x, w in ws if x_street - 4 <= x < x_mail - 4]
        name += [w for x, w in ws if x < x_street - 4 and _norm(w) not in ("NAME", "REGISTERED", "AGENT")]
    text = re.sub(r"(\d{5}-)\s+(\d{4})", r"\1\2", " ".join(words))
    found = re.search(WA_ADDR, text)
    return (tuple(g.strip() for g in found.groups()) if found else None), " ".join(name)


COMMERCIAL_AGENT = re.compile(r"\b(INC|LLC|L\.L\.C|CORP|CORPORATION|COMPANY|CO|SERVICES?|AGENTS?|LTD|PLLC|LLP)\b\.?", re.I)
PO_BOX = re.compile(r"^P\.?\s*O\.?\s*BOX\b", re.I)


def extract_wa(t: PdfText) -> tuple[dict, dict]:
    # The page footer ("This document is a public record … Amount Received: $200.00") lands inside the address block.
    s = re.sub(r"This document is a public record.*?Amount Received: \$[\d.,]+ ?", "", _flat(t))
    name = _m(r"Business Name:? #? ?(.+?) (?:UBI Number|Business Type|REGISTERED AGENT\b(?! OF\b)|NONPROFIT|"
              r"JURISDICTION|DOING BUSINESS|PRINCIPAL OFFICE|NATURE OF BUSINESS|EFFECTIVE DATE|DURATION|ANY OTHER|PURPOSE)", s)
    ubi = re.sub(r"\D", "", _m(r"UBI (?:#|Number):? ([\d ]{9,11})", s))
    phone = _m(r"PRINCIPAL OFFICE Phone: (\+?[\d(][\d() .-]{6,}\d)", s)
    addr, source = None, ""
    for rx, src in ((r"Principal Office Street Address: (.+?) Principal Office Mailing", "Principal Office Street Address"),
                    (r"PRINCIPAL OFFICE Phone:.{0,600}? Street Address: (.+?) (?:Mailing Address|GOVERNORS|EXECUTOR|This document)",
                     "PRINCIPAL OFFICE · Street Address")):
        found = re.search(rx, s)
        if found and (addr := split_address(found.group(1))):
            source = src
            break
    agent, agent_name = _wa_agent(t)
    if addr and agent and PO_BOX.match(addr[0]) and not PO_BOX.match(agent[0]):
        addr, source = agent, "Registered Agent · Street Address (trụ sở chỉ in PO BOX)"
    elif addr and agent and _norm(addr[0]) == _norm(agent[0]) and COMMERCIAL_AGENT.search(agent_name):
        # The principal office printed is a commercial registered agent's office (e.g. "… SERVICES INC." in Spokane):
        # the owner then uses the principal office MAILING address, where the company really is (not a PO box).
        # An individual agent at the same street is the company's own address: kept.
        one = r"(\d[^:]*?, (?:UNITED STATES|USA|MEXICO|CANADA))"  # a street address that starts with a number
        mail = (split_address(_m(r"PRINCIPAL OFFICE Phone:.{0,900}? Mailing Address: " + one, s))
                or split_address(_m(r"Principal Office Mailing Address: " + one, s)))
        if mail and not re.match(r"P\.?\s*O\.?\s*BOX", mail[0], re.I) and _norm(mail[0]) != _norm(addr[0]):
            addr, source = mail, "Principal Office · Mailing Address (địa chỉ trụ sở trùng địa chỉ registered agent)"
    if not addr:
        addr = agent
        source = "Registered Agent · Street Address (phôi không có trụ sở chính)" if addr else ""
    street, city, state, zipc = addr or ("", "", "", "")
    note = f"Lấy từ: {source}" if source else None
    fields = {
        "A": field(name, "text"),
        "D": field(phone, "text", None if phone else "Phôi không in số điện thoại trụ sở"),
        "F": field(us_style_address(street, city, state, zipc), "text", note),
        "G": field(city, "text", note), "H": field(state, "text"), "I": field(zipc, "text"),
        "J": field(ubi, "text", "UBI, bỏ khoảng trắng"),
    }
    fields["E"] = field(short_name(name), "auto", "Tự sinh từ A")
    extra = {"form": _m(r"UBI #: [\d ]+ (.+?) (?:UBI NUMBER|BUSINESS INFORMATION|BUSINESS NAME)", s).title(),
             "address_source": source, "email": _m(r"([\w.+-]+@[\w-]+\.[\w.]+)", s).lower(),
             "date_filed": _m(r"Date Filed: (\d{2}/\d{2}/\d{4})", s), "nature_of_business": _m(r"Nature of Business: (.+?) REGISTERED AGENT", s)}
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

def _cross_check(out: dict, ai: dict):
    """California: compare J and A with the copies printed on a later page (read separately by the AI).
    The result is kept on the field (`check`); validate() blocks a J mismatch. A manual edit replaces the field."""
    j = out["J"]["value"]
    if re.fullmatch(r"[\d ]+", j):
        out["J"]["value"] = j.replace(" ", "")
    for k, norm in (("J", lambda v: re.sub(r"\D", "", v)), ("A", lambda v: re.sub(r"[^A-Z0-9]", "", v.upper()))):
        rep = ai.get(f"{k}_repeat") or {}
        if not out[k]["value"]:
            continue
        if rep.get("found") and rep.get("value", "").strip():
            other = rep["value"].strip()
            out[k]["check"] = {"other": other, "match": norm(other) == norm(out[k]["value"])}
        else:
            out[k]["check"] = {"other": "", "match": None}


def fields_from_ai(ai: dict, doc_type: str) -> dict:
    out = {}
    for k in ("A", "D", "F", "G", "H", "I", "J"):
        f = ai.get(k) or {}
        out[k] = field(f.get("value", "") if f.get("found") else "", "ai")
    if doc_type == "ca":
        _cross_check(out, ai)
    h = out["H"]["value"]
    if h.upper() in ("CALIFORNIA", "CALIF.", "CALIF"):
        out["H"] = field("CA", "ai", f"Chuẩn hoá “{h}” → CA")
    out["E"] = field(short_name(out["A"]["value"]), "auto", "Tự sinh từ A")
    return out
