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
