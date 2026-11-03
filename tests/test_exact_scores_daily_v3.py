"""Pure no-network tests for daily SportData -> genuine V3 publication orchestration."""
from __future__ import annotations
import json
import tempfile
import unittest
from datetime import datetime,date,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace

from scripts.run_exact_scores_v3_daily import (
    BASE_CUTOFF, DAILY_HISTORY_SUBDIR, future_fixtures, historical_daily_rows
)


def response(records, *,ok=True):
    return SimpleNamespace(ok=ok,games=records,reason="test-only source")


def event(ident=123,*,now="2026-11-03T20:00:00Z",sport_id=1,status_group=1):
    return {
      "id":ident,"sportId":sport_id,"startTime":now,
      "statusGroup":status_group,
      "homeCompetitor":{"name":"Home FC","id":40,"score":0},
      "awayCompetitor":{"name":"Away FC","id":59,"score":0},
      "competitionDisplayName":"Test League","competitionId":55
    }


def utc_dt(t):
    return datetime.fromisoformat(t.replace("Z","+00:00")) if t else None


def match(day,i):
    return {
      "id":f"id-{i}","sportId":1,
      "start_time":str(day)+"T10:00:00Z",
      "home_team":"Home","away_team":"Away",
      "competition":"League","is_finished":True,
      "home_score":1,"away_score":0,
      "source_home_team_id":"1","source_away_team_id":"2",
      "source_competition_id":"3"
    }


class TestExactDailyPipeline(unittest.TestCase):
    def test_upcoming_only_certified_utc_day(self):
        now=utc_dt("2026-11-03T15:00:00Z")
        records=[
          event(11,now="2026-11-03T20:00:00Z"),
          event(12,now="2026-11-03T12:00:00Z"),
          event(13,now="2026-11-04T20:00:00Z"),
          event(14,now="2026-11-03T20:00:00Z",sport_id=2),
          event(15,now="2026-11-03T20:00:00Z",status_group=4)
        ]
        choices=future_fixtures(response(records),now,converter=utc_dt)
        self.assertEqual(len(choices),1)
        self.assertEqual(choices[0]["id"],"sportsapipro:11")
        self.assertEqual(choices[0]["kickoff_utc"],"2026-11-03T20:00:00Z")
        self.assertEqual(set(choices[0]),{"id","league","home","away","kickoff_utc"})
        self.assertNotIn("home_score",json.dumps(choices))
        self.assertNotIn("actual_score",json.dumps(choices))

    def test_provider_error_never_turns_into_fake_fixtures(self):
        with self.assertRaisesRegex(RuntimeError,"unavailable"):
            future_fixtures(response([],ok=False),utc_dt("2026-11-03T15:00:00Z"),converter=utc_dt)
        self.assertEqual(future_fixtures(response([]),utc_dt("2026-11-03T15:00:00Z"),converter=utc_dt),[])

    def test_daily_authenticated_cache_before_fetching_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            counter=[]
            def fetcher(day,other,**kwargs):
                self.assertEqual(day,other);counter.append(day)
                return response([match(day,day.day)])
            def snap(day,result):
                rows=result.games
                return {"day":str(day),"verified":True,"certified_football_count":len(rows),"matches":rows}
            def seal(obj,key,label):
                return (label+"\n"+json.dumps(obj)).encode()
            def open_(data,key,label):
                txt=data.decode();self.assertTrue(txt.startswith(label+"\n"))
                return json.loads(txt[len(label)+1:])
            d1=BASE_CUTOFF+timedelta(days=1)
            d2=BASE_CUTOFF+timedelta(days=2)
            first,days=historical_daily_rows(base,d2,fetcher=fetcher,
                normalizer=snap,sealer=seal,opener=open_,key=b"fake",verbose=False)
            self.assertEqual(len(counter),2)
            self.assertEqual(len(first),2)
            self.assertEqual(first[0]["id"],"sportsapipro-daily:id-25")
            self.assertTrue((base/(str(d1)+".enc")).exists())
            self.assertEqual(days[0]["source"],"verified_sportdata_api")
            counter.clear()
            again,days2=historical_daily_rows(base,d2,fetcher=fetcher,
                normalizer=snap,sealer=seal,opener=open_,key=b"fake",verbose=False)
            self.assertEqual(counter,[])
            self.assertEqual(again,first)
            self.assertEqual(days2[0]["source"],"encrypted_cache")

    def test_no_unverified_day_can_reach_v3_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=BASE_CUTOFF+timedelta(days=1)
            def source(*args,**kwargs):return response([],ok=False)
            with self.assertRaisesRegex(RuntimeError,"Cannot verify"):
                historical_daily_rows(Path(tmp),d,fetcher=source,
                    normalizer=lambda day,result:None,
                    sealer=lambda *a:b"empty",opener=lambda *a:None,key=b"?",verbose=False)

    def test_uncertified_event_is_rejected_before_encrypted_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            day=BASE_CUTOFF+timedelta(days=1)
            with self.assertRaisesRegex(RuntimeError,"Missing completed certified"):
                historical_daily_rows(Path(tmp),day,
                    fetcher=lambda *a,**k:response([]),
                    normalizer=lambda d,r:{"day":str(d),"verified":True,"certified_football_count":0,"matches":[]},
                    sealer=lambda *a:b"none",opener=lambda *a:None,key=b"x",verbose=False)
            self.assertEqual(list(Path(tmp).glob("*.enc")),[])

    def test_tampered_encrypted_day_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            day=BASE_CUTOFF+timedelta(days=1)
            (Path(tmp)/(str(day)+".enc")).write_bytes(b"tampered")
            with self.assertRaisesRegex(RuntimeError,"ciphertext authentication failed"):
                historical_daily_rows(Path(tmp),day,
                    fetcher=lambda *a,**k:response([]),
                    normalizer=lambda *a:None,sealer=lambda *a:b"none",
                    opener=lambda *a:(_ for _ in ()).throw(RuntimeError("ciphertext authentication failed")),
                    key=b"x",verbose=False)

if __name__=="__main__":
    unittest.main()
