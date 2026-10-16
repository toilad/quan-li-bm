import respx
from tests.conftest import drain
from tests.mocks import FakeSheet, cp_ok, install_doh

from wg_core.db import session_scope
from wg_core.integrations.inet import Inet
from wg_core.models import Job, RootDomain
from wg_core.modules.domains import service as domains

CP = "https://turboweb-022607.000nethost.com:2083/execute"
ROW = 7


def _tick(*names):
    with session_scope() as s:
        return domains.set_selected(s, list(names), True)


def test_nothing_ticked_by_default_and_blocked_roots_cannot_be_ticked():
    with session_scope() as s:
        assert s.query(RootDomain).filter_by(selected=True).count() == 0
    res = _tick("vietcart.site", "167nailspa.com", "huxma.life")
    assert res["changed"] == ["huxma.life"]
    assert set(res["refused"]) == {"vietcart.site", "167nailspa.com"}


def test_enqueue_refuses_unticked_root_and_bad_label():
    _tick("huxma.life")
    with session_scope() as s:
        out = domains.enqueue_rows(s, [
            {"row": 5, "company": "A", "root": "yhawt.press", "label": "acme"},       # not ticked
            {"row": 6, "company": "B", "root": "huxma.life", "label": "bad_label"},    # invalid label
            {"row": 7, "company": "C", "root": "huxma.life", "label": "acme"},
        ])
    assert set(out["refused"]) == {5, 6} and [q["row"] for q in out["queued"]] == [7]


def test_same_fqdn_twice_is_one_job():
    _tick("huxma.life")
    with session_scope() as s:
        a = domains.enqueue_rows(s, [{"row": 7, "company": "C", "root": "huxma.life", "label": "acme"}])
        b = domains.enqueue_rows(s, [{"row": 7, "company": "C", "root": "huxma.life", "label": "acme"}])
    assert a["queued"][0]["job_id"] == b["queued"][0]["job_id"] and b["queued"][0]["created"] is False


def _routes(m, sheet, ips):
    sheet.install(m)
    install_doh(m, ips)
    m.get(f"{CP}/DomainInfo/single_domain_data").respond(200, json={"result": {"status": 1, "data": {"documentroot": "/home/u1/public_html/huxma.life", "type": "addon_domain"}}})
    m.get(f"{CP}/SubDomain/listsubdomains").mock(return_value=cp_ok([]))
    return m.get(f"{CP}/SubDomain/addsubdomain").mock(return_value=cp_ok(None))


def test_real_dns_step_is_blocked_until_inet_documents_it():
    _tick("huxma.life")
    sheet = FakeSheet({ROW: {"A": "Acme LLC"}})
    with respx.mock(assert_all_called=False) as m:
        add = _routes(m, sheet, {})
        with session_scope() as s:
            job_id = domains.enqueue_rows(s, [{"row": ROW, "company": "Acme LLC", "root": "huxma.life", "label": "acme"}])["queued"][0]["job_id"]
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "blocked" and "PATCH /domain/{id}/record" in j.last_error
        assert not j.state.get("dns_created")
    assert not add.called and sheet.writes == []  # nothing created, B untouched


def test_full_flow_with_dns_adapter_mocked(monkeypatch):
    monkeypatch.setattr(Inet, "create_a_record", lambda self, d, label, ip: None)
    _tick("huxma.life")
    sheet = FakeSheet({ROW: {"A": "Acme LLC", "C": ""}})
    with respx.mock(assert_all_called=False) as m:
        add = _routes(m, sheet, {"acme.huxma.life": []})
        with session_scope() as s:
            job_id = domains.enqueue_rows(s, [{"row": ROW, "company": "Acme LLC", "root": "huxma.life", "label": "acme"}])["queued"][0]["job_id"]
        drain()
        with session_scope() as s:  # DNS not propagated yet → retry later, created steps kept
            j = s.get(Job, job_id)
            assert j.status == "queued" and j.state["dns_created"] and j.state["host_created"]
            j.run_after = j.created_at
        install_doh(m, {"acme.huxma.life": ["103.75.187.26"]})
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "done" and j.state["written_b"] == "acme.huxma.life"
    assert add.call_count == 1  # cPanel subdomain created once, not on retry
    assert sheet.writes == [(f"B{ROW}", "acme.huxma.life")]  # only B, never C
    assert add.calls[0].request.url.params["dir"] == "public_html/acme.huxma.life"


