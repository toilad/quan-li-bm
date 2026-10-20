"""Retries after an answer was lost must not repeat a side effect (duplicate Sheet row, second subdomain, re-upload)."""
import httpx
import respx

from tests.conftest import drain
from tests.mocks import FakeSheet, install_drive
from tests.test_full_line import _doc
from wg_core.db import session_scope
from wg_core.models import Job, PdfDocument
from wg_core.modules.pdf import service as pdf


def _retry_now(job_id):
    with session_scope() as s:
        j = s.get(Job, job_id)
        j.run_after = j.created_at


def test_sheet_append_whose_reply_was_lost_is_not_written_twice():
    sheet = FakeSheet({3: {"A": "Existing Co", "J": "2024-000000001", "H": "WY"}})
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m, ghost_append=1)  # Sheets writes the row but the answer is a 503
        install_drive(m)
        with session_scope() as s:
            doc = _doc(s)
            job, _ = pdf.request_save(s, doc)
            job_id, doc_id = job.id, doc.id
        drain()
        with session_scope() as s:
            assert s.get(Job, job_id).status == "queued"  # transient → retry later
        _retry_now(job_id)
        drain()
    with session_scope() as s:
        assert s.get(Job, job_id).status == "done" and s.get(PdfDocument, doc_id).sheet_row == 4
    assert len(sheet.appends) == 1  # the row written by the lost attempt was found and reused
    assert sheet.writes[-1][0] == "K4"


def test_google_network_error_is_retried_not_failed():
    sheet = FakeSheet({})
    with respx.mock(assert_all_called=False) as m:
        # the row write times out (registered before the fake's own routes, so it is the one matched)
        m.put(url__regex=r".*/values/.*A\d+(%3A|:)K\d+.*").mock(side_effect=httpx.ConnectTimeout("timed out"))
        sheet.install(m)
        install_drive(m)
        with session_scope() as s:
            doc = _doc(s)
            job, _ = pdf.request_save(s, doc)
            job_id = job.id
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "queued" and "lỗi mạng" in j.last_error  # will retry, not "failed"


# ───────── domains ─────────

def test_subdomain_created_by_a_lost_attempt_is_not_created_again_and_b_waits_for_the_right_company():
    from tests.mocks import cp_account, cp_ok, install_doh
    from tests.test_dns_write import batch_mode, fake_inet
    from tests.test_domains import CP, ROW, _tick
    from wg_core.modules.domains import service as domains

    _tick("huxma.life")
    batch_mode()
    sheet = FakeSheet({ROW: {"A": "Acme LLC"}})
    calls = {"list": 0}

    def listsub(request):  # empty at the pre-check, present afterwards (created by the attempt whose answer was lost)
        calls["list"] += 1
        return cp_ok([] if calls["list"] == 1 else [{"domain": "acme.huxma.life", "basedir": "public_html/acme.huxma.life"}])

    with respx.mock(assert_all_called=False) as m:
        sheet.install(m)
        install_doh(m, {"acme.huxma.life": ["103.75.187.26"]})
        cp_account(m, CP)
        m.get(f"{CP}/DomainInfo/single_domain_data").respond(200, json={"status": 1, "data": {"documentroot": "/home/u1/public_html/huxma.life"}})
        m.get(f"{CP}/SubDomain/listsubdomains").mock(side_effect=listsub)
        m.get(f"{CP}/AddonDomain/listaddondomains").mock(return_value=cp_ok([]))  # not an addon domain
        add = m.get(f"{CP}/SubDomain/addsubdomain").mock(return_value=cp_ok(None))
        fake_inet().install(m)
        with session_scope() as s:
            job_id = domains.enqueue_rows(s, [{"row": ROW, "company": "Acme LLC", "root": "huxma.life", "label": "acme"}])["queued"][0]["job_id"]
        sheet.rows[ROW]["A"] = "Someone Else LLC"  # the owner sorted the Sheet meanwhile
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "conflict" and "Someone Else LLC" in j.last_error
    assert not add.called and sheet.writes == []  # not created twice; B not written on another company's row


def test_b1_does_not_wait_for_dns_propagation():
    """Owner, 2026-10-20: "tạo xong là xong" — B is written once the A record is on iNET and the name on cPanel."""
    from tests.mocks import install_doh
    from tests.test_dns_write import batch_mode, fake_inet
    from tests.test_domains import ROW, _routes, _tick
    from wg_core.modules.domains import service as domains

    _tick("huxma.life")
    batch_mode()
    sheet = FakeSheet({ROW: {"A": "Acme LLC"}})
    with respx.mock(assert_all_called=False) as m:
        _routes(m, sheet, {})
        fake_inet().install(m)
        with session_scope() as s:
            job_id = domains.enqueue_rows(s, [{"row": ROW, "company": "Acme LLC", "root": "huxma.life", "label": "acme"}])["queued"][0]["job_id"]
        drain()  # public DNS has nothing yet
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "done" and j.attempts == 1 and j.state["written_b"] == "acme.huxma.life"
    assert sheet.writes == [(f"B{ROW}", "acme.huxma.life")]


