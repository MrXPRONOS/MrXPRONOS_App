"""Tests: strict last completed H2H must win the predicted BTTS side."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from bsd_v2_core import V2History, fixture_datetime, predict_v2, score_matrix, markets_from_matrix
from bsd_v2_btts_h2h import (
    btts_h2h_decision, filter_candidates_by_last_h2h, last_completed_h2h,
)


class LastH2HBTTSRuleTests(unittest.TestCase):
    def setUp(self):
        self.at = datetime(2026, 10, 20, 18, tzinfo=timezone.utc)
        self.event = {
            "id": 1000, "event_date": self.at.isoformat(), "status": "notstarted",
            "home_team_id": 11, "away_team_id": 22, "league_id": 9,
        }

    def meeting(self, ident, days_ago, home=11, away=22, score=(1, 1)):
        return {
            "id": ident,
            "event_date": (self.at - timedelta(days=days_ago)).isoformat(),
            "status": "finished", "home_team_id": home, "away_team_id": away,
            "home_score": score[0], "away_score": score[1], "league_id": 9,
        }

    def test_latest_not_oldest_and_reversed_venue(self):
        # Old result YES, newest result NO even with reversed home/away.
        games = [
            self.meeting(1, 90, score=(2, 2)),
            self.meeting(2, 8, home=22, away=11, score=(1, 0)),
            self.meeting(3, 3, home=11, away=33, score=(3, 3)),
        ]
        index = V2History(games)
        most_recent = last_completed_h2h(self.event, index)
        self.assertEqual(most_recent["event_id"], 2)
        self.assertFalse(most_recent["btts_yes"])
        self.assertEqual(btts_h2h_decision(self.event, index, "BTTS_YES")[:2],
                         (False, "btts_last_h2h_lost"))
        self.assertEqual(btts_h2h_decision(self.event, index, "BTTS_NO")[:2],
                         (True, "btts_last_h2h_won"))

    def test_no_h2h_rejects_both_btts_but_keeps_other_markets(self):
        index = V2History([self.meeting(1, 30, home=11, away=33)])
        candidates = markets_from_matrix(score_matrix(1.2, 1.4))
        audit = []
        allowed, previous = filter_candidates_by_last_h2h(
            self.event, index, candidates, audit)
        self.assertIsNone(previous)
        self.assertTrue(all(c.family != "btts" for c in allowed))
        self.assertEqual({a["key"] for a in audit}, {"BTTS_YES", "BTTS_NO"})
        self.assertTrue(all(a["result"] == "btts_last_h2h_missing" for a in audit))
        self.assertEqual([c.key for c in allowed], [c.key for c in candidates
                                                     if c.family != "btts"])

    def test_last_h2h_yes_keeps_only_btts_yes(self):
        index = V2History([self.meeting(1, 3, score=(1, 3))])
        original = markets_from_matrix(score_matrix(1.5, 1.2))
        kept, previous = filter_candidates_by_last_h2h(self.event, index, original)
        self.assertTrue(previous["btts_yes"])
        self.assertIn("BTTS_YES", [c.key for c in kept])
        self.assertNotIn("BTTS_NO", [c.key for c in kept])

    def test_future_h2h_and_current_match_do_not_leak(self):
        old = self.meeting(1, 20, score=(0, 0))
        future = dict(self.event, id=2, status="finished", home_score=7, away_score=7)
        later = self.meeting(3, -1, score=(2, 2))
        index = V2History([old, future, later])
        result = last_completed_h2h(self.event, index)
        self.assertEqual(result["event_id"], old["id"])
        self.assertFalse(result["btts_yes"])

    def test_settlement_delay_prevents_early_h2h(self):
        earlier = self.meeting(1, 10, score=(1, 1))
        recently_finished = dict(
            self.meeting(2, 1, score=(0, 0)),
            event_date=(self.at - timedelta(hours=2)).isoformat()
        )
        result = last_completed_h2h(self.event, V2History([earlier, recently_finished]))
        self.assertEqual(result["event_id"], 1)
        self.assertTrue(result["btts_yes"])

    def test_find_beyond_last_twelve_team_matches(self):
        prior = self.meeting(1, 300, home=22, away=11, score=(0, 3))
        other = [self.meeting(100+i, 120-i, home=11, away=99+i,
                              score=(i%3, 0)) for i in range(35)]
        result = last_completed_h2h(self.event, V2History([prior]+other))
        self.assertEqual(result["event_id"], 1)
        self.assertFalse(result["btts_yes"])

    def test_predict_v2_market_audit_mentions_last_h2h_rule(self):
        # Enough team history for a market prediction, but no team-11/team-22 H2H.
        games = []
        for i in range(30):
            games.extend([
                self.meeting(2000+i, 100-i, home=11, away=33,
                             score=(2, 0)),
                self.meeting(3000+i, 100-i, home=44, away=22,
                             score=(1, 2)),
            ])
        audit = []
        prediction, reason = predict_v2(self.event, V2History(games),
                                         market_audit=audit)
        self.assertTrue(any(a.get("key") == "BTTS_YES" and
                            a.get("result") == "btts_last_h2h_missing"
                            for a in audit))
        self.assertTrue(any(a.get("key") == "BTTS_NO" and
                            a.get("result") == "btts_last_h2h_missing"
                            for a in audit))
        if prediction is not None:
            self.assertNotIn(prediction["prediction"]["key"], ("BTTS_YES", "BTTS_NO"))


if __name__ == "__main__":
    unittest.main()
