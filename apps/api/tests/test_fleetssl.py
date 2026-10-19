"""The "Let's Encrypt SSL" plugin Issue (FleetSSL cPanel) through a cPanel session opened with the iNET API.
Mocked; every answer shape as seen live on 2026-10-19 (nick 2)."""
import json
from urllib.parse import parse_qs

import httpx
import pytest
import respx

from tests.conftest import drain
from tests.mocks import cp_ok, wrap
from wg_core.db import session_scope
from wg_core.integrations.errors import NotAvailable, NotConfigured, Permanent
from wg_core.integrations.fleetssl import FleetSSL
from wg_core.integrations.inet import BASE
from wg_core.models import Job

PANEL = "https://turboweb-022607.inet.vn:2083"
PLUGIN = f"{PANEL}/cpsess1234567890/frontend/jupiter/letsencrypt/letsencrypt.live.cgi"
LOGIN_URL = f"{PANEL}/cpsess1234567890/login/?session=u1%3asecret&goto_uri=%2f"
LIVE_LIST = {"success": True, "errors": None, "data": {"virtual_hosts": {"a.example.com": {
    "virtual_host": "a.example.com", "dns_identifiers": ["a.example.com"], "challenge_method": "http-01"}}}}


def inet_session(m, hosting="levantoan.000web.com", result=1):
    hosts = m.get(url__startswith=f"{BASE}/hosting").mock(return_value=wrap(
        {"content": [{"id": 4808242, "domainName": hosting, "status": "active"}], "totalPages": 1}, "/v1/hosting"))
    inner = json.dumps({"metadata": {"result": result, "reason": "Created session" if result else "Access denied", "command": "create_user_session"},
                        "data": {"url": LOGIN_URL, "cp_security_token": "/cpsess1234567890", "session": "x", "expires": 1}})
    login = m.post(f"{BASE}/hosting/4808242/login").mock(return_value=wrap(inner, "/v1/hosting/4808242/login"))
    m.get(url__startswith=f"{PANEL}/cpsess1234567890/login/").mock(
        return_value=httpx.Response(302, headers={"location": f"{PANEL}/cpsess1234567890/frontend/jupiter/index.html"}))
    m.get(f"{PANEL}/cpsess1234567890/frontend/jupiter/index.html").respond(200, text="<html>cPanel</html>")
    return hosts, login


def test_session_comes_from_the_iNET_API_and_the_list_is_read():
    with respx.mock() as m:
        hosts, login = inet_session(m)
        lst = m.get(url__startswith=PLUGIN).mock(return_value=httpx.Response(200, json=LIVE_LIST))
        with FleetSSL("n1", "levantoan.000web.com") as p:
            certs = p.certificates()
    assert certs["a.example.com"]["dns_identifiers"] == ["a.example.com"]
    assert login.calls[0].request.headers["Authorization"] == "Bearer k1"  # nick 1's own iNET key, no password
    assert lst.calls[0].request.url.params["api_function"] == "list-certificates"


def test_issue_is_for_exactly_one_name_and_checks_the_lock_first(monkeypatch):
    from wg_core import write_guard

    calls = []
    monkeypatch.setattr(write_guard, "check", lambda op, fqdn: calls.append((op, fqdn)))
    with respx.mock() as m:
        inet_session(m)
        route = m.post(url__startswith=PLUGIN).mock(return_value=httpx.Response(200, json={"success": True, "errors": None, "data": {}}))
        with FleetSSL("n1", "levantoan.000web.com") as p:
            p.issue("new.example.com")
    body = json.loads(route.calls[0].request.content)
    assert route.calls[0].request.url.params["api_function"] == "issue-certificate"
    assert body == {"virtual_host": "new.example.com", "dns_identifiers": ["new.example.com"], "challenge_method": "http-01", "dry_run": False}
    assert calls == [("ssl", "new.example.com")]


@pytest.mark.real_guard
def test_issue_is_refused_while_locked_before_any_request():
    with respx.mock(assert_all_called=False) as m:
        anything = m.route().mock(return_value=httpx.Response(200, json={"success": True}))
        with pytest.raises(NotAvailable, match="KHOÁ"):
            FleetSSL("n1", "levantoan.000web.com").issue("new.example.com")
    assert not anything.called


def test_no_iNET_key_means_not_configured():
    with pytest.raises(NotConfigured, match="INET_API_KEY_N2"):
        FleetSSL("n2", "ntp88.com")


def test_hosting_missing_or_session_refused_are_clear_errors():
    with respx.mock(assert_all_called=False) as m:
        inet_session(m, hosting="other.example.com")
        with pytest.raises(Permanent, match="không thấy hosting"):
            FleetSSL("n1", "levantoan.000web.com").certificates()
    with respx.mock(assert_all_called=False) as m:
        inet_session(m, result=0)
        with pytest.raises(Permanent, match="Access denied"):
            FleetSSL("n1", "levantoan.000web.com").certificates()


def test_plugin_failure_message_is_kept():
    with respx.mock() as m:
        inet_session(m)
        m.get(url__startswith=PLUGIN).mock(return_value=httpx.Response(200, json={"success": False, "errors": ["Validation failed: DNS problem"]}))
        with pytest.raises(Permanent, match="DNS problem"):
            FleetSSL("n1", "levantoan.000web.com").certificates()


# ───────── inside step 2 ─────────

def _b2(monkeypatch, cert_answers):
    from tests import test_websites as tw
    from wg_core.integrations import net

    answers = iter(cert_answers)
    last = {"v": (False, "chưa có chứng chỉ hợp lệ")}

    def cert(domain):
        last["v"] = next(answers, last["v"])
        return last["v"]

    monkeypatch.setattr(net, "cert_valid", cert)
    sheet = tw._sheet()
    with respx.mock(assert_all_called=False) as m:
        upload, ai = tw._routes(m, sheet)
        inet_session(m)
        autossl = m.get(url__regex=r".*/SSL/start_autossl_check.*").mock(return_value=cp_ok(None))
        m.get(f"{tw.CP}/SSL/get_autossl_renewal_status").mock(return_value=cp_ok({"has_problems": 1}))
        issue = m.post(url__startswith=PLUGIN).mock(return_value=httpx.Response(200, json={"success": True, "errors": None, "data": {}}))
        job_id = tw._run("lawyer-legal")
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        return j.status, j.last_error, dict(j.state), issue, upload, autossl, sheet


def test_b2_issues_ssl_for_this_domain_then_builds(monkeypatch):
    status, err, st, issue, upload, autossl, sheet = _b2(monkeypatch, [(False, "chưa có"), (True, "chứng chỉ hợp lệ · Let's Encrypt")])
    assert status == "done", err
    assert issue.call_count == 1 and json.loads(issue.calls[0].request.content)["virtual_host"] == "acme.huxma.life"
    assert upload.called and not autossl.called and st["ssl_issue_tries"] == 1


def test_b2_waits_and_uploads_nothing_while_the_certificate_is_not_there(monkeypatch):
    status, err, st, issue, upload, autossl, sheet = _b2(monkeypatch, [(False, "chưa có")])
    assert status == "queued" and "Chưa có SSL" in err
    assert issue.call_count == 1 and not upload.called and not autossl.called and sheet.writes == []
