"""Extended BSD V3 offline QA: source integrity, free quote routing, gated projection."""
from __future__ import annotations
import unittest
from datetime import datetime,timedelta,timezone
from bsd_v3 import __version__  # package import must remain side-effect free
from bsd_v3.quality import audit_event,clean_fixture_batch,audit_history
from bsd_v3.legacy import score_matrix,markets_from_matrix
from bsd_v3.ensemble import projected_matrix
from bsd_v3.probabilities import prove_coherence
from bsd_v3.free_odds import FreeMultiMarketOdds
from bsd_v3.quotes import validate_quote
from bsd_v3.policy import label_candidate

UTC=timezone.utc
NOW=datetime(2026,11,6,12,tzinfo=UTC)

def match(event_id,kickoff,home=1,away=2,status="notstarted",home_score=None,away_score=None):
    return {"id":event_id,"home_team_id":home,"away_team_id":away,
            "home_team":"Alpha FC","away_team":"Beta FC",
            "league_id":7,"status":status,"event_date":kickoff.isoformat(),
            "home_score":home_score,"away_score":away_score}

class TestFixtureIntegrity(unittest.TestCase):
    def test_duplicate_and_score_conflicts(self):
        future=NOW+timedelta(hours=4)
        first=match(1,future)
        dup=dict(first)
        conflicting=match(2,future,home=9)
        accepted,rejected=clean_fixture_batch([first,dup,conflicting,
                                                 match(2,future),
                                                 match(3,future,home_score=2)],now=NOW)
        self.assertEqual(accepted,[first])
        self.assertEqual(rejected["same_fixture_duplicate"],1)
        self.assertEqual(rejected["conflicting_duplicate"],2)
        self.assertEqual(rejected["future_score_in_fixture"],1)

    def test_history_scores_and_future_rejected(self):
        old=match(10,NOW-timedelta(days=2),status="finished",home_score=2,away_score=1)
        future=match(12,NOW+timedelta(days=1),status="finished",home_score=1,away_score=0)
        cleaned,diag=audit_history([old,old,future,match(11,NOW,status="finished")],now=NOW)
        self.assertEqual(len(cleaned),1)
        self.assertEqual(diag["rejected"]["duplicate_exact"],1)
        self.assertEqual(diag["rejected"]["future_history"],1)
        self.assertEqual(diag["rejected"]["unsettled_history"],1)

    def test_invalid_ids_or_kickoffs(self):
        self.assertEqual(audit_event(match(True,NOW+timedelta(hours=2)),now=NOW),
                         "invalid_event_id")
        bad=match(10,NOW+timedelta(hours=2))
        bad["event_date"]="invalid"
        self.assertEqual(audit_event(bad,now=NOW),"invalid_kickoff")
        self.assertEqual(audit_event(match(11,NOW-timedelta(minutes=2)),now=NOW),
                         "already_started")

class FakeBSD:
    def __init__(self):
        self.calls=0
    def get_json(self,path,params,ttl):
        self.calls+=1
        return {"count":0,"results":[]}

class FakeReply:
    status_code=200
    def __init__(self,payload):self.payload=payload
    def json(self):return self.payload

class FakeSession:
    def __init__(self,payload):self.calls=0;self.payload=payload
    def get(self,url,timeout,allow_redirects):
        self.calls+=1
        self.last_url=url
        return FakeReply(self.payload)

def bookmaker_board(now=NOW,kickoff=NOW+timedelta(hours=3),in_play=False):
    return {"fixtures":[{
        "home_team":"Alpha FC","away_team":"Beta FC",
        "commence_time":kickoff.isoformat(),"in_play":in_play,
        "bookmakers":[{"kind":"sportsbook","key":"named_freebook",
                       "last_update":(now-timedelta(minutes=10)).isoformat(),
                       "markets":{
                          "h2h":[{"name":"Alpha FC","price":-120},
                                 {"name":"Beta FC","price":200},
                                 {"name":"Draw","price":245}],
                          "totals":[{"name":"Over","point":2.5,"price":130},
                                    {"name":"Under","point":2.5,"price":-155}]
                       }}]
    }]}

