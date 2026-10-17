"""Addon domain vs subdomain: decided per root from the live cPanel account, never per nick.

Shape copied from the 922 addon domains already on nick 3 (read-only check, 2026-10-17): newdomain = subdomain =
the whole name, parked on the primary domain, document root public_html/<name>.
"""
import httpx
import pytest
import respx

from tests.conftest import drain
from tests.mocks import FakeSheet, cp_ok, cp_err, install_doh
from tests.test_dns_write import batch_mode, fake_inet
from tests.test_domains import CP, ROW, _tick
from wg_core.db import session_scope
from wg_core.integrations.cpanel import CPanel
from wg_core.integrations.errors import NotConfigured, Permanent
from wg_core.models import Job
from wg_core.modules.domains import service as domains

MAIN, IP, FQDN = "levantoan.000web.com", "103.75.187.26", "acme.huxma.life"


def _addon_account(m, addons=None, subs=None):
    """huxma.life is NOT on the account (single_domain_data fails for it); the primary domain is."""
    def one(request):
        d = request.url.params["domain"]
        if d == MAIN:
            return cp_ok({"documentroot": f"/home/u1/public_html", "ip": IP, "type": "main_domain"})
        return cp_err(f"The domain “{d}” does not belong to this account.")

    m.get(f"{CP}/DomainInfo/single_domain_data").mock(side_effect=one)
    m.get(f"{CP}/DomainInfo/list_domains").mock(return_value=cp_ok({"main_domain": MAIN, "addon_domains": [], "sub_domains": [], "parked_domains": []}))
    m.get(f"{CP}/SubDomain/listsubdomains").mock(side_effect=subs or (lambda r: cp_ok([])))
    m.get(f"{CP}/AddonDomain/listaddondomains").mock(side_effect=addons or (lambda r: cp_ok([])))
    return (m.get(f"{CP}/AddonDomain/addaddondomain").mock(return_value=cp_ok({"domain": FQDN})),
            m.get(f"{CP}/SubDomain/addsubdomain").mock(return_value=cp_ok(None)))


def _job():
    with session_scope() as s:
        return domains.enqueue_rows(s, [{"row": ROW, "company": "Acme LLC", "root": "huxma.life", "label": "acme"}])["queued"][0]["job_id"]


def _run(addons=None, subs=None, dns=True):
    _tick("huxma.life")
    batch_mode()
    sheet, inet = FakeSheet({ROW: {"A": "Acme LLC"}}), fake_inet()
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m)
        install_doh(m, {FQDN: [IP]} if dns else {})
        add_addon, add_sub = _addon_account(m, addons, subs)
        inet.install(m)
        job_id = _job()
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        return j.status, j.last_error, j.state, add_addon, add_sub, sheet, inet


def test_root_not_on_the_account_becomes_an_addon_domain_with_the_existing_shape():
    status, err, state, add_addon, add_sub, sheet, inet = _run()
    assert status == "done", err
    assert state["host_mode"] == "addon" and state["host_main"] == MAIN
    assert add_addon.call_count == 1 and not add_sub.called
    q = add_addon.calls[0].request.url.params
    assert (q["newdomain"], q["subdomain"], q["dir"], q["disallowdot"]) == (FQDN, FQDN, f"public_html/{FQDN}", "0")
    assert sheet.writes == [(f"B{ROW}", FQDN)] and len(inet.patches) == 1  # one A record, then B


def test_root_on_the_account_still_uses_subdomain_and_never_the_addon_api():
    from tests.test_domains import _routes

    _tick("huxma.life")
    batch_mode()
    sheet = FakeSheet({ROW: {"A": "Acme LLC"}})
    with respx.mock(assert_all_called=False) as m:
        add_sub = _routes(m, sheet, {FQDN: [IP]})
        addon_api = m.route(url__startswith=f"{CP}/AddonDomain/").mock(return_value=cp_ok([]))
        fake_inet().install(m)
        job_id = _job()
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "done" and j.state["host_mode"] == "subdomain"
    assert add_sub.call_count == 1 and not any("addaddondomain" in str(c.request.url) for c in addon_api.calls)


def test_addon_already_there_from_a_lost_attempt_is_not_created_again():
    calls = {"n": 0}

    def addons(request):  # empty at the pre-check, present when the create step looks again
        calls["n"] += 1
        return cp_ok([] if calls["n"] == 1 else [{"domain": FQDN, "subdomain": FQDN, "rootdomain": MAIN, "basedir": f"public_html/{FQDN}"}])

    status, err, _, add_addon, add_sub, sheet, _ = _run(addons=addons)
    assert status == "done", err
    assert not add_addon.called and not add_sub.called and sheet.writes == [(f"B{ROW}", FQDN)]


