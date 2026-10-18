"""Addon domain vs subdomain, the API 2 adapter, the real-write lock and the cPanel response format.

All mocked (respx). Shapes come from the official docs and from read-only calls on nick 3 (cPanel 138, 2026-10-17):
/execute/ answers {"status", "data", "errors", …} at the top level; API 2 answers {"cpanelresult": {…}}; the 922 addons
on nick 3 are newdomain = subdomain = the name, parked on the primary domain, folder public_html/<name>.
"""
import httpx
import pytest
import respx

from tests.conftest import drain
from tests.mocks import FakeSheet, cp_account, cp_err, cp_ok, install_doh
from tests.test_dns_write import batch_mode, fake_inet
from tests.test_domains import CP, ROW, _tick
from wg_core import runtime_config
from wg_core.db import session_scope
from wg_core.integrations.cpanel import CPanel
from wg_core.integrations.cpanel_api2 import CPanelApi2
from wg_core.integrations.errors import NotAvailable, NotConfigured, Permanent
from wg_core.models import Job
from wg_core.modules.domains import service as domains

HOST = "turboweb-022607.000nethost.com"
API2 = f"https://{HOST}:2083/json-api/cpanel"
MAIN, IP, FQDN = "levantoan.000web.com", "103.75.187.26", "acme.huxma.life"
ADDON = {"domain": FQDN, "subdomain": FQDN, "rootdomain": MAIN, "fullsubdomain": f"{FQDN}.{MAIN}", "basedir": f"public_html/{FQDN}"}


def api2_ok(domain=FQDN):
    return httpx.Response(200, json={"cpanelresult": {"apiversion": 2, "module": "AddonDomain", "func": "addaddondomain",
                                                      "event": {"result": 1}, "data": [{"result": 1, "reason": f"{domain} created", "domain": domain}]}})


def stats(version="138.0 (build 15)"):
    """StatsBar::get_stats as answered live by cPanel 138: the version is in `value`, `count` is null."""
    return cp_ok([{"id": "cpanelversion", "name": "cpanelversion", "item": "cPanel Version", "value": version, "count": None}])


def _addon_account(m, addons=None, subs=None, dirs=(), main_docroot="/home/u1/public_html", entry=ADDON, version="138.0 (build 15)"):
    """huxma.life is NOT on the account (single_domain_data fails for it, list_domains does not list it)."""
    def one(request):
        d = request.url.params["domain"]
        if d == MAIN and main_docroot:
            return cp_ok({"documentroot": main_docroot, "ip": IP, "type": "main_domain"})
        return cp_err(f"Unable to locate the domain: {d}")

    cp_account(m, CP, main=MAIN, addon=("sustainlife.io.vn",), dirs=dirs)
    m.get(f"{CP}/StatsBar/get_stats").mock(return_value=stats(version))
    m.get(f"{CP}/DomainInfo/single_domain_data").mock(side_effect=one)
    m.get(f"{CP}/SubDomain/listsubdomains").mock(side_effect=subs or (lambda r: cp_ok([])))
    routes = {"api2": m.get(API2).mock(return_value=api2_ok()),
              "uapi": m.get(f"{CP}/AddonDomain/addaddondomain").mock(return_value=cp_ok({"domain": FQDN})),
              "sub": m.get(f"{CP}/SubDomain/addsubdomain").mock(return_value=cp_ok(None))}

    def created(request):  # listaddondomains: empty until a create call was made, then the new addon
        return cp_ok([entry] if routes["api2"].called or routes["uapi"].called else [])

    m.get(f"{CP}/AddonDomain/listaddondomains").mock(side_effect=addons or created)
    return routes


def _job():
    with session_scope() as s:
        return domains.enqueue_rows(s, [{"row": ROW, "company": "Acme LLC", "root": "huxma.life", "label": "acme"}])["queued"][0]["job_id"]


def _run(addons=None, subs=None, dirs=(), api2=None, entry=ADDON, version="138.0 (build 15)"):
    _tick("huxma.life")
    batch_mode()
    sheet, inet = FakeSheet({ROW: {"A": "Acme LLC"}}), fake_inet()
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m)
        install_doh(m, {FQDN: [IP]})
        routes = _addon_account(m, addons, subs, dirs, entry=entry, version=version)
        if api2 is not None:
            routes["api2"].mock(return_value=api2)
        inet.install(m)
        job_id = _job()
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        return j, routes, sheet, inet


