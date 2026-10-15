"""No-network/no-secret tests of the optional private BSD form provider."""
import unittest
from datetime import datetime, timedelta, timezone

from scripts.football_bsd_private_history import attach, build_private_index
from scripts.football_match_source_router import route_all

AS_OF = datetime(2025, 2, 12, 12, tzinfo=timezone.utc)


def hist(i, team=101, opp=300, league=39, *, kickoff=None, home_name=None, score=(2, 1)):
    when = kickoff or f"2025-02-{i+1:02d}T10:00:00Z"
    return {"id": 1000+i+team, "status": "finished", "event_date": when,
            "league_id": league, "league_name": "Premier League",
            "home_team_id": team, "away_team_id": opp+i,
            "home_team": {"id": team, "name": home_name or ("Arsenal FC" if team == 101 else "Chelsea FC")},
            "away_team": {"id": opp+i, "name": f"Opposition-{opp+i}"},
            "home_score": score[0], "away_score": score[1]}


def archive():
    return [hist(i, team=101, opp=300) for i in range(7)] + [
        hist(i, team=202, opp=500) for i in range(7)
    ]


def match(*, native=False):
    refs = {"bsd": {"id": "999"}} if native else {"espn": {"id": "E1"}}
    return {"fixture_key": "fixture-abc",
            "home_team": "Arsenal", "away_team": "Chelsea",
            "kickoff_utc": "2025-02-13T18:00:00Z", "league_labels": ["Premier League"],
            "league_verified": True, "status": "prematch", "sources": refs,
            "discovered_by": "bsd" if native else "espn",
            "ambiguous_match": False, "scores_conflict": False, "league_conflict": False}


def current():
    return [{"id": 999, "event_date": "2025-02-13T18:00:00Z",
             "home_team_id": 101, "away_team_id": 202, "league_id": 39,
             "home_team": {"id": 101, "name": "Arsenal FC"},
             "away_team": {"id": 202, "name": "Chelsea FC"},
             "status": "notstarted"}]


class BSDPrivateFormTests(unittest.TestCase):
    def test_permission_gate_never_reveals_private_history(self):
        games, stats, report = attach([match()], archive(), as_of=AS_OF)
        self.assertEqual(report["status"], "permission_required")
        self.assertIsNone(report["historic_match_count"])
        self.assertEqual(games[0]["sources"], match()["sources"])
        self.assertEqual(stats["bsd"], {})
        self.assertEqual(stats["bsd_history"], {})

    def test_cross_provider_recovers_only_unambiguous_bsd_team_ids(self):
        games, stats, report = attach([match()], archive(), as_of=AS_OF, explicitly_authorized=True)
        self.assertEqual(report["cross_provider_history_count"], 1)
        ref = games[0]["sources"]["bsd_history"]
        self.assertTrue(ref["id"].startswith("hist:bsd:"))
        self.assertIsNone(ref["original_fixture_id"])
        self.assertTrue(ref["not_a_fixture_discovery"])
        self.assertEqual(games[0]["sources"]["espn"]["id"], "E1")
        self.assertEqual(games[0]["discovered_by"], "espn")
        decision, state = route_all(games, stats, analysis_at=AS_OF)
        self.assertEqual(state["with_goal_family"], 1)
        self.assertEqual(decision[0]["families"]["goals"]["provider"], "bsd_history")
        self.assertIn("btts", decision[0]["ready_families"])
        self.assertIn("totals", decision[0]["ready_families"])
        self.assertIn("corners", decision[0]["needs_more_data"])
        self.assertFalse(decision[0]["prediction_eligible"])
        self.assertFalse(report["production_modified"])
        self.assertFalse(report["secret_archive_exposed"])

    def test_original_bsd_fixture_ids_never_replaced(self):
        games, stats, report = attach([match(native=True)], archive(), current(),
                                     as_of=AS_OF, explicitly_authorized=True)
        self.assertEqual(report["native_fixture_count"], 1)
        self.assertNotIn("bsd_history", games[0]["sources"])
        self.assertEqual(games[0]["sources"]["bsd"]["id"], "999")
        self.assertIn("999", stats["bsd"])
        choice, _ = route_all(games, stats, analysis_at=AS_OF)
        self.assertEqual(choice[0]["families"]["goals"]["provider"], "bsd")

    def test_unverified_native_fixture_id_does_not_force_other_team(self):
        games, stats, report = attach([match(native=True)], archive(), [],
                                     as_of=AS_OF, explicitly_authorized=True)
        self.assertEqual(report["attached_fixtures"], 0)
        self.assertEqual(report["rejection_summary"]["unverified_bsd_fixture_id"], 1)

    def test_wrong_native_team_or_kickoff_never_join(self):
        broken = current()
        broken[0]["away_team"]["name"] = "Manchester City"
        games, _, report = attach([match(native=True)], archive(), broken,
                                  as_of=AS_OF, explicitly_authorized=True)
        self.assertEqual(report["attached_fixtures"], 0)
        self.assertEqual(report["rejection_summary"]["bsd_fixture_team_mismatch"], 1)

    def test_multiple_ids_same_name_and_league_is_ambiguous(self):
        ambiguous = archive() + [hist(i, team=555, opp=800, home_name="Arsenal FC") for i in range(7)]
        games, _, report = attach([match()], ambiguous,
                                  as_of=AS_OF, explicitly_authorized=True)
        self.assertEqual(report["attached_fixtures"], 0)
        self.assertEqual(report["rejection_summary"]["unresolved_team_identity"], 1)

    def test_finished_but_not_settled_4_hours_ago_is_not_in_history(self):
        historic = archive()
        # A recent result cannot help reach the minimum before its settlement delay.
        # Remove three Arsenal games, add one recent unresolved game.
        historic = [x for x in historic if x["home_team_id"] != 101 or x["event_date"] < "2025-02-05"]
        historic.append(hist(80, team=101, opp=900, kickoff="2025-02-12T11:00:00Z"))
        games, _, report = attach([match()], historic, as_of=AS_OF, explicitly_authorized=True)
        self.assertEqual(report["attached_fixtures"], 0)
        self.assertEqual(report["rejection_summary"]["insufficient_or_stale_bsd_history"], 1)

    def test_archive_scores_must_be_finished(self):
        bad = hist(1, team=101)
        bad["status"] = "live"
        index, names, quality = build_private_index([bad])
        self.assertEqual(quality["valid_finished_records"], 0)
        self.assertEqual(index, {})


if __name__ == "__main__":
    unittest.main()
