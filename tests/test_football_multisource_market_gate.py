import unittest
from datetime import datetime,timedelta,timezone
from scripts.football_multisource_market_gate import selected_quote,verify_selected_markets,certified_native_shadow_fixture,extract_new_verified_rows

NOW=datetime(2026,10,15,12,tzinfo=timezone.utc)

def choice():
    return {
        "key":"OVER_25","name":"Over 2.5","market":"over_under",
        "outcome":"over","internal_market_code":"OU_2.5_OVER_FT",
        "market_code":"OU_2.5_OVER_FT",
        "probability":0.82,"conservative_probability":0.76,
    }

def prices(delta_minutes=7,*,market="OU_2.5_OVER_FT",source="bsd_consensus"):
    return {market:{
        "odds":1.81,"origin":source,"bookmaker":"consensus",
        "updated_at":(NOW-timedelta(minutes=delta_minutes)).isoformat()
    }}

class MarketWitnessTests(unittest.TestCase):
    def test_selected_market_has_original_verified_quote(self):
        selected,why=selected_quote(choice(),prices(),at=NOW)
        self.assertEqual(why,"verified_real_consensus_market")
        self.assertEqual(selected["odds_source"],"bsd_consensus")
        self.assertEqual(selected["internal_market_code"],"OU_2.5_OVER_FT")
        self.assertFalse(selected["estimated_odds"])

    def test_other_market_never_substitutes_for_selected_one(self):
        selected,why=selected_quote(choice(),prices(market="OU_1.5_OVER_FT"),at=NOW)
        self.assertIsNone(selected)
        self.assertEqual(why,"selected_market_not_quoted")

    def test_stale_or_future_quote_never_qualifies(self):
        for age in (121,-1):
            with self.subTest(age=age):
                selected,why=selected_quote(choice(),prices(delta_minutes=age),at=NOW)
                self.assertIsNone(selected)
                self.assertEqual(why,"selected_market_quote_stale_or_untimed")

    def test_only_real_consensus_pricing_is_allowed(self):
        selected,why=selected_quote(choice(),prices(source="mrxpronos_model"),at=NOW)
        self.assertIsNone(selected)
        self.assertEqual(why,"selected_market_not_quoted")
        selected,why=selected_quote(choice(),prices(source="bsd_bookmaker"),at=NOW)
        self.assertIsNone(selected)
        self.assertEqual(why,"selected_market_not_quoted")

    def test_only_official_native_id_can_replace_external_research_id_in_canary(self):
        source={
            "_schedule_verified_by":"openfootball_cc0",
            "league_verified":True,"status":"prematch",
            "home_team":"Arsenal","away_team":"Chelsea",
        }
        adapted={
            "id":7_500_000_000_000_042,"_derived_research_id":True,
            "home_team":{"id":7_000_001,"name":"Arsenal"},
            "away_team":{"id":7_000_002,"name":"Chelsea"},
            "event_date":"2026-10-16T19:00:00Z","status":"notstarted",
            "league_id":7_600_001,"league_name":"Premier League",
        }
        official={
            "id":12345,"home_team":{"id":101,"name":"Arsenal"},
            "away_team":{"id":102,"name":"Chelsea"},
            "event_date":"2026-10-16T19:05:00Z","status":"notstarted",
        }
        event=certified_native_shadow_fixture(source,adapted,official,at=NOW)
        self.assertEqual(event["id"],12345)
        self.assertEqual(event["home_team_id"] if "home_team_id" in event else event["home_team"]["id"],7_000_001)
        self.assertTrue(event["_native_bsd_id_verified_in_process"])
        self.assertEqual(adapted["id"],7_500_000_000_000_042)
        self.assertEqual(official["id"],12345)
        for kind in ("wrong_team","wrong_date","synthetic_native","unverified","wrong_status"):
            with self.subTest(case=kind):
                x=dict(source); y=dict(adapted); z=dict(official)
                if kind=="wrong_team":
                    z["away_team"]={"id":102,"name":"Tottenham"}
                elif kind=="wrong_date":
                    z["event_date"]="2026-10-16T19:16:00Z"
                elif kind=="synthetic_native":
                    z["id"]=7_500_000_000_000_042
                elif kind=="unverified":
                    x["league_verified"]=False
                else:
                    z["status"]="finished"
                with self.assertRaises(ValueError):
                    certified_native_shadow_fixture(x,y,z,at=NOW)

    def test_extracts_only_new_native_rows_with_real_prices(self):
        accepted={
            "id":"bsd:12345","source_event_id":12345,"source":"bsd",
            "event_date":"2026-10-16T19:05:00+00:00","combo_only":False,
            "prediction":{
                "selection_key":"OVER_25","market":"over_under","odds":1.81,
                "confidence":78.0,"odds_source":"bsd_consensus","estimated_odds":False,
            },
        }
        dry={"source":"bsd","matches":[accepted]}
        base={"source":"bsd","matches":[],"performance_tracker":{}}
        rows=extract_new_verified_rows(dry,base,{12345},historical_published_ids=set())
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]["multisource_verification"]["v21_and_value_guard_passed"])
        self.assertTrue(rows[0]["multisource_verification"]["production_assembler_created_row"])
        self.assertNotIn("multisource_verification",accepted)

    def test_rejects_estimated_or_non_consensus_candidate_output(self):
        row={
            "id":"bsd:12345","source_event_id":12345,"source":"bsd",
            "event_date":"2026-10-16T19:05:00+00:00","combo_only":False,
            "prediction":{
                "selection_key":"OVER_25","market":"over_under","odds":1.81,
                "confidence":78.0,"odds_source":"mrxpronos_model","estimated_odds":True,
            },
        }
        with self.assertRaises(AssertionError):
            extract_new_verified_rows({"source":"bsd","matches":[row]},
                                      {"source":"bsd","matches":[]},{12345},historical_published_ids=set())


    def test_extract_never_recreates_a_retired_historical_coupon(self):
        accepted={
            "id":"bsd:12345","source_event_id":12345,"source":"bsd",
            "prediction":{
                "selection_key":"OVER_25","market":"over_under","odds":1.81,
                "confidence":78.0,"odds_source":"bsd_consensus",
                "estimated_odds":False,
            },
        }
        with self.assertRaisesRegex(AssertionError,"Already published"):
            extract_new_verified_rows(
                {"source":"bsd","matches":[accepted]},
                {"source":"bsd","matches":[]},
                {12345},historical_published_ids={"12345"})

    def test_extraction_requires_historical_ledger_evidence(self):
        with self.assertRaisesRegex(ValueError,"append-only"):
            extract_new_verified_rows(
                {"source":"bsd","matches":[]},
                {"source":"bsd","matches":[]},
                {12345},historical_published_ids=None)

    def test_untrusted_production_feed_or_more_than_eight_events_rejected(self):
        with self.assertRaises(ValueError):
            verify_selected_markets([],[],{"source":"sportdata","matches":[]},at=NOW,historical_ledger={"schema":"bsd-v2-publication-ledger-1","entries":[]})
        with self.assertRaises(ValueError):
            verify_selected_markets([],[(None,None,{})]*9,
                {"source":"bsd","matches":[],"performance_tracker":{}},at=NOW,historical_ledger={"schema":"bsd-v2-publication-ledger-1","entries":[]})

if __name__=="__main__":
    unittest.main()