def test_b_filled_meanwhile_is_conflict_not_overwrite(monkeypatch):
    monkeypatch.setattr(Inet, "create_a_record", lambda self, d, label, ip: None)
    _tick("huxma.life")
    sheet = FakeSheet({ROW: {"A": "Acme LLC"}})
    with respx.mock(assert_all_called=False) as m:
        _routes(m, sheet, {"acme.huxma.life": []})
        with session_scope() as s:
            job_id = domains.enqueue_rows(s, [{"row": ROW, "company": "Acme LLC", "root": "huxma.life", "label": "acme"}])["queued"][0]["job_id"]
        drain()
        sheet.rows[ROW]["B"] = "someone-else.example.com"
        install_doh(m, {"acme.huxma.life": ["103.75.187.26"]})
        with session_scope() as s:
            s.get(Job, job_id).run_after = s.get(Job, job_id).created_at
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "conflict" and j.state["orphan"]["fqdn"] == "acme.huxma.life"
    assert sheet.writes == []


def test_unticked_root_stops_a_queued_job_before_creating(monkeypatch):
    monkeypatch.setattr(Inet, "create_a_record", lambda self, d, label, ip: (_ for _ in ()).throw(AssertionError("must not run")))
    _tick("huxma.life")
    with session_scope() as s:
        job_id = domains.enqueue_rows(s, [{"row": ROW, "company": "Acme", "root": "huxma.life", "label": "acme"}])["queued"][0]["job_id"]
        s.get(RootDomain, "huxma.life").selected = False  # e.g. edited directly in DB
    sheet = FakeSheet({ROW: {"A": "Acme"}})
    with respx.mock(assert_all_called=False) as m:
        _routes(m, sheet, {})
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "failed" and "không còn được tích chọn" in j.last_error


def test_busy_root_cannot_be_unticked():
    _tick("huxma.life")
    with session_scope() as s:
        domains.enqueue_rows(s, [{"row": ROW, "company": "Acme", "root": "huxma.life", "label": "acme"}])
        res = domains.set_selected(s, ["huxma.life"], False)
    assert res["refused"] == {"huxma.life": "Đang có tác vụ trên miền này — bỏ chọn sau khi xong"}


def test_read_only_nick_check_marks_roots_on_hosting_and_keeps_inet_raw():
    import httpx

    with respx.mock(assert_all_called=False) as m:
        m.get(f"{CP}/DomainInfo/list_domains").mock(return_value=cp_ok({
            "main_domain": "levantoan.000web.com", "addon_domains": ["sustainlife.io.vn", "huxma.life"], "sub_domains": ["a.huxma.life"], "parked_domains": []}))
        ver = m.get(f"{CP}/StatsBar/get_stats").mock(return_value=cp_ok([{"name": "cpanelversion", "id": "cpanelversion", "count": "11.130.0.15", "item": "cPanel Version"}]))
        inet = m.get("https://developers.inet.vn/api/gateway/v1/domain").mock(return_value=httpx.Response(200, json={"content": [{"x": 1}]}))
        with session_scope() as s:
            out = domains.check_nick(s, "n1")
    assert out["cpanel"]["ok"] and set(out["cpanel"]["on_hosting"]) == {"sustainlife.io.vn", "huxma.life"}
    assert "yhawt.press" in out["cpanel"]["missing"]
    assert out["cpanel"]["version"] == "11.130.0.15" and ver.calls[0].request.url.params["display"] == "cpanelversion"
    assert out["inet"]["ok"] and out["inet"]["top_level"] == ["content"] and inet.calls[0].request.method == "GET"
    # a root not on the hosting can no longer be ticked; one on it can
    res = _tick("yhawt.press", "huxma.life")
    assert res["changed"] == ["huxma.life"] and "cPanel" in res["refused"]["yhawt.press"]


def test_nick_check_without_keys_reports_each_service():
    with session_scope() as s:
        out = domains.check_nick(s, "n2")  # no CPANEL_*_N2 / INET_API_KEY_N2 in the test env
    assert not out["cpanel"]["ok"] and "CPANEL_TOKEN_N2" in out["cpanel"]["error"]
    assert not out["inet"]["ok"] and "INET_API_KEY_N2" in out["inet"]["error"]
