"""Business phone numbers (owner's rules, 2026-10-19): kept as printed, otherwise provided from the owner's own provider
account with an area code of the company's state — never made up. The provider (Twilio) is MOCKED here: no real number
is looked up or bought by these tests."""
import re

import httpx
import pytest
import respx

from tests.test_pdf_ocr import _ocr_doc
from wg_core.db import session_scope
from wg_core.integrations.errors import NotAvailable, Permanent
from wg_core.models import PdfDocument, PhoneAssignment
from wg_core.modules.pdf.fields import validate
from wg_core.phones import check, tag, website_phone

TW = "https://api.twilio.com/2010-04-01/Accounts/AC00000000000000000000000000000000"


# ───── the checks ─────

@pytest.mark.parametrize("number, state, level, words", [
    ("1 (619) 555-6382", "CA", "error", "555"),          # a movie / example number (seen in the Sheet)
    ("12092333214", "WA", "warn", "209 không thuộc bang WA"),  # a California code for a Washington company
    ("206-291-0886", "WA", None, ""),
    ("+55 (11) 44321746", "SP", None, ""),
    ("(53) 96756-2645", "SP", "warn", "DDD 53 thuộc RS"),
    ("123", "WA", "error", "10 chữ số"),
    ("(212) 555-0100", "NY", "error", "555"),
    ("(212) 410-0100", "NY", "warn", "Chưa có bảng mã vùng"),
])
def test_check(number, state, level, words):
    problems = check(number, state)
    if level is None:
        assert problems == []
    else:
        assert problems[0]["level"] == level and words in problems[0]["message"], problems


def test_a_provided_number_must_match_the_state():
    assert check("+12092333214", "WA", provisioned=True)[0]["level"] == "error"


def test_tag_and_validation():
    pdf = {"D": {"value": "206-291-0886", "source": "text"}, "H": {"value": "WA"}}
    tag(pdf)
    assert pdf["D"]["phone_source"] == "source_pdf" and pdf["D"]["value"] == "206-291-0886"  # kept as printed
    # no number on the PDF → a temporary number with the state's area code (owner, 2026-10-19), from the reserved
    # fictional block 555-0100…0199 so it can never be a stranger's line
    none = {"A": {"value": "Sample Ridge LLC"}, "D": {"value": "", "source": "missing"}, "H": {"value": "WA"}}
    tag(none)
    d = none["D"]
    assert d["phone_source"] == "placeholder" and re.fullmatch(r"\(206\) 555-01\d\d", d["value"]) and "TẠM" in d["note"]
    again = {"A": {"value": "Sample Ridge LLC"}, "D": {"value": ""}, "H": {"value": "WA"}}
    tag(again)
    assert again["D"]["value"] == d["value"]  # stable per company
    issues = validate({**{k: {"value": "x"} for k in "AEFGIJ"}, "H": {"value": "WA"}, "D": d}, "wa")
    assert issues["D"]["level"] == "warn" and "TẠM" in issues["D"]["message"]  # a reminder, does not block saving
    ca = {"A": {"value": "X LLC"}, "D": {"value": ""}, "H": {"value": ""}}
    tag(ca, {"form": "LLC-1", "state_of_form": "CA"})
    assert ca["D"]["value"].startswith("(213) 555-01") and ca["D"]["state"] == "CA"
    issues = validate({**{k: {"value": "x"} for k in "AEFGIJ"}, "H": {"value": ""}, "D": ca["D"]}, "ca")
    assert "TẠM" in issues["D"]["message"]  # checked against CA, not "state unknown"
    br = {"A": {"value": "X LTDA"}, "D": {"value": ""}, "H": {"value": "SP"}}
    tag(br)
    assert br["D"]["value"] == "" and br["D"]["phone_source"] == "needs_setup"  # no reserved block in Brazil
    fake = validate({**{k: {"value": "x"} for k in "AEFGIJ"}, "H": {"value": "CA"}, "D": {"value": "1 (619) 555-6382"}}, "ca")
    assert fake["D"]["level"] == "error"  # a 555 number that is not the app's temporary one


