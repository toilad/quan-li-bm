import json

import httpx
import respx
from tests.conftest import drain
from tests.mocks import FakeSheet, anthropic_json, cp_ok, install_doh

from wg_core.db import session_scope
from wg_core.models import Job
from wg_core.modules.websites import service as web

CP = "https://turboweb-022607.000nethost.com:2083/execute"
DOMAIN, ROW = "acme.huxma.life", 9
GOOD = {"tagline": "Plumbing repairs and installations done right", "hero_subtitle": "Acme Plumbing LLC handles residential plumbing work.",
        "primary_cta": "Get a Quote", "intro_paragraph": "Acme Plumbing LLC offers plumbing services.",
        "about_short": "Acme Plumbing LLC is a plumbing company.", "about_full": "Para one.\n\nPara two.\n\nPara three.",
        "contact_intro": "Send us a message.", "footer_blurb": "Plumbing services.",
        "meta_description_home": "Plumbing services.", "meta_description_about": "About us.", "meta_description_contact": "Contact.",
        "meta_description_faq": "FAQ.",
        "services": [{"title": "Repairs", "description": "Pipe repairs."}, {"title": "Installs", "description": "Fixture installs."},
                     {"title": "Inspections", "description": "System checks."}],
        "why_choose_us": [{"title": "Clear quotes", "description": "We explain the work."}, {"title": "Tidy work", "description": "We clean up."},
                          {"title": "Easy to reach", "description": "Call or write to us."}],
        "faqs": [{"q": f"Q{c}?", "a": "Contact us."} for c in "abcde"]}
INVENTED = {**GOOD, "intro_paragraph": "Acme Plumbing LLC has 15 years of experience and is award-winning."}


def _sheet():
    return FakeSheet({ROW: {"A": "Acme Plumbing LLC", "B": DOMAIN, "C": "", "D": "(307) 555-0101", "F": "1 Main St", "G": "Cheyenne", "H": "WY", "I": "82001"}})


def _routes(m, sheet, docroot="sites/acme", https_body="<title>Acme Plumbing LLC</title>"):
    sheet.install(m)
    install_doh(m, {DOMAIN: ["103.75.187.26"]})
    m.get(f"{CP}/SubDomain/listsubdomains").mock(return_value=cp_ok([{"domain": DOMAIN, "basedir": docroot, "dir": f"/home/u1/{docroot}"}] if docroot else []))
    m.get(f"{CP}/AddonDomain/listaddondomains").mock(return_value=cp_ok([]))  # not an addon domain
    m.get(f"{CP}/DomainInfo/single_domain_data").respond(200, json={"status": 0, "errors": ["not found"]})
    m.get(f"{CP}/Fileman/list_files").mock(return_value=cp_ok({"files": [{"file": "old-notes.txt", "type": "file"}], "dirs": []}))
    upload = m.post(f"{CP}/Fileman/upload_files").mock(return_value=cp_ok({"succeeded": 6, "failed": 0, "uploads": []}))
    m.get(f"{CP}/SSL/start_autossl_check").mock(return_value=cp_ok(None))
    m.get(f"{CP}/SSL/is_autossl_check_in_progress").mock(return_value=cp_ok(0))
    m.get(f"{CP}/SSL/get_autossl_problems").mock(return_value=cp_ok([]))
    m.get(f"https://{DOMAIN}/").mock(return_value=httpx.Response(200, text=https_body))
    ai = m.post("https://api.anthropic.com/v1/messages").mock(side_effect=[anthropic_json(INVENTED), anthropic_json(GOOD)])
    return upload, ai


def _run(template="lawyer-legal"):
    with session_scope() as s:
        web.choose(s, DOMAIN, template, detected="corporate-firm")
        return web.enqueue_rows(s, [{"row": ROW, "domain": DOMAIN, "company": "Acme Plumbing LLC"}])["queued"][0]["job_id"]


