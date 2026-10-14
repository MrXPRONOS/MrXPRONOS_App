import copy
import unittest

from scripts.football_multisource_release_gate import assess


def reports():
    v2 = {
        "test_only": True, "production_modified": False,
        "calibrated_production_coupons": 0,
        "input_api_fixtures": 1401,
        "calendar_corroborated_fixtures": 28,
        "qualified_external_fixtures": 25,
        "raw_v2_candidates": 25,
        "historic_matches": 9004,
        "no_bookmaker_quote_gate": {
            "fixtures_checked": 25,
            "accepted_with_no_bookmaker_quotes": 0,
            "used_original_predict_v2": True,
            "publication_enabled": False,
        },
        "external_pricing_bridge": {
            "inspected_fixtures": 25,
            "native_bsd_odds_event_ids_verified": 0,
            "external_to_bookmaker_event_matches_verified": 0,
            "publication_enabled": False,
        },
    }
    calendar = {"coverage": {"schedule_matches_confirmed": 28}}
    fixtures = {"total_fixtures": 1401}
    sportscore = {
        "new_events_added_to_prediction_pipeline": 0,
        "no_production_writes": True, "possible_incomplete_coverage": True,
    }
    return [v2, calendar, fixtures, sportscore]


class ReleaseGateTests(unittest.TestCase):
    def test_research_success_not_equivalent_to_publication_authorization(self):
        decision = assess(*reports())
        self.assertEqual(decision["decision"], "NO_GO")
        self.assertTrue(decision["research_pipeline_passed"])
        self.assertFalse(decision["production_publication_authorized"])
        self.assertFalse(decision["research_branch_fusion_authorized_by_this_report"])
        self.assertGreaterEqual(len(decision["blocking_requirements"]), 6)
        self.assertEqual(decision["source_metrics"]["unpriced_v2_research_candidates"], 25)

    def test_real_research_calibration_proof_does_not_authorize_production(self):
        extra={
            "research_only":True,"production_publication_authorized":False,
            "raw_or_private_events_exported":False,"telegram_posts":0,
            "all_native_bsd_v2_fit_functions_used":True,
            "full_calibration_and_specialists_executed":True,
            "training_sufficiency_requirements_met":True,
            "upcoming_research":{"official_bookmaker_quotes_loaded":False},
            "holdout_evaluation":{
                "strict_pre_day_data_availability_enforced":True,
                "not_a_verified_kickoff_or_odds_backtest":True,
                "matches_examined":120,
                "selected_without_market_quotes":111,
                "wins_of_selected_unpriced_markets":94,"hit_rate":0.8468,
            },
        }
        rows=reports()
        result=assess(*rows,extra)
        self.assertTrue(result["checks"]["native_research_model_calibration_reproduced"])
        self.assertEqual(result["calibrated_replay_2026"]["selected_successes"],94)
        self.assertEqual(result["decision"],"NO_GO")
        self.assertFalse(result["production_publication_authorized"])
        corrupted=copy.deepcopy(extra)
        corrupted["holdout_evaluation"]["wins_of_selected_unpriced_markets"]=112
        with self.assertRaises(ValueError):
            assess(*rows,corrupted)
        corrupted=copy.deepcopy(extra)
        corrupted["holdout_evaluation"]["not_a_verified_kickoff_or_odds_backtest"]=False
        with self.assertRaises(ValueError):
            assess(*rows,corrupted)

    def test_native_link_and_consensus_prices_are_proof_not_publication_authorization(self):
        evidence={
            "scope":"read_only_identity_evidence",
            "research_only":True,"native_event_ids_exported":False,
            "no_data_json_modified":True,
            "original_production_publication_enabled":False,
            "external_total":918,"external_cc0_verified":22,
            "one_to_one_native_event_links":21,
            "official_league_metadata_requested":4,
            "official_league_metadata_verified":4,
            "bsd_http_calls":9,
            "read_only_native_consensus_price_audit":{
                "official_native_events_quoted_attempts":2,
                "events_with_fresh_consensus_market_prices":2,
                "fresh_consensus_market_prices":28,
                "event_ids_selected_only_from_confirmed_native_links":True,
                "consensus_is_not_executable_bookmaker_offer":True,
                "independent_bookmaker_selection_codes_verified":0,
                "raw_market_prices_or_event_ids_exported":False,
                "production_market_policy_approved":False,
            }
        }
        decision=assess(*reports(),None,evidence)
        self.assertTrue(decision["checks"]["independently_corroborated_native_event_links_observed"])
        self.assertTrue(decision["checks"]["fresh_bsd_consensus_market_prices_observed"])
        self.assertEqual(decision["source_metrics"]["authentic_bsd_event_links_from_private_validation"],21)
        self.assertEqual(decision["source_metrics"]["fresh_bsd_consensus_market_prices_from_private_validation"],28)
        self.assertEqual(decision["decision"],"NO_GO")
        self.assertFalse(decision["production_publication_authorized"])
        invalid=copy.deepcopy(evidence)
        invalid["read_only_native_consensus_price_audit"]["independent_bookmaker_selection_codes_verified"]=2
        with self.assertRaises(ValueError):
            assess(*reports(),None,invalid)
        invalid=copy.deepcopy(evidence)
        invalid["one_to_one_native_event_links"]=23
        with self.assertRaises(ValueError):
            assess(*reports(),None,invalid)

    def test_zero_candidates_is_not_false_claim_of_production_readiness(self):
        rows = reports()
        rows[0]["raw_v2_candidates"] = 0
        rows[0]["qualified_external_fixtures"] = 0
        rows[0]["calendar_corroborated_fixtures"] = 0
        rows[0]["no_bookmaker_quote_gate"]["fixtures_checked"] = 0
        rows[0]["external_pricing_bridge"]["inspected_fixtures"] = 0
        verdict = assess(*rows)
        self.assertEqual(verdict["decision"], "NO_GO")
        self.assertFalse(verdict["production_publication_authorized"])

    def test_inconsistent_funnel_cannot_be_certified(self):
        rows = reports()
        rows[0]["raw_v2_candidates"] = 26
        with self.assertRaises(ValueError):
            assess(*rows)
        rows = reports()
        rows[0]["external_pricing_bridge"]["inspected_fixtures"] = 24
        with self.assertRaises(ValueError):
            assess(*rows)

    def test_no_publication_modification_or_telegram_activation(self):
        rows = reports()
        rows[0]["production_modified"] = True
        with self.assertRaises(ValueError):
            assess(*rows)
        rows = reports()
        rows[0]["no_bookmaker_quote_gate"]["publication_enabled"] = True
        with self.assertRaises(ValueError):
            assess(*rows)
        rows = reports()
        rows[3]["new_events_added_to_prediction_pipeline"] = 1
        with self.assertRaises(ValueError):
            assess(*rows)

    def test_missing_evidence_or_invalid_type_is_error(self):
        rows = reports()
        rows[1] = {}
        with self.assertRaises(ValueError):
            assess(*rows)
        rows = reports()
        rows[0]["historic_matches"] = True
        with self.assertRaises(ValueError):
            assess(*rows)

    def test_reports_are_not_mutated(self):
        rows = reports()
        original = copy.deepcopy(rows)
        assess(*rows)
        self.assertEqual(original, rows)


if __name__ == "__main__":
    unittest.main()