# ───────── creating the addon ─────────

def test_cpanel_138_creates_the_addon_with_the_uapi_function():
    # official spec 11.138.0.10: x-cpanel-api-version UAPI, x-cpanel-available-version "cPanel 138"
    j, routes, sheet, inet = _run()
    assert j.status == "done", j.last_error
    assert j.state["host_mode"] == "addon" and j.state["host_main"] == MAIN
    assert routes["uapi"].call_count == 1 and not routes["api2"].called and not routes["sub"].called
    q = routes["uapi"].calls[0].request.url.params
    assert (q["newdomain"], q["subdomain"], q["dir"], q["disallowdot"]) == (FQDN, FQDN, f"public_html/{FQDN}", "0")
    assert routes["uapi"].calls[0].request.headers["Authorization"] == "cpanel u1:t1"  # nick 1's own token
    assert sheet.writes == [(f"B{ROW}", FQDN)] and len(inet.patches) == 1


@pytest.mark.parametrize("version", ["136.0 (build 7)", "11.130.0.15"])
def test_older_cpanel_uses_the_api2_adapter(version):
    j, routes, sheet, _ = _run(version=version)
    assert j.status == "done", j.last_error
    assert routes["api2"].call_count == 1 and not routes["uapi"].called
    q = routes["api2"].calls[0].request.url.params
    assert (q["cpanel_jsonapi_apiversion"], q["cpanel_jsonapi_module"], q["cpanel_jsonapi_func"]) == ("2", "AddonDomain", "addaddondomain")
    assert (q["newdomain"], q["subdomain"], q["dir"]) == (FQDN, FQDN, f"public_html/{FQDN}")
    assert sheet.writes == [(f"B{ROW}", FQDN)]


def test_unreadable_version_stops_before_creating():
    j, routes, sheet, _ = _run(version="")
    assert j.status == "failed" and "phiên bản cPanel" in j.last_error
    assert not routes["api2"].called and not routes["uapi"].called and sheet.writes == []


def test_owner_override_wins_over_the_version():
    runtime_config.put("CPANEL_ADDON_API_N1", "api2")
    j, routes, *_ = _run()
    assert j.status == "done", j.last_error
    assert routes["api2"].call_count == 1 and not routes["uapi"].called


def test_api2_failure_reason_is_shown_and_b_stays_empty():
    fail = httpx.Response(200, json={"cpanelresult": {"apiversion": 2, "event": {"result": 1},
                                                      "data": [{"result": 0, "reason": "Sorry, the domain is already in use."}]}})
    j, _, sheet, _ = _run(api2=fail, version="136.0 (build 7)")
    assert j.status == "failed" and "already in use" in j.last_error and sheet.writes == []


def test_api2_error_field_and_wrong_shape_are_failures():
    with respx.mock() as m:
        m.get(API2).mock(side_effect=[httpx.Response(200, json={"cpanelresult": {"apiversion": 2, "error": "Access denied"}}),
                                      httpx.Response(200, json={"status": 1, "data": None})])
        api = CPanelApi2(CPanel("n1", HOST))
        with pytest.raises(Permanent, match="Access denied"):
            api.add_addon(FQDN, f"public_html/{FQDN}")
        with pytest.raises(Permanent, match="không phải định dạng API 2"):
            api.add_addon(FQDN, f"public_html/{FQDN}")


def test_create_that_reports_success_but_is_not_listed_stops():
    j, routes, sheet, _ = _run(addons=lambda r: cp_ok([]))
    assert j.status == "failed" and "không liệt kê" in j.last_error
    assert routes["uapi"].call_count == 1 and sheet.writes == []


def test_created_addon_with_another_document_root_is_a_conflict():
    j, _, sheet, _ = _run(entry={**ADDON, "basedir": "public_html/other"})
    assert j.status == "conflict" and "public_html/other" in j.last_error and sheet.writes == []


def test_addon_already_there_from_a_lost_attempt_is_not_created_again():
    calls = {"n": 0}

    def addons(request):  # empty at the pre-check, present when the create step looks again
        calls["n"] += 1
        return cp_ok([] if calls["n"] == 1 else [ADDON])

    j, routes, sheet, _ = _run(addons=addons)
    assert j.status == "done", j.last_error
    assert not routes["api2"].called and not routes["uapi"].called and sheet.writes == [(f"B{ROW}", FQDN)]


