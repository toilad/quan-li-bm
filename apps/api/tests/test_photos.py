"""Website photos from Pexels (mocked): chosen per domain, downloaded once, shipped with the site, credited."""
import httpx
import pytest
import respx

from tests.conftest import drain
from tests.test_websites import DOMAIN, ROW, _routes, _run, _sheet
from wg_core.db import session_scope
from wg_core.integrations import pexels
from wg_core.integrations.errors import Permanent
from wg_core.models import Job

SEARCH = "https://api.pexels.com/v1/search"
JPEG = b"\xff\xd8\xff\xe0fake-jpeg"


def _photo(i: int) -> dict:
    base = f"https://images.pexels.com/photos/{i}/pexels-photo-{i}.jpeg"
    return {"id": i, "url": f"https://www.pexels.com/photo/{i}/", "photographer": f"Photographer {i % 4}",
            "photographer_url": f"https://www.pexels.com/@p{i % 4}", "alt": f"Photo {i}",
            "src": {k: f"{base}?size={k}" for k in ("original", "large2x", "large", "medium", "portrait", "landscape", "tiny")}}


def _pexels(m, status=200):
    def search(request):
        assert request.headers["Authorization"] == "test-pexels-key"
        orient = request.url.params["orientation"]
        start = {"portrait": 100, "landscape": 200, "square": 300}[orient]
        return httpx.Response(status, json={"photos": [_photo(start + i) for i in range(30)]} if status == 200 else {},
                              headers={"X-Ratelimit-Remaining": "199"})

    s = m.get(url__startswith=SEARCH).mock(side_effect=search)
    img = m.get(url__startswith="https://images.pexels.com/").mock(return_value=httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"}))
    return s, img


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "test-pexels-key")


def test_build_ships_the_photos_with_the_site_and_credits_pexels(key):
    sheet = _sheet()
    with respx.mock(assert_all_called=False) as m:
        upload, _ = _routes(m, sheet)
        search, img = _pexels(m)
        job_id = _run("expert-travel")
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "done", j.last_error
        slots = {p["slot"] for p in j.state["photos"]}
    assert slots == {"hero", "about", "band", "why", "faq", "contact", "about-page"}
    assert search.call_count <= 3 and img.call_count == 7  # one search per orientation, each photo downloaded once
    assert len({p["id"] for p in j.state["photos"]}) == 7  # no photo used twice on a site
    body = upload.calls[0].request.content.decode("utf-8", "ignore")
    assert 'filename="photo-hero.jpg"' in body and 'src="photo-hero.jpg"' in body
    from wg_core.config import settings

    built = settings().data_dir / "sites" / DOMAIN
    for page in ("index.html", "about.html", "faq.html", "contact.html", "privacy.html", "terms.html"):
        html = (built / page).read_text(encoding="utf-8")
        assert "images.pexels.com" not in html, page  # pages do not hot-link
    assert 'src="photo-hero.jpg"' in (built / "index.html").read_text(encoding="utf-8")
    assert 'src="photo-about-page.jpg"' in (built / "about.html").read_text(encoding="utf-8")
    assert (built / "photo-hero.jpg").read_bytes() == JPEG
    assert 'href="https://www.pexels.com"' in body and "Photos by" in body and "Photographer" in body
    assert sheet.writes == [(f"C{ROW}", f"https://{DOMAIN}")]


def test_same_domain_same_photos_other_domain_other_photos(key):
    from wg_core.modules.websites import photos
    from wg_core.modules.websites.brand_render import design

    with respx.mock(assert_all_called=False) as m:
        _pexels(m)
        a = photos.choose("a.example.com", "expert-travel", design({"domain": "a.example.com"}, "expert-travel"))
        a2 = photos.choose("a.example.com", "expert-travel", design({"domain": "a.example.com"}, "expert-travel"))
        b = photos.choose("b.example.com", "expert-travel", design({"domain": "b.example.com"}, "expert-travel"))
    assert [p["id"] for p in a] == [p["id"] for p in a2]
    assert [p["id"] for p in a] != [p["id"] for p in b]


def test_without_a_key_the_site_uses_gradient_panels():
    sheet = _sheet()
    with respx.mock(assert_all_called=False) as m:
        upload, _ = _routes(m, sheet)
        search, _ = _pexels(m)
        job_id = _run("expert-travel")
        drain()
    with session_scope() as s:
        assert s.get(Job, job_id).status == "done" and s.get(Job, job_id).state["photos"] == []
    assert not search.called and "<img" not in upload.calls[0].request.content.decode("utf-8", "ignore")


def test_a_refused_key_stops_the_build_instead_of_publishing_without_photos(key):
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


def test_preview_shows_the_same_photos_and_caches_the_search(client, key):
    with respx.mock(assert_all_called=False) as m:
        search, _ = _pexels(m)
        params = {"template": "expert-travel", "domain": "p.example.com", "company": "Acme LLC"}
        r = client.get("/api/websites/preview", params=params)
        n = search.call_count
        client.get("/api/websites/preview", params={**params, "page": "about.html"})
        assert search.call_count == n  # cached: no extra Pexels requests
    assert r.status_code == 200 and "https://images.pexels.com/photos/" in r.text and "Photos by" in r.text
    assert client.get("/api/websites/preview", params={**params, "template": "nope"}).status_code == 404


def test_key_check_is_read_only_and_reports_the_remaining_quota(client, key):
    with respx.mock(assert_all_called=False) as m:
        search, img = _pexels(m)
        r = client.get("/api/photos/check").json()
    assert r == {"ok": True, "found": 30, "remaining": "199"} and search.call_count == 1 and not img.called
