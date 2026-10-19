"""Final offline tests for #04, #08, #09, #10, and old Telegram corrections."""
import copy
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from crypto import export_breaking_v2 as br,export_exchanges_v2 as ex
from crypto import export_regulation_v2 as rg
from crypto.production_live_v1 import alert_is_new,news_already_posted
from crypto.regulation_10_approval import approved_report,official_url
from crypto.editorial_fr import exchange_synopsis,breaking_synopsis
from crypto.history_corrector import caption

UTC=timezone.utc

class FinalLiveTests(unittest.TestCase):
    def test_real_alert_first_new_then_sustained_suppressed(self):
        state={"sent":{}}
        raw={"status":"real_alert","row":{"symbol":"BTC","level":5,"direction":"up"},
             "observations":[{"symbol":"BTC","change":5.5,"level":5}]}
        with patch("crypto.production_live_v1.seed.write_state"):
            self.assertTrue(alert_is_new(state,raw))
            # An unacknowledged detection is not a published Telegram alert.
            self.assertTrue(alert_is_new(state,raw))
            state.setdefault("alert_last_published_signal",{})["BTC"] = {
                "level":5,"direction":"up"}
            state.setdefault("alert_rearmed",{})["BTC"] = False
            self.assertFalse(alert_is_new(state,raw))
            raw["observations"][0]["change"]=10.1
            raw["observations"][0]["level"]=10
            raw["row"]["level"]=10
            self.assertTrue(alert_is_new(state,raw))
            raw["status"]="no_alert"
            raw["observations"][0]["change"]=3
            raw["observations"][0]["level"]=0
            self.assertFalse(alert_is_new(state,raw))
            raw["status"]="real_alert"
            raw["observations"][0]["change"]=5.3
            raw["observations"][0]["level"]=5
            raw["row"]["level"]=5
            self.assertTrue(alert_is_new(state,raw))

    def test_shared_news_fingerprint_deduplication(self):
        state={"sent":{}}
        d={"fingerprints":["12345abc","67890def"]}
        self.assertFalse(news_already_posted(state,d))
        state["news_fingerprints"]["12345abc"]={"number":8,"message_id":10}
        self.assertTrue(news_already_posted(state,d))

    def test_braking_headline_contradictions_rejected(self):
        now=datetime.now(UTC)
        a={"source":"CoinDesk","title":"Bitcoin ETF approval announced by regulator",
           "url":"https://www.coindesk.com/news/real-approval",
           "published_at":(now-timedelta(hours=2)).isoformat(),"topic":"bitcoin"}
        b={**a,"source":"The Block","url":"https://www.theblock.co/news/real-rejection",
           "title":"Bitcoin ETF rejection announced by regulator"}
        self.assertFalse(br.corroborates(a,b))
        b["title"]="Bitcoin ETF approval announced after regulator review"
        self.assertTrue(br.corroborates(a,b))
        d=br.build_report((a,b),now)
        br.validate_real(d,now)
        self.assertIn("Bitcoin",d["headline_fr"])
        self.assertIn("approbation",d["headline_fr"].lower())

    def test_exchange_news_uses_safe_french_synopsis(self):
        d=ex.demo_report()
        self.assertIn("Binance".upper(),d["headline_fr"])
        self.assertEqual(
            exchange_synopsis("OKX","OKX lists new tokens","FRAIS & TRADING"),
            "OKX : annonce concernant les cotations")
        self.assertIn("Ethereum",breaking_synopsis("ethereum","Ethereum network outage announced"))

    def sample_legal(self):
        now=datetime.now(UTC)
        a=rg.parse_entry({
            "title":"SEC proposes new regulation for crypto asset custody rules",
            "link":"https://www.sec.gov/newsroom/press-releases/crypto-custody-real",
            "published_parsed":(now-timedelta(hours=2)).timetuple(),
        },"SEC",now)
        candidate=rg.select_candidate([a],{"reviewed_urls":[]},now)
        approval={
            "candidate_fingerprint":candidate["fingerprint"],
            "source_url":a["url"],
            "human_approved":True,
            "jurisdiction_checked":True,"stage_checked":True,"effective_date_checked":True,
            "primary_text_checked":True,"exceptions_checked":True,
            "approved_by":"Éditeur de contrôle QA",
            "title_fr":"La SEC propose de nouvelles règles sur la conservation de cryptoactifs",
            "summary_fr":"Proposition réglementaire concernant la conservation de cryptoactifs. Ceci ne signifie pas une entrée en vigueur.",
            "jurisdiction":"ÉTATS-UNIS",
            "review_note":"Contrôle QA sur un exemple de titre, sans aucune publication réelle.",
            "verified_stage":"PROPOSITION","effective_date":"non_applicable",
            "official_source":"SEC",
            "official_url":"https://www.sec.gov/newsroom/press-releases/crypto-custody-real",
            "reviewed_at":now.isoformat(),
        }
        return candidate,approval,now

    def test_manual_legal_review_checks_all_material_details(self):
        candidate,approval,now=self.sample_legal()
        d=approved_report(candidate,approval,now)
        self.assertEqual(d["status"],"editorially_approved")
        self.assertTrue(d["human_approved"])
        self.assertEqual(d["approval"]["verified_stage"],"PROPOSITION")
        for field in ("human_approved","jurisdiction_checked","stage_checked",
                      "effective_date_checked","primary_text_checked","exceptions_checked"):
            bad=copy.deepcopy(approval)
            bad[field]=False
            with self.subTest(field=field),self.assertRaises(ValueError):
                approved_report(candidate,bad,now)

    def test_official_domain_and_effective_date_constraints(self):
        candidate,approval,now=self.sample_legal()
        bad=copy.deepcopy(approval)
        bad["official_url"]="https://www.sec.gov.evil.tld/legislation"
        with self.assertRaises(ValueError):
            approved_report(candidate,bad,now)
        bad=copy.deepcopy(approval)
        bad["verified_stage"]="ENTRÉE EN VIGUEUR ANNONCÉE"
        with self.assertRaises(ValueError):
            approved_report(candidate,bad,now)
        bad=copy.deepcopy(approval)
        bad["reviewed_at"]=(now-timedelta(days=5)).isoformat()
        with self.assertRaises(ValueError):
            approved_report(candidate,bad,now)

    def test_history_corrections_use_original_corrected_facts(self):
        import json
        from pathlib import Path
        d=json.loads(Path("crypto/history_corrections_2026_10_18.json").read_text())
        values={r["number"]:r for r in d["corrections"]}
        self.assertEqual(values[1]["market_cap_usd"],2718295617920)
        self.assertEqual(values[3]["volume_24h_usd"],84256758343.4)
        for n in (1,3,9):
            self.assertIn("RECTIFICATIF",caption(values[n]))
            self.assertLess(len(caption(values[n])),1024)


if __name__=="__main__":
    unittest.main()
