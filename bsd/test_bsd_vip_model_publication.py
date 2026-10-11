"""End-to-end regression of VIP with the two allowed odds sources."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from bsd_v2_publish import assemble


class VIPModelPublicationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 11, 9, tzinfo=timezone.utc)
        self.fixture = {
            "id": 7342,
            "event_date": (self.now + timedelta(hours=6)).isoformat(),
            "status": "notstarted",
            "home_team_id": 11,
            "away_team_id": 22,
            "home_team": "Club A",
            "away_team": "Club B",
            "league_id": 50,
            "league_name": "Test League",
        }
        self.selection = {
            "key": "1X",
            "name": "Double chance 1X",
            "market": "double_chance",
            "outcome": "1X",
            "line": None,
            "internal_market_code": "DC_1X_FT",
            "probability": .825,
            "conservative_probability": .815,
            "fair_odds": round(1 / .825, 4),
            "bookmaker_odds": None,
            "calibration_samples": 100,
        }
        self.football = {
            "id": "bsd:7342",
            "source": "bsd",
            "home_team_id": 11,
            "away_team_id": 22,
            "league_id": 50,
            "category": "vip",
            "model_version": "bsd-v2-isolated",
            "model_audit": {
                "league_samples": 100,
                "home_recent_matches": 12,
                "away_recent_matches": 12,
                "home_venue_matches": 6,
                "away_venue_matches": 6,
            },
            "prediction": self.selection,
            "ranked_candidates": [],
        }

    def publish(self, quotes):
        with patch("bsd_v2_publish.predict_v2", return_value=(self.football, "ok")):
            return assemble(
                {}, [self.fixture], [], now=self.now, calibration=None,
                policy=None, rho=0,
                odds_fetcher=lambda *args: (quotes, {}),
                max_odds_requests=1,
            )

    def test_qualified_vip_uses_model_when_bsd_missing(self):
        out = self.publish({})
        self.assertEqual(len(out["matches"]), 1)
        match = out["matches"][0]
        self.assertEqual(match["category"], "vip")
        self.assertTrue(match["recommendation_eligible"])
        self.assertEqual(match["signal_tier"], "INDICATIF")
        self.assertEqual(match["prediction"]["odds_source"], "mrxpronos_model")
        self.assertTrue(match["prediction"]["estimated_odds"])
        self.assertGreaterEqual(match["prediction"]["odds"], 1.20)
        self.assertEqual(out["diagnostics"]["vip_funnel"]["newly_published_by_category"]["vip"], 1)

    def test_bsd_real_odds_cannot_bypass_independent_value_gate(self):
        out = self.publish({"DC_1X_FT": {"odds": 1.20, "origin": "bsd_consensus"}})
        self.assertEqual(out["matches"], [])
        self.assertEqual(out["diagnostics"]["vip_funnel"]["vip_before_price_and_v21"], 1)
        self.assertEqual(out["diagnostics"]["vip_funnel"]["vip_rejected_after_football_selection"], 1)

if __name__ == "__main__":
    unittest.main()
