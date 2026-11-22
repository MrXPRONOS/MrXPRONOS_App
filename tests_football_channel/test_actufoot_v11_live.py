"""Offline regression checks for Actu Foot V1.1; no real Telegram/D1 writes."""
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from scripts import actufoot_v11_live as mod

NOW = datetime(2026, 11, 22, 21, 30, tzinfo=timezone.utc)


def row(**override):
    value = {
        "id": "987654",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "home_team_id": "1",
        "away_team_id": "2",
        "home_score": 1,
        "away_score": 0,
        "league_name": "English Premier League",
        "state": "in",
        "event_date": (NOW - timedelta(minutes=55)).isoformat(),
    }
    value.update(override)
    return value


class RoutingTests(unittest.TestCase):
    def test_premier_routes_scores_and_premier_only(self):
        self.assertEqual(mod.topical_roles(row()), {"scores", "premier"})

    def test_champions(self):
        self.assertEqual(mod.topical_roles(row(league_name="UEFA Champions League")),
                         {"scores", "champions"})

    def test_africa_national(self):
        self.assertEqual(mod.topical_roles(row(
            home_team="Togo", away_team="Senegal",
            league_name="Africa Cup of Nations")),
            {"scores", "africa", "national"})

    def test_club_not_national_without_competition(self):
        self.assertNotIn("national", mod.topical_roles(row(home_team="Togo FC")))

    def test_no_mercato_or_debrief_on_scores(self):
        for league in ("English Premier League", "UEFA Champions League", "French Ligue 1"):
            roles = mod.topical_roles(row(league_name=league))
            self.assertNotIn("mercato", roles)
            self.assertNotIn("debrief", roles)
            self.assertNotIn("flash", roles)

    def test_fixtures_select_current_only(self):
        matches = [
            row(),
            row(id="987655", event_date=(NOW - timedelta(hours=9)).isoformat()),
            row(id="987656", state="pre"),
            row(id="987657", home_score=None),
        ]
        with patch.object(mod, "is_relevant", return_value=True):
            selected = mod.select_matches(matches, NOW)
        self.assertEqual([m["id"] for m in selected], ["987654"])

    def test_wrong_team_or_id_never_publishes(self):
        candidate = row()
        self.assertFalse(mod.valid_summary(candidate, row(id="000")))
        self.assertFalse(mod.valid_summary(candidate, row(home_team="Tottenham")))
        self.assertFalse(mod.valid_summary(candidate, row(home_team_id="999")))
        self.assertTrue(mod.valid_summary(candidate, row()))


class EventTests(unittest.TestCase):
    def test_no_historical_flood_on_first_observation(self):
        info = row(minute=68)
        self.assertEqual(mod.derive_events(row(), info, {}, None), [])

    def test_first_kickoff_only_near_start(self):
        events = mod.derive_events(row(), row(minute=3), {}, None)
        self.assertEqual([e[0] for e in events], ["kickoff"])

    def test_goal_from_verified_timeline(self):
        info = row(home_score=2, minute=70)
        old = {"score": "1-0", "phase": "live", "minute": 68}
        goals = [{
            "id": "goal1", "minute_total": 69,
            "home_score": 2, "away_score": 0, "player": "Saka",
        }]
        with patch.object(mod, "extract_goals", return_value=goals):
            events = mod.derive_events(row(), info, {}, old)
        self.assertIn(("goal", "score:987654:2-0", {"player": "Saka"}), events)

    def test_unknown_goal_scorer_is_never_fabricated(self):
        info = row(home_score=2, minute=70)
        old = {"score": "1-0", "phase": "live", "minute": 68}
        with patch.object(mod, "extract_goals", return_value=[]):
            events = mod.derive_events(row(), info, {}, old)
        self.assertIn(("score_update", "score:987654:2-0", {}), events)

    def test_halftime_and_final_each_have_stable_key(self):
        old = {"score": "1-0", "phase": "live", "minute": 45}
        half = mod.derive_events(row(), row(
            status_detail="Halftime", period=1, minute=45), {}, old)
        self.assertTrue(any(e[0] == "halftime" and e[1] == "halftime:987654" for e in half))
        ended = mod.derive_events(row(), row(state="post", minute=90), {}, old)
        self.assertTrue(any(e[0] == "fulltime" and e[1] == "fulltime:987654" for e in ended))

    def test_red_card_needs_actual_event(self):
        old = {"score": "1-0", "phase": "live", "minute": 65}
        cards = [{"type": "red", "id": "rc1", "minute": 66, "player": "A"}]
        with patch.object(mod, "extract_cards", return_value=cards):
            events = mod.derive_events(row(), row(minute=69), {}, old)
        self.assertTrue(any(e[0] == "red" and e[1] == "red:987654:rc1" for e in events))

    def test_scorecard_escapes_html(self):
        text = mod.event_lines(row(home_team="<b>Arsenal</b>"),
                               {"score": "1-0", "phase": "live", "minute": 30}, "board")
        self.assertIn("&lt;b&gt;", text)
        self.assertNotIn('https://', text)

    def test_finished_first_seen_is_not_backfilled(self):
        self.assertEqual(mod.derive_events(row(), row(
            state="post", minute=90), {}, None), [])


class LedgerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.ledger = MagicMock()
        self.ledger.rows.return_value = []
        self.ledger.query.return_value = {"results": []}
        self.ledger.claim.return_value = True
        self.ledger.mark.return_value = True
        self.session = MagicMock()
        self.counters = mod.Counter()
        self.counters["now"] = NOW
        self.counters["daily"] = set()
        self.counters["slots"] = set()
        self.counters["seen"] = set()

    def publish(self, ref="id", role="scores"):
        with patch.object(mod, "bot_api", return_value={"message_id": 900}):
            return mod.publish(self.ledger, self.session, "secret",
                               "@ScoresFootClassements", NOW.date().isoformat(),
                               ref, "texte", self.counters, {"scores"}, role)

    def test_atomic_reservations_precede_telegram_delivery(self):
        self.assertEqual(self.publish(), 900)
        self.assertEqual(self.ledger.claim.call_count, 3)
        self.ledger.mark.assert_called_once()
        self.assertEqual(self.counters["sent"], 1)

    def test_duplicate_same_cycle(self):
        self.assertEqual(self.publish("same"), 900)
        self.assertEqual(self.publish("same"), None)
        self.assertEqual(self.counters["sent"], 1)

    def test_no_rights_no_write(self):
        self.assertIsNone(mod.publish(
            self.ledger, self.session, "secret",
            "@ScoresFootClassements", NOW.date().isoformat(), "id",
            "txt", self.counters, set(), "scores"))
        self.ledger.claim.assert_not_called()

    def test_ambiguous_send_is_quarantined(self):
        with patch.object(mod, "bot_api", side_effect=RuntimeError("TELEGRAM_API_UNCERTAIN_Timeout")):
            self.assertIsNone(mod.publish(
                self.ledger, self.session, "secret",
                "@ScoresFootClassements", NOW.date().isoformat(),
                "ambiguous", "texte", self.counters, {"scores"}, "scores"))
        self.ledger.set_status.assert_called_once_with(
            mod.POST_KIND, "ambiguous", NOW.date().isoformat(), "uncertain")

    def test_failed_state_compare_and_swap_is_blocked(self):
        self.ledger.query.return_value = {"meta": {"changes": 0}}
        with self.assertRaisesRegex(RuntimeError, "STATE_RACE"):
            mod.commit_state(self.ledger, NOW.date().isoformat(), "987654",
                             {"score": "1-0"}, None)

    def test_dry_run_sends_nothing(self):
        with patch.object(mod, "fetch_espn_day", return_value=[row()]):
            with patch.object(mod, "select_matches", return_value=[row()]):
                report = mod.cycle(NOW, dry_run=True, session=self.session,
                                   channels={r: "@SomePublicChannel" for r in mod.EXPECTED_ROLES})
        self.assertEqual(report["mode"], "dry-run")
        self.assertEqual(report["selected"], 1)
        self.ledger.claim.assert_not_called()


if __name__ == "__main__":
    unittest.main()
