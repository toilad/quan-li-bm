"""The "Let's Encrypt SSL" plugin Issue (FleetSSL cPanel) — mocked; answer shape as seen live on 2026-10-19."""
import os
from urllib.parse import parse_qs

import httpx
import pytest
import respx

from tests.conftest import drain
from tests.mocks import cp_ok
from wg_core.db import session_scope
from wg_core.integrations.errors import NotAvailable, NotConfigured, Permanent
from wg_core.integrations.fleetssl import FleetSSL
from wg_core.models import Job

HOST = "turboweb-022607.000nethost.com"
URL = f"https://{HOST}:2083/frontend/jupiter/letsencrypt/letsencrypt.live.cgi"
LIVE_LIST = {"success": True, "errors": None, "data": {"virtual_hosts": {"a.example.com": {
    "virtual_host": "a.example.com", "dns_identifiers": ["a.example.com"], "challenge_method": "http-01",
    "cpanel_cert_id": "a_example_com_x", "cpanel_key_id": "k"}}}}


@pytest.fixture
def password():
    os.environ["CPANEL_PASSWORD_N1"] = "pw-123 test"
    yield
    os.environ.pop("CPANEL_PASSWORD_N1", None)


def test_without_the_password_the_plugin_is_not_configured():
    with pytest.raises(NotConfigured, match="CPANEL_PASSWORD_N1"):
        FleetSSL("n1", HOST)


def test_list_reads_the_live_shape_with_basic_auth(password):
    with respx.mock() as m:
        route = m.get(url__startswith=URL).mock(return_value=httpx.Response(200, json=LIVE_LIST))
        certs = FleetSSL("n1", HOST).certificates()
    assert certs["a.example.com"]["dns_identifiers"] == ["a.example.com"]
    req = route.calls[0].request
    assert req.url.params["api_version"] == "1" and req.url.params["api_function"] == "list-certificates"
    assert req.headers["Authorization"].startswith("Basic ")


def test_issue_is_for_exactly_one_name_and_never_without_the_lock(password, monkeypatch):
    from wg_core import write_guard

    calls = []
    monkeypatch.setattr(write_guard, "check", lambda op, fqdn: calls.append((op, fqdn)))
    with respx.mock() as m:
        route = m.post(url__startswith=URL).mock(return_value=httpx.Response(200, json={"success": True, "errors": None, "data": {}}))
        FleetSSL("n1", HOST).issue("new.example.com")
    body = parse_qs(route.calls[0].request.content.decode())
    assert route.calls[0].request.url.params["api_function"] == "issue-certificate"
    assert body == {"virtual_host": ["new.example.com"], "dns_identifiers": ["new.example.com"], "challenge_method": ["http-01"], "dry_run": ["0"]}
    assert calls == [("ssl", "new.example.com")]  # the owner's lock is checked first


@pytest.mark.real_guard
def test_issue_is_refused_while_locked(password):
    with respx.mock(assert_all_called=False) as m:
        route = m.post(url__startswith=URL).mock(return_value=httpx.Response(200, json={"success": True, "data": {}}))
        with pytest.raises(NotAvailable, match="KHOÁ"):
            FleetSSL("n1", HOST).issue("new.example.com")
    assert not route.called


@pytest.mark.parametrize("answer, error", [
    (httpx.Response(403, text="denied"), NotConfigured),
    (httpx.Response(200, headers={"content-type": "text/html"}, text="<html><form id=login_form>cPanel Login</form></html>"), NotConfigured),
    (httpx.Response(200, json={"success": False, "errors": ["Validation failed: DNS problem"]}), Permanent),
])
def test_errors_are_named(password, answer, error):
    with respx.mock() as m:
        m.get(url__startswith=URL).mock(return_value=answer)
        with pytest.raises(error):
            FleetSSL("n1", HOST).certificates()


# ───────── inside step 2 ─────────

def _b2(monkeypatch, cert_answers, dns=("103.75.187.26",), with_password=True):
    from tests import test_websites as tw
    from wg_core.integrations import net

    answers = iter(cert_answers)
    last = {"v": (False, "chưa có chứng chỉ hợp lệ")}

    def cert(domain):
        try:
            last["v"] = next(answers)
        except StopIteration:
            pass
        return last["v"]

    monkeypatch.setattr(net, "cert_valid", cert)
    if with_password:
        os.environ["CPANEL_PASSWORD_N1"] = "pw"
    sheet = tw._sheet()
    try:
        with respx.mock(assert_all_called=False) as m:
            upload, ai = tw._routes(m, sheet)
            install = m.get(url__regex=r".*/SSL/start_autossl_check.*").mock(return_value=cp_ok(None))
            m.get(f"{tw.CP}/SSL/get_autossl_renewal_status").mock(return_value=cp_ok({"has_problems": 1}))
            issue = m.post(url__startswith=URL).mock(return_value=httpx.Response(200, json={"success": True, "errors": None, "data": {}}))

            job_id = tw._run("lawyer-legal")
            drain()
        with session_scope() as s:
            j = s.get(Job, job_id)
            return j.status, j.last_error, dict(j.state), issue, upload, install, sheet
    finally:
        os.environ.pop("CPANEL_PASSWORD_N1", None)


def test_b2_issues_ssl_for_this_domain_then_builds(monkeypatch):
    status, err, st, issue, upload, autossl, sheet = _b2(monkeypatch, [(False, "chưa có"), (True, "chứng chỉ hợp lệ · Let's Encrypt")])
    assert status == "done", err
    assert issue.call_count == 1 and parse_qs(issue.calls[0].request.content.decode())["virtual_host"] == ["acme.huxma.life"]
    assert upload.called and not autossl.called and st["ssl_issue_tries"] == 1


def test_b2_without_the_password_waits_and_uploads_nothing(monkeypatch):
    status, err, st, issue, upload, autossl, sheet = _b2(monkeypatch, [(False, "chưa có")], with_password=False)
    assert status == "queued" and "Chưa có SSL" in err
    assert not issue.called and not upload.called and not autossl.called and sheet.writes == []
