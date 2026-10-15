"""Offline tests for production source corroboration: strictly no market changes."""
import copy
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from bsd_v2_multisource import annotate,canonical,corroborate_existing_feed,CALENDARS

NOW=datetime(2026,10,15,9,tzinfo=timezone.utc)

def match(*,league="Premier League",status="notstarted",home="Arsenal",away="Chelsea",at="2026-10-16T19:00:00+00:00"):
    return {"source":"bsd","id":"bsd:7","source_event_id":7,
        "home_team":home,"away_team":away,"league":league,
        "status":status,"event_date":at,
        "prediction":{"selection_key":"OVER_15","odds":1.56,
            "odds_source":"bsd_consensus","confidence":78.9}}

class FakeResponse:
    status_code=200
    content=b'{"matches":[]}'
    def __init__(self,body):
        self._body=body
    def json(self):return self._body

class FakeSession:
    def __init__(self,missing=None):
        self.calls=[]
        self.missing=missing
    def get(self,url,*,timeout,allow_redirects,headers):
        assert not allow_redirects
        assert url.startswith("https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/")
        self.calls.append(url)
        if self.missing and "en.1.json" in url:
            raise TimeoutError("simulated")
        items=[{"date":"2026-10-16","team1":"Arsenal","team2":"Chelsea"}] if "en.1.json" in url else []
        return FakeResponse({"matches":items})

class ProductionCorroborationTests(unittest.TestCase):
    def test_source_matching_only_proven_day_and_teams_and_league(self):
        feed={"source":"bsd","matches":[match()]}
        prior=copy.deepcopy(feed["matches"][0]["prediction"])
        report=annotate(feed,session=FakeSession(),now=NOW)
        self.assertEqual(report["calendar_confirmed"],1)
        self.assertEqual(report["files_ok"],8)
        self.assertEqual(report["status"],"ok")
        self.assertEqual(feed["matches"][0]["prediction"],prior)
        self.assertEqual(feed["matches"][0]["source"],"bsd")
        self.assertTrue(feed["matches"][0]["multisource_verification"]["cc0_calendar_corroborated"])
        self.assertFalse(report["changes_prediction_or_quoted_prices"])

    def test_no_inference_from_wrong_team_league_date_or_past(self):
        cases=[
            match(home="Tottenham"),match(away="Arsenal"),
            match(league="Serie A"),
            match(at="2026-10-17T19:00:00+00:00"),
            match(at="2026-10-14T19:00:00+00:00"),
            match(status="finished"),
        ]
        for candidate in cases:
            with self.subTest(row=candidate):
                feed={"source":"bsd","matches":[candidate]}
                previous=copy.deepcopy(candidate["prediction"])
                audit=annotate(feed,session=FakeSession(),now=NOW)
                self.assertEqual(audit["calendar_confirmed"],0)
                self.assertNotIn("multisource_verification",candidate)
                self.assertEqual(previous,candidate["prediction"])

    def test_repeated_generation_drops_stale_confirmations(self):
        row=match()
        feed={"source":"bsd","matches":[row]}
        self.assertEqual(annotate(feed,session=FakeSession(),now=NOW)["calendar_confirmed"],1)
        report=annotate(feed,session=FakeSession(missing=True),now=NOW)
        self.assertEqual(report["status"],"degraded")
        self.assertEqual(report["calendar_confirmed"],0)
        self.assertNotIn("multisource_verification",row)

    def test_multiple_leagues_for_same_pair_never_confirms(self):
        feed={"source":"bsd","matches":[match()]}
        schedules=[("2026-10-16","arsenal","chelsea","premier league"),
                   ("2026-10-16","arsenal","chelsea","championship")]
        report=corroborate_existing_feed(feed,schedules,now=NOW)
        self.assertEqual(report["calendar_confirmed"],0)
        self.assertNotIn("multisource_verification",feed["matches"][0])

    def test_source_unavailable_does_not_change_existing_feed(self):
        f={"source":"bsd","matches":[match()]}
        before=copy.deepcopy(f["matches"])
        r=annotate(f,session=FakeSession(missing=True),now=NOW)
        self.assertEqual(r["files_ok"],7)
        self.assertEqual(r["status"],"degraded")
        self.assertEqual(f["matches"],before)

    def test_invalid_feed_and_clock_refused(self):
        with self.assertRaises(ValueError):
            annotate({"source":"unknown","matches":[]},session=FakeSession(),now=NOW)
        with self.assertRaises(ValueError):
            corroborate_existing_feed({"source":"bsd","matches":[]},[],now=datetime(2026,10,15))

    def test_normalization_does_not_fuzzy_guess_aliases(self):
        self.assertEqual(canonical("Atlético  Madrid"),"atletico madrid")
        self.assertNotEqual(canonical("Man United"),canonical("Manchester United"))
        self.assertEqual(len(CALENDARS),8)

if __name__=="__main__":
    unittest.main()
