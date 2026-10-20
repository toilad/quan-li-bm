"""Washington Secretary of State filings and the Brazil "Ficha cadastral" — the two forms most of the owner's Sheet rows
come from (sample of 200 originals, 2026-10-19: WA 141, Ficha 20, Comprovante 29). Made-up companies and numbers; the
text is laid out the way pdfplumber returns the real forms."""
from wg_core.modules.pdf.extract import PdfText, detect, extract_text_layer, split_address
from wg_core.modules.pdf.fields import validate

HEAD = "Filed Secretary of State State of Washington Date Filed: 01/02/2026 Effective Date: 01/02/2026 UBI #: 600 111 222 "
FOOT = ("This document is a public record. For more information visit www.sos.wa.gov/corporations Work Order #: "
        "2026010200000001 - 1 Received Date: 01/02/2026 Amount Received: $200.00 ")


def agent_lines(name: str, street: str, mailing: str) -> list:
    """Page-1 words of the registered agent block: Name | Street Address | Mailing Address columns."""
    return [
        (300, [(36, "REGISTERED"), (138, "AGENT")]),
        (340, [(39, "Registered"), (91, "Agent"), (135, "Street"), (165, "Address"), (357, "Mailing"), (395, "Address")]),
        (365, [(39 + 30 * i, w) for i, w in enumerate(name.split())]
         + [(135 + 25 * i, w) for i, w in enumerate(street.split())] + [(357 + 25 * i, w) for i, w in enumerate(mailing.split())]),
        (404, [(36, "REGISTERED"), (138, "AGENT"), (194, "CONSENT")]),
    ]


def wa(text: str, lines: list | None = None) -> dict:
    t = PdfText(pages=2, text=HEAD + text, lines=lines or [])
    assert detect(t).doc_type == "wa"
    fields, extra = extract_text_layer(t, "wa")
    return {k: v["value"] for k, v in fields.items()} | {"_src": extra["address_source"], "_cands": extra["address_candidates"],
                                                        "_warn": fields["F"].get("warning", ""), "_note": fields["F"].get("note", "")}


def test_annual_report_principal_office():
    f = wa("EXPRESS ANNUAL REPORT WITH CHANGES BUSINESS INFORMATION Business Name: NORTH FORK CIDER LLC UBI Number: 600 111 222 "
           "Business Type: WA LIMITED LIABILITY COMPANY Principal Office Street Address: 100 MAIN ST NE SUITE B, LACEY, WA, 98516, "
           "UNITED STATES Principal Office Mailing Address: PO BOX 1, TUMWATER, WA, 98512-6295, UNITED STATES Expiration Date: x "
           "PRINCIPAL OFFICE Phone: 3605550100 Email: " + FOOT)
    assert f["A"] == "NORTH FORK CIDER LLC" and f["J"] == "600111222" and f["D"] == "3605550100"
    assert f["F"] == "100 MAIN ST NE SUITE B, LACEY, WA 98516" and (f["G"], f["H"], f["I"]) == ("LACEY", "WA", "98516")
    assert f["E"] == "northforkc"  # first 10 characters, like the old app


def test_certificate_principal_office_in_another_state_with_a_floor_and_no_footer_in_the_address():
    f = wa("CERTIFICATE OF FORMATION UBI NUMBER UBI Number: 600 111 222 BUSINESS NAME Business Name BAY TILE LLC REGISTERED AGENT "
           "RCW 23.95.410 Registered Agent Name Street Address Mailing Address ... PRINCIPAL OFFICE Phone: 214-555-0111 Email: A@B.COM "
           + FOOT + "Street Address: 95 THIRD STREET, 2ND FLOOR, SAN FRANCISCO, CA, 94103, UNITED STATES Mailing Address: 95 THIRD "
           "STREET, 2ND FLOOR, SAN FRANCISCO, CA, 94103, UNITED STATES")
    assert f["F"] == "95 THIRD STREET, 2ND FLOOR, SAN FRANCISCO, CA 94103" and f["H"] == "CA" and f["D"] == "214-555-0111"


