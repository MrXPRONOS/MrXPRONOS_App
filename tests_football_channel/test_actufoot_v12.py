"""Actu Foot V1.2: fully offline, no Telegram, D1, or ESPN network calls."""
import json
import unittest
from collections import Counter
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from scripts import actufoot_v12 as v12

NOW = datetime(2026, 11, 23, 22, 12, tzinfo=timezone.utc)


def fixture(**changes):
    row = {"id": "54321", "home_team": "River Plate", "away_team": "Lanús",
           "home_team_id": "11", "away_team_id": "12", "home_score": 3,
           "away_score": 1, "state": "post",
           "league_name": "Liga Profesional Argentina",
           "event_date": (NOW - timedelta(minutes=120)).isoformat()}
    row.update(changes)
    return row


def group(team_count=6, group_name="Table principale"):
    entries = []
    for i in range(team_count):
        entries.append({
            "team": {"id": str(i + 1), "displayName": f"Club {i + 1}"},
            "stats": [
                {"name": "rank", "value": i + 1},
                {"name": "points", "value": 40 - i * 2},
                {"name": "gamesPlayed", "value": 19},
                {"name": "pointDifferential", "value": 12 - i},
            ],
        })
    return {"name": group_name, "standings": {"entries": entries}}


def payload(*groups, season=2026):
    return {"season": {"year": season, "displayName": "2026-27"},
            "children": list(groups)}


class DebriefTests(unittest.TestCase):
    def setUp(self):
        self.row = fixture()
        self.info = fixture()

    def test_render_verified_final_and_goals_and_cards(self):
        goals = [{"id": "g1", "minute_text": "90+3", "player": "Un buteur",
                  "team": "River Plate", "home_score": 3, "away_score": 1}]
        cards = [{"id": "r1", "type": "red", "minute": 71, "player": "Défenseur"}]
        with patch.object(v12, "extract_goals", return_value=goals), \
             patch.object(v12, "extract_cards", return_value=cards), \
             patch.object(v12, "extract_shootout_kicks", return_value=[]):
            text = v12.debrief_message(self.row, self.info, {})
        self.assertTrue(text.startswith("<b>🏁 River Plate 3–1 Lanús</b>"))
        self.assertIn("Liga Profesional Argentina", text)
        self.assertIn("⚽ 90+3' · Un buteur · River Plate", text)
        self.assertIn("🟥 Défenseur · 71", text)
        self.assertIn("<blockquote>", text)
        self.assertTrue(text.endswith("<i>📰 Source : ESPN</i>"))
        self.assertNotIn("https://", text)

    def test_stats_and_shootout_only_when_verified(self):
        info = fixture(home_shootout_score=5, away_shootout_score=4)
        with patch.object(v12, "extract_goals", return_value=[]), \
             patch.object(v12, "extract_cards", return_value=[]), \
             patch.object(v12, "extract_shootout_kicks", return_value=[]), \
             patch.object(v12, "extract_team_stats", return_value={
                 "home": {"possession": "58%", "corners": 7},
                 "away": {"possession": "42%", "corners": 1},
             }):
            output = v12.debrief_message(self.row, info, {})
        self.assertIn("Possession : 58% – 42%", output)
        self.assertIn("Corners : 7 – 1", output)
        self.assertIn("Tirs au but : 5–4", output)
        self.assertNotIn("Tirs cadrés", output)

    def test_no_debrief_while_live_or_wrong_teams(self):
        self.assertIsNone(v12.debrief_message(self.row, fixture(state="in"), {}))
        self.assertIsNone(v12.debrief_message(
            self.row, fixture(away_team="Not Lanus"), {}))

    def test_escaping_and_no_fabricated_scorer(self):
        with patch.object(v12, "extract_goals", return_value=[
            {"id": "1", "minute_text": "82", "player": "", "team": "<FC>"}
        ]), patch.object(v12, "extract_cards", return_value=[]), \
             patch.object(v12, "extract_shootout_kicks", return_value=[]):
            output = v12.debrief_message(
                fixture(home_team="<River>"), fixture(home_team="<River>"), {})
        self.assertIn("&lt;River&gt;", output)
        self.assertIn("Buteur non indiqué", output)
        self.assertIn("&lt;FC&gt;", output)
        self.assertNotIn("<FC>", output)

    def test_shootout_kick_is_not_double_counted_as_goal(self):
        with patch.object(v12, "extract_goals", return_value=[
            {"id": "shoot1", "minute": 120, "player": "FakeGoal"}
        ]), patch.object(v12, "extract_shootout_kicks", return_value=[
            {"id": "shoot1", "outcome": "made"}
        ]), patch.object(v12, "extract_cards", return_value=[]):
            output = v12.debrief_message(self.row, self.info, {})
        self.assertNotIn("FakeGoal", output)

    def test_score_validation_fails_closed(self):
        self.assertEqual(v12.verified_score({"home_score": True, "away_score": 1}), "")
        self.assertEqual(v12.verified_score({"home_score": 1, "away_score": None}), "")
        self.assertEqual(v12.verified_score({"home_score": 3, "away_score": 1}), "3–1")


