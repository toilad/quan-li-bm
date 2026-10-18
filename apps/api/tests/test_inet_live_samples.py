"""The iNET client against real gateway answers (tests/fixtures/inet_live_samples.json): read-only calls made with
nick 3's own API key on 2026-10-18, sanitised. Not hand-made mocks — one test per response shape."""
import json
from pathlib import Path

import httpx
import pytest
import respx

from wg_core.integrations.errors import NotConfigured, Permanent
from wg_core.integrations.inet import BASE, Inet, dns_provider

SAMPLES = json.loads((Path(__file__).parent / "fixtures" / "inet_live_samples.json").read_text(encoding="utf-8"))


def live(name):
    x = SAMPLES[name]
    return httpx.Response(x["http"], headers={"content-type": x["content_type"]}, content=json.dumps(x["body"], ensure_ascii=False).encode())


@pytest.fixture
def api():
    return Inet("n1")


def test_samples_are_sanitised():
    raw = json.dumps(SAMPLES, ensure_ascii=False)
    for real in ("toandao", "namecheapp", "groupany", "zentrivo", "202.92.7", "4575828", "facebook-domain-verification"):
        assert real not in raw


def test_live_envelope_is_success_data_meta():
    body = SAMPLES["list_domains"]["body"]
    assert set(body) == {"success", "data", "meta"} and body["success"] is True
    assert {"content", "totalPages", "totalElements", "size", "number"} <= set(body["data"])


def test_live_domain_list_is_read_inside_data(api):
    with respx.mock() as m:
        m.get(url__regex=rf"^{BASE}/domain(\?.*)?$").mock(return_value=live("list_domains"))
        doms = api.list_domains()
    assert len(doms) == 2 and doms[0]["name"] == "d1.example" and isinstance(doms[0]["id"], int)  # was 0 before the fix


def test_live_find_detail_and_records(api):
    with respx.mock() as m:
        m.get(url__regex=rf"^{BASE}/domain\?name=.*$").mock(return_value=live("find_domain"))
        m.get(url__regex=rf"^{BASE}/domain/\d+$").mock(return_value=live("domain_detail"))
        m.get(url__regex=rf"^{BASE}/domain/\d+/record$").mock(return_value=live("records"))
        name = SAMPLES["find_domain"]["body"]["data"]["content"][0]["name"]
        d = api.find_domain(name)
        assert d and d["name"] == name
        ns = api.nameservers(int(d["id"]))
        assert ns == {"ns1.inet.vn", "ns2.inet.vn"} and dns_provider(ns) == "inet"
        recs = api.records(int(d["id"]))
    assert [r["type"] for r in recs] == ["TXT", "TXT", "A"] and recs[2]["ttl"] == 300  # ttl comes back as a number


def test_live_bad_or_missing_key_names_iNETs_message_and_is_a_config_problem(api):
    for name in ("bad_key", "no_key"):
        with respx.mock() as m:
            m.get(url__startswith=f"{BASE}/domain").mock(return_value=live(name))
            with pytest.raises(NotConfigured, match="API key không hợp lệ"):
                api.list_domains()


def test_live_unknown_endpoint_is_a_permanent_error_with_the_message(api):
    with respx.mock() as m:
        m.get(url__startswith=f"{BASE}/domain").mock(return_value=live("not_found_path"))
        with pytest.raises(Permanent, match="API endpoint không tồn tại"):
            api.list_domains()


def test_success_false_with_http_200_is_not_taken_as_data(api):
    with respx.mock() as m:
        m.get(url__startswith=f"{BASE}/domain").mock(return_value=httpx.Response(200, json={"success": False, "error": "Lỗi thử"}))
        with pytest.raises(Permanent, match="Lỗi thử"):
            api.list_domains()


def test_paging_follows_total_pages(api):
    pages = {"1": ["a.example"], "2": ["b.example"], "3": ["c.example"]}

    def answer(request):
        p = request.url.params.get("page", "1")
        return httpx.Response(200, json={"success": True, "data": {"content": [{"id": int(p), "name": pages[p][0]}], "totalPages": 3,
                                                                  "number": int(p) - 1, "size": 1, "totalElements": 3}, "meta": {}})

    with respx.mock() as m:
        m.get(url__startswith=f"{BASE}/domain").mock(side_effect=answer)
        assert [d["name"] for d in api.list_domains()] == ["a.example", "b.example", "c.example"]