# ───────── stop before writing anything ─────────

@pytest.mark.parametrize("case", ["addon exists", "leftover subdomain on primary", "folder exists"])
def test_existing_name_or_folder_is_refused_before_any_dns_write(case):
    addons = (lambda r: cp_ok([ADDON])) if case == "addon exists" else None

    def subs(request):
        rx = request.url.params.get("regex", "")
        return cp_ok([{"domain": f"{FQDN}.{MAIN}", "basedir": f"public_html/{FQDN}"}] if case.startswith("leftover") and MAIN.replace(".", r"\.") in rx else [])

    j, routes, sheet, inet = _run(addons=addons, subs=subs, dirs=(FQDN,) if case == "folder exists" else ())
    assert j.status == "failed", j.last_error
    expect = {"addon exists": "đã tồn tại", "leftover subdomain on primary": f"{FQDN}.{MAIN}", "folder exists": f"public_html/{FQDN}"}[case]
    assert expect in j.last_error
    assert not routes["api2"].called and not routes["uapi"].called and inet.patches == [] and sheet.writes == []


# ───────── classification ─────────

def _mode(root, **account):
    def one(request):
        d = request.url.params["domain"]
        known = {MAIN: "main_domain", "huxma.life": "addon_domain"}
        return cp_ok({"documentroot": f"/home/u1/public_html/{d}", "ip": IP, "type": known[d]}) if d in known else cp_err("Unable to locate")

    with respx.mock(assert_all_called=False) as m:
        cp_account(m, CP, main=account.get("main", MAIN), addon=("huxma.life",), parked=("alias.example",), subs=("shop.huxma.life",))
        m.get(f"{CP}/DomainInfo/single_domain_data").mock(side_effect=account.get("one", one))
        return CPanel("n1", HOST).creation_mode(root)


def test_classification_main_addon_alias_subdomain_absent_unknown():
    assert _mode(MAIN) | {} == _mode(MAIN) and _mode(MAIN)["mode"] == "subdomain" and _mode(MAIN)["kind"] == "main"
    addon = _mode("huxma.life")
    assert (addon["mode"], addon["kind"], addon["parent"]) == ("subdomain", "addon", "huxma.life")
    absent = _mode("namecheapp.site")
    assert (absent["mode"], absent["kind"], absent["parent"]) == ("addon", "absent", MAIN)
    alias = _mode("alias.example")
    assert alias["mode"] is None and "alias" in alias["reason"]
    sub = _mode("shop.huxma.life")
    assert sub["mode"] is None and "subdomain" in sub["reason"]
    unknown = _mode("namecheapp.site", main="")
    assert unknown["mode"] is None and "miền chính" in unknown["reason"]
    no_docroot = _mode("namecheapp.site", one=lambda r: cp_ok({"ip": IP}))
    assert no_docroot["mode"] is None and "document root" in no_docroot["reason"]


def test_alias_root_stops_the_preview_with_the_reason():
    from wg_core.modules.domains import dns_plan

    _tick("huxma.life")
    with respx.mock(assert_all_called=False) as m:
        install_doh(m, {})
        FakeSheet({ROW: {"A": "Acme LLC"}}).install(m)
        cp_account(m, CP, main=MAIN, addon=(), parked=("huxma.life",))
        m.get(f"{CP}/DomainInfo/single_domain_data").mock(return_value=cp_ok({"documentroot": "/home/u1/public_html", "ip": IP}))
        fake_inet().install(m)
        with session_scope() as s:
            row = dns_plan.preview(s, [{"row": ROW, "company": "Acme LLC", "root": "huxma.life", "label": "acme"}])["rows"][0]
    assert row["action"] == "refuse" and "alias" in row["reason"]


def test_preview_shows_how_each_name_will_be_created():
    from wg_core.modules.domains import dns_plan

    _tick("huxma.life")
    with respx.mock(assert_all_called=False) as m:
        install_doh(m, {})
        FakeSheet({ROW: {"A": "Acme LLC"}}).install(m)
        _addon_account(m)
        fake_inet().install(m)
        with session_scope() as s:
            row = dns_plan.preview(s, [{"row": ROW, "company": "Acme LLC", "root": "huxma.life", "label": "acme"}])["rows"][0]
    assert row["action"] == "add" and row["host_mode"] == "addon"
    assert any("addon domain" in c and MAIN in c for c in row["checks"])


