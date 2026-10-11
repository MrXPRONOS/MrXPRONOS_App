"""Regression tests for the read-only VIP funnel diagnostic."""
import unittest

from bsd_vip_diagnostics import summarize_vip_funnel


def preprice(category, probability, *, league=100, recent=12, venue=6):
    return {
        "category": category,
        "conservative_probability": probability,
        "league_samples": league,
        "home_recent_matches": recent,
        "away_recent_matches": recent,
        "home_venue_matches": venue,
        "away_venue_matches": venue,
        "selection_key": "OVER_15",
    }


class VIPFunnelTests(unittest.TestCase):
    def test_rejected_vip_is_counted_before_pricing(self):
        rows = [
            {"event_id": "1", "event_date": "2026-10-11T18:00:00Z",
             "preprice": preprice("vip", .86),
             "pricing": {"odds_source": "mrxpronos_model", "odds": 1.30},
             "status": "rejected", "reason": "v21_insufficient_indicative_price_edge"},
            {"event_id": "2", "preprice": preprice("vip", .88),
             "pricing": {"odds_source": "bsd_consensus", "odds": 1.50},
             "status": "published", "reason": None},
            {"event_id": "3", "preprice": preprice("pro", .81),
             "status": "rejected", "reason": "v21_observation_not_recommended"},
            {"event_id": "4", "status": "rejected", "reason": "no_qualified_market"},
            {"event_id": "5", "status": "rejected", "reason": "outside_upcoming_window"},
        ]
        existing = [{"category": "pro"}, {"category": "vip"}]
        result = summarize_vip_funnel(rows, existing)
        self.assertEqual(result["examined_fixture_count"], 5)
        self.assertEqual(result["preprice_classified_total"], 3)
        self.assertEqual(result["preprice_category_counts"], {"simple": 0, "pro": 1, "vip": 2})
        self.assertEqual(result["vip_before_price_and_v21"], 2)
        self.assertEqual(result["vip_rejected_after_football_selection"], 1)
        self.assertEqual(result["vip_rejection_reasons"], {"v21_insufficient_indicative_price_edge": 1})
        self.assertEqual(result["newly_published_by_category"]["vip"], 1)
        self.assertEqual(result["all_published_by_category_including_history"]["vip"], 1)
        self.assertEqual(result["progressive_vip_threshold_counts"]["plus_home_away_history_at_least_5_each"], 2)
        self.assertEqual(len(result["vip_candidates"]), 2)

    def test_progressive_criteria_and_nonclassifiable(self):
        rows = [
            {"preprice": preprice("pro", .80), "status": "rejected", "reason": "low"},
            {"preprice": preprice("pro", .85, league=40), "status": "rejected", "reason": "low"},
            {"preprice": preprice("pro", .85, recent=10), "status": "rejected", "reason": "low"},
            {"preprice": preprice("pro", .85, venue=2), "status": "rejected", "reason": "low"},
            {"preprice": preprice("vip", .85), "status": "rejected", "reason": "low"},
            {"status": "rejected", "reason": "daily_publication_cap"},
        ]
        result = summarize_vip_funnel(rows, [])
        self.assertEqual(list(result["progressive_vip_threshold_counts"].values()), [5, 4, 3, 2, 1])
        self.assertEqual(result["vip_before_price_and_v21"], 1)
        self.assertEqual(result["not_classified_reason_counts"], {"daily_publication_cap": 1})
        self.assertEqual(result["newly_published_by_category"]["vip"], 0)

    def test_empty_safe(self):
        result = summarize_vip_funnel([], [])
        self.assertEqual(result["vip_before_price_and_v21"], 0)
        self.assertEqual(result["preprice_classified_total"], 0)
        self.assertEqual(result["vip_candidates"], [])


if __name__ == "__main__":
    unittest.main()
