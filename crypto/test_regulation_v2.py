"""Offline tests of Mr XPRONOS regulatory news #10."""
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from crypto import export_regulation_v2 as reg

UTC = timezone.utc


class RegulatoryNewsTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(UTC)
        self.title = "SEC proposes new regulation for crypto asset custody rules"

    def entry(self, source="SEC", title=None, offset=2):
        host = reg.FEEDS[source][1]
        url = "https://www." + host + "/newsroom/press-releases/regulation-crypto-2026"
        return reg.parse_entry({
            "title": title or self.title,
            "link": url,
            "published_parsed": (self.now - timedelta(hours=offset)).timetuple(),
        }, source, self.now)

    def test_eight_free_media_and_three_public_regulators(self):
        self.assertEqual(len(reg.EDITORIAL_FEEDS), 8)
        self.assertEqual(len(reg.REGULATOR_FEEDS), 3)
        self.assertEqual(len(reg.FEEDS), 11)
        self.assertEqual(len(set(domain for url, domain in reg.FEEDS.values())), 11)

    def test_demo_is_explicit_and_not_a_real_candidate(self):
        d = reg.demo_report()
        self.assertTrue(d["is_demo"])
        self.assertTrue(d["approval_required"])
        with self.assertRaises(ValueError):
            reg.validate_candidate(d, self.now)

    def test_accept_qualifying_official_announcement(self):
        x = self.entry()
        self.assertTrue(x["official"])
        self.assertEqual(x["region"], "ÉTATS-UNIS")
        self.assertEqual(x["stage"], "PROPOSITION")

    def test_accept_verified_media_with_attribution(self):
        x = self.entry(source="CoinDesk",
                       title="EU proposes crypto asset licensing regulation for exchanges")
        self.assertFalse(x["official"])
        self.assertEqual(x["region"], "UNION EUROPÉENNE")
        self.assertEqual(x["stage"], "PROPOSITION")

    def test_reject_non_crypto_and_non_regulatory_news(self):
        for t in ("SEC proposes new airline safety regulation this year",
                  "Bitcoin price soars as crypto traders celebrate today",
                  "Sponsored: US crypto regulation news this week",
                  "Bitcoin price prediction after SEC approved ETF"):
            with self.assertRaises(ValueError):
                self.entry(title=t)

    def test_reject_undated_and_stale_articles(self):
        for offset in (100, -2):
            with self.assertRaises(ValueError):
                self.entry(offset=offset)
        with self.assertRaises(ValueError):
            reg.parse_entry({"title": self.title,
                             "link": "https://sec.gov/newsroom/crypto-regulation-2026"},
                            "SEC", self.now)

    def test_reject_unapproved_domains(self):
        for url in ("https://sec.gov.evil.org/news/regulation-crypto",
                    "http://www.sec.gov/newsroom/press-release-crypto",
                    "https://bad.org/news/crypto-rule",
                    "https://www.sec.gov/"):
            with self.assertRaises(ValueError):
                reg.canonical_url(url, "SEC")

    def test_eu_commission_approved_host_variants(self):
        good = "https://ec.europa.eu/commission/presscorner/detail/en/ip_2026_1"
        self.assertEqual(reg.canonical_url(good, "Commission européenne"), good)
        good2 = "https://commission.europa.eu/presscorner/news/detail"
        self.assertEqual(reg.canonical_url(good2, "Commission européenne"), good2)

    def test_uncertain_legal_status_is_not_claimed(self):
        title = "SEC issues crypto guidance about digital asset markets"
        self.assertEqual(reg.stage(title), "STATUT JURIDIQUE À VÉRIFIER")

    def test_lifecycle_labels_are_distinct(self):
        self.assertEqual(reg.stage("EU proposes new crypto law"), "PROPOSITION")
        self.assertEqual(reg.stage("EU approves crypto law"), "ADOPTION ANNONCÉE")
        self.assertEqual(reg.stage("EU crypto law enters into force"), "ENTRÉE EN VIGUEUR ANNONCÉE")
        self.assertEqual(reg.stage("EU opens consultation on crypto rules"), "CONSULTATION")

    def test_candidate_is_held_for_mandatory_human_review(self):
        article = self.entry()
        d = reg.select_candidate([article], {"reviewed_urls": []}, self.now)
        self.assertEqual(d["status"], "pending_human_review")
        self.assertFalse(d["legal_status_confirmed"])
        self.assertTrue(d["approval_required"])
        reg.validate_candidate(d, self.now)

    def test_press_candidate_remains_unapproved_even_if_publisher(self):
        article = self.entry("CoinDesk", "SEC proposes new rules for stablecoins")
        d = reg.select_candidate([article], {"reviewed_urls": []}, self.now)
        self.assertTrue(d["approval_required"])
        self.assertEqual(d["primary"]["source"], "CoinDesk")

    def test_prefer_official_first_party_regulatory_text(self):
        press = self.entry("CoinDesk", "SEC proposes new stablecoin licensing regulation")
        official = self.entry("SEC")
        d = reg.select_candidate([press, official], {"reviewed_urls": []}, self.now)
        self.assertEqual(d["primary"]["source"], "SEC")

    def test_skip_already_reviewed_article(self):
        article = self.entry()
        state = {"reviewed_urls": [reg.fingerprint(article)]}
        self.assertIsNone(reg.select_candidate([article], state, self.now))

    def test_guard_rejects_review_bypass_and_tampering(self):
        d = reg.select_candidate([self.entry()], {"reviewed_urls": []}, self.now)
        d["approval_required"] = False
        with self.assertRaises(ValueError):
            reg.validate_candidate(d, self.now)
        d["approval_required"] = True
        d["primary"]["stage"] = "ENTRÉE EN VIGUEUR ANNONCÉE"
        with self.assertRaises(ValueError):
            reg.validate_candidate(d, self.now)

    def test_registry_fail_closed(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            p.write_text('{"reviewed_urls": ["ok", 7]}')
            with self.assertRaises(ValueError):
                reg.load_state(p)


if __name__ == "__main__":
    unittest.main()
