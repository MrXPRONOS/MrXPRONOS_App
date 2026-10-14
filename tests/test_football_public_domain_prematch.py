"""Offline contract checks of lawful OpenFootball-to-daily routing."""
import unittest
from datetime import datetime, timezone

from scripts.football_public_domain_prematch import generate, historical_index
from scripts.football_match_source_router import route_all

AS_OF = datetime(2025, 2, 10, 10, tzinfo=timezone.utc)


def row(i, *, source="openfootball", day=None, home="Arsenal FC", away=None, score=(2, 1), league="Premier League"):
    return {
        "source": source, "source_id": f"{i:064x}",
        "status": "finished", "match_date": day or f"2025-02-{i:02d}",
        "league": league, "home_team": home,
        "away_team": away or f"Rival {i}", "home_score": score[0], "away_score": score[1],
    }


def fixtures(*, matchday="2025-02-11T18:00:00Z", league="Premier League"):
    return [{
        "fixture_key": "canonical-123", "home_team": "Arsenal", "away_team": "Chelsea",
        "league_labels": [league], "league_verified": True,
        "kickoff_utc": matchday, "status": "prematch",
        "discovered_by": "espn", "sources": {"espn": {"id": "123"}},
        "ambiguous_match": False, "scores_conflict": False,
        "league_conflict": False,
    }]


def history():
    return [row(i) for i in range(1, 8)] + [
        row(i+20, home="Chelsea FC", away=f"Other {i}")
        for i in range(1, 8)
    ]


class PublicDomainPrematchTests(unittest.TestCase):
    def test_realistic_form_attaches_to_discovery_without_fake_native_event_id(self):
        enriched, stats, report = generate(fixtures(), history(), as_of=AS_OF)
        self.assertEqual(report["with_public_domain_goal_features"], 1)
        match = enriched[0]
        self.assertEqual(match["discovered_by"], "espn")
        ref = match["sources"]["openfootball"]
        self.assertTrue(ref["id"].startswith("hist:openfootball:"))
        self.assertIsNone(ref["original_fixture_id"])
        self.assertTrue(ref["not_a_fixture_discovery"])
        routed, health = route_all(enriched, stats, analysis_at=AS_OF)
        self.assertEqual(health["with_goal_family"], 1)
        self.assertIn("goals", routed[0]["ready_families"])
        self.assertIn("btts", routed[0]["ready_families"])
        self.assertIn("totals", routed[0]["ready_families"])
        self.assertIn("corners", routed[0]["needs_more_data"])
        self.assertIn("cards", routed[0]["needs_more_data"])
        self.assertEqual(routed[0]["families"]["goals"]["provider"], "openfootball")
        self.assertTrue(routed[0]["families"]["goals"]["fallback_used"])
        self.assertFalse(routed[0]["prediction_eligible"])
        self.assertFalse(report["production_publishing_allowed"])
        self.assertFalse(report["training_approved"])
        provenance = stats["openfootball"][ref["id"]]
        self.assertEqual(provenance["evidence_grade"], "single_source_unconfirmed_scores")
        self.assertEqual(provenance["source_fixture_id_kind"], "derived_local_not_native")

    def test_cannot_analyze_same_day_or_future_history(self):
        records = history() + [
            row(101, home="Arsenal FC", score=(30, 0), day="2025-02-10"),
            row(102, home="Chelsea FC", score=(30, 0), day="2025-02-11"),
        ]
        enriched, stats, report = generate(fixtures(), records, as_of=AS_OF)
        sid = enriched[0]["sources"]["openfootball"]["id"]
        hist = stats["openfootball"][sid]
        self.assertAlmostEqual(hist["families"]["goals"]["home_goals_for"], 2.)
        self.assertLess(hist["samples"]["home"], 30)
        self.assertNotIn(f"{101:064x}", hist["historical_event_ids"]["home"])

    def test_missing_league_or_conflicting_fixtures_stay_without_stats(self):
        for change in ({"league_labels": []}, {"league_conflict": True}, {"ambiguous_match": True},
                       {"scores_conflict": True}, {"status": "not_prematch"}):
            match = dict(fixtures()[0], **change)
            matches, stats, report = generate([match], history(), as_of=AS_OF)
            self.assertNotIn("openfootball", matches[0]["sources"])
            self.assertFalse(stats["openfootball"])
            self.assertEqual(report["with_public_domain_goal_features"], 0)

    def test_stale_historical_season_must_not_be_reused(self):
        match = fixtures(matchday="2026-10-20T18:00:00Z")
        future_as_of = datetime(2026, 10, 14, tzinfo=timezone.utc)
        data, stats, report = generate(match, history(), as_of=future_as_of)
        self.assertEqual(report["with_public_domain_goal_features"], 0)
        self.assertNotIn("openfootball", data[0]["sources"])

    def test_only_approved_public_domain_source_is_indexed(self):
        bad = row(101, source="licensed_csv")
        teams, report = historical_index([bad])
        self.assertEqual(teams, {})
        self.assertEqual(report["valid_unique_matches"], 0)

    def test_conflicting_same_source_scores_are_quarantined(self):
        a = row(1)
        b = dict(a, source_id=f"{120:064x}", home_score=4)
        teams, report = historical_index([a, b])
        self.assertEqual(teams, {})
        self.assertEqual(report["source_warnings"]["conflicting_duplicate"], 1)

    def test_insufficient_history_is_explicit(self):
        data, stats, report = generate(fixtures(), history()[:4], as_of=AS_OF)
        self.assertEqual(report["with_public_domain_goal_features"], 0)
        self.assertEqual(report["skipped"]["insufficient_or_stale_team_history"], 1)

    def test_already_started_fixture_does_not_get_prematch_form(self):
        data, _, report = generate(fixtures(matchday="2025-02-09T18:00:00Z"), history(), as_of=AS_OF)
        self.assertEqual(report["with_public_domain_goal_features"], 0)


if __name__ == "__main__":
    unittest.main()
