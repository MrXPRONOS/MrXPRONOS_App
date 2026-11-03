"""Chronological, leak-free genuine Hybrid V3 daily plumbing tests (no live API)."""
from __future__ import annotations
import unittest
from datetime import datetime,date,timezone,timedelta
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from scripts.forecast_hybrid_v3_daily import (
    extract_fixture,recent_bsd_match,recent_verified_matches,forecast_day,
    parse_iso,TargetFixture,MINIMUM_LEAD,HISTORY_CUTOFF,TRAIN_CUTOFF,
    V3_VERSION,HYBRID_NAME, namespace_id
)

NOW=datetime(2026,11,3,6,0,tzinfo=timezone.utc)

def match(*, status="notstarted", when="2026-11-03T16:00:00Z",score=False):
    return {
        "id":123,"status":status,"event_date":when,
        "home_team":{"id":12,"name":"Club domicile"},
        "away_team":{"id":24,"name":"Club extérieur"},
        "home_team_id":12,"away_team_id":24,"league_id":8,
        "league_name":"Ligue nationale",
        "home_score":1 if score else None,
        "away_score":0 if score else None,
    }

class TestLiveV3(unittest.TestCase):
    def test_only_authentic_future_kickoffs_with_no_scores(self):
        m=extract_fixture(match(),now=NOW)
        self.assertIsNotNone(m)
        fixture,kickoff=m
        self.assertEqual(fixture.key,"bsd:123")
        self.assertEqual(fixture.home_id,"bsd_12")
        self.assertEqual(fixture.competition_id,"bsd_8")
        self.assertEqual(kickoff.hour,16)
        for kwargs in (
            {"status":"finished"}, {"when":"2026-11-02T16:00:00Z"},
            {"when":"2026-11-03T06:19:00Z"},
            {"score":True}, {"status":"postponed"},
        ):
            self.assertIsNone(extract_fixture(match(**kwargs),now=NOW))

    def test_recent_results_only_finished_prior_day(self):
        past=match(status="finished",when="2026-11-02T19:00:00Z",score=True)
        row=recent_bsd_match(past,target=NOW.date())
        self.assertEqual((row.hg,row.ag),(1,0))
        self.assertEqual(row.day,date(2026,11,2))
        self.assertEqual(row.home_id,"bsd_12")
        self.assertIsNone(recent_bsd_match(match(status="notstarted",score=True),target=NOW.date()))
        self.assertIsNone(recent_bsd_match(match(status="finished",score=True),target=NOW.date()))
        self.assertIsNone(recent_bsd_match(match(status="finished",score=True,when="2026-10-24T10:00:00Z"),target=NOW.date()))

    def test_archive_freshness_and_api_audit(self):
        prior=match(status="finished",when="2026-11-01T18:00:00Z",score=True)
        newer=match(status="finished",when="2026-11-02T18:00:00Z",score=True)
        newer["id"]=124
        class FakeClient:
            def list_events(self, start, end, **kwargs):
                self.start,self.end=start,end
                return SimpleNamespace(complete=True,events=[newer],total_reported=1)
        client=FakeClient()
        got,info=recent_verified_matches([prior]*1001,client,target=NOW.date())
        self.assertEqual(len(got),2)
        self.assertEqual(info["last_history_day"],"2026-11-02")
        self.assertEqual(client.start,date(2026,11,1))
        self.assertEqual(client.end,date(2026,11,2))
        self.assertEqual(len({m.key for m in got}),2)

    def test_unavailable_or_incomplete_archive_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"not authenticated"):
            recent_verified_matches([],None,target=NOW.date())

    def test_no_target_labels_passed_to_hybrid_v3(self):
        class FakeState:
            last_ingested_day=date(2026,11,2)
            opponent_state=SimpleNamespace(provider_names={})
            def features(self,fixture):
                self.recorded=fixture
                assert not hasattr(fixture,"hg") and not hasattr(fixture,"ag")
                return {"h":1.5,"a":1.1,"vector":np.zeros(54),
                        "form_samples":{"home":{},"away":{}}}
        st=FakeState()
        hist=np.ones((11,11),dtype=float)/121
        final=np.ones((11,11),dtype=float)/121
        final[1,0]+=.05
        final/=final.sum()
        with patch("scripts.forecast_hybrid_v3_daily.training_and_state",
                   return_value=(st,"frozen_models",-.04,TRAIN_CUTOFF,{"frozen":True})), \
             patch("scripts.forecast_hybrid_v3_daily.hist_v3_grid",return_value=hist), \
             patch("scripts.forecast_hybrid_v3_daily.hybrid_v3_grid",return_value=final):
            results,audit=forecast_day(now=NOW,source_rows=["sealed"],recent_rows=[],events=[match()])
        self.assertEqual(len(results),1)
        self.assertEqual(results[0]["model"],HYBRID_NAME)
        self.assertEqual(results[0]["model_fit_latest_day"],"2025-12-31")
        self.assertEqual(results[0]["history_latest_day"],"2026-11-02")
        self.assertEqual(results[0]["grid"][1][0],float(final[1,0]))
        self.assertEqual(audit,{"frozen":True})
        for forbidden in ("actual_score","home_score","away_score","hit","result"):
            self.assertNotIn(forbidden,results[0])

    def test_conflicting_real_provider_identity_becomes_safe_local(self):
        from scripts.forecast_hybrid_v3_daily import safe_target_identity
        fixture,_=extract_fixture(match(),now=NOW)
        state=SimpleNamespace(provider_names={
            ("global-provider-id", "bsd_12"):"differenthistoricalclub"
        })
        fixed,changed=safe_target_identity(fixture,state)
        self.assertEqual(changed,1)
        self.assertIsNone(fixed.home_id)
        self.assertEqual(fixed.away_id,"bsd_24")
        self.assertEqual(fixed.home,fixture.home)
        self.assertEqual(fixed.away,fixture.away)

    def test_mismatched_fixture_or_future_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"[Tt]imezone"):
            parse_iso("2026-11-03T18:00:00")
        self.assertIsNone(extract_fixture(match(status="inprogress"),now=NOW))
        self.assertIsNone(namespace_id("0007"))
        self.assertEqual(HISTORY_CUTOFF,date(2026,10,24))
        self.assertEqual(V3_VERSION,"ml_v3_frozen_experimental_20261029")

if __name__=="__main__":
    unittest.main()
