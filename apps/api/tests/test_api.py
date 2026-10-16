import glob

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FIXTURES
from wg_core.config import settings


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_status_reports_configuration(client):
    r = client.get("/api/status").json()
    assert r["ai"]["configured"] is True and r["ai"]["model"] == "claude-opus-5-5"
    n1 = next(n for n in r["nicks"] if n["id"] == "n1")
    assert n1["cpanel"]["configured"] and n1["inet_key"]
    n2 = next(n for n in r["nicks"] if n["id"] == "n2")
    assert not n2["cpanel"]["configured"] and "CPANEL_TOKEN_N2" in n2["cpanel"]["missing"]
    assert any("PATCH" in u["why"] for u in r["unavailable"])


def test_sheet_not_configured_returns_503_not_fake_data(client, monkeypatch):
    monkeypatch.setattr(settings(), "sheet_id", "")
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


@pytest.mark.skipif(not glob.glob(str(FIXTURES / "*LTDA*.pdf")), reason="fixtures not present")
def test_pdf_upload_extract_edit_and_save_validation(client):
    p = sorted(glob.glob(str(FIXTURES / "*LTDA*.pdf")))[0]
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