def test_a_website_never_shows_a_failing_number():
    assert website_phone("1 (619) 555-6382", "CA") == ("", "Đầu số 555 là số dành cho phim ảnh / ví dụ — không phải số doanh nghiệp thật")
    assert website_phone("206-291-0886", "WA") == ("206-291-0886", "")
    assert website_phone("12092333214", "WA")[0] == "12092333214"  # a code from another state: a warning, still shown
    assert website_phone("(206) 555-0142", "WA") == ("(206) 555-0142", "")  # the temporary number is shown (owner)


# ───── the provider step ─────

def _wa_doc():
    doc_id = _ocr_doc()
    with session_scope() as s:
        d = s.get(PdfDocument, doc_id)
        d.fields = {**d.fields, "H": {"value": "WA", "source": "ocr", "checked": True},
                    "D": {"value": "", "source": "missing", "phone_source": "needs_setup"}}
    return doc_id


def test_without_a_provider_nothing_is_filled(client):
    doc_id = _wa_doc()
    r = client.get(f"/api/pdf/{doc_id}/phone").json()
    assert r["provider"] is None and "TWILIO_ACCOUNT_SID" in r["message"] and r["owned"] == []
    assert client.get("/api/pdf").json()[0]["fields"]["D"]["value"] == ""


@pytest.fixture
def twilio(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC00000000000000000000000000000000")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "0" * 32)
    with respx.mock(assert_all_called=False) as m:
        m.get(f"{TW}/IncomingPhoneNumbers.json").mock(return_value=httpx.Response(200, json={"incoming_phone_numbers": [
            {"phone_number": "+12065550100", "friendly_name": "movie", "sid": "PN1"},   # 555: never usable
            {"phone_number": "+12092330000", "friendly_name": "CA number", "sid": "PN2"},  # another state
            {"phone_number": "+12067340000", "friendly_name": "free WA", "sid": "PN3"}]}))
        m.get(f"{TW}/AvailablePhoneNumbers/US/Local.json").mock(return_value=httpx.Response(200, json={"available_phone_numbers": [
            {"phone_number": "+13605551234", "region": "WA", "locality": "Olympia"},     # 555 → dropped
            {"phone_number": "+13603480000", "region": "WA", "locality": "Olympia"},
            {"phone_number": "+15033480000", "region": "OR", "locality": "Portland"}]}))   # other state → dropped
        buy = m.post(f"{TW}/IncomingPhoneNumbers.json").mock(return_value=httpx.Response(201, json={"phone_number": "+13603480000", "sid": "PN9"}))
        yield m, buy


def test_owned_number_of_the_state_is_assigned_once(client, twilio):
    _, buy = twilio
    doc_id = _wa_doc()
    r = client.get(f"/api/pdf/{doc_id}/phone").json()
    usable = [o["number"] for o in r["owned"] if not o["in_use"] and not o["problems"]]
    assert r["provider"] == "Twilio" and usable == ["+12067340000"]
    assert [a["number"] for a in r["available"]] == ["+13603480000"] and r["available"][0]["cost"] is True
    d = client.post(f"/api/pdf/{doc_id}/phone", json={"number": "+12067340000"}).json()["fields"]["D"]
    assert d["value"] == "+1 (206) 734-0000" and d["phone_source"] == "provisioned" and d["verified_active"] is False
    assert "chưa xác minh đang hoạt động" in d["note"] and not buy.called
    other = _wa_doc()
    r = client.post(f"/api/pdf/{other}/phone", json={"number": "+12067340000"})
    assert r.status_code >= 400 and "đã dùng" in r.text  # one number, one company
    r = client.post(f"/api/pdf/{other}/phone", json={"number": "+12092330000"})
    assert r.status_code >= 400 and "209" in r.text  # area code of another state
    with session_scope() as s:
        assert s.query(PhoneAssignment).count() == 1


def test_buying_needs_confirmation_and_the_open_lock(client, twilio):
    _, buy = twilio
    doc_id = _wa_doc()
    r = client.post(f"/api/pdf/{doc_id}/phone", json={"number": "+13603480000", "buy": True})
    assert r.status_code >= 400 and "xác nhận phí" in r.text and not buy.called


@pytest.mark.real_guard
def test_buying_is_refused_while_the_lock_is_closed(twilio):
    from wg_core.modules.pdf import phone_setup

    _, buy = twilio
    doc_id = _wa_doc()
    with session_scope() as s, pytest.raises(NotAvailable, match="KHOÁ"):
        phone_setup.assign(s, s.get(PdfDocument, doc_id), "+13603480000", buy=True, confirm_cost=True)
    assert not buy.called


@pytest.mark.real_guard
def test_buying_with_the_lock_open_then_relocks(twilio):
    from wg_core import write_guard
    from wg_core.models import AppSetting
    from wg_core.modules.pdf import phone_setup

    _, buy = twilio
    doc_id = _wa_doc()
    with session_scope() as s:
        sw = write_guard.load(s)
        s.merge(AppSetting(key=write_guard.KEY, value={**sw, "enabled": True, "ops": ["phone"]}))
    with session_scope() as s:
        d = phone_setup.assign(s, s.get(PdfDocument, doc_id), "+13603480000", buy=True, confirm_cost=True)
    assert buy.called and d["phone_source"] == "provisioned" and d["value"] == "+1 (360) 348-0000"
    with session_scope() as s:
        assert not write_guard.load(s)["enabled"]  # one purchase per opening
        assert s.get(PhoneAssignment, "+13603480000").bought is True


def test_typing_a_number_is_marked_manual(client):
    doc_id = _wa_doc()
    d = client.patch(f"/api/pdf/{doc_id}", json={"fields": {"D": "206-291-0886"}}).json()["fields"]["D"]
    assert d["phone_source"] == "manual" and d["value"] == "206-291-0886"


def test_only_d_changes_when_a_number_is_assigned(client, twilio):
    doc_id = _wa_doc()
    before = {k: v for k, v in client.get("/api/pdf").json()[0]["fields"].items() if k != "D"}
    client.post(f"/api/pdf/{doc_id}/phone", json={"number": "+12067340000"})
    after = {k: v for k, v in next(d for d in client.get("/api/pdf").json() if d["id"] == doc_id)["fields"].items() if k != "D"}
    assert after == before


def test_assign_rejects_a_non_us_company():
    doc_id = _wa_doc()
    from wg_core.modules.pdf import phone_setup

    with session_scope() as s:
        d = s.get(PdfDocument, doc_id)
        d.fields = {**d.fields, "H": {"value": "SP"}}
        with pytest.raises(Permanent, match="Chỉ gán được số Mỹ"):
            phone_setup.assign(s, d, "+12067340000")


def test_the_website_build_takes_the_checked_number():
    from wg_core.modules.websites.service import facts_of, site_phone

    cells = {"A": "X LLC", "D": "1 (619) 555-6382", "F": "1 Main St, San Diego, CA 92101", "G": "San Diego", "H": "CA", "I": "92101"}
    assert site_phone(cells)[0] == "" and "555" in site_phone(cells)[1]
    assert facts_of(cells)["Phone"] == ""  # the site copy never mentions it either
    assert site_phone({**cells, "D": "(619) 234-5678"}) == ("(619) 234-5678", "")


def test_state_for_the_area_code():
    from wg_core.modules.pdf.phone_setup import _state

    llc1 = PdfDocument(fields={"H": {"value": ""}}, extra={"form": "LLC-1", "state_of_form": "CA"})
    llc5 = PdfDocument(fields={"H": {"value": ""}}, extra={"form": "LLC-5", "state_of_form": "CA", "formation_state": "MARYLAND"})
    wa = PdfDocument(fields={"H": {"value": "WA"}}, extra={})
    assert (_state(llc1), _state(llc5), _state(wa)) == ("CA", "", "WA")  # a foreign LLC is never put in its home state
