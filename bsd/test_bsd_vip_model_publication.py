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

    def test_model_pro_at_80pct_can_publish_without_changing_vip_classification(self):
        self.football["category"] = "pro"
        self.football["prediction"]["probability"] = .815
        self.football["prediction"]["conservative_probability"] = .805
        self.football["prediction"]["fair_odds"] = round(1 / .815, 4)
        out = self.publish({})
        self.assertEqual(len(out["matches"]), 1)
        self.assertEqual(out["matches"][0]["category"], "pro")
        self.assertEqual(out["matches"][0]["prediction"]["odds_source"], "mrxpronos_model")
        self.assertEqual(out["matches"][0]["signal_tier"], "INDICATIF")
        self.assertEqual(out["diagnostics"]["vip_funnel"]["newly_published_by_category"]["vip"], 0)
        self.assertEqual(out["diagnostics"]["vip_funnel"]["newly_published_by_category"]["pro"], 1)

    def test_model_below_775pct_is_rejected(self):
        self.football["category"] = "pro"
        self.football["prediction"]["probability"] = .805
        self.football["prediction"]["conservative_probability"] = .774
        out = self.publish({})
        self.assertEqual(out["matches"], [])
        self.assertEqual(
            out["diagnostics"]["rejections"]["v21_model_confidence_or_price_below_floor"], 1
        )

    def test_model_pro_at_77_7pct_can_publish_with_indicative_price(self):
        self.football["category"] = "pro"
        self.football["prediction"]["probability"] = .785
        self.football["prediction"]["conservative_probability"] = .777
        self.football["prediction"]["fair_odds"] = round(1 / .785, 4)
        out = self.publish({})
        self.assertEqual(len(out["matches"]), 1)
        pick = out["matches"][0]
        self.assertEqual(pick["category"], "pro")
        self.assertEqual(pick["prediction"]["odds_source"], "mrxpronos_model")
        self.assertTrue(pick["prediction"]["estimated_odds"])
        self.assertGreaterEqual(pick["prediction"]["odds"], 1.20)

    def test_simple_with_real_bsd_edge_can_publish_at_76_7pct(self):
        self.football["category"] = "simple"
        self.football["prediction"]["probability"] = .779
        self.football["prediction"]["conservative_probability"] = .767
        self.football["prediction"]["fair_odds"] = round(1 / .779, 4)
        out = self.publish({"DC_1X_FT": {"odds": 1.41, "origin": "bsd_consensus"}})
        self.assertEqual(len(out["matches"]), 1)
        pick = out["matches"][0]
        self.assertEqual(pick["category"], "simple")
        self.assertEqual(pick["prediction"]["odds_source"], "bsd_consensus")
        self.assertEqual(pick["signal_tier"], "QUALIFIE")

    def test_bsd_real_odds_cannot_bypass_independent_value_gate(self):
        out = self.publish({"DC_1X_FT": {"odds": 1.20, "origin": "bsd_consensus"}})
        self.assertEqual(out["matches"], [])
        self.assertEqual(out["diagnostics"]["vip_funnel"]["vip_before_price_and_v21"], 1)
        self.assertEqual(out["diagnostics"]["vip_funnel"]["vip_rejected_after_football_selection"], 1)

if __name__ == "__main__":
    unittest.main()