class StandingsTests(unittest.TestCase):
    def test_verified_group_has_real_rank_points_matches_and_difference(self):
        parsed = v12.standings_groups(payload(group()), 2026)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["entries"][0]["rank"], 1)
        self.assertEqual(parsed[0]["entries"][0]["pts"], 40)
        self.assertEqual(parsed[0]["entries"][0]["played"], 19)
        self.assertEqual(parsed[0]["entries"][0]["gd"], 12)

    def test_stale_season_is_rejected(self):
        self.assertEqual(v12.standings_groups(payload(group(), season=2025), 2026), [])
        self.assertEqual(v12.standings_groups({"children": [group()]}, 2026), [])

    def test_missing_statistics_never_become_zero(self):
        table = group()
        for e in table["standings"]["entries"]:
            e["stats"] = [x for x in e["stats"] if x["name"] != "points"]
        self.assertEqual(v12.standings_groups(payload(table), 2026), [])

    def test_groups_are_not_concatenated_into_fake_single_table(self):
        result = v12.standings_groups(payload(group(group_name="Groupe A"),
                                               group(group_name="Groupe B")), 2026)
        self.assertEqual(len(result), 2)
        self.assertEqual([r["name"] for r in result], ["Groupe A", "Groupe B"])

    def test_duplicate_team_or_rank_rejects_bad_table(self):
        table = group()
        table["standings"]["entries"][1]["team"]["id"] = "1"
        self.assertEqual(v12.standings_groups(payload(table), 2026), [])

    def test_render_table_trends_only_when_previous_rank_known(self):
        leagues = {"eng.1": v12.standings_groups(payload(group()), 2026)}
        prior = {"eng.1": {"1": 2, "2": 1}}
        message, snapshot = v12.standings_message(leagues, prior, NOW)
        self.assertIn("Premier League", message)
        self.assertIn("Club 1 · 40 pts · 19 MJ · diff. +12 ↑1", message)
        self.assertIn("Club 2 · 38 pts · 19 MJ · diff. +11 ↓1", message)
        self.assertIn("📰 Source : ESPN", message)
        self.assertEqual(snapshot["eng.1"]["1"], 1)
        blank, _ = v12.standings_message(leagues, {}, NOW)
        self.assertNotIn("↑1", blank)

    def test_absent_tables_never_trigger_publication(self):
        self.assertEqual(v12.standings_message({}, {}, NOW), (None, {}))

    def test_api_refuses_unapproved_league(self):
        session = MagicMock()
        with self.assertRaises(ValueError):
            v12.fetch_standings(session, "../bad", 2026)
        session.get.assert_not_called()

    def test_api_requires_a_matching_season(self):
        session = MagicMock()
        session.get.return_value.json.return_value = payload(group(), season=2025)
        self.assertEqual(v12.fetch_standings(session, "eng.1", 2026), [])
        url = session.get.call_args.args[0]
        self.assertEqual(url, v12.STANDINGS_URL.format(code="eng.1"))


