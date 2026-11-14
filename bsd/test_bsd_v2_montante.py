import unittest
from datetime import datetime, timedelta, timezone
from bsd.bsd_v2_montante import POLICY, choose, check

NOW = datetime(2026, 11, 14, 8, tzinfo=timezone.utc)


def fixture(name="A", *, odds=1.30, source="bsd_consensus", p=89.0, confidence=91.0,
            kickoff_hours=4, age_minutes=30, key="X2", category="vip"):
    return {
        "id": "bsd:" + name, "source_event_id": name, "source": "bsd",
        "status": "notstarted", "is_finished": False,
        "recommendation_eligible": True, "category": category,
        "event_date": (NOW + timedelta(hours=kickoff_hours)).isoformat(),
        "league": "Ligue test", "home_team": "Equipe " + name, "away_team": "Visiteurs",
        "prediction": {
            "selection_key": key, "market": "double_chance", "label": "Double chance X2",
            "confidence": confidence, "model_probability": confidence,
            "conservative_probability": p, "odds": odds,
            "odds_source": source, "odds_updated_at": (NOW-timedelta(minutes=age_minutes)).isoformat(),
            "estimated_odds": source == "mrxpronos_model", "recommendation_eligible": True,
            "signal_tier": "PREMIUM", "calibration_samples": 150,
        }
    }


def feed(*matches, generated_at=NOW):
    return {"source": "bsd", "model_version": "bsd-v2-isolated",
            "generated_at": generated_at.isoformat(), "matches": list(matches), "performance_tracker": {}}


class DailyMontanteTests(unittest.TestCase):
    def setUp(self):
        self.empty = {"schema": POLICY, "days": {}}

    def test_picks_only_one_high_quality(self):
        r, l = choose(feed(fixture("1"), fixture("2", p=86.0)), self.empty, now=NOW)
        self.assertEqual(r["status"], "selected")
        self.assertEqual(r["selection"]["id"], "bsd:1")
        self.assertEqual(len(l["days"]), 1)

    def test_no_pick_when_only_estimated(self):
        r, _ = choose(feed(fixture(source="mrxpronos_model")), self.empty, now=NOW)
        self.assertEqual(r["status"], "no_pick")

    def test_strictly_above_120(self):
        r, _ = choose(feed(fixture(odds=1.2)), self.empty, now=NOW)
        self.assertEqual(r["status"], "no_pick")

    def test_rejects_outdated_quote(self):
        r, _ = choose(feed(fixture(age_minutes=361)), self.empty, now=NOW)
        self.assertEqual(r["status"], "no_pick")

    def test_rejects_short_lead(self):
        r, _ = choose(feed(fixture(kickoff_hours=.5)), self.empty, now=NOW)
        self.assertEqual(r["status"], "no_pick")

    def test_immutability_across_retries(self):
        _, ledger = choose(feed(fixture("first")), self.empty, now=NOW)
        r, ledger2 = choose(feed(fixture("later", p=95)), ledger, now=NOW + timedelta(hours=1))
        self.assertEqual(r["selection"]["id"], "bsd:first")
        self.assertTrue(r["frozen"])
        self.assertEqual(ledger, ledger2)

    def test_rejects_under45_even_at_high_probability(self):
        r, _ = choose(feed(fixture(key="UNDER_45")), self.empty, now=NOW)
        self.assertEqual(r["status"], "no_pick")

    def test_price_edge_matters(self):
        r, _ = choose(feed(fixture(odds=1.21, p=82)), self.empty, now=NOW)
        self.assertEqual(r["status"], "no_pick")

    def test_historical_drift_veto(self):
        f = feed(fixture())
        f["performance_tracker"] = {"by_selection": {"X2": {"n": 100, "wins": 70, "sum_pred": 89.0}}}
        r, _ = choose(f, self.empty, now=NOW)
        self.assertEqual(r["status"], "no_pick")

    def test_no_silent_pick_from_stale_feed(self):
        r, _ = choose(feed(fixture(), generated_at=NOW - timedelta(hours=13)), self.empty, now=NOW)
        self.assertEqual(r["reason"], "stale_or_missing_feed_timestamp")

    def test_excludes_simple(self):
        r, _ = choose(feed(fixture(category="simple")), self.empty, now=NOW)
        self.assertEqual(r["status"], "no_pick")

    def test_secondary_can_win_if_verified(self):
        m = fixture("ok", source="mrxpronos_model")
        secondary = fixture("ok", odds=1.40, p=88.0)["prediction"]
        secondary["selection_key"] = "1X"
        m["predictions"] = [m["prediction"], secondary]
        r, _ = choose(feed(m), self.empty, now=NOW)
        self.assertEqual(r["selection"]["selection_key"], "1X")

    def test_unknown_missing_timestamp_fails_closed(self):
        m = fixture()
        m["prediction"].pop("odds_updated_at")
        r, _ = choose(feed(m), self.empty, now=NOW)
        self.assertEqual(r["status"], "no_pick")

    def test_today_only(self):
        r, _ = choose(feed(fixture(kickoff_hours=25)), self.empty, now=NOW)
        self.assertEqual(r["status"], "no_pick")


if __name__ == "__main__":
    unittest.main()