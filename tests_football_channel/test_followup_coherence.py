"""Tests unitaires hors réseau : parcours complet d'une rencontre sélectionnée."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "bsd"))
import football_followup as follow
import football_match_lifecycle as lifecycle
import football_channel as channel

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


def fixture(ident, home="Arsenal", away="Chelsea", start=None):
    start = start or NOW + timedelta(hours=2)
    return {
        "id": ident, "event_date": start.isoformat(),
        "home_team": {"id": 1, "name": home, "logo": "https://example.org/home.png"},
        "away_team": {"id": 2, "name": away, "logo": "https://example.org/away.png"},
        "league_name": "Premier League",
        "status": "notstarted",
    }


def event(status, h=0, a=0, minute=0):
    return {
        "id": "espn123", "event_date": (NOW + timedelta(hours=2)).isoformat(),
        "source": "espn", "home_team": "Arsenal", "away_team": "Chelsea",
        "home_logo": "https://example.org/home.png",
        "away_logo": "https://example.org/away.png",
        "home_score": h, "away_score": a, "minute": minute,
        "state": status, "status_detail": "STATUS_" + status.upper(),
    }


class FollowupTests(unittest.TestCase):
    def test_pin_only_valid_prematch(self):
        stored = {}
        before = fixture("bsd123")
        ref = follow.follow(stored, before, NOW)
        self.assertEqual(ref, follow.key(before))
        self.assertEqual(follow.base_events(stored, NOW)[0]["follow_ref"], ref)
        self.assertEqual(len(stored), 1)
        with self.assertRaises(ValueError):
            follow.follow({}, fixture("late", start=NOW-timedelta(minutes=5)), NOW)

    def test_max_two_followed_and_no_third(self):
        stored = {}
        follow.follow(stored, fixture("a"), NOW)
        follow.follow(stored, fixture("b", "PSG", "Marseille"), NOW)
        self.assertFalse(follow.selection_allowed(stored, NOW))
        with self.assertRaises(ValueError):
            follow.follow(stored, fixture("c", "Real Madrid", "Barcelona"), NOW)

    def test_track_strict_orientation_and_kickoff(self):
        stored = {}
        ref = follow.follow(stored, fixture("a"), NOW)
        self.assertEqual(follow.tracked_fixture(fixture("espn", "Arsenal FC", "Chelsea FC"), stored, NOW), ref)
        self.assertIsNone(follow.tracked_fixture(fixture("other", "Chelsea", "Arsenal"), stored, NOW))
        self.assertIsNone(follow.tracked_fixture(fixture("other", start=NOW+timedelta(days=5)), stored, NOW))

    def test_history_round_trip_and_completion(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            h = channel.History(path)
            ref = follow.follow(h.followed, fixture("a"), NOW)
            h.mark("avant_match:a", "avant_match", NOW)
            h.save(NOW)
            restored = channel.History(path)
            self.assertIn(ref, restored.followed)
            self.assertTrue(restored.seen("avant_match:a"))
            follow.completed(restored.followed, ref, NOW+timedelta(hours=4))
            restored.save(NOW+timedelta(hours=4))
            self.assertFalse(follow.base_events(channel.History(path).followed, NOW+timedelta(hours=4)))

    @patch("football_match_lifecycle.fetch_espn_summary", return_value={})
    @patch("football_match_lifecycle.collect_external")
    def test_critical_match_stages_and_final_result(self, collect, _summary):
        stored = {}
        ref = follow.follow(stored, fixture("bsd123"), NOW)
        base = follow.base_events(stored, NOW)
        sent = set()

        collect.return_value = [event("in", 0, 0, 3)]
        begin = lifecycle.lifecycle_signals(base, sent, NOW+timedelta(hours=2,minutes=3), object(),
                                            lambda _: 100, tracked_only=True)
        starts = [s for s in begin if s["kind"] == "kickoff"]
        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0]["follow_ref"], ref)
        sent.add(starts[0]["key"])

        collect.return_value = [event("in", 1, 1, 40)]
        middle = lifecycle.lifecycle_signals(base, sent, NOW+timedelta(hours=2,minutes=40), object(),
                                             lambda _: 100, tracked_only=True)
        score = next(x for x in middle if x["kind"] == "score_update")
        self.assertEqual(score["score"], "1-1")
        sent.add(score["key"])

        collect.return_value = [dict(event("in", 1, 1, 45), status_detail="STATUS_HALFTIME")]
        half = lifecycle.lifecycle_signals(base, sent, NOW+timedelta(hours=2,minutes=50), object(),
                                           lambda _: 100, tracked_only=True)
        halves = [x for x in half if x["kind"] == "mi_temps"]
        self.assertEqual(len(halves), 1)
        sent.add(halves[0]["key"])

        collect.return_value = [event("post", 2, 1, 90)]
        final = lifecycle.lifecycle_signals(base, sent, NOW+timedelta(hours=4), object(),
                                            lambda _: 100, tracked_only=True)
        finales = [x for x in final if x["kind"] == "resultat_final"]
        self.assertEqual(len(finales), 1)
        post = channel.followed_final_publication(finales[0])
        self.assertEqual(post.card["scores"], (2, 1))
        self.assertNotIn("2 – 1", post.text)
        self.assertIn("Fin du match suivi", post.text)
        sent.add(post.key)
        again = lifecycle.lifecycle_signals(base, sent, NOW+timedelta(hours=4), object(),
                                            lambda _: 100, tracked_only=True)
        self.assertFalse([x for x in again if x["kind"] == "resultat_final"])

    @patch("football_match_lifecycle.collect_external")
    def test_unselected_live_match_not_published(self, collect):
        collect.return_value = [event("in", 2, 2, 65)]
        self.assertEqual(lifecycle.lifecycle_signals([], set(), NOW, object(),
                                                     lambda _: 100, tracked_only=True), [])
        stored = {}
        follow.follow(stored, fixture("a"), NOW)
        other = dict(event("in", 1, 0, 40), home_team="Liverpool", away_team="Everton")
        collect.return_value = [other]
        self.assertFalse(lifecycle.lifecycle_signals(follow.base_events(stored, NOW), set(), NOW,
                                                     object(), lambda _: 100, tracked_only=True))


if __name__ == "__main__":
    unittest.main()