def test_website_document_root_of_an_addon_comes_from_the_addon_list():
    with respx.mock(assert_all_called=False) as m:
        m.get(f"{CP}/AddonDomain/listaddondomains").mock(return_value=cp_ok([ADDON]))
        sub = m.get(f"{CP}/SubDomain/listsubdomains").mock(return_value=cp_ok([]))
        assert CPanel("n1", HOST).document_root(FQDN) == (f"public_html/{FQDN}", "AddonDomain::listaddondomains")
    assert not sub.called


# ───────── the real-write lock (production behaviour) ─────────

def _writes(cp):
    from wg_core.integrations.inet import Inet

    return {"host-sub": lambda: cp.add_subdomain("acme", "huxma.life", f"public_html/{FQDN}"),
            "host-addon-api2": lambda: CPanelApi2(cp).add_addon(FQDN, f"public_html/{FQDN}"),
            "host-addon-uapi": lambda: cp.add_addon_uapi(FQDN, f"public_html/{FQDN}"),
            "upload": lambda: cp.upload_files(f"public_html/{FQDN}", {"index.html": b"x"}, fqdn=FQDN),
            "ssl": lambda: cp.start_autossl(FQDN),
            "dns": lambda: Inet("n1").create_a_record("huxma.life", "acme", IP)}


@pytest.mark.real_guard
def test_every_real_write_is_locked_by_default_and_nothing_is_sent():
    with respx.mock(assert_all_called=False) as m:
        anything = m.route().mock(return_value=cp_ok(None))
        for name, write in _writes(CPanel("n1", HOST)).items():
            with pytest.raises(NotAvailable, match="KHOÁ"):
                write()
    assert not anything.called  # the lock is checked before any request


@pytest.mark.real_guard
def test_trial_allows_only_the_approved_name_and_the_approved_operations():
    from wg_core import write_guard
    from wg_core.modules.domains import dns_plan

    _tick("huxma.life")
    with session_scope() as s:
        dns_plan.set_switch(s, enabled=True, trial_fqdn=FQDN, ops=["dns", "host"])
    sw = write_guard.load()
    assert write_guard.why_not(sw, "host", FQDN) is None and write_guard.why_not(sw, "dns", FQDN) is None
    assert "miền thử" in write_guard.why_not(sw, "host", "other.huxma.life")
    assert "chưa cho phép" in write_guard.why_not(sw, "upload", FQDN) and "chưa cho phép" in write_guard.why_not(sw, "ssl", FQDN)
    with session_scope() as s:  # domain trial passed + upload allowed: upload still only for the trial name
        dns_plan.set_switch(s, ops=["dns", "host", "upload"])
        dns_plan.mark_trial(s, FQDN, 1)
    sw = write_guard.load()
    assert write_guard.why_not(sw, "host", "other.huxma.life") is None
    assert write_guard.why_not(sw, "upload", FQDN) is None and "miền thử" in write_guard.why_not(sw, "upload", "other.huxma.life")
    with session_scope() as s:
        assert write_guard.mark_web_trial(s, FQDN, 2)
    assert write_guard.why_not(write_guard.load(), "upload", "other.huxma.life") is None
    with session_scope() as s:  # a new trial name locks everything back to that name
        dns_plan.set_switch(s, trial_fqdn="beta.huxma.life")
    assert "miền thử" in write_guard.why_not(write_guard.load(), "host", "other.huxma.life")
    with pytest.raises(ValueError):
        with session_scope() as s:
            dns_plan.set_switch(s, ops=["delete"])


# ───────── response format, auth, tokens ─────────

