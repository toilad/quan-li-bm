"""Real DNS writes over the iNET API (documented PATCH /domain/{id}/record, ACTION_ADD), against an in-memory iNET:
switch OFF by default, trial on one owner-chosen subdomain, read-only preview + single-use confirmation, never
overwrite / edit / delete, never call the iNET record API for a domain on other nameservers, every call logged."""
import respx
from tests.conftest import drain
from tests.mocks import FakeInet, FakeSheet, install_doh
from tests.test_domains import CP, ROW, _routes, _tick

from wg_core.db import session_scope
from wg_core.models import AppSetting, Job, JobLog
from wg_core.modules.domains import service as domains

IP = "103.75.187.26"
INET_NS = ["ns1.inet.vn", "ns2.inet.vn"]




def fake_inet(records=None, ns=None, drop_on_add=False, name="huxma.life"):
    if records is None:
        records = [{"id": 1, "name": "@", "type": "A", "data": IP, "ttl": 300},
                   {"id": 2, "name": "www", "type": "CNAME", "data": "huxma.life", "ttl": 300}]
    return FakeInet({name: {"id": 501, "ns": ns or INET_NS, "records": records}}, drop_on_add=drop_on_add)


def batch_mode():
    """As if the owner enabled real DNS writes and the trial already passed."""
    with session_scope() as s:
        s.merge(AppSetting(key="dns_write", value={"enabled": True, "trial_fqdn": "t.huxma.life", "trial_passed": True,
                                                           "ops": ["dns", "host", "upload", "ssl"], "web_trial_passed": True}))


def _job(label="acme"):
    with session_scope() as s:
        return domains.enqueue_rows(s, [{"row": ROW, "company": "Acme LLC", "root": "huxma.life", "label": label}])["queued"][0]["job_id"]


def _logs(job_id):
    with session_scope() as s:
        return [x.message for x in s.query(JobLog).filter_by(job_id=job_id).order_by(JobLog.id)]


def test_dns_write_is_off_by_default_nothing_is_written():
    _tick("huxma.life")
    sheet, inet = FakeSheet({ROW: {"A": "Acme LLC"}}), fake_inet()
    with respx.mock(assert_all_called=False) as m:
        add = _routes(m, sheet, {})
        patch = inet.install(m)
        job_id = _job()
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "blocked" and "Ghi thật đang KHOÁ" in j.last_error and not j.state.get("dns_created")
    assert not patch.called and not add.called and sheet.writes == []  # nothing created, B untouched


def test_full_flow_adds_exactly_one_record_via_action_add_and_keeps_the_others():
    _tick("huxma.life")
    batch_mode()
    sheet, inet = FakeSheet({ROW: {"A": "Acme LLC", "C": ""}}), fake_inet()
    with respx.mock(assert_all_called=False) as m:
        add = _routes(m, sheet, {"acme.huxma.life": []})
        patch = inet.install(m)
        job_id = _job()
        drain()
        with session_scope() as s:  # DNS not propagated yet → retry later, created steps kept
            j = s.get(Job, job_id)
            assert j.status == "queued" and j.state["dns_created"] and j.state["host_created"]
            assert j.state["dns_record"] == {"result": "created", "domain_id": 501, "record_id": 9001}
            j.run_after = j.created_at
        install_doh(m, {"acme.huxma.life": [IP]})
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "done" and j.state["written_b"] == "acme.huxma.life"
    assert inet.patches == [{"recordList": [{"domainId": 501, "name": "acme", "type": "A", "data": IP, "ttl": "300", "action": "ACTION_ADD"}]}]
    assert patch.call_count == 1 and add.call_count == 1  # neither repeated on retry
    assert add.calls[0].request.url.params["dir"] == "public_html/acme.huxma.life"
    assert [r["id"] for r in inet.domains["huxma.life"]["records"]] == [1, 2, 9001]  # old records untouched
    assert sheet.writes == [(f"B{ROW}", "acme.huxma.life")]  # only B, never C
    logs = "\n".join(_logs(job_id))
    assert "iNET PATCH /domain/501/record [ACTION_ADD acme A 103.75.187.26 ttl 300] → HTTP 200" in logs
    assert "2 bản ghi cũ giữ nguyên" in logs and "Bearer" not in logs and "k1" not in logs.split()


