"""Website photos from Pexels (mocked, documented response shape) — used when its key is set, before Pixabay."""
import httpx
import pytest
import respx

from tests.conftest import drain
from tests.test_websites import DOMAIN, _routes, _run, _sheet
from wg_core.db import session_scope
from wg_core.integrations import pexels
from wg_core.integrations.errors import Permanent
from wg_core.models import Job, JobLog

SEARCH = "https://api.pexels.com/v1/search"
JPEG = b"\xff\xd8\xff\xe0fake-jpeg"
KEY = "test-pexels-key-456"


def _photo(i: int) -> dict:
    base = f"https://images.pexels.com/photos/{i}/pexels-photo-{i}.jpeg"
    return {"id": i, "url": f"https://www.pexels.com/photo/{i}/", "photographer": f"Photographer {i % 4}",
            "photographer_url": f"https://www.pexels.com/@p{i % 4}", "alt": f"Photo {i}",
            "src": {k: f"{base}?size={k}" for k in ("original", "large2x", "large", "medium", "portrait", "landscape", "tiny")}}


def _pexels(m, status=200):
    def search(request):
        assert request.headers["Authorization"] == KEY and KEY not in str(request.url)  # key in the header only
        start = {"portrait": 100, "landscape": 200, "square": 300}[request.url.params["orientation"]]
        if status != 200:
            return httpx.Response(status, json={})
        return httpx.Response(200, json={"photos": [_photo(start + i) for i in range(30)]}, headers={"X-Ratelimit-Remaining": "199"})

    s = m.get(url__startswith=SEARCH).mock(side_effect=search)
    img = m.get(url__startswith="https://images.pexels.com/").mock(return_value=httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"}))
    return s, img


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", KEY)


def test_build_uses_pexels_ships_the_photos_and_credits_pexels(key):
    from wg_core.config import settings

    sheet = _sheet()
    with respx.mock(assert_all_called=False) as m:
        upload, _ = _routes(m, sheet)
        search, img = _pexels(m)
        job_id = _run("expert-travel")
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "done", j.last_error
        chosen = j.state["photos"]
        logs = " ".join(x.message for x in s.query(JobLog).filter_by(job_id=job_id))
    assert {p["provider"] for p in chosen} == {"pexels"} and len({p["id"] for p in chosen}) == 7
    assert search.call_count <= 3 and img.call_count == 7
    portrait = [p for p in chosen if p["slot"] == "why"][0]
    assert portrait["src"].endswith("size=portrait")  # the size matching the slot
    built = settings().data_dir / "sites" / DOMAIN
    for page in ("index.html", "about.html", "contact.html"):
        html = (built / page).read_text(encoding="utf-8")
        assert "images.pexels.com" not in html and 'href="https://www.pexels.com/"' in html and "on <a" in html, page
    assert 'src="photo-hero.jpg"' in (built / "index.html").read_text(encoding="utf-8")
    assert KEY not in logs and "Pexels: 7 ảnh" in logs
    assert 'filename="photo-hero.jpg"' in upload.calls[0].request.content.decode("utf-8", "ignore")


def test_pexels_is_preferred_when_both_keys_are_set(key, monkeypatch):
    from wg_core.modules.websites import photos

    monkeypatch.setenv("PIXABAY_API_KEY", "test-pixabay")
    assert photos.provider_name() == "pexels"
    monkeypatch.setenv("PEXELS_API_KEY", "")
    assert photos.provider_name() == "pixabay"


def test_a_refused_pexels_key_stops_the_build(key):
    sheet = _sheet()
    with respx.mock(assert_all_called=False) as m:
        upload, _ = _routes(m, sheet)
        _pexels(m, status=401)
        job_id = _run("expert-travel")
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "blocked" and "Pexels" in j.last_error
    assert not upload.called and sheet.writes == []


def test_only_pexels_image_urls_are_downloaded():
    with pytest.raises(Permanent):
        pexels.download("https://evil.example.com/x.jpg")


def test_key_check_for_pexels(client, key):
    with respx.mock(assert_all_called=False) as m:
        search, img = _pexels(m)
        r = client.get("/api/photos/check", params={"provider": "pexels"}).json()
    assert r == {"ok": True, "provider": "pexels", "found": 30, "remaining": "199", "in_use": True}
    assert search.call_count == 1 and not img.called
    assert client.get("/api/photos/check", params={"provider": "nope"}).status_code == 404