def test_addon_found_with_another_document_root_is_a_conflict_not_an_overwrite():
    calls = {"n": 0}

    def addons(request):
        calls["n"] += 1
        return cp_ok([] if calls["n"] == 1 else [{"domain": FQDN, "subdomain": FQDN, "rootdomain": MAIN, "basedir": "public_html/other"}])

    status, err, _, add_addon, _, sheet, _ = _run(addons=addons)
    assert status == "conflict" and "public_html/other" in err
    assert not add_addon.called and sheet.writes == []


def test_existing_name_is_refused_before_any_dns_write():
    status, err, _, add_addon, _, sheet, inet = _run(
        addons=lambda r: cp_ok([{"domain": FQDN, "subdomain": FQDN, "rootdomain": MAIN, "basedir": f"public_html/{FQDN}"}]))
    assert status == "failed" and "đã là addon domain" in err
    assert not add_addon.called and inet.patches == [] and sheet.writes == []


def test_leftover_subdomain_on_the_primary_domain_is_refused():
    # addaddondomain would silently reuse <name>.<primary> and whatever is in its folder
    def subs(request):
        rx = request.url.params.get("regex", "")
        return cp_ok([{"domain": f"{FQDN}.{MAIN}", "basedir": f"public_html/{FQDN}"}] if MAIN.replace(".", r"\.") in rx else [])

    status, err, _, add_addon, _, _, inet = _run(subs=subs)
    assert status == "failed" and f"{FQDN}.{MAIN}" in err
    assert not add_addon.called and inet.patches == []


def test_preview_shows_how_each_name_will_be_created():
    from wg_core.modules.domains import dns_plan

    _tick("huxma.life")
    with respx.mock(assert_all_called=False) as m:
        install_doh(m, {})
        _addon_account(m)
        fake_inet().install(m)
        with session_scope() as s:
            out = dns_plan.preview(s, [{"row": ROW, "company": "Acme LLC", "root": "huxma.life", "label": "acme"}])
    item = out["rows"][0]
    assert item["action"] == "add" and item["host_mode"] == "addon"
    assert any("addon domain" in c and MAIN in c for c in item["checks"])


def test_website_document_root_of_an_addon_comes_from_the_addon_list():
    with respx.mock(assert_all_called=False) as m:
        m.get(f"{CP}/AddonDomain/listaddondomains").mock(return_value=cp_ok([{"domain": FQDN, "basedir": f"public_html/{FQDN}"}]))
        sub = m.get(f"{CP}/SubDomain/listsubdomains").mock(return_value=cp_ok([]))
        assert CPanel("n1", "turboweb-022607.000nethost.com").document_root(FQDN) == (f"public_html/{FQDN}", "AddonDomain::listaddondomains")
    assert not sub.called


# ───────── auth / permission errors ─────────

@pytest.mark.parametrize("code", [401, 403])
def test_bad_token_or_missing_permission_says_which_module(code):
    with respx.mock() as m:
        m.get(f"{CP}/AddonDomain/addaddondomain").respond(code)
        with pytest.raises(NotConfigured) as e:
            CPanel("n1", "turboweb-022607.000nethost.com").add_addon(FQDN, f"public_html/{FQDN}")
    assert "AddonDomain" in str(e.value) and "t1" not in str(e.value)  # the token is never in the message


def test_feature_disabled_on_the_account_is_a_clear_permanent_error():
    with respx.mock() as m:
        m.get(f"{CP}/AddonDomain/addaddondomain").mock(return_value=cp_err("You do not have the feature “addondomains”."))
        with pytest.raises(Permanent) as e:
            CPanel("n1", "turboweb-022607.000nethost.com").add_addon(FQDN, f"public_html/{FQDN}")
    assert "addondomains" in str(e.value)


def test_each_nick_uses_only_its_own_token():
    import os

    os.environ.update({"CPANEL_USER_N3": "u3", "CPANEL_TOKEN_N3": "t3"})
    try:
        with respx.mock() as m:
            r1 = m.get(url__startswith=f"{CP}/StatsBar/get_stats").mock(return_value=cp_ok([{"name": "cpanelversion", "count": "1"}]))
            r3 = m.get(url__startswith="https://turboweb-082302.000nethost.com:2083/execute/StatsBar/get_stats").mock(
                return_value=cp_ok([{"name": "cpanelversion", "count": "3"}]))
            assert CPanel("n1", "turboweb-022607.000nethost.com").version() == "1"
            assert CPanel("n3", "turboweb-082302.000nethost.com").version() == "3"
        assert r1.calls[0].request.headers["Authorization"] == "cpanel u1:t1"
        assert r3.calls[0].request.headers["Authorization"] == "cpanel u3:t3"
    finally:
        for k in ("CPANEL_USER_N3", "CPANEL_TOKEN_N3"):
            os.environ.pop(k, None)
    with pytest.raises(NotConfigured) as e:  # nick 2 has no token: never falls back to another nick's
        CPanel("n2", "turboweb-022607.000nethost.com")
    assert "CPANEL_TOKEN_N2" in str(e.value)