def test_same_record_already_on_inet_is_not_sent_again():
    _tick("huxma.life")
    batch_mode()
    sheet = FakeSheet({ROW: {"A": "Acme LLC"}})
    inet = fake_inet(records=[{"id": 7, "name": "acme", "type": "A", "data": IP, "ttl": 300}])
    with respx.mock(assert_all_called=False) as m:
        _routes(m, sheet, {"acme.huxma.life": [IP]})  # e.g. an earlier attempt stopped right after adding it
        patch = inet.install(m)
        job_id = _job()
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "done" and j.state["dns_record"]["result"] == "exists"
    assert not patch.called


def test_other_record_with_the_same_name_is_never_overwritten():
    _tick("huxma.life")
    batch_mode()
    recs = [{"id": 8, "name": "acme", "type": "CNAME", "data": "elsewhere.example.com", "ttl": 300}]
    sheet, inet = FakeSheet({ROW: {"A": "Acme LLC"}}), fake_inet(records=list(recs))
    with respx.mock(assert_all_called=False) as m:
        add = _routes(m, sheet, {})
        patch = inet.install(m)
        job_id = _job()
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "conflict" and "CNAME elsewhere.example.com" in j.last_error
    assert not patch.called and not add.called and sheet.writes == []
    assert inet.domains["huxma.life"]["records"] == recs


def test_patch_that_loses_other_records_stops_everything():
    _tick("huxma.life")
    batch_mode()
    sheet, inet = FakeSheet({ROW: {"A": "Acme LLC"}}), fake_inet(drop_on_add=True)
    with respx.mock(assert_all_called=False) as m:
        add = _routes(m, sheet, {})
        inet.install(m)
        job_id = _job()
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "failed" and "bản ghi cũ không còn" in j.last_error
    assert not add.called and sheet.writes == []
    assert any(x.startswith("CẢNH BÁO") for x in _logs(job_id))


def test_domain_not_on_inet_nameservers_never_calls_the_inet_record_api():
    _tick("huxma.life")
    batch_mode()
    sheet, inet = FakeSheet({ROW: {"A": "Acme LLC"}}), fake_inet(ns=["ada.ns.cloudflare.com", "bob.ns.cloudflare.com"])
    with respx.mock(assert_all_called=False) as m:
        _routes(m, sheet, {})
        patch = inet.install(m)
        job_id = _job()
        drain()
        record_calls = [c for c in m.calls if c.request.url.path.endswith("/record")]
    with session_scope() as s:
        assert s.get(Job, job_id).status == "blocked"
    assert not patch.called and not record_calls


def _preview(client, rows):
    items = [{"row": r, "company": f"Co {r}", "root": "huxma.life", "label": lab} for r, lab in rows]
    return client.post("/api/domains/preview", json={"items": items}).json()


def _docroot_with_ip(m, ip=IP):
    m.get(f"{CP}/DomainInfo/single_domain_data").respond(200, json={"status": 1, "data": {"documentroot": "/home/u1/public_html/huxma.life", "ip": ip}})