class CycleTests(unittest.TestCase):
    def setUp(self):
        self.ledger = MagicMock()
        self.ledger.rows.return_value = []
        self.ledger.query.return_value = {"results": []}
        self.session = MagicMock()
        self.channels = {role: "@" + role.capitalize() + "Channel"
                         for role in v12.live.EXPECTED_ROLES}

    def test_dry_run_does_not_write_to_d1_or_telegram(self):
        with patch.object(v12.live, "fetch_espn_day", return_value=[fixture()]), \
             patch.object(v12.live, "select_matches", return_value=[fixture()]), \
             patch.object(v12.live, "fetch_espn_summary", return_value={}), \
             patch.object(v12.live, "parse_espn_summary_match", return_value=fixture()):
            out = v12.cycle(NOW, mode="debrief", dry_run=True,
                            session=self.session, ledger=self.ledger,
                            channels=self.channels)
        self.assertEqual(out["debrief_candidates"], 1)
        self.ledger.claim.assert_not_called()
        self.ledger.query.assert_not_called()

    def test_debrief_requires_real_v11_board_observation(self):
        with patch.object(v12.live, "fetch_espn_day", return_value=[fixture()]), \
             patch.object(v12.live, "select_matches", return_value=[fixture()]), \
             patch.object(v12.live, "verified_roles", return_value={"debrief"}), \
             patch.object(v12.live, "state_row", return_value=({"phase": "final"}, "")), \
             patch.object(v12.live, "fetch_espn_summary") as fetch_summary:
            result = v12.cycle(NOW, mode="debrief", session=self.session,
                               ledger=self.ledger, token="secret", channels=self.channels)
        self.assertEqual(result["debrief_sent"], 0)
        self.assertEqual(result["skipped_unverified"], 1)
        fetch_summary.assert_not_called()

    def test_debrief_publishes_once_for_observed_match(self):
        with patch.object(v12.live, "fetch_espn_day", return_value=[fixture()]), \
             patch.object(v12.live, "select_matches", return_value=[fixture()]), \
             patch.object(v12.live, "verified_roles", return_value={"debrief"}), \
             patch.object(v12.live, "state_row", return_value=({"board_id": 22}, "")), \
             patch.object(v12.live, "fetch_espn_summary", return_value={}), \
             patch.object(v12.live, "parse_espn_summary_match", return_value=fixture()), \
             patch.object(v12.live, "publish", return_value=88) as publish:
            result = v12.cycle(NOW, mode="debrief", session=self.session,
                               ledger=self.ledger, token="secret", channels=self.channels)
        self.assertEqual(result["debrief_sent"], 1)
        self.assertIn("v12:debrief:54321", publish.call_args.args[5])
        self.assertIn("🏁 River Plate", publish.call_args.args[6])

    def test_cross_day_duplicate_is_rejected_before_publish(self):
        self.ledger.query.return_value = {"results": [{"ref_id": "existing"}]}
        with patch.object(v12.live, "fetch_espn_day", return_value=[fixture()]), \
             patch.object(v12.live, "select_matches", return_value=[fixture()]), \
             patch.object(v12.live, "verified_roles", return_value={"debrief"}), \
             patch.object(v12.live, "publish") as publish:
            result = v12.cycle(NOW, mode="debrief", session=self.session,
                               ledger=self.ledger, token="secret", channels=self.channels)
        self.assertEqual(result["skipped_existing"], 1)
        publish.assert_not_called()

    def test_rights_must_be_verified_before_d1_write(self):
        with patch.object(v12.live, "verified_roles", return_value=set()):
            with self.assertRaisesRegex(RuntimeError, "RIGHTS_NOT_VERIFIED"):
                v12.cycle(NOW, mode="standings", session=self.session,
                          ledger=self.ledger, token="secret", channels=self.channels)
        self.ledger.query.assert_not_called()

    def test_standings_quota_receipt_and_snapshot(self):
        with patch.object(v12.live, "verified_roles", return_value={"scores"}), \
             patch.object(v12, "fetch_standings", return_value=v12.standings_groups(
                 payload(group()), 2026)), \
             patch.object(v12.live, "publish", return_value=77) as publish, \
             patch.object(v12, "_store_ranks") as store:
            result = v12.cycle(NOW, mode="standings", session=self.session,
                               ledger=self.ledger, token="secret", channels=self.channels)
        self.assertEqual(result["standings_leagues"], len(v12.LEAGUES))
        self.assertEqual(result["standings_sent"], 1)
        self.assertIn(":v12:standings:2026-11-23", publish.call_args.args[5])
        store.assert_called_once()

    def test_same_day_ranking_receipt_prevents_duplicate_and_new_fetch(self):
        self.ledger.query.return_value = {"results": [{"ref_id": "sent today"}]}
        with patch.object(v12.live, "verified_roles", return_value={"scores"}), \
             patch.object(v12, "fetch_standings") as fetch, \
             patch.object(v12.live, "publish") as publish:
            out = v12.cycle(NOW, mode="standings",
                            session=self.session, ledger=self.ledger,
                            token="secret", channels=self.channels)
        self.assertEqual(out["skipped_existing"], 1)
        fetch.assert_not_called()
        publish.assert_not_called()

    def test_missing_real_data_prevents_sending_rankings(self):
        with patch.object(v12.live, "verified_roles", return_value={"scores"}), \
             patch.object(v12, "fetch_standings", return_value=[]), \
             patch.object(v12.live, "publish") as publish:
            result = v12.cycle(NOW, mode="standings", session=self.session,
                               ledger=self.ledger, token="secret", channels=self.channels)
        self.assertEqual(result["standings_sent"], 0)
        publish.assert_not_called()

    def test_standings_only_runs_at_scheduled_hour_in_all_mode(self):
        t = NOW.replace(hour=19)
        with patch.object(v12.live, "fetch_espn_day", return_value=[]), \
             patch.object(v12.live, "select_matches", return_value=[]), \
             patch.object(v12, "fetch_standings") as fetch:
            result = v12.cycle(t, mode="all", dry_run=True,
                               session=self.session, channels=self.channels)
        self.assertEqual(result["standings_leagues"], 0)
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
