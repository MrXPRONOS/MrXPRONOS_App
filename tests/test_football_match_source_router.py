"""Offline router tests: provenance, missingness, no lookahead, correct fallback."""
import unittest
from datetime import datetime, timedelta, timezone
from scripts.football_match_source_router import route_fixture as _route_fixture, route_all as _route_all

FIXTURE = {
    "fixture_key": "2026-10-14|arsenal|chelsea",
    "kickoff_utc": "2026-10-14T18:00:00Z",
    "home_team": "Arsenal", "away_team": "Chelsea",
    "sources": {
        "espn": {"id": "E45"},
        "sportscore": {"id": "S67"},
        "bsd": {"id": "B88"},
    },
    "discovered_by": "espn", "ambiguous_match": False,
    "league_conflict": False, "scores_conflict": False,
}

AS_OF = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


def route_fixture(fixture, stats, **kwargs):
    return _route_fixture(fixture, stats, analysis_at=AS_OF, **kwargs)


def route_all(fixtures, stats, **kwargs):
    return _route_all(fixtures, stats, analysis_at=AS_OF, **kwargs)

FAMILIES = {
    "goals": {"home_goals_for": 2.0, "home_goals_against": 1.0, "away_goals_for": 0.9, "away_goals_against": 1.5},
    "btts": {"home_btts_rate": .6, "away_btts_rate": .7},
    "totals": {"home_over_2_5_rate": .5, "away_over_2_5_rate": .4},
    "corners": {"home_corners_avg": 5, "away_corners_avg": 4},
    "cards": {"home_yellow_cards_avg": 3, "away_yellow_cards_avg": 2},
}


def source(provider, sid, family="goals", sample=12, *, observed="2026-10-14T10:00:00Z", until="2026-10-13T22:00:00Z", **changes):
    obj = {
        "provider_fixture_id": sid, "phase": "prematch",
        "observed_at": observed, "history_until": until,
        "samples": {"home": sample, "away": sample},
        "families": {family: dict(FAMILIES[family])},
        "verified_identity": True, "license_ok": True,
    }
    obj.update(changes)
    return obj


class RouterTest(unittest.TestCase):
    def test_prefer_source_with_stats_not_first_listed(self):
        evidence = {"espn": {}, "sportscore": {"S67": source("sportscore", "S67")}, "bsd": {}}
        chosen = route_fixture(FIXTURE, evidence)
        self.assertEqual(chosen["families"]["goals"]["provider"], "sportscore")
        self.assertTrue(chosen["families"]["goals"]["fallback_used"])
        self.assertFalse(chosen["prediction_eligible"])

    def test_no_empty_stats_as_zeros(self):
        got = route_fixture(FIXTURE, {})
        self.assertEqual(got["ready_families"], [])
        self.assertIn("goals", got["needs_more_data"])
        self.assertIsNone(got["preferred_overall_source"])

    def test_select_different_providers_per_family(self):
        data = {
            "espn": {"E45": source("espn", "E45", family="corners")},
            "bsd": {"B88": source("bsd", "B88", family="goals")},
        }
        got = route_fixture(FIXTURE, data)
        self.assertEqual(got["families"]["goals"]["provider"], "bsd")
        self.assertEqual(got["families"]["corners"]["provider"], "espn")
        self.assertEqual(got["families"]["cards"]["status"], "missing")
        self.assertFalse(got["prediction_eligible"])

    def test_reject_future_outcomes_disguised_as_stats(self):
        data = {"bsd": {"B88": source("bsd", "B88", observed="2026-10-14T19:00:00Z")}}
        got = route_fixture(FIXTURE, data)
        self.assertEqual(got["families"]["goals"]["rejected_providers"]["bsd"], "future_information")

    def test_reject_snapshot_not_yet_available_as_of_analysis(self):
        data = {"bsd": {"B88": source("bsd", "B88", observed="2026-10-14T14:00:00Z")}}
        got = route_fixture(FIXTURE, data)
        self.assertEqual(got["families"]["goals"]["rejected_providers"]["bsd"], "snapshot_not_yet_available")

    def test_kickoff_already_started_must_stop_prematch(self):
        f = dict(FIXTURE, kickoff_utc="2026-10-14T11:00:00Z")
        got = route_fixture(f, {"bsd": {"B88": source("bsd", "B88")}})
        self.assertEqual(got["families"]["goals"]["status"], "rejected")

    def test_reject_history_after_collection(self):
        data = {"bsd": {"B88": source("bsd", "B88", until="2026-10-14T12:00:00Z")}}
        got = route_fixture(FIXTURE, data)
        self.assertEqual(got["families"]["goals"]["rejected_providers"]["bsd"], "history_after_collection")

    def test_reject_fake_probabilities_and_nonfinite(self):
        data = {"bsd": {"B88": source("bsd", "B88", family="btts", families={"btts": {"home_btts_rate": 1.5, "away_btts_rate": .7}})}}
        got = route_fixture(FIXTURE, data)
        self.assertEqual(got["families"]["btts"]["status"], "missing")

    def test_protect_stable_provider_identity(self):
        data = {"bsd": {"B88": source("bsd", "wrong-id")}}
        got = route_fixture(FIXTURE, data)
        self.assertEqual(got["families"]["goals"]["rejected_providers"]["bsd"], "fixture_id_mismatch")

    def test_reject_invalid_licenses(self):
        data = {"bsd": {"B88": source("bsd", "B88", license_ok=False)}}
        got = route_fixture(FIXTURE, data)
        self.assertEqual(got["families"]["goals"]["rejected_providers"]["bsd"], "unapproved_data_usage")

    def test_reject_unverified_matches(self):
        data = {"bsd": {"B88": source("bsd", "B88", verified_identity=False)}}
        got = route_fixture(FIXTURE, data)
        self.assertEqual(got["families"]["goals"]["rejected_providers"]["bsd"], "unverified_identity")

    def test_ambiguous_fixture_never_gets_statistics(self):
        f = dict(FIXTURE, ambiguous_match=True)
        got = route_fixture(f, {"bsd": {"B88": source("bsd", "B88")}})
        self.assertEqual(got["families"]["goals"]["status"], "rejected")

    def test_request_all_sources_zero_probability_of_publication(self):
        result, report = route_all([FIXTURE], {"espn": {"E45": source("espn", "E45")}})
        self.assertEqual(report["with_goal_family"], 1)
        self.assertEqual(report["model_enabled"], False)
        self.assertEqual(report["telegram_posts"], 0)
        self.assertEqual(result[0]["families"]["goals"]["provider"], "espn")

    def test_invalid_phase_must_fail(self):
        got = route_fixture(FIXTURE, {"bsd": {"B88": source("bsd", "B88", phase="live")}})
        self.assertEqual(got["families"]["goals"]["rejected_providers"]["bsd"], "not_prematch")


if __name__ == "__main__":
    unittest.main()