def test_both_documented_uapi_envelopes_are_read_and_anything_else_is_refused():
    item = {"name": "cpanelversion", "value": "138.0 (build 15)", "count": None}
    with respx.mock() as m:
        m.get(f"{CP}/StatsBar/get_stats").mock(side_effect=[
            # what /execute/ answered live (top level)
            httpx.Response(200, json={"messages": None, "status": 1, "metadata": {"transformed": 1}, "errors": None, "data": [item], "warnings": None}),
            # what the spec documents for this older function (the `uapi` command-line envelope)
            httpx.Response(200, json={"apiversion": 3, "func": "get_stats", "module": "StatsBar",
                                      "result": {"status": 1, "data": [item], "errors": None, "messages": None, "metadata": {}, "warnings": None}}),
            httpx.Response(200, json={"apiversion": 3, "result": {"status": 0, "data": None, "errors": ["Access denied"]}}),
            httpx.Response(200, json={"data": [item]})])
        cp = CPanel("n1", HOST)
        assert cp.version() == "138.0 (build 15)" and cp.version() == "138.0 (build 15)"
        with pytest.raises(Permanent, match="Access denied"):
            cp.version()
        with pytest.raises(Permanent, match="không phải định dạng UAPI"):
            cp.version()


@pytest.mark.parametrize("code", [401, 403])
@pytest.mark.parametrize("path", ["uapi", "api2"])
def test_bad_token_or_missing_permission_names_the_function_never_the_token(code, path):
    with respx.mock(assert_all_called=False) as m:
        m.get(f"{CP}/AddonDomain/addaddondomain").respond(code)
        m.get(API2).respond(code)
        cp = CPanel("n1", HOST)
        with pytest.raises(NotConfigured) as e:
            cp.add_addon_uapi(FQDN, "public_html/x") if path == "uapi" else CPanelApi2(cp).add_addon(FQDN, "public_html/x")
    assert "AddonDomain" in str(e.value) and "t1" not in str(e.value)


def test_feature_disabled_on_the_account_is_a_clear_permanent_error():
    with respx.mock() as m:
        m.get(f"{CP}/AddonDomain/addaddondomain").mock(return_value=cp_err("You do not have the feature “addondomains”."))
        with pytest.raises(Permanent, match="addondomains"):
            CPanel("n1", HOST).add_addon_uapi(FQDN, f"public_html/{FQDN}")


def test_each_nick_uses_only_its_own_token():
    import os

    os.environ.update({"CPANEL_USER_N3": "u3", "CPANEL_TOKEN_N3": "t3"})
    try:
        with respx.mock() as m:
            r1 = m.get(url__startswith=f"{CP}/StatsBar/get_stats").mock(return_value=cp_ok([{"name": "cpanelversion", "count": "1"}]))
            r3 = m.get(url__startswith="https://turboweb-082302.000nethost.com:2083/execute/StatsBar/get_stats").mock(
                return_value=cp_ok([{"name": "cpanelversion", "count": "3"}]))
            assert CPanel("n1", HOST).version() == "1"
            assert CPanel("n3", "turboweb-082302.000nethost.com").version() == "3"
        assert r1.calls[0].request.headers["Authorization"] == "cpanel u1:t1"
        assert r3.calls[0].request.headers["Authorization"] == "cpanel u3:t3"
    finally:
        for k in ("CPANEL_USER_N3", "CPANEL_TOKEN_N3"):
            os.environ.pop(k, None)
    with pytest.raises(NotConfigured) as e:  # nick 2 has no token: never falls back to another nick's
        CPanel("n2", HOST)
    assert "CPANEL_TOKEN_N2" in str(e.value)


def test_cpanel_token_is_stored_encrypted_and_never_returned(client):
    from wg_core.runtime_config import StoredSetting  # noqa: F401  (the table the value lands in)

    assert client.put("/api/settings", json={"name": "CPANEL_TOKEN_N2", "value": "SECRETTOKENXYZ0123456789"}).status_code == 200
    assert "SECRETTOKENXYZ0123456789" not in client.get("/api/settings").text
    with session_scope() as s:
        from sqlalchemy import text

        raw = s.execute(text("SELECT value FROM stored_settings WHERE name='CPANEL_TOKEN_N2'")).scalar()
    assert raw and "SECRETTOKENXYZ0123456789" not in raw  # Fernet ciphertext, not the token
    assert client.put("/api/settings", json={"name": "CPANEL_ADDON_API_N2", "value": "soap"}).status_code == 422
    assert client.put("/api/settings", json={"name": "CPANEL_ADDON_API_N2", "value": "uapi"}).status_code == 200


# ───────── locks itself again ─────────

