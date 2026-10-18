import respx
from tests.conftest import drain
from tests.mocks import FakeSheet, cp_account, cp_ok, install_doh, wrap

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
    cp_account(m, CP)
    m.get(f"{CP}/DomainInfo/single_domain_data").respond(200, json={"status": 1, "data": {"documentroot": "/home/u1/public_html/huxma.life", "type": "addon_domain"}})
    m.get(f"{CP}/SubDomain/listsubdomains").mock(return_value=cp_ok([]))
    m.get(f"{CP}/AddonDomain/listaddondomains").mock(return_value=cp_ok([]))
    return m.get(f"{CP}/SubDomain/addsubdomain").mock(return_value=cp_ok(None))


def test_b_filled_meanwhile_is_conflict_not_overwrite():
    from tests.test_dns_write import batch_mode, fake_inet

    _tick("huxma.life")
    batch_mode()
    sheet = FakeSheet({ROW: {"A": "Acme LLC"}})
    with respx.mock(assert_all_called=False) as m:
        _routes(m, sheet, {"acme.huxma.life": []})
        fake_inet().install(m)
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
    from tests.test_dns_write import batch_mode

    monkeypatch.setattr(Inet, "create_a_record", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")))
    _tick("huxma.life")
    batch_mode()
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


def test_read_only_nick_check_marks_roots_on_hosting_and_in_inet():
    import httpx

    with respx.mock(assert_all_called=False) as m:
        m.get(f"{CP}/DomainInfo/list_domains").mock(return_value=cp_ok({
            "main_domain": "levantoan.000web.com", "addon_domains": ["sustainlife.io.vn", "huxma.life"],
            "sub_domains": ["sustainlife.io.vn.levantoan.000web.com", "huxma.life.levantoan.000web.com", "a.huxma.life"], "parked_domains": []}))
        m.get(f"{CP}/AddonDomain/listaddondomains").mock(return_value=cp_ok([
            {"domain": d, "subdomain": d, "rootdomain": "levantoan.000web.com", "fullsubdomain": f"{d}.levantoan.000web.com", "basedir": f"public_html/{d}"} for d in ("sustainlife.io.vn", "huxma.life")]))
        ver = m.get(f"{CP}/StatsBar/get_stats").mock(return_value=cp_ok([{"name": "cpanelversion", "id": "cpanelversion", "count": "11.130.0.15", "item": "cPanel Version"}]))
        inet = m.get(url__startswith="https://developers.inet.vn/api/gateway/v1/domain").mock(return_value=wrap({
            "content": [{"id": 1, "name": "huxma.life"}, {"id": 2, "name": "sustainlife.io.vn"}], "totalPages": 1}, "/v1/domain"))
        with session_scope() as s:
            out = domains.check_nick(s, "n1")
    assert out["cpanel"]["ok"] and set(out["cpanel"]["on_hosting"]) == {"sustainlife.io.vn", "huxma.life"}
    assert "yhawt.press" in out["cpanel"]["missing"]
    c = out["cpanel"]
    assert (c["main"], c["addon"], c["subdomain"], c["parked"], c["addon_docroot_pattern"]) == ("levantoan.000web.com", 2, 1, 0, 2)
    assert c["modes"]["huxma.life"] == "subdomain" and c["modes"]["yhawt.press"] == "addon"  # per root, read live
    assert out["cpanel"]["version"] == "11.130.0.15" and ver.calls[0].request.url.params["display"] == "cpanelversion"
    assert out["inet"]["ok"] and out["inet"]["domains"] == 2 and "yhawt.press" in out["inet"]["missing"]
    assert all(c.request.method == "GET" for c in inet.calls)
    # a root that is not on the hosting can be ticked too: its names are created as addon domains
    res = _tick("yhawt.press", "huxma.life")
    assert res["changed"] == ["yhawt.press", "huxma.life"] and res["refused"] == {}


def test_nick_check_without_keys_reports_each_service():
    with session_scope() as s:
        out = domains.check_nick(s, "n2")  # no CPANEL_*_N2 / INET_API_KEY_N2 in the test env
    assert not out["cpanel"]["ok"] and "CPANEL_TOKEN_N2" in out["cpanel"]["error"]
    assert not out["inet"]["ok"] and "INET_API_KEY_N2" in out["inet"]["error"]


def test_subdomain_labels_fold_accents_and_drop_legal_forms():
    cases = {"CONSTRUÇÕES SILVA LTDA": "construcoessilva", "N Triangle Ranch, Inc.": "ntriangleranch",
             "Padaria São José - ME": "padariasaojose", "ME Salon LLC": "mesalon", "Alpha S/A": "alpha"}
    assert {name: domains.slug(name) for name in cases} == cases


def test_label_comes_from_column_e_like_the_existing_domains():
    assert domains.label_for({"A": "VEGA LAVANDERIA LTDA", "E": "vegalavanderialtda"}) == "vegalavanderialtda"
    assert domains.label_for({"A": "N Triangle Ranch, Inc.", "E": ""}) == "ntriangleranch"  # no E → legacy rule
    assert domains.label_for({"A": "Alpha S/A", "E": "alpha s/a"}) == "alpha"  # invalid E → legacy rule


def test_a_company_that_already_has_a_domain_is_not_offered_or_previewed(client):
    from wg_core.modules.domains import dns_plan

    _tick("huxma.life")
    sheet = FakeSheet({7: {"A": "Acme LLC", "J": "12.345.678/0001-90"},
                       8: {"A": "acme  llc", "B": "acmellc.yhawt.press"},          # same name, other row, has a domain
                       9: {"A": "Other Name", "J": "12345678000190", "B": "x.press"},  # same registration number
                       10: {"A": "Beta LLC", "E": "betallc"}})
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m)
        with session_scope() as s:
            out = domains.scan(s)
        assert [r["row"] for r in out["rows"]] == [10] and out["rows"][0]["label"] == "betallc"
        assert any(e["row"] == 7 and "dòng 8" in e["reason"] for e in out["excluded"])
        with session_scope() as s:
            p = dns_plan.preview(s, [{"row": 7, "company": "Acme LLC", "root": "huxma.life", "label": "acme"}])
    assert p["rows"][0]["action"] == "refuse" and "đã có miền acmellc.yhawt.press" in p["rows"][0]["reason"]