def test_principal_office_at_a_commercial_agent_uses_the_mailing_address():
    street = "522 W RIVERSIDE AVE STE N, SPOKANE, WA, 99201-0580,"
    f = wa("CERTIFICATE OF FORMATION BUSINESS NAME Business Name GREEN LAKE PAINTING LLC REGISTERED AGENT RCW 23.95.410 x "
           "PRINCIPAL OFFICE Phone: Email: X@Y.COM Street Address: " + FOOT + street + " UNITED STATES Mailing Address: 4011 "
           "MERIDIAN AVE N, SEATTLE, WA, 98103-8305, UNITED STATES EXECUTOR",
           agent_lines("NORTHWEST AGENT, LLC", street, street))
    assert f["F"] == "4011 MERIDIAN AVE N, SEATTLE, WA 98103-8305" and "Mailing" in f["_src"]
    assert f["D"] == ""  # no phone printed: left empty, never guessed


def test_individual_agent_at_the_same_street_keeps_the_principal_office():
    street = "3219 NE SUNSET BLVD STE B, RENTON, WA, 98056,"
    f = wa("CERTIFICATE OF FORMATION BUSINESS NAME Business Name OLIVO TACOS LLC REGISTERED AGENT RCW 23.95.410 x PRINCIPAL "
           "OFFICE Phone: 425-555-0100 Email: Street Address: " + street + " UNITED STATES Mailing Address: 375 UNION AVE SE UNIT "
           "174, RENTON, WA, 98059, UNITED STATES", agent_lines("ERIKA SAMPLE", street, "375 UNION AVE SE UNIT 174, RENTON, WA, 98059,"))
    assert f["F"] == "3219 NE SUNSET BLVD STE B, RENTON, WA 98056"


def test_agent_address_is_only_a_suggestion_po_box_office_kept_and_flagged():
    """Owner's rule (2026-10-19): a registered agent's address never fills F–I by itself."""
    agent = agent_lines("JANE SAMPLE", "2551 DONOVAN AVE, BELLINGHAM, WA, 98225-7621,", "PO BOX 257, OLYMPIA, WA, 98507-0257,")
    f = wa("CERTIFICATE OF FORMATION BUSINESS NAME Business Name BRAIDS L.L.C. REGISTERED AGENT x PRINCIPAL OFFICE Phone: "
           "678-555-0104 Email: Street Address: PO BOX 257, OLYMPIA, WA, 98507-0257, UNITED STATES Mailing Address: PO BOX 257, "
           "OLYMPIA, WA, 98507-0257, UNITED STATES", agent)
    assert f["F"] == "PO BOX 257, OLYMPIA, WA 98507-0257" and "PO BOX" in f["_warn"]  # the company's own, as printed
    assert [(c["role"], c["street"]) for c in f["_cands"]] == [("agent", "2551 DONOVAN AVE")]
    f = wa("ARTICLES OF INCORPORATION BUSINESS NAME Business Name: 401 SUMMIT OWNERS ASSOCIATION NONPROFIT GROSS REVENUE x",
           agent_lines("BRYCE SAMPLE", "1620 WOODARD AVE NW UNIT C3, OLYMPIA, WA, 98502-", "1620 WOODARD AVE NW UNIT C3, OLYMPIA, WA,")
           + [(372, [(135, "4225,"), (165, "UNITED"), (200, "STATES")])])
    assert f["A"] == "401 SUMMIT OWNERS ASSOCIATION" and f["F"] == f["G"] == f["I"] == ""  # no office printed
    assert "không có địa chỉ trụ sở" in f["_note"]
    [c] = f["_cands"]
    assert (c["role"], c["street"], c["city"], c["zip"]) == ("agent", "1620 WOODARD AVE NW UNIT C3", "OLYMPIA", "98502")


def test_a_company_named_registered_agent():
    f = wa("CERTIFICATE OF FORMATION BUSINESS NAME Business Name # REGISTERED AGENT OF OREGON LLC REGISTERED AGENT RCW 23.95.410 x")
    assert f["A"] == "REGISTERED AGENT OF OREGON LLC"


def test_split_address_reads_from_the_end():
    assert split_address("CARRETERA KM. 17.5 # 8100, TLAJOMULCO DE ZUNIGA, JALISCO, 45640, MEXICO") == (
        "CARRETERA KM. 17.5 # 8100", "TLAJOMULCO DE ZUNIGA", "JALISCO", "45640")
    assert split_address("1701 COMMERCE ST, TACOMA, WA, 98402- 3207, UNITED STATES") == ("1701 COMMERCE ST", "TACOMA", "WA", "98402-3207")
    assert split_address("SEATTLE, WA") is None


