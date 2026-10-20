"""Pre-kickoff team-form regime tests: attacks, defence, H2H-era, venues and veto."""
import sys,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from bsd_v2_core import V2History
from exact_scores_h2h import H2HIndex
from bsd_form_shift import form_shift,simple_market_veto_keys
from grouped_correct_score_engine import selection_summary
from bsd_form_shift_singles_backtest import run

AT=datetime(2026,10,20,17,tzinfo=timezone.utc)
def e(k,dt,h,a,hs,aws):
    return {"id":k,"event_date":dt.isoformat(),"home_team_id":h,
            "away_team_id":a,"home_score":hs,"away_score":aws,
            "status":"finished","league_id":11}
TARGET={"id":9901,"event_date":AT.isoformat(),"home_team_id":10,"away_team_id":20,
        "status":"notstarted","league_id":11}

def dataset(surge=True, future=False):
    events=[]
    # Build sufficient form *before* H2H meetings: historical H2H context must
    # reflect the teams as of THAT date, not updated attack figures from 2026.
    for i in range(10):
        when=datetime(2024,7,1,tzinfo=timezone.utc)+timedelta(days=12*i)
        events.append(e(100+i,when,10,100+i,1,0))
        events.append(e(200+i,when,200+i,20,0,1))
    for i in range(3):
        when=datetime(2025,3,1,tzinfo=timezone.utc)+timedelta(days=75*i)
        events.append(e(300+i,when,10,20,1,0))
    # 15 more recent fixtures each, grouped in chronological order.
    for i in range(15):
        when=datetime(2026,2,1,tzinfo=timezone.utc)+timedelta(days=15*i)
        recent=i>=10
        scored=3 if surge and recent else 1
        conceded=2 if surge and recent else 0
        events.append(e(400+i,when,10,300+i,scored,conceded))
        events.append(e(500+i,when,400+i,20,conceded,scored))
    if future:
        events.append(e(8888,AT+timedelta(days=2),10,20,10,8))
    return V2History(events)

class TeamRegimeTests(unittest.TestCase):
    def test_recent_five_vs_prior_ten_detects_attack_and_defence_surge(self):
        index=dataset(True)
        risk=form_shift(TARGET,index,H2HIndex(index),expected={"home":1.7,"away":1.6},
                        under25=.68,direction={"direction":"neutral"})
        self.assertTrue(risk["valid"])
        self.assertTrue(risk["flags"]["home_attack_surged"])
        self.assertTrue(risk["flags"]["away_attack_surged"])
        self.assertTrue(risk["flags"]["home_defence_weakened"])
        self.assertTrue(risk["flags"]["away_defence_weakened"])
        self.assertFalse(risk["variant_pass"]["combined"])
        self.assertTrue(risk["bsd_low_goals_veto"])
        self.assertIn("UNDER_25",simple_market_veto_keys(risk))
        self.assertIn("UNDER_45",simple_market_veto_keys(risk))
    def test_h2h_context_uses_only_form_before_old_meeting(self):
        idx=dataset(True)
        r=form_shift(TARGET,idx,H2HIndex(idx))
        ctx=r["historic_h2h_form"]
        self.assertEqual(ctx["meetings"],3)
        self.assertGreaterEqual(ctx["form_samples"],2)
        self.assertLess(ctx["home_scored_then"],1.6)
        self.assertGreater(r["home"]["recent"]["scored"],2.5)
        self.assertTrue(r["flags"]["home_vs_old_h2h_attack_jump"])
    def test_future_results_never_influence_form(self):
        index1=dataset(True)
        index2=dataset(True,True)
        r1=form_shift(TARGET,index1,H2HIndex(index1),expected={"home":1.4,"away":1.3},under25=.7)
        r2=form_shift(TARGET,index2,H2HIndex(index2),expected={"home":1.4,"away":1.3},under25=.7)
        self.assertEqual(r1,r2)
    def test_no_surge_preserves_priority(self):
        idx=dataset(False)
        r=form_shift(TARGET,idx,H2HIndex(idx),expected={"home":1.05,"away":1.1},under25=.71)
        self.assertTrue(r["valid"])
        self.assertFalse(r["flags"]["home_attack_surged"])
        self.assertTrue(r["variant_pass"]["combined"])
        self.assertEqual(simple_market_veto_keys(r),())
    def test_missing_old_form_is_not_a_fabricated_certain_risk(self):
        idx=V2History([e(1,AT-timedelta(days=10),10,30,1,0)])
        r=form_shift(TARGET,idx,H2HIndex(idx))
        self.assertFalse(r["valid"])
        self.assertEqual(simple_market_veto_keys(r),())
    def test_grouped_policy_gate_returns_none_only_for_rejected_form(self):
        item={"group_id":"G1","scores":[[0,0],[1,0],[0,1]],
              "probability":.4,"direction_eligible":True,"tier":"recherche_prioritaire",
              "odds":None,"expected_value":None}
        choices=selection_summary({"groups":[item],
            "form_shift":{"variant_pass":{"combined":False,"recent_attack":True}}})
        self.assertIsNone(choices["form_combined"])
        self.assertEqual(choices["form_recent_attack"],item)
        self.assertEqual(choices["with_h2h_under"],item)
    def test_single_market_backtest_handles_empty_history(self):
        out=run([],years=(2025,2026))
        self.assertEqual(out["results"]["2026"]["base"]["n"],0)
        self.assertEqual(out["results"]["2026"]["form_guard"]["n"],0)

if __name__=="__main__":unittest.main()
