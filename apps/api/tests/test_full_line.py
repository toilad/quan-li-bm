"""The whole line on ONE in-memory Sheet, every external service mocked:
PDF saved (Drive + A, D–K) → domain created (B) → website built and HTTPS-checked (C).

iNET is an in-memory account following the documented API. The domain step goes the way the owner will run it:
trial subdomain named → switch on → read-only preview → confirmed plan → job. Real job handlers, real queue."""
import hashlib

import httpx
import respx
from tests.conftest import drain
from tests.mocks import FakeInet, FakeSheet, anthropic_json, cp_ok, install_doh, install_drive
from tests.test_websites import GOOD

from wg_core.db import session_scope
from wg_core.models import Job, PdfDocument, SheetWrite
from wg_core.modules.domains import dns_plan
from wg_core.modules.domains import service as domains
from wg_core.modules.pdf import service as pdf
from wg_core.modules.pdf.fields import field
from wg_core.modules.websites import service as web

CP = "https://turboweb-022607.000nethost.com:2083/execute"
IP = "103.75.187.26"
FQDN = "acme.huxma.life"
PDF_BYTES = b"%PDF-1.4\n% synthetic test document, no real company\n%%EOF\n"


def _doc(s) -> PdfDocument:
    md5 = hashlib.md5(PDF_BYTES).hexdigest()
    pdf.storage_path(md5).write_bytes(PDF_BYTES)
    values = {"A": "Acme Plumbing LLC", "D": "(11) 3251-4400", "F": "RUA EXEMPLO, 100 - CENTRO", "G": "SAO PAULO",
              "H": "SP", "I": "01.001-000", "J": "11.222.333/0001-81"}  # public example CNPJ, not a real filing
    fields = {k: field(v, "text") for k, v in values.items()}
    fields["E"] = field("acmeplumbingllc", "auto")
    d = PdfDocument(md5=md5, original_name="synthetic.pdf", size=len(PDF_BYTES), pages=1, has_text=True, doc_type="br",
                    fields=fields, extra={"email": "contato@acme.example", "email_verified": True}, industry={}, status="review")
    s.add(d)
    s.flush()
    return d


def _cpanel(m, answers):
    created = {}

    def listsub(request):
        return cp_ok([{"domain": FQDN, "basedir": f"public_html/{FQDN}", "dir": f"/home/u1/public_html/{FQDN}"}] if created else [])

    def addsub(request):
        created["dir"] = request.url.params["dir"]
        answers[FQDN] = [IP]  # the stubbed A record "propagates" once the host exists
        return cp_ok(None)

    m.get(f"{CP}/DomainInfo/single_domain_data").respond(200, json={"result": {"status": 1, "data": {
        "documentroot": "/home/u1/public_html/huxma.life", "type": "addon_domain", "ip": IP}}})
    m.get(f"{CP}/SubDomain/listsubdomains").mock(side_effect=listsub)
    add = m.get(f"{CP}/SubDomain/addsubdomain").mock(side_effect=addsub)
    upload = m.post(f"{CP}/Fileman/upload_files").mock(return_value=cp_ok({"succeeded": 8, "failed": 0, "uploads": []}))
    m.get(f"{CP}/SSL/start_autossl_check").mock(return_value=cp_ok(None))
    m.get(f"{CP}/SSL/is_autossl_check_in_progress").mock(return_value=cp_ok(0))
    m.get(f"{CP}/SSL/get_autossl_problems").mock(return_value=cp_ok([]))
    return add, upload


