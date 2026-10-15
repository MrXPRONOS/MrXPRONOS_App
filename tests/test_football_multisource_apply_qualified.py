import unittest
from copy import deepcopy
from datetime import datetime,timezone

from scripts.football_multisource_apply_qualified import apply

NOW=datetime(2026,10,15,12,tzinfo=timezone.utc)

def ledger(*ids):
    return {
        "schema":"bsd-v2-publication-ledger-1",
        "entries":[{
            "key":str(ident)+"|2026-10-16T19:05:00+00:00",
            "source_event_id":str(ident),
            "original_pick":{"selection_key":"OVER_25"},
        } for ident in ids],
    }


def row(ident=12345, selection="OVER_25", source="bsd_consensus", estimated=False):
    pick={
        "selection_key":selection,"market":"over_under","odds":1.81,
        "confidence":78.0,"odds_source":source,"estimated_odds":estimated,
    }
    return {
        "id":f"bsd:{ident}","source_event_id":ident,"source":"bsd",
        "event_date":"2026-10-16T19:05:00+00:00","date":"2026-10-16",
        "home_team":"A","away_team":"B","league":"Premier League",
        "combo_only":False,"prediction":pick,
        "multisource_verification":{
            "mode":"qualified_external_candidate",
            "schedule_corroborated":True,
            "native_bsd_event_verified":True,
            "selected_market_real_consensus_price":True,
            "v21_and_value_guard_passed":True,
            "production_assembler_created_row":True,
        },
    }


class QualifiedApplyTests(unittest.TestCase):
    def test_zero_candidates_is_valid_and_preserves_matches(self):
        feed={"source":"bsd","matches":[{"id":"bsd:1","source_event_id":1}],"diagnostics":{}}
        before=deepcopy(feed["matches"])
        report=apply(feed,[],now=NOW,publication_ledger=ledger())
        self.assertEqual(report["added"],0)
        self.assertEqual(feed["matches"],before)
        self.assertTrue(feed["diagnostics"]["multisource_generation"]["enabled"])

    def test_adds_only_fully_verified_real_priced_row(self):
        feed={"source":"bsd","matches":[],"diagnostics":{}}
        report=apply(feed,[row()],now=NOW,publication_ledger=ledger())
        self.assertEqual(report["added"],1)
        self.assertEqual(len(feed["matches"]),1)
        self.assertEqual(feed["matches"][0]["source_event_id"],12345)

    def test_same_existing_selection_is_idempotent(self):
        candidate=row()
        existing=deepcopy(candidate)
        existing.pop("multisource_verification")
        feed={"source":"bsd","matches":[existing],"diagnostics":{}}
        report=apply(feed,[candidate],now=NOW,publication_ledger=ledger())
        self.assertEqual(report,{"staged":1,"added":0,"duplicates":1})
        self.assertEqual(len(feed["matches"]),1)

    def test_never_changes_existing_market(self):
        feed={"source":"bsd","matches":[row(selection="UNDER_35")],"diagnostics":{}}
        with self.assertRaisesRegex(ValueError,"alter"):
            apply(feed,[row(selection="OVER_25")],now=NOW,publication_ledger=ledger())

    def test_rejects_estimated_non_consensus_or_incomplete_proof(self):
        for candidate in (row(source="mrxpronos_model",estimated=True),row()):
            if candidate["prediction"]["odds_source"]=="bsd_consensus":
                candidate["multisource_verification"]["v21_and_value_guard_passed"]=False
            with self.subTest(candidate=candidate["prediction"]["odds_source"]):
                with self.assertRaises(ValueError):
                    apply({"source":"bsd","matches":[],"diagnostics":{}},[candidate],now=NOW,publication_ledger=ledger())

    def test_retired_event_in_append_only_history_is_never_republished(self):
        # No row remains in the current public feed, but the original
        # selection is still permanently recorded in the ledger.
        feed={"source":"bsd","matches":[],"diagnostics":{}}
        original=deepcopy(feed)
        with self.assertRaisesRegex(ValueError,"re-publish"):
            apply(feed,[row()],now=NOW,publication_ledger=ledger(12345))
        self.assertEqual(feed,original)

    def test_all_or_nothing_if_later_candidate_fails(self):
        feed={"source":"bsd","matches":[],"diagnostics":{"old":"unchanged"}}
        before=deepcopy(feed)
        invalid=row(ident=12346)
        invalid["multisource_verification"]["v21_and_value_guard_passed"]=False
        with self.assertRaises(ValueError):
            apply(feed,[row(),invalid],now=NOW,publication_ledger=ledger())
        self.assertEqual(feed,before)

    def test_conflicting_native_source_id_is_rejected(self):
        candidate=row()
        candidate["id"]="bsd:99999"
        with self.assertRaisesRegex(ValueError,"conflicting BSD identity"):
            apply({"source":"bsd","matches":[],"diagnostics":{}},
                  [candidate],now=NOW,publication_ledger=ledger())

    def test_missing_or_malformed_historical_ledger_is_rejected(self):
        for history in ({},{"schema":"incorrect","entries":[]},None):
            with self.subTest(history=history):
                with self.assertRaises(ValueError):
                    apply({"source":"bsd","matches":[],"diagnostics":{}},
                          [],now=NOW,publication_ledger=history)

    def test_pipeline_summary_allows_zero_and_stays_aggregate_only(self):
        import json
        stats={
            "external_total":15,"independent_cc0_calendar_confirmed":4,
            "one_to_one_native_event_links":3,"qualified_candidate_rows_staged":0,
            "raw_unpublished_fixture":"Example FC vs Sample FC",
            "read_only_native_consensus_price_audit":{
                "historically_published_native_links_excluded":1,
                "unpublished_native_links_in_48h_window":2,
                "official_native_events_quoted_attempts":2,
                "actual_48h_publication_window_quote_attempts":2,
                "fresh_consensus_market_prices":7,
            },
            "full_model_selected_market_consensus_audit":{
                "aggregate":{},
                "native_full_assembler_canary":{"events_within_native_48h_window":2},
            },
        }
        feed={"source":"bsd","matches":[],"diagnostics":{}}
        apply(feed,[],now=NOW,publication_ledger=ledger(),aggregate_report=stats)
        summary=feed["diagnostics"]["multisource_generation"]["coverage"]
        self.assertEqual(summary["football_model_market_candidates"],0)
        self.assertEqual(summary["historical_events_excluded_from_price_probes"],1)
        self.assertNotIn("Example FC",json.dumps(feed))

    def test_rejects_more_than_eight_rows(self):
        with self.assertRaises(ValueError):
            apply({"source":"bsd","matches":[],"diagnostics":{}},
                  [row(ident=20000+i) for i in range(9)],now=NOW,publication_ledger=ledger())


if __name__=="__main__":
    unittest.main()