def test_preview_shows_subdomain_root_nick_ip_then_trial_then_batch(client):
    _tick("huxma.life")
    sheet, inet = FakeSheet({7: {"A": "Co 7"}, 8: {"A": "Co 8"}}), fake_inet()
    with respx.mock(assert_all_called=False) as m:
        _routes(m, sheet, {})
        patch = inet.install(m)
        _docroot_with_ip(m)
        p = _preview(client, [(7, "acme"), (8, "beta")])
        assert p["mode"] == "off" and p["token"] is None and "KHOÁ" in p["blocked"]
        r7 = next(r for r in p["rows"] if r["row"] == 7)
        assert (r7["fqdn"], r7["root"], r7["nick"], r7["ip"], r7["dns_provider"], r7["action"]) == \
            ("acme.huxma.life", "huxma.life", "iNET-1", IP, "inet", "add")
        assert r7["domain_id"] == 501 and r7["hosting_ip"] == IP and r7["existing"] == []
        assert client.put("/api/domains/dns-write", json={"enabled": True}).status_code == 422  # trial domain first
        assert client.put("/api/domains/dns-write", json={"trial_fqdn": "x.not-mine.com"}).status_code == 422
        sw = client.put("/api/domains/dns-write", json={"trial_fqdn": "acme.huxma.life", "enabled": True, "ops": ["dns", "host"]}).json()
        assert sw["mode"] == "trial"
        p = _preview(client, [(7, "acme"), (8, "beta")])
        assert p["token"] is None and "chỉ được chạy đúng 1 miền thử" in p["blocked"]
        p = _preview(client, [(7, "acme")])
        assert p["token"] and not p["blocked"]
        assert any("iNET GET /domain?name=huxma.life" in x["message"] for x in p["api_log"])
        assert not patch.called  # the preview only reads
        r = client.post("/api/domains/run", json={"token": p["token"]})
        assert r.status_code == 200 and len(r.json()["queued"]) == 1
        assert client.post("/api/domains/run", json={"token": p["token"]}).status_code == 409  # single use
        drain()
        install_doh(m, {"acme.huxma.life": [IP]})
        with session_scope() as s:
            for j in s.query(Job):
                j.run_after = j.created_at
        drain()
        sw = client.get("/api/domains/dns-write").json()
        assert sw["trial_passed"] and sw["mode"] == "off" and "đã xong" in sw["locked_reason"]  # trial passed → locked again
        p = _preview(client, [(8, "beta")])
        assert p["token"] is None and "KHOÁ" in p["blocked"]  # nothing spreads to other names by itself
        assert client.put("/api/domains/dns-write", json={"enabled": True}).json()["mode"] == "batch"  # the owner reopens
        p = _preview(client, [(8, "beta")])
        assert p["token"] and p["mode"] == "batch"
    assert sheet.rows[7]["B"] == "acme.huxma.life" and not sheet.rows[8].get("B")
    assert patch.call_count == 1


def test_preview_refuses_wrong_hosting_ip_and_a_root_missing_from_the_nicks_inet_account(client):
    _tick("huxma.life")
    sheet = FakeSheet({7: {"A": "Co 7"}})
    with respx.mock(assert_all_called=False) as m:
        _routes(m, sheet, {})
        fake_inet(name="other-domain.com").install(m)  # huxma.life is not in this nick's iNET account
        p = _preview(client, [(7, "acme")])
        assert p["rows"][0]["action"] == "refuse" and "không thuộc tài khoản iNET" in p["rows"][0]["reason"]
        _docroot_with_ip(m, "10.0.0.9")
        p = _preview(client, [(7, "acme")])
        assert p["rows"][0]["action"] == "refuse" and "khác IP của" in p["rows"][0]["reason"]


def test_run_without_a_confirmed_preview_is_refused(client):
    _tick("huxma.life")
    assert client.post("/api/domains/run", json={"token": "nope"}).status_code == 409
    assert client.post("/api/domains/run", json={"items": [{"row": 5, "root": "huxma.life", "label": "x"}]}).status_code == 422


def test_full_record_names_from_inet_are_recognised():
    from wg_core.integrations.inet import record_label

    assert record_label("acme.huxma.life.", "huxma.life") == "acme" and record_label("ACME.huxma.life", "huxma.life") == "acme"
    assert record_label("huxma.life", "huxma.life") == "@" and record_label("@", "huxma.life") == "@"
    _tick("huxma.life")
    batch_mode()
    sheet = FakeSheet({ROW: {"A": "Acme LLC"}})
    inet = fake_inet(records=[{"id": 7, "name": "acme.huxma.life.", "type": "A", "data": IP, "ttl": 300}])
    with respx.mock(assert_all_called=False) as m:
        _routes(m, sheet, {"acme.huxma.life": [IP]})
        patch = inet.install(m)
        job_id = _job()
        drain()
    with session_scope() as s:
        assert s.get(Job, job_id).state["dns_record"]["result"] == "exists"
    assert not patch.called  # the record written as a full name is the same record: never added twice
