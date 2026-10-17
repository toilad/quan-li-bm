"""The cPanel client against real answers (tests/fixtures/cpanel_live_samples.json): read-only calls made on nick 3
(cPanel 138.0 build 15) on 2026-10-17, sanitised. These are not hand-made mocks — the parser is checked against what
the server actually sent, one test per response shape."""
import json
from pathlib import Path

import httpx
import pytest
import respx

from wg_core.integrations.cpanel import CPanel
from wg_core.integrations.cpanel_api2 import CPanelApi2, choose
from wg_core.integrations.errors import NotConfigured, Permanent

SAMPLES = json.loads((Path(__file__).parent / "fixtures" / "cpanel_live_samples.json").read_text(encoding="utf-8"))
HOST = "turboweb-022607.000nethost.com"
CP = f"https://{HOST}:2083/execute"


def live(name):
    x = SAMPLES[name]
    if "body_html" in x:
        return httpx.Response(x["http"], headers={"content-type": x["content_type"]}, text=x["body_html"])
    return httpx.Response(x["http"], headers={"content-type": x["content_type"]}, content=json.dumps(x["body"]).encode())


@pytest.fixture
def cp():
    return CPanel("n1", HOST)


def test_samples_are_sanitised():
    raw = json.dumps(SAMPLES)
    for real in ("toandao", "namecheapp", "vdcspksihosting", "202.92.7", "acdesigners", "crestcar"):
        assert real not in raw


def test_live_uapi_envelope_is_top_level(cp):
    body = SAMPLES["uapi_get_stats_cpanelversion"]["body"]
    assert "status" in body and "result" not in body  # the shape the server really sends over /execute/
    with respx.mock() as m:
        m.get(f"{CP}/StatsBar/get_stats").mock(return_value=live("uapi_get_stats_cpanelversion"))
        assert cp.version() == "138.0 (build 15)" and cp.major_version() == 138  # value, not the null count


def test_live_version_picks_uapi_for_addon_creation(cp):
    with respx.mock() as m:
        m.get(f"{CP}/StatsBar/get_stats").mock(return_value=live("uapi_get_stats_cpanelversion"))
        assert choose(cp, "auto") == "uapi"


def test_live_list_domains_and_classification(cp):
    with respx.mock() as m:
        m.get(f"{CP}/DomainInfo/list_domains").mock(return_value=live("uapi_list_domains"))
        assert cp.list_domains()["main_domain"] == "d1.example"
        assert [cp.classify(d) for d in ("d1.example", "d17.example", "d2.example", "d4.d1.example", "new.example")] == \
            ["main", "addon", "alias", "subdomain", "absent"]


def test_live_single_domain_data_found_and_not_found(cp):
    with respx.mock() as m:
        m.get(f"{CP}/DomainInfo/single_domain_data").mock(side_effect=[live("uapi_single_domain_data_main"), live("uapi_single_domain_data_not_on_account")])
        d = cp.domain_data("d1.example")
        assert (d["documentroot"], d["ip"], d["type"]) == ("/home/cpuser/public_html", "203.0.113.10", "main_domain")
        assert cp.domain_data("d15.example") is None  # status 0 "Unable to locate the domain" → not on the account


def test_live_creation_mode_for_a_root_not_on_the_account(cp):
    def one(request):
        return live("uapi_single_domain_data_main") if request.url.params["domain"] == "d1.example" else live("uapi_single_domain_data_not_on_account")

    with respx.mock() as m:
        m.get(f"{CP}/DomainInfo/list_domains").mock(return_value=live("uapi_list_domains"))
        m.get(f"{CP}/DomainInfo/single_domain_data").mock(side_effect=one)
        how = cp.creation_mode("d15.example")
    assert (how["mode"], how["kind"], how["parent"], how["ip"], how["docroot"]) == ("addon", "absent", "d1.example", "203.0.113.10", "/home/cpuser/public_html")


def test_live_addon_and_subdomain_entries(cp):
    with respx.mock() as m:
        m.get(f"{CP}/AddonDomain/listaddondomains").mock(side_effect=[live("uapi_listaddondomains_one"), live("uapi_listaddondomains_none"), live("uapi_listaddondomains_one")])
        m.get(f"{CP}/SubDomain/listsubdomains").mock(return_value=live("uapi_listsubdomains_one"))
        a = cp.addon("d17.example")
        assert (a["subdomain"], a["rootdomain"], a["basedir"]) == ("d17.example", "d1.example", "public_html/d17.example")  # the nick-3 pattern
        assert cp.addon("zz.example") is None
        assert cp.document_root("d17.example") == ("public_html/d17.example", "AddonDomain::listaddondomains")
        assert cp.subdomain("d4.d1.example")["basedir"] == "public_html/d4.d1.example"


