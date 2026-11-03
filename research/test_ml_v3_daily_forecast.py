"""No-leakage tests for native Hybrid V3 daily generation from fresh BSD history."""
from __future__ import annotations
import unittest
from datetime import datetime,date,timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from ml_v3_daily_forecast import archive_tail,fixtures_today,label,competition

ASOF=datetime(2026,11,3,6,0,0,tzinfo=timezone.utc)

def event(ident,iso,status="finished",home_score=1,away_score=0):
    return {
      "id":ident,"event_date":iso,"status":status,
      "home_team":{"name":"Club A","id":12},
      "away_team":{"name":"Club B","id":13},
      "league":{"name":"League Verified"},
      "home_score":home_score,"away_score":away_score,
    }


class NativeV3DailyTests(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(label(event(1,"2026-11-02T12:00:00Z"),"home"),"Club A")
        self.assertEqual(competition(event(1,"2026-11-02T12:00:00Z")),"League Verified")
        self.assertEqual(label({"home_team_name":"Club X"},"home"),"Club X")

    def test_latest_archive_drops_today_even_with_final_results(self):
        values=[event(100+i,f"2026-11-02T{(i%12+8):02d}:00:00Z") for i in range(60)]
        values.append(event(300,"2026-11-03T02:00:00Z"))
        values.append(event(301,"2026-11-02T02:00:00Z",status="notstarted"))
        values.append(event(302,"2026-10-24T09:00:00Z"))
        recent=archive_tail(values,asof=ASOF)
        self.assertEqual(len(recent),60)
        self.assertEqual(max(row.day for row in recent),date(2026,11,2))
        self.assertTrue(all(row.key.startswith("bsd-tail:") for row in recent))
        self.assertTrue(all(row.hg == 1 and row.ag==0 for row in recent))

    def test_reject_stale_and_inadequate_archive(self):
        values=[event(100+i,"2026-10-27T12:00:00Z") for i in range(60)]
        with self.assertRaisesRegex(ValueError,"stale"):
            archive_tail(values,asof=ASOF)
        with self.assertRaisesRegex(ValueError,"too few"):
            archive_tail(values[:3],asof=ASOF)

    def test_upcoming_api_filters_started_and_postmatch(self):
        events=[
            event(1,"2026-11-03T06:03:00Z","scheduled",None,None),
            event(2,"2026-11-03T09:00:00Z","scheduled",None,None),
            event(3,"2026-11-03T10:00:00Z","finished",3,2),
            event(4,"2026-11-02T19:00:00Z","scheduled",None,None),
            event(5,"2026-11-03T11:00:00Z","upcoming",None,None),
        ]
        client=MagicMock()
        client.list_events.return_value=SimpleNamespace(events=events,
                         complete=True,total_reported=5,pages_fetched=1)
        future=fixtures_today(client,asof=ASOF)
        self.assertEqual([r["id"] for r in future],["bsd-upcoming:2","bsd-upcoming:5"])
        self.assertTrue(all("home_score" not in r and "actual_score" not in r for r in future))
        self.assertTrue(all(r["kickoff_utc"]>ASOF.isoformat().replace("+00:00","Z") for r in future))

    def test_refuse_incomplete_source(self):
        client=MagicMock()
        client.list_events.return_value=SimpleNamespace(events=[],complete=False,total_reported=500,pages_fetched=1)
        with self.assertRaisesRegex(ValueError,"Incomplete"):
            fixtures_today(client,asof=ASOF)


if __name__=="__main__":
    unittest.main()
