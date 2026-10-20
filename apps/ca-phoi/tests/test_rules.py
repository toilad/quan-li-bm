import random
import tempfile
import unittest
from pathlib import Path

from ca_phoi import rules
from ca_phoi.jobs import random_batch
from ca_phoi.store import DONE, Store


def row(title, date="04/28/2004", status="Active", etype=rules.DOMESTIC_LLC):
    return {"TITLE": [title], "FILING_DATE": date, "STATUS": status, "ENTITY_TYPE": etype,
            "ID": 1, "RECORD_NUM": "rn"}


SOI = {"AMENDMENT_TYPE": "Statement of Information", "AMENDMENT_NUM": "BA2024", "DOWNLOAD_LINK": "/x/soi"}
INIT = {"AMENDMENT_TYPE": "Initial Filing", "AMENDMENT_NUM": "200412110197", "DOWNLOAD_LINK": "/x/init",
        "AMENDMENT_DATE": "4/28/2004"}


class FilterTest(unittest.TestCase):
    def ok(self, r, **kw):
        return rules.reject_reason(rules.parse_row(r), **kw) is None

    def test_parse(self):
        t = rules.parse_row(row("SNC MANAGEMENT & HOLDINGS, LLC (200412110197)"))
        self.assertEqual((t.entity_name, t.entity_number, t.date),
                         ("SNC MANAGEMENT & HOLDINGS, LLC", "200412110197", "2004-04-28"))

    def test_rules(self):
        self.assertTrue(self.ok(row("SNC MANAGEMENT & HOLDINGS, LLC (200412110197)")))
        self.assertTrue(self.ok(row("HOLDINGSPHERE LLC (201102410200)", date="01/07/2011")))
        self.assertTrue(self.ok(row("ABC HOLDINGS LLC (1)", etype=rules.FOREIGN_LLC)))
        self.assertFalse(self.ok(row("ABC HOLDINGS, INC. (1)", etype="Stock Corporation - CA - General")))
        self.assertFalse(self.ok(row("ABC HOLDINGS L.L.C. (1)")))           # must end in LLC
        self.assertFalse(self.ok(row("ABC LLC HOLDINGS (1)")))
        self.assertFalse(self.ok(row("ABC HOLDINGS LLC (1)", date="01/01/2017")))
        self.assertTrue(self.ok(row("ABC HOLDINGS LLC (1)", date="12/31/2016")))
        self.assertFalse(self.ok(row("ABC HOLDINGS LLC (1)", status="Suspended - FTB")))
        self.assertTrue(self.ok(row("ABC HOLDINGS LLC (1)", status="Suspended - FTB"), active_only=False))
        # converted entity: number filed 2016, Initial Filing Date from the old corporation (2010)
        self.assertFalse(self.ok(row("HOLDINGS MANAGER, LLC (201622510332)", date="07/26/2010")))
        self.assertTrue(self.ok(row("X LLC (200501010001)", date="12/30/2004")))  # late-Dec numbering
        self.assertTrue(self.ok(row("SNC MANAGEMENT & HOLDINGS, LLC (200412110197)", date="04/28/2004")))
        name30 = "A" * 26 + " LLC"
        self.assertTrue(self.ok(row(f"{name30} (1)")))
        self.assertFalse(self.ok(row(f"B{name30} (1)")))
        self.assertTrue(self.ok(row(f"B{name30} (1)"), max_name_len=31))


class InitialFilingTest(unittest.TestCase):
    def test_picks_initial(self):
        p = rules.pick_initial_filing([SOI, INIT], "200412110197")
        self.assertEqual(p.filing["DOWNLOAD_LINK"], "/x/init")

    def test_never_substitutes_statement_of_information(self):
        p = rules.pick_initial_filing([SOI, dict(SOI, AMENDMENT_NUM="BA2026")], "200412110197")
        self.assertIsNone(p.filing)
        self.assertEqual(p.skip_reason, "no Initial Filing in history")

    def test_initial_without_pdf_or_wrong_number(self):
        self.assertIsNone(rules.pick_initial_filing([dict(INIT, DOWNLOAD_LINK=None), SOI], "200412110197").filing)
        self.assertIsNone(rules.pick_initial_filing([INIT], "999").filing)
        self.assertIsNone(rules.pick_initial_filing([INIT, INIT], "200412110197").filing)

    def test_conversion_in_history(self):
        conv = {"AMENDMENT_TYPE": "Legacy Conversion", "AMENDMENT_NUM": "", "DOWNLOAD_LINK": None}
        self.assertIsNone(rules.pick_initial_filing([SOI, conv, INIT], "200412110197").filing)

    def test_form(self):
        self.assertTrue(rules.expected_form(rules.DOMESTIC_LLC).startswith("LLC-1"))
        self.assertTrue(rules.expected_form(rules.FOREIGN_LLC).startswith("LLC-5"))


class FilenameTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(rules.safe_filename("SNC MANAGEMENT & HOLDINGS, LLC"), "SNC MANAGEMENT & HOLDINGS LLC.pdf")
        self.assertEqual(rules.safe_filename("HORUS HOLDINGS LLC"), "HORUS HOLDINGS LLC.pdf")
        self.assertEqual(rules.safe_filename('A/B: "C" <D>? LLC'), "A B C D LLC.pdf")
        self.assertEqual(rules.safe_filename("ABC HOLDINGS, LLC", "200912345678"),
                         "ABC HOLDINGS LLC - 200912345678.pdf")


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.db")
        self.store.ensure_keywords([f"k{i}" for i in range(8)])

    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()

    def test_random_prefers_not_run(self):
        for k in ["k0", "k1", "k2", "k3", "k4"]:
            self.store.set_keyword(k, DONE)
        b = random_batch(self.store, rng=random.Random(1))
        self.assertEqual(sorted(b), ["k5", "k6", "k7"])  # only 3 left: take what remains
        for k in b:
            self.store.set_keyword(k, DONE)
        self.assertEqual(len(set(random_batch(self.store))), 5)

    def test_dedupe_and_history(self):
        t = rules.parse_row(row("ABC HOLDINGS LLC (200912345678)"))
        self.assertTrue(self.store.add_target(t, "k0"))
        self.assertFalse(self.store.add_target(t, "k1"))       # same entity from another keyword
        self.store.record_download(t.entity_number, t.entity_name, "k0", "OK", "ABC HOLDINGS LLC.pdf", "")
        self.assertEqual(self.store.pending_count(), 0)
        self.store.db.execute("DELETE FROM targets")
        self.assertFalse(self.store.add_target(t, "k2"))       # downloaded on an earlier day: never again


if __name__ == "__main__":
    unittest.main()