def test_live_folder_listing(cp):
    with respx.mock() as m:
        m.get(f"{CP}/Fileman/list_files").mock(return_value=live("uapi_list_files_dirs"))
        assert cp.folder_exists("public_html/d17.example") and not cp.folder_exists("public_html/new.example")


def test_live_autossl_flag(cp):
    with respx.mock() as m:
        m.get(f"{CP}/SSL/is_autossl_check_in_progress").mock(return_value=live("uapi_is_autossl_check_in_progress"))
        assert cp.autossl_in_progress() is False


def test_live_uapi_error(cp):
    with respx.mock() as m:
        m.get(f"{CP}/StatsBar/get_stats").mock(return_value=live("uapi_unknown_module"))
        with pytest.raises(Permanent, match="Failed to load module"):
            cp.version()


def test_live_uapi_without_valid_credentials_is_the_login_page(cp):
    with respx.mock() as m:
        m.get(f"{CP}/StatsBar/get_stats").mock(return_value=live("uapi_no_auth"))
        with pytest.raises(NotConfigured, match="trang đăng nhập"):  # not a "temporary" error retried forever
            cp.version()


def test_live_api2_envelope(cp):
    res = SAMPLES["api2_listaddondomains_one"]["body"]["cpanelresult"]
    assert res["apiversion"] == 2 and isinstance(res["data"], list) and res["event"] == {"result": 1}
    denied = SAMPLES["api2_no_auth"]["body"]["cpanelresult"]
    assert denied["apiversion"] == "2" and isinstance(denied["data"], dict)  # string version, object data — both live


def test_live_api2_access_denied_is_a_credentials_problem(cp):
    with respx.mock() as m:
        m.get(f"https://{HOST}:2083/json-api/cpanel").mock(return_value=live("api2_no_auth"))
        with pytest.raises(NotConfigured):
            CPanelApi2(cp).add_addon("new.example", "public_html/new.example")


def test_api2_object_data_with_result_0_is_a_failure_even_with_http_200(cp):
    """The live 'Access denied' body, but delivered with HTTP 200: data is an object with result "0"."""
    denied = SAMPLES["api2_no_auth"]["body"]
    with respx.mock() as m:
        m.get(f"https://{HOST}:2083/json-api/cpanel").mock(return_value=httpx.Response(200, json=denied))
        with pytest.raises(Permanent, match="Access denied"):
            CPanelApi2(cp).add_addon("new.example", "public_html/new.example")


@pytest.mark.parametrize("code", [500, 502, 503])
def test_server_error_is_temporary(cp, code):
    from wg_core.integrations.errors import Transient

    with respx.mock() as m:
        m.get(f"{CP}/StatsBar/get_stats").respond(code)
        with pytest.raises(Transient):
            cp.version()


def test_server_errors_are_retried_a_limited_number_of_times_then_the_job_fails():
    """A cPanel that keeps answering 503: the domain job is retried, then stops as failed — never an endless loop."""
    from tests.conftest import drain
    from tests.mocks import FakeSheet, install_doh
    from tests.test_dns_write import batch_mode, fake_inet
    from tests.test_domains import ROW, _tick
    from wg_core.db import session_scope
    from wg_core.models import Job
    from wg_core.modules.domains import service as domains

    _tick("huxma.life")
    batch_mode()
    with respx.mock(assert_all_called=False) as m:
        FakeSheet({ROW: {"A": "Acme LLC"}}).install(m)
        install_doh(m, {})
        fake_inet().install(m)
        busy = m.route(url__startswith=CP).respond(503)
        with session_scope() as s:
            job_id = domains.enqueue_rows(s, [{"row": ROW, "company": "Acme LLC", "root": "huxma.life", "label": "acme"}])["queued"][0]["job_id"]
        for _ in range(10):
            with session_scope() as s:
                j = s.get(Job, job_id)
                if j.status != "queued":
                    break
                j.run_after = j.created_at
            drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "failed" and "503" in j.last_error and j.attempts == j.max_attempts == 5
    assert busy.call_count == 5  # one cPanel call per attempt, then it stops