class TestFreeOddsRouter(unittest.TestCase):
    def test_one_free_board_for_two_events_with_correct_identity(self):
        session=FakeSession(bookmaker_board())
        bsd=FakeBSD()
        router=FreeMultiMarketOdds(bsd,enable_public_board=True,session=session)
        future=NOW+timedelta(hours=3)
        quotes,meta=router(match(200,future),NOW)
        self.assertEqual(bsd.calls,1)
        self.assertEqual(session.calls,1)
        self.assertEqual(meta["no_payment_required"],True)
        self.assertIn("OU_2.5_OVER_FT",quotes)
        self.assertEqual(quotes["OU_2.5_OVER_FT"]["bookmaker"],"named_freebook")
        q,reason=validate_quote(quotes["OU_2.5_OVER_FT"],now=NOW,kickoff=future)
        self.assertEqual(reason,"ok")
        self.assertTrue(q["named_bookmaker_quote"])
        self.assertFalse(q["availability_confirmed"])
        self.assertTrue(label_candidate(
            {"key":"OVER_25","family":"goals","probability":.75,
             "conservative_probability":.70},{"level":"full"},q)["value_shadow"])
        different=match(201,future,home=5,away=6)
        different["home_team"]="Other City"
        other,_=router(different,NOW)
        self.assertEqual(other,{})
        self.assertEqual(session.calls,1)
        self.assertEqual(bsd.calls,2)

    def test_live_public_board_rejected(self):
        bsd=FakeBSD()
        router=FreeMultiMarketOdds(bsd,enable_public_board=True,
                                   session=FakeSession(bookmaker_board(in_play=True)))
        quotes,meta=router(match(200,NOW+timedelta(hours=3)),NOW)
        self.assertEqual(quotes,{})

class FakeResultModel:
    def predict(self,event,index,original):
        return (.65,.2,.15)

class FakeGoalModel:
    blend=1.
    def predict_over(self,event,index):
        return {1.5:.84,2.5:.65,3.5:.31,4.5:.12}

class TestSpecialistProjection(unittest.TestCase):
    def test_specialist_projections_keep_probabilities_coherent(self):
        event=match(1,NOW+timedelta(hours=2))
        base=score_matrix(1.4,1.0)
        changed=projected_matrix(event,None,base,
                                 {"result":FakeResultModel(),"goals":FakeGoalModel()},
                                 {"result":.40,"goals":.60})
        rows=markets_from_matrix(changed)
        self.assertTrue(prove_coherence(rows))
        self.assertAlmostEqual(sum(changed.values()),1.,places=10)
        self.assertNotAlmostEqual(changed[(1,0)],base[(1,0)],places=5)


class TestH2HSafety(unittest.TestCase):
    def test_btts_legacy_filter_audited_without_discarding_market(self):
        from bsd_v3.legacy import V2History
        from bsd_v3.guardrails import family_guards
        from bsd_v3.selection import serialize_candidates
        old=match(11,NOW-timedelta(days=5),status="finished",home_score=0,away_score=1)
        index=V2History([old])
        upcoming=match(22,NOW+timedelta(hours=4))
        base=score_matrix(1.3,1.2)
        guards,evidence=family_guards(upcoming,index,base,{})
        self.assertEqual(guards["BTTS_YES"],"btts_last_h2h_lost")
        self.assertNotIn("BTTS_NO",guards)
        q={"odds":3.5,"verified":True,"executable":True,
           "benchmark_only":False,"bookmaker":"named_book"}
        candidates=markets_from_matrix(base)
        rows=serialize_candidates(candidates,
            {"home_recent_matches":12,"away_recent_matches":12,
             "home_venue_matches":6,"away_venue_matches":6,"league_samples":100},
            {"level":"full","league_games":100,"venue_games":6,"recent_games":12},
            {"BTTS_YES_FT":q},market_guards=guards)
        yes=next(r for r in rows if r["key"]=="BTTS_YES")
        self.assertEqual(yes["decision"]["legacy_guard_reason"],"btts_last_h2h_lost")
        self.assertFalse(yes["decision"]["pro_vip_shadow"])
        self.assertEqual(len(rows),16)

    def test_missing_head_to_head_keeps_btts_research_candidate(self):
        from bsd_v3.legacy import V2History
        from bsd_v3.guardrails import family_guards
        guards,evidence=family_guards(match(44,NOW+timedelta(hours=2)),
                                      V2History([]),score_matrix(1.4,1.2),{})
        self.assertEqual(guards["BTTS_YES"],"btts_last_h2h_missing")
        self.assertEqual(guards["BTTS_NO"],"btts_last_h2h_missing")

if __name__=="__main__":
    unittest.main()
