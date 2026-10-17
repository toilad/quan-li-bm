import glob

import pytest

from tests.conftest import FIXTURES  # noqa: F401
from tests.test_pdf import BR as BR_SAMPLES
from wg_core.config import settings




def test_status_reports_configuration(client):
    r = client.get("/api/status").json()
    assert r["ai"]["configured"] is True and r["ai"]["model"] == "claude-opus-5-5"
    n1 = next(n for n in r["nicks"] if n["id"] == "n1")
    assert n1["cpanel"]["configured"] and n1["inet_key"]
    n2 = next(n for n in r["nicks"] if n["id"] == "n2")
    assert not n2["cpanel"]["configured"] and "CPANEL_TOKEN_N2" in n2["cpanel"]["missing"]
    assert any("mass_edit_zone" in u["why"] for u in r["unavailable"]) and not any("PATCH" in u["why"] for u in r["unavailable"])


def test_sheet_not_configured_returns_503_not_fake_data(client, monkeypatch):
    monkeypatch.setenv("SHEET_ID", "")
    r = client.get("/api/domains/rows")
    assert r.status_code == 503 and r.json()["status"] == "not_configured" and "SHEET_ID" in r.json()["missing"]
    r = client.get("/api/websites/rows")
    assert r.status_code == 503


def test_domain_run_refused_without_ticked_root(client):
    r = client.post("/api/domains/run", json={"items": [{"row": 5, "root": "huxma.life", "label": "x"}]})
    assert r.status_code == 422


def test_roots_listing_and_select(client):
    roots = client.get("/api/domains/roots").json()
    assert [len(n["roots"]) for n in roots] == [11, 3, 11]
    assert not any(r["selected"] for n in roots for r in n["roots"])
    res = client.post("/api/domains/roots/select", json={"names": ["huxma.life", "vietcart.site"], "on": True}).json()
    assert res["changed"] == ["huxma.life"] and "vietcart.site" in res["refused"]


@pytest.mark.skipif(not BR_SAMPLES, reason="fixtures not present")
def test_pdf_upload_extract_edit_and_save_validation(client):
    p = BR_SAMPLES[0]
    up = client.post("/api/pdf/upload", files=[("files", ("x.pdf", open(p, "rb").read(), "application/pdf"))]).json()[0]
    assert up["doc_type"] == "br" and up["status"] == "review" and up["fields"]["A"]["value"]
    again = client.post("/api/pdf/upload", files=[("files", ("y.pdf", open(p, "rb").read(), "application/pdf"))]).json()[0]
    assert again["duplicate"] is True and again["id"] == up["id"]
    # clearing a critical field blocks saving server-side
    client.patch(f"/api/pdf/{up['id']}", json={"fields": {"A": ""}})
    r = client.post(f"/api/pdf/{up['id']}/save", json={"confirm_missing": True})
    assert r.status_code == 422 and any(x.startswith("A:") for x in r.json()["detail"]["reasons"])
    assert client.get(f"/api/pdf/{up['id']}/file").content[:4] == b"%PDF"
    bad = client.post("/api/pdf/upload", files=[("files", ("n.pdf", b"not a pdf", "application/pdf"))]).json()[0]
    assert bad["status"] == "rejected"


def test_ai_model_check_uses_models_api(client):
    import respx

    with respx.mock(assert_all_called=False) as m:
        route = m.get("https://api.anthropic.com/v1/models/claude-opus-5-5").respond(200, json={
            "type": "model", "id": "claude-opus-5-5", "display_name": "Claude Opus 5.5", "created_at": "2026-01-01T00:00:00Z",
            "max_input_tokens": 1000000, "max_tokens": 128000})
        r = client.get("/api/ai/check").json()
    assert route.called and r["id"] == "claude-opus-5-5" and r["max_input_tokens"] == 1000000


def test_website_preview_is_the_real_legacy_output(client):
    r = client.get("/api/websites/preview", params={"template": "lawyer-legal", "domain": "acme.example.com", "company": "Acme LLC"})
    assert r.status_code == 200 and r.text.startswith("<!DOCTYPE html>")
    assert "cdn.tailwindcss.com" in r.text and "law,courthouse,justice,books" in r.text and "Acme LLC" in r.text
    assert client.get("/api/websites/preview", params={"template": "lawyer-legal", "page": "about.html"}).status_code == 200
    assert client.get("/api/websites/preview", params={"template": "lawyer-legal", "page": "../x"}).status_code == 404


def test_pdf_email_is_used_for_websites_only_after_the_owner_verifies_it(client):
    from wg_core.db import session_scope
    from wg_core.models import PdfDocument
    from wg_core.modules.websites.service import email_of

    with session_scope() as s:
        d = PdfDocument(md5="e" * 32, original_name="x.pdf", size=1, doc_type="br", status="saved",
                        fields={"J": {"value": "11.222.333/0001-81"}}, extra={"email": "Contato@Acme.example"})
        s.add(d)
        s.flush()
        doc_id = d.id
        none_email = PdfDocument(md5="f" * 32, original_name="y.pdf", size=1, doc_type="br", status="review", fields={}, extra={})
        s.add(none_email)
        s.flush()
        none_id = none_email.id
    cells = {"J": "11.222.333/0001-81"}
    with session_scope() as s:
        assert email_of(s, cells) == ""  # printed on the PDF but not verified → not used
    r = client.patch(f"/api/pdf/{doc_id}", json={"email_verified": True})  # allowed even after saving
    assert r.status_code == 200 and r.json()["extra"]["email_verified"] is True
    with session_scope() as s:
        assert email_of(s, cells) == "contato@acme.example"
    client.patch(f"/api/pdf/{doc_id}", json={"email_verified": False})
    with session_scope() as s:
        assert email_of(s, cells) == ""
    assert client.patch(f"/api/pdf/{none_id}", json={"email_verified": True}).status_code == 422  # nothing to verify