def test_wa_validation_warns_but_does_not_block_a_foreign_office():
    fields = {k: {"value": v} for k, v in {"A": "X LLC", "D": "+1 206 555 0100", "E": "xllc", "F": "CALLE 1, GUADALAJARA, JALISCO 45640", "G": "GUADALAJARA", "H": "JALISCO",
                                              "I": "45640", "J": "600111222"}.items()}
    issues = validate(fields, "wa")
    # a foreign office: warnings only — H not a US state, and D's area code cannot be matched to a state
    assert {k: v["level"] for k, v in issues.items()} == {"H": "warn", "D": "warn"}


def test_ficha_cadastral():
    text = ("FICHA CADASTRAL DE EMPRESA Dados publicos · Receita Federal - dados abertos CNPJ PADARIA BOA MASSA LTDA Nome fantasia: "
            "BOA MASSA CNPJ: 11.222.333/0001-81 ATIVA Situacao cadastral ATIVA Data inicio atividade 09/05/1994 CNAE principal "
            "1091102 - Fabricação de produtos de padaria Endereco RUA RUI BARBOSA · 661 · SALA 2 · CENTRO · PERUIBE, SP · CEP 11750000 "
            "Municipio / UF PERUIBE / SP CEP 11750000 Telefone +55 (11) 44321746 E-mail CONTATO@EXEMPLO.COM.BR Documento gerado")
    t = PdfText(pages=1, text=text)
    d = detect(t)
    assert d.doc_type == "br" and "FICHA" in d.reason
    f, extra = extract_text_layer(t, "br")
    v = {k: x["value"] for k, x in f.items()}
    assert v["A"] == "PADARIA BOA MASSA LTDA" and v["J"] == "11.222.333/0001-81" and v["D"] == "+55 (11) 44321746"
    assert v["F"] == "RUA RUI BARBOSA, 661, SALA 2, CENTRO, PERUIBE, SP 11750000"
    assert (v["G"], v["H"], v["I"]) == ("PERUIBE", "SP", "11750000")
    assert extra["form"] == "ficha" and extra["email"] == "contato@exemplo.com.br" and extra["cnae_principal"].startswith("1091102")
    assert not {k for k, x in validate(f, "br").items() if x["level"] == "error"}
    t2 = PdfText(pages=1, text=text.replace("Telefone +55 (11) 44321746 ", "Telefone "))
    assert extract_text_layer(t2, "br")[0]["D"]["value"] == ""  # empty phone: never "E-mail"


# ───── F = FULL address, G/H/I parsed back from it (owner, 2026-10-20) — every document type ─────

def test_full_address_rule_f_g_h_i_consistent():
    from wg_core.modules.pdf.extract import address_consistent, fields_from_ai
    from wg_core.modules.pdf.fields import validate

    assert address_consistent("R 7 DE SAMPLE, 876, SALA 302, CENTRO, BLUMENAU, SC 89010202", "BLUMENAU", "SC", "89010202")
    assert address_consistent("R 7 DE SAMPLE, 876, SALA 302, CENTRO, BLUMENAU, SC 89010202", "BLUMENAU", "SC", "89.010-202")
    assert address_consistent("100 Sample Blvd., Ste. 640, Los Angeles, CA 90049-1234", "Los Angeles", "CA", "90049-1234")
    assert not address_consistent("210 Sample Street", "La Jolla", "CA", "92037")  # F = street only: a bug
    issues = validate({k: {"value": v} for k, v in {"A": "X LLC", "J": "201099900001", "F": "210 Sample Street",
                                                     "G": "La Jolla", "H": "CA", "I": "92037"}.items()}, "ca")
    assert issues["F"]["level"] == "error" and "đầy đủ" in issues["F"]["message"]
    # the AI reader returning a street line only: F is completed from G/H/I, never left as the street alone
    ai = {k: {"value": v, "found": True} for k, v in {"A": "X LLC", "F": "210 Sample Street", "G": "La Jolla", "H": "CA",
                                                       "I": "92037", "J": "201099900001"}.items()}
    f = fields_from_ai(ai, "wy")
    assert (f["F"]["value"], f["G"]["value"], f["H"]["value"], f["I"]["value"]) == ("210 Sample Street, La Jolla, CA 92037", "La Jolla", "CA", "92037")
    br = fields_from_ai({**ai, "F": {"value": "R SAMPLE, 876, SALA 302, CENTRO", "found": True}, "G": {"value": "BLUMENAU", "found": True},
                         "H": {"value": "SC", "found": True}, "I": {"value": "89.010-202", "found": True}}, "br")
    assert br["F"]["value"] == "R SAMPLE, 876, SALA 302, CENTRO, BLUMENAU, SC 89010202"
