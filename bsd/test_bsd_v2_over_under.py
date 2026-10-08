"""Over/Under model: coherence, chronology, pricing and uncertainty regression."""
import unittest
from datetime import datetime,timedelta,timezone
from bsd_v2_core import V2History,score_matrix,markets_from_matrix,predict_v2
from bsd_v2_over_under import (features,total_distribution,TotalGoalsModel,
    adjust_candidates,fit_total_model,uncertainty)

class TotalsTests(unittest.TestCase):
    def setUp(self):
        now=datetime(2026,10,8,10,tzinfo=timezone.utc)
        self.future={"id":900,"event_date":(now+timedelta(days=2)).isoformat(),
                     "status":"notstarted","home_team_id":1,"away_team_id":2,"league_id":9}
        self.games=[]
        for i in range(40):
            self.games.append({"id":i+1,"event_date":(now-timedelta(days=41-i)).isoformat(),
               "status":"finished","home_team_id":1 if i%2 else 2,
               "away_team_id":2 if i%2 else 1,"league_id":9,
               "home_score":1+(i%2),"away_score":i%3})
        self.index=V2History(self.games)

    def test_normalized_and_monotonic_total_distributions(self):
        for avg,var in ((1.2,1.2),(2.4,5.0),(3.1,10.0)):
            d=total_distribution(avg,var)
            self.assertAlmostEqual(sum(d),1.,places=8)
            self.assertTrue(all(x>=0 for x in d))
            probs=[sum(d[int(line)+1:]) for line in (1.5,2.5,3.5,4.5)]
            self.assertEqual(probs,sorted(probs,reverse=True))

    def test_features_have_opponent_venue_and_dispersion(self):
        row=features(self.future,self.index)
        self.assertIsNotNone(row)
        self.assertGreater(row["mean"],0)
        self.assertGreater(row["opponent_adjusted_mean"],0)
        self.assertGreaterEqual(row["league_samples"],20)

    def test_chronological_features_ignore_future_result(self):
        before=features(self.future,self.index)
        injected=dict(self.future,status="finished",home_score=20,away_score=20)
        later=features(self.future,V2History(self.games+[injected]))
        self.assertEqual(before,later)

    def test_model_keeps_other_markets(self):
        baseline=markets_from_matrix(score_matrix(1.5,1.1))
        model=TotalGoalsModel(blend=1.)
        changed=adjust_candidates(self.future,self.index,baseline,model)
        original={x.key:x for x in baseline}
        new={x.key:x for x in changed}
        for key in ("1","X","2","1X","X2","12","BTTS_YES","BTTS_NO"):
            self.assertEqual(original[key],new[key])
        for key in ("15","25","35","45"):
            self.assertAlmostEqual(new["OVER_"+key].probability+new["UNDER_"+key].probability,1,places=7)

    def test_fallback_for_no_training_data(self):
        model,diag=fit_total_model(self.index)
        self.assertEqual(model.blend,0.)
        self.assertEqual(diag["reason"],"insufficient_2024_data")

    def test_uncertainty_can_block_volatile_games(self):
        model=TotalGoalsModel(blend=.5)
        self.assertIsNotNone(uncertainty(self.future,self.index,model,baseline_total=15.))

    def test_verified_120_quote_rule_applies_to_ou(self):
        generated=markets_from_matrix(score_matrix(1.7,1.5))
        from bsd_v2_core import choose_market
        chosen=next(c for c in generated if c.key=="OVER_15")
        cheap,_=choose_market(generated,odds_by_market={chosen.market_code:1.19},
             require_odds=True,min_probability=.1)
        good,_=choose_market(generated,odds_by_market={chosen.market_code:1.30},
             require_odds=True,min_probability=.1,excluded_keys={"UNDER_45"})
        self.assertIsNone(cheap)
        self.assertEqual(good["candidate"].key,"OVER_15")

if __name__=="__main__":unittest.main()