def test_pdf_to_domain_to_website_on_one_sheet():
    inet = FakeInet({"huxma.life": {"id": 501, "ns": ["ns1.inet.vn", "ns2.inet.vn"], "records": [{"id": 1, "name": "@", "type": "A", "data": IP, "ttl": 300}]}})
    sheet = FakeSheet({3: {"A": "Existing Co", "B": "old.example.com", "C": "https://old.example.com", "J": "2024-000000001"}})
    answers: dict[str, list[str]] = {}
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m)
        install_drive(m)
        install_doh(m, answers)
        add, upload = _cpanel(m, answers)
        patch = inet.install(m)
        m.get(f"https://{FQDN}/").mock(return_value=httpx.Response(200, text="<title>Acme Plumbing LLC</title>"))
        ai = m.post("https://api.anthropic.com/v1/messages").mock(return_value=anthropic_json(GOOD))

        # 1 · PDF Manager: save → Drive → Sheet A, D–K (B, C empty)
        with session_scope() as s:
            doc = _doc(s)
            assert not pdf.save_check(doc, confirm_missing=False, critical_checked=False)
            pdf.request_save(s, doc)
        drain()
        assert len(sheet.appends) == 1
        row = 4
        assert sheet.rows[row]["A"] == "Acme Plumbing LLC" and sheet.rows[row]["B"] == "" and sheet.rows[row]["C"] == ""
        assert sheet.rows[row]["K"].startswith("=HYPERLINK(")

        # 2 · Domain Manager: ticked root → trial named + switch on → preview (read-only) → confirmed plan →
        #     A record (ACTION_ADD) + cPanel subdomain → DNS verified → B
        with session_scope() as s:
            assert domains.set_selected(s, ["huxma.life"], True)["changed"] == ["huxma.life"]
            dns_plan.set_switch(s, enabled=True, trial_fqdn=FQDN)
        with session_scope() as s:
            plan = dns_plan.preview(s, [{"row": row, "company": "Acme Plumbing LLC", "root": "huxma.life", "label": "acme"}])
            assert plan["token"] and plan["rows"][0]["action"] == "add" and plan["rows"][0]["ip"] == IP and not patch.called
        with session_scope() as s:
            q = domains.enqueue_rows(s, dns_plan.take_plan(s, plan["token"]))
            assert not q["refused"]
        drain()
        assert inet.patches == [{"recordList": [{"domainId": 501, "name": "acme", "type": "A", "data": IP, "ttl": "300", "action": "ACTION_ADD"}]}]
        with session_scope() as s:
            assert dns_plan.mode(dns_plan.get_switch(s)) == "batch"  # the trial passed
        assert add.call_count == 1 and add.calls[0].request.url.params["dir"] == f"public_html/{FQDN}"
        assert sheet.rows[row]["B"] == FQDN and sheet.rows[row]["C"] == ""

        # 3 · SSL + Website: the row now has B and an empty C → build → upload → AutoSSL → HTTPS → C
        with session_scope() as s:
            ready = [r for r in web.scan(s)["rows"] if r["row"] == row]
            assert ready and ready[0]["nick"] and ready[0]["ip"] == IP  # the existing row (C filled) is not offered
            assert all(r["row"] != 3 for r in web.scan(s)["rows"])
            q = web.enqueue_rows(s, [{"row": row, "domain": FQDN, "company": "Acme Plumbing LLC"}])
            assert not q["refused"]
        drain()

    with session_scope() as s:
        jobs = {j.kind: j for j in s.query(Job)}
        assert {k: j.status for k, j in jobs.items()} == {"pdf_save": "done", "domain_create": "done", "web_build": "done"}, \
            {k: j.last_error for k, j in jobs.items()}
        assert jobs["web_build"].state["doc_root"] == f"public_html/{FQDN}"
        writes = [(w.range, w.new_value) for w in s.query(SheetWrite).order_by(SheetWrite.id)]
    assert sheet.rows[row]["C"] == f"https://{FQDN}"
    assert sheet.rows[3] == {"A": "Existing Co", "B": "old.example.com", "C": "https://old.example.com", "J": "2024-000000001"}  # untouched
    assert [w[0] for w in writes][-2:] == [f"B{row}", f"C{row}"]  # B only by Domain Manager, C only after HTTPS works
    assert ai.call_count == 1 and upload.call_count == 1
    body = upload.calls[0].request.content.decode("utf-8", "ignore")
    assert 'action="mailto:contato@acme.example"' in body  # verified email → the legacy contact form is shown
    assert "Acme Plumbing LLC" in body and "(11) 3251-4400" in body