def test_full_build_uses_chosen_template_and_reported_docroot():
    from wg_core import runtime_config

    runtime_config.put("SITE_COPY_AI", "on")  # this test covers the AI path
    sheet = _sheet()
    with respx.mock(assert_all_called=False) as m:
        upload, ai = _routes(m, sheet)
        job_id = _run("lawyer-legal")
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "done", j.last_error
        assert j.state["built_template"] == "lawyer-legal" and j.state["doc_root"] == "sites/acme"
    assert ai.call_count == 2  # invented "15 years … award" rejected, regenerated
    req = upload.calls[0].request
    assert req.url.params["dir"] == "sites/acme" and req.url.params["overwrite"] == "0"
    body = req.content.decode("utf-8", "ignore")
    assert "#1e3a8a" in body and "Playfair Display" in body  # the chosen template (Lawyer Legal Firm) drives colours and fonts
    assert "loremflickr" not in body  # no hot-linked random photo service
    assert "cdn.tailwindcss.com" in body and body.count('filename="index.html"') == 1 and 'filename="sitemap.xml"' in body
    for claim in ("What Our Customers Say", "Trusted by", "100%", "24/7", "A Look at Our Work"):
        assert claim not in body, claim
    sent = json.loads(ai.calls[1].request.content)
    assert sent["model"] == "claude-opus-5-5" and sent["output_config"]["format"]["type"] == "json_schema"
    assert sheet.writes == [(f"C{ROW}", f"https://{DOMAIN}")]


def test_domain_missing_on_cpanel_stops_before_upload():
    sheet = _sheet()
    with respx.mock(assert_all_called=False) as m:
        upload, ai = _routes(m, sheet, docroot=None)
        job_id = _run()
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "failed" and "cPanel không có" in j.last_error
    assert not upload.called and not ai.called and sheet.writes == []


def test_https_not_ready_retries_without_reupload_and_c_stays_empty():
    sheet = _sheet()
    with respx.mock(assert_all_called=False) as m:
        upload, _ = _routes(m, sheet, https_body="<title>Default cPanel page</title>")
        job_id = _run()
        drain()
        with session_scope() as s:
            j = s.get(Job, job_id)
            assert j.status == "queued" and j.state["uploaded"] and not j.state.get("https_ok")
            j.run_after = j.created_at
        m.get(f"https://{DOMAIN}/").mock(return_value=httpx.Response(200, text="<title>Acme Plumbing LLC</title>"))
        drain()
    with session_scope() as s:
        assert s.get(Job, job_id).status == "done"
    assert upload.call_count == 1
    assert sheet.writes == [(f"C{ROW}", f"https://{DOMAIN}")]


def test_c_already_filled_is_never_overwritten():
    sheet = _sheet()
    sheet.rows[ROW]["C"] = "https://old.example.com"
    with respx.mock(assert_all_called=False) as m:
        upload, _ = _routes(m, sheet)
        job_id = _run()
        drain()
    with session_scope() as s:
        assert s.get(Job, job_id).status == "conflict"
    assert not upload.called and sheet.writes == []



def test_without_ai_the_site_is_built_for_free_and_nothing_is_sent_to_anthropic():
    sheet = _sheet()
    with respx.mock(assert_all_called=False) as m:
        upload, ai = _routes(m, sheet)
        job_id = _run("lawyer-legal")
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "done", j.last_error
        assert j.state["copy_source"] == "offline"
    assert not ai.called and upload.called


def test_free_copy_is_stable_per_domain_differs_between_domains_and_invents_nothing():
    from wg_core.modules.websites.content_check import problems
    from wg_core.modules.websites.offline_copy import write_site_copy
    from wg_core.modules.websites.templates import TEMPLATES

    facts = {"Company": "Acme Plumbing LLC", "Phone": "(307) 555-0100", "Address": "1 Main St, Cheyenne WY 82001",
             "City": "CHEYENNE", "State": "WY"}
    for t in TEMPLATES:
        c = write_site_copy(facts, t.id, "acme.example.com")
        assert not problems(c, facts), (t.id, problems(c, facts))
        assert c == write_site_copy(facts, t.id, "acme.example.com")  # same domain → same text on every re-run
        assert "Acme Plumbing LLC" in c["intro_paragraph"] and "Cheyenne, WY" in c["about_full"]
    a, b = (write_site_copy(facts, "corporate-firm", d) for d in ("one.example.com", "two.example.com"))
    assert (a["tagline"], a["services"], a["why_choose_us"]) != (b["tagline"], b["services"], b["why_choose_us"])
