import os
import unittest
from datetime import date
from unittest.mock import patch

from bsd_api import BSDPage
from football_multisource import (
    FETCH_PRIORITY,
    PROVIDER_QUALITY,
    MultiSourceFootballClient,
    _bsd_compatible,
    _openliga_competitions,
    map_events_to_reference_ids,
)


def match(provider="espn", ident="1", home="Arsenal", away="Chelsea",
          kickoff="2026-10-13T18:00:00Z", status="notstarted"):
    return _bsd_compatible(
        provider=provider,
        provider_id=ident,
        home=home,
        away=away,
        kickoff=kickoff,
        status=status,
        league="Premier League",
    )


class FakeBsd:
    def __init__(self, events=None):
        self.events = events or []
        self.calls = 0
        self.requests_made = 0
        self.rate_limit_remaining = 999

    def list_events(self, *args, **kwargs):
        self.calls += 1
        self.requests_made += 1
        return BSDPage(self.events, len(self.events), 1, True)

    def list_team_recent_events(self, **kwargs):
        self.calls += 1
        return []

    def get_h2h(self, *args, **kwargs):
        self.calls += 1
        return {"source": "bsd", "total_matches": 0}


class StubMulti(MultiSourceFootballClient):
    def __init__(self, free_rows, bsd=None):
        super().__init__(bsd=bsd, max_free_requests=10)
        self.free_rows = free_rows

    def _espn_day(self, day):
        return [x for x in self.free_rows if x.get("provider") == "espn"]

    def _sportscore_day(self, day):
        return [x for x in self.free_rows if x.get("provider") == "sportscore"]

    def _openliga_day(self, day):
        return [x for x in self.free_rows if x.get("provider") == "openligadb"]

    def _thesportsdb_day(self, day):
        return [x for x in self.free_rows if x.get("provider") == "thesportsdb"]


class MultiSourceTests(unittest.TestCase):
    def test_quality_and_fetch_order_are_intentional(self):
        self.assertGreater(PROVIDER_QUALITY["espn"], PROVIDER_QUALITY["bsd"])
        self.assertGreater(PROVIDER_QUALITY["bsd"], PROVIDER_QUALITY["sportscore"])
        self.assertGreater(PROVIDER_QUALITY["sportscore"], PROVIDER_QUALITY["openligadb"])
        self.assertGreater(PROVIDER_QUALITY["openligadb"], PROVIDER_QUALITY["thesportsdb"])
        self.assertEqual(FETCH_PRIORITY[-1], "bsd")

    def test_openliga_2026_uses_multiple_high_quality_competitions(self):
        rows = _openliga_competitions(date(2026, 10, 13))
        shortcuts = {shortcut for shortcut, season, _label in rows}
        self.assertTrue({"bl1", "bl2", "bl3", "ucl", "dfb", "ffb1"}.issubset(shortcuts))
        self.assertTrue({"uel2026", "uecl2026", "nla", "wm26"}.issubset(shortcuts))
        self.assertTrue(all(season == 2026 for _shortcut, season, _label in rows))
        old_rows = _openliga_competitions(date(2026, 5, 13))
        old_shortcuts = {shortcut for shortcut, _season, _label in old_rows}
        self.assertIn("fbl1", old_shortcuts)
        self.assertNotIn("ffb1", old_shortcuts)

    def test_bsd_is_not_called_when_free_coverage_is_enough(self):
        bsd = FakeBsd([{"id": 999}])
        client = StubMulti([match("espn")], bsd=bsd)
        with patch.dict(os.environ, {"FOOTBALL_FREE_MIN_MATCHES_PER_DAY": "1"}):
            page = client.list_events(date(2026, 10, 13), date(2026, 10, 13))
        self.assertEqual(bsd.calls, 0)
        self.assertEqual(len(page.events), 1)
        self.assertIn("espn", page.events[0]["provider_sources"])

    def test_bsd_is_fallback_when_free_sources_are_empty(self):
        bsd_event = {
            "id": 999,
            "home_team": {"name": "Arsenal"},
            "away_team": {"name": "Chelsea"},
            "event_date": "2026-10-13T18:00:00Z",
            "status": "notstarted",
        }
        bsd = FakeBsd([bsd_event])
        client = StubMulti([], bsd=bsd)
        with patch.dict(os.environ, {"FOOTBALL_FREE_MIN_MATCHES_PER_DAY": "1"}):
            page = client.list_events(date(2026, 10, 13), date(2026, 10, 13))
        self.assertEqual(bsd.calls, 1)
        self.assertEqual(str(page.events[0]["id"]), "999")

    def test_higher_quality_provider_wins_but_lower_source_fills_gaps(self):
        espn = match("espn", "401")
        espn["home_logo"] = ""
        sportscore = match("sportscore", "arsenal-chelsea")
        sportscore["home_logo"] = "https://example.com/arsenal.png"
        client = StubMulti([sportscore, espn])
        with patch.dict(os.environ, {"FOOTBALL_FREE_MIN_MATCHES_PER_DAY": "1"}):
            page = client.list_events(date(2026, 10, 13), date(2026, 10, 13))
        self.assertEqual(len(page.events), 1)
        self.assertEqual(page.events[0]["provider_quality"], PROVIDER_QUALITY["espn"])
        self.assertEqual(page.events[0]["home_logo"], "https://example.com/arsenal.png")
        self.assertIn("sportscore", page.events[0]["provider_sources"])

    def test_free_result_maps_back_to_existing_bsd_identity(self):
        reference = {
            "id": "777",
            "source_event_id": "777",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "event_date": "2026-10-13T18:00:00Z",
        }
        free = match(
            "sportscore", "arsenal-chelsea", status="finished",
            kickoff="2026-10-13T18:02:00Z",
        )
        free["home_score"], free["away_score"] = 2, 1
        mapped, missing = map_events_to_reference_ids([reference], [free])
        self.assertFalse(missing)
        self.assertEqual(mapped[0]["id"], "777")
        self.assertEqual(mapped[0]["provider_event_id"], "sportscore:arsenal-chelsea")
        self.assertEqual(mapped[0]["home_score"], 2)


if __name__ == "__main__":
    unittest.main()
