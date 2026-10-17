"""Website photos from Pixabay (mocked, documented response shape): chosen per domain, downloaded once, shipped
with the site, credited; the key never appears in logs or pages."""
import httpx
import pytest
import respx

from tests.conftest import drain
from tests.test_websites import DOMAIN, ROW, _routes, _run, _sheet
from wg_core.db import session_scope
from wg_core.integrations import pixabay
from wg_core.integrations.errors import Permanent
from wg_core.models import Job, JobLog

API = "https://pixabay.com/api/"
JPEG = b"\xff\xd8\xff\xe0fake-jpeg"
KEY = "test-pixabay-key-123"


def _hit(i: int) -> dict:
    return {"id": i, "pageURL": f"https://pixabay.com/photos/sample-{i}/", "type": "photo", "tags": "office, desk, work",
            "previewURL": f"https://cdn.pixabay.com/photo/{i}_150.jpg", "webformatURL": f"https://pixabay.com/get/{i}_640.jpg",
            "largeImageURL": f"https://pixabay.com/get/{i}_1280.jpg", "imageWidth": 4000, "imageHeight": 3000,
            "user_id": 1000 + i % 4, "user": f"author{i % 4}", "userImageURL": ""}


def _pixabay(m, status=200):
    def search(request):
        assert request.url.params["key"] == KEY and request.url.params["image_type"] == "photo"
        assert request.url.params["safesearch"] == "true" and len(request.url.params["q"]) <= 100
        start = {"vertical": 100, "horizontal": 200, "all": 300}[request.url.params["orientation"]]
        if status != 200:
            return httpx.Response(status, text="[ERROR 400] Invalid or missing API key")
        return httpx.Response(200, json={"total": 500, "totalHits": 500, "hits": [_hit(start + i) for i in range(30)]},
                              headers={"X-RateLimit-Remaining": "99"})

    s = m.get(url__startswith=API).mock(side_effect=search)
    img = m.get(url__startswith="https://pixabay.com/get/").mock(return_value=httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"}))
    return s, img


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("PIXABAY_API_KEY", KEY)


def test_build_ships_the_photos_with_the_site_and_credits_pixabay(key):
    from wg_core.config import settings

    sheet = _sheet()
    with respx.mock(assert_all_called=False) as m:
        upload, _ = _routes(m, sheet)
        search, img = _pixabay(m)
        job_id = _run("expert-travel")
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "done", j.last_error
        chosen = j.state["photos"]
        logs = " ".join(x.message for x in s.query(JobLog).filter_by(job_id=job_id))
    assert {p["slot"] for p in chosen} == {"hero", "about", "band", "why", "faq", "contact", "about-page"}
    assert search.call_count <= 3 and img.call_count == 7  # one search per orientation, each photo downloaded once
    assert len({p["id"] for p in chosen}) == 7 and all(p["src"].endswith("_1280.jpg") for p in chosen)
    body = upload.calls[0].request.content.decode("utf-8", "ignore")
    assert 'filename="photo-hero.jpg"' in body and KEY not in body and KEY not in logs
    built = settings().data_dir / "sites" / DOMAIN
    for page in ("index.html", "about.html", "faq.html", "contact.html", "privacy.html", "terms.html"):
        html = (built / page).read_text(encoding="utf-8")
        assert "pixabay.com/get/" not in html, page  # no permanent hotlinking
        assert 'href="https://pixabay.com/"' in html and "Photos by" in html, page  # source shown
    index = (built / "index.html").read_text(encoding="utf-8")
    assert 'src="photo-hero.jpg"' in index and 'alt="office, desk, work"' in index
    assert 'href="https://pixabay.com/users/author' in index
    assert (built / "photo-hero.jpg").read_bytes() == JPEG
    assert sheet.writes == [(f"C{ROW}", f"https://{DOMAIN}")]


def test_same_domain_same_photos_other_domain_other_photos(key):
    from wg_core.modules.websites import photos
    from wg_core.modules.websites.brand_render import design

    with respx.mock(assert_all_called=False) as m:
        _pixabay(m)
        pick = lambda dom: [p["id"] for p in photos.choose(dom, "expert-travel", design({"domain": dom}, "expert-travel"))]  # noqa: E731
        a, a2, b = pick("a.example.com"), pick("a.example.com"), pick("b.example.com")
    assert a == a2 and a != b


def test_without_a_key_the_site_uses_gradient_panels():
    sheet = _sheet()
    with respx.mock(assert_all_called=False) as m:
        upload, _ = _routes(m, sheet)
        search, _ = _pixabay(m)
        job_id = _run("expert-travel")
        drain()
    with session_scope() as s:
        assert s.get(Job, job_id).status == "done" and s.get(Job, job_id).state["photos"] == []
    assert not search.called and "<img" not in upload.calls[0].request.content.decode("utf-8", "ignore")


def test_a_refused_key_stops_the_build_instead_of_publishing_without_photos(key):
    sheet = _sheet()
    with respx.mock(assert_all_called=False) as m:
        upload, _ = _routes(m, sheet)
        _pixabay(m, status=400)
        job_id = _run("expert-travel")
        drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "blocked" and "Pixabay" in j.last_error and KEY not in j.last_error
    assert not upload.called and sheet.writes == []


def test_rate_limit_waits_as_pixabay_says(key):
    from wg_core.integrations.errors import Transient

    with respx.mock(assert_all_called=False) as m:
        m.get(url__startswith=API).respond(429, text="API rate limit exceeded", headers={"X-RateLimit-Reset": "42"})
        with pytest.raises(Transient) as e:
            pixabay.search("office", "landscape")
    assert e.value.retry_after == 42


def test_only_pixabay_image_urls_are_downloaded():
    with pytest.raises(Permanent):
        pixabay.download("https://evil.example.com/x.jpg")


def test_preview_shows_the_same_photos_and_caches_the_search(client, key):
    with respx.mock(assert_all_called=False) as m:
        search, img = _pixabay(m)
        params = {"template": "expert-travel", "domain": "p.example.com", "company": "Acme LLC"}
        r = client.get("/api/websites/preview", params=params)
        n = search.call_count
        client.get("/api/websites/preview", params={**params, "page": "about.html"})
        assert search.call_count == n and not img.called  # cached; the preview never downloads
    assert r.status_code == 200 and "https://pixabay.com/get/" in r.text and "Photos by" in r.text and KEY not in r.text
    assert client.get("/api/websites/preview", params={**params, "template": "nope"}).status_code == 404


def test_key_check_is_read_only_and_reports_the_remaining_quota(client, key):
    with respx.mock(assert_all_called=False) as m:
        search, img = _pixabay(m)
        r = client.get("/api/photos/check").json()
    assert r == {"ok": True, "found": 30, "remaining": "99"} and search.call_count == 1 and not img.called