# ───────── websites ─────────

def _web(m, sheet, files=None, https_body="<title>Acme Plumbing LLC</title>"):
    from tests.mocks import cp_ok, install_doh
    from tests.test_websites import CP, DOMAIN, GOOD
    from tests.mocks import anthropic_json

    sheet.install(m)
    install_doh(m, {DOMAIN: ["103.75.187.26"]})
    m.get(f"{CP}/SubDomain/listsubdomains").mock(return_value=cp_ok([{"domain": DOMAIN, "basedir": "sites/acme"}]))
    m.get(f"{CP}/AddonDomain/listaddondomains").mock(return_value=cp_ok([]))  # not an addon domain
    m.get(f"{CP}/Fileman/list_files").mock(return_value=cp_ok({"files": [{"file": f, "type": "file"} for f in (files or [])], "dirs": []}))
    m.get(f"{CP}/SSL/start_autossl_check").mock(return_value=cp_ok(None))
    m.get(f"{CP}/SSL/is_autossl_check_in_progress").mock(return_value=cp_ok(0))
    m.get(f"{CP}/SSL/get_autossl_problems").mock(return_value=cp_ok([]))
    m.get(f"https://{DOMAIN}/").mock(return_value=httpx.Response(200, text=https_body))
    m.post("https://api.anthropic.com/v1/messages").mock(return_value=anthropic_json(GOOD))


def test_existing_site_files_in_the_folder_are_never_replaced():
    from tests.test_websites import _run, _sheet, CP

    sheet = _sheet()
    with respx.mock(assert_all_called=False) as m:
        _web(m, sheet, files=["index.html", "wp-config.php"])
        upload = m.post(f"{CP}/Fileman/upload_files").mock(return_value=httpx.Response(200, json={"status": 1, "data": {"failed": 0}}))
        job_id = _run()
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "failed" and "index.html" in j.last_error
    assert not upload.called and sheet.writes == []


def test_upload_whose_answer_was_lost_is_redone_over_its_own_files_only():
    from tests.test_websites import _run, _sheet, CP, DOMAIN

    sheet = _sheet()
    with respx.mock(assert_all_called=False) as m:
        _web(m, sheet)
        upload = m.post(f"{CP}/Fileman/upload_files").mock(side_effect=[
            httpx.ReadTimeout("lost"), httpx.Response(200, json={"status": 1, "data": {"succeeded": 8, "failed": 0, "uploads": []}})])
        job_id = _run()
        drain()
        _retry_now(job_id)
        drain()
    with session_scope() as s:
        assert s.get(Job, job_id).status == "done"
    assert [c.request.url.params["overwrite"] for c in upload.calls] == ["0", "1"]
    assert sheet.writes == [("C9", f"https://{DOMAIN}")]


def test_https_check_accepts_a_company_name_with_an_ampersand():
    from tests.test_websites import _run, CP, DOMAIN

    sheet = FakeSheet({9: {"A": "Silva & Cia Ltda", "B": DOMAIN, "C": "", "D": "(11) 3251-4400", "G": "Sao Paulo", "H": "SP"}})
    with respx.mock(assert_all_called=False) as m:
        _web(m, sheet, https_body="<title>Silva &amp; Cia Ltda</title>")
        m.post(f"{CP}/Fileman/upload_files").mock(return_value=httpx.Response(200, json={"status": 1, "data": {"failed": 0}}))
        job_id = _run()
        drain()
    with session_scope() as s:
        assert s.get(Job, job_id).status == "done", s.get(Job, job_id).last_error
    assert sheet.writes == [("C9", f"https://{DOMAIN}")]


def test_ssl_is_waited_for_without_using_up_retries():
    from tests.test_websites import _run, _sheet, CP

    sheet = _sheet()
    with respx.mock(assert_all_called=False) as m:
        _web(m, sheet, https_body="<title>Default cPanel page</title>")
        m.post(f"{CP}/Fileman/upload_files").mock(return_value=httpx.Response(200, json={"status": 1, "data": {"failed": 0}}))
        job_id = _run()
        for _ in range(8):
            drain()
            _retry_now(job_id)
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "queued" and "HTTPS chưa chạy" in j.last_error and sheet.writes == []


def test_pixabay_page_past_the_results_is_not_a_bad_key(monkeypatch):
    from wg_core.integrations import pixabay

    monkeypatch.setenv("PIXABAY_API_KEY", "k")
    with respx.mock(assert_all_called=False) as m:
        m.get(url__startswith="https://pixabay.com/api/").respond(400, text="[ERROR 400] page is out of valid range")
        assert pixabay.search("office", "landscape", page=3)["photos"] == []