@pytest.mark.real_guard
@pytest.mark.parametrize("status", ["done", "failed", "conflict", "blocked"])
def test_trial_job_locks_everything_again_when_it_ends(status):
    from wg_core import write_guard
    from wg_core.modules.domains import dns_plan

    _tick("huxma.life")
    with session_scope() as s:
        dns_plan.set_switch(s, enabled=True, trial_fqdn=FQDN, ops=["dns", "host"])
        why = write_guard.after_job(s, "domain_create", status, {"fqdn": FQDN})
    assert why and FQDN in why
    sw = write_guard.load()
    assert not sw["enabled"] and sw["locked_reason"] == why
    with pytest.raises(NotAvailable, match="KHOÁ"):
        write_guard.check("host", FQDN)


@pytest.mark.real_guard
def test_any_failed_write_job_locks_again_even_in_batch_mode_but_a_done_one_does_not():
    from wg_core import write_guard
    from wg_core.modules.domains import dns_plan

    _tick("huxma.life")
    with session_scope() as s:
        dns_plan.set_switch(s, enabled=True, trial_fqdn=FQDN, ops=["dns", "host"])
        dns_plan.mark_trial(s, FQDN, 1)  # batch
        assert write_guard.after_job(s, "domain_create", "done", {"fqdn": "beta.huxma.life"}) is None
        assert write_guard.after_job(s, "pdf_save", "failed", {}) is None  # not a hosting write
    assert write_guard.load()["enabled"]
    with session_scope() as s:
        assert write_guard.after_job(s, "web_build", "failed", {"domain": "beta.huxma.life"})
    assert not write_guard.load()["enabled"]


@pytest.mark.real_guard
def test_a_restart_locks_again():
    from wg_core import registry, write_guard
    from wg_core.modules.domains import dns_plan

    _tick("huxma.life")
    with session_scope() as s:
        dns_plan.set_switch(s, enabled=True, trial_fqdn=FQDN, ops=["dns", "host"])
    assert write_guard.load()["enabled"]
    registry.setup()  # what the API and the worker run when they start
    sw = write_guard.load()
    assert not sw["enabled"] and "khởi động lại" in sw["locked_reason"] and sw["trial_fqdn"] == FQDN


@pytest.mark.real_guard
def test_job_runner_relocks_after_the_trial_job():
    """End to end through the real runner: the trial domain job finishes, the lock closes by itself."""
    from wg_core import write_guard
    from wg_core.modules.domains import dns_plan

    _tick("huxma.life")
    with session_scope() as s:
        dns_plan.set_switch(s, enabled=True, trial_fqdn=FQDN, ops=["dns", "host"])
    sheet, inet = FakeSheet({ROW: {"A": "Acme LLC"}}), fake_inet()
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m)
        install_doh(m, {FQDN: [IP]})
        _addon_account(m)
        inet.install(m)
        job_id = _job()
        drain()
    with session_scope() as s:
        assert s.get(Job, job_id).status == "done"
    sw = write_guard.load()
    assert sw["trial_passed"] and not sw["enabled"] and "đã xong" in sw["locked_reason"]


@pytest.mark.real_guard
def test_extra_approved_names_only_for_names_the_app_created_and_cleared_on_relock():
    from wg_core import write_guard
    from wg_core.models import SheetWrite
    from wg_core.modules.domains import dns_plan

    _tick("huxma.life")
    with session_scope() as s:
        s.add(SheetWrite(tab="Phoi US", range="B9", old_value="", new_value="beta.huxma.life", job_id=None))
    with session_scope() as s:
        dns_plan.set_switch(s, enabled=True, trial_fqdn=FQDN, ops=["ssl"])
        with pytest.raises(ValueError):
            dns_plan.set_switch(s, also=["never-made.huxma.life"])
        dns_plan.set_switch(s, also=["beta.huxma.life"])
    sw = write_guard.load()
    assert write_guard.why_not(sw, "ssl", "beta.huxma.life") is None and write_guard.why_not(sw, "ssl", FQDN) is None
    assert "miền thử" in write_guard.why_not(sw, "ssl", "gamma.huxma.life")
    assert "chưa cho phép" in write_guard.why_not(sw, "host", "beta.huxma.life")
    with session_scope() as s:
        write_guard.relock(s, "xong")
    sw = write_guard.load()
    assert not sw["enabled"] and sw["also"] == []
