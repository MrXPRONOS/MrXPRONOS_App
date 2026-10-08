"""Régressions BTTS V2 : isolation temporelle, marchés Oui/Non, forme, calibration."""
import unittest
from datetime import datetime,timedelta,timezone
from dataclasses import replace
from bsd_v2_core import V2History,score_matrix,markets_from_matrix,predict_v2
from bsd_v2_btts import (btts_features,BTTSModel,btts_candidates,
                         fit_btts_model,FEATURE_COUNT,FEATURE_LABELS)


class BTTSTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,8,10,tzinfo=timezone.utc)
        self.history=[]
        for i in range(24):
            day=self.now-timedelta(days=30-i)
            self.history.append({
                "id":i+1,"event_date":day.isoformat(),"status":"finished",
                "home_team_id":11 if i%2==0 else 22,
                "away_team_id":22 if i%2==0 else 11,
                "home_score":2 if i%3 else 0,
                "away_score":1 if i%4 else 0,
                "league_id":9,
            })
        self.match={"id":300,"event_date":(self.now+timedelta(days=1)).isoformat(),
                    "status":"notstarted","home_team_id":11,"away_team_id":22,
                    "league_id":9}

    def test_features_include_venue_opponent_and_league(self):
        features=btts_features(self.match,V2History(self.history))
        self.assertEqual(len(features),FEATURE_COUNT)
        self.assertEqual(len(FEATURE_LABELS),FEATURE_COUNT)
        self.assertGreater(features[1],-.5)
        self.assertTrue(all(abs(x)<2 for x in features))

    def test_no_match_result_leaks_into_own_features(self):
        base=btts_features(self.match,V2History(self.history))
        future=dict(self.match,status="finished",home_score=12,away_score=12)
        other=btts_features(self.match,V2History(self.history+[future]))
        self.assertEqual(base,other)

    def test_yes_no_sum_to_one_and_other_markets_untouched(self):
        baseline=markets_from_matrix(score_matrix(1.4,1.2))
        model=BTTSModel((0.3,)+(0.,)*(FEATURE_COUNT-1),1.0,150,100)
        changed=btts_candidates(self.match,V2History(self.history),baseline,model)
        indexed={c.key:c for c in changed}
        original={c.key:c for c in baseline}
        self.assertAlmostEqual(indexed["BTTS_YES"].probability+
                               indexed["BTTS_NO"].probability,1.,places=10)
        self.assertNotAlmostEqual(indexed["BTTS_YES"].probability,
                                  original["BTTS_YES"].probability)
        for k in original:
            if not k.startswith("BTTS_"):
                self.assertEqual(indexed[k],original[k])

    def test_model_with_zero_blend_is_baseline(self):
        baseline=markets_from_matrix(score_matrix(1.4,1.2))
        model=BTTSModel((0.,)*FEATURE_COUNT,0.)
        after=btts_candidates(self.match,V2History(self.history),baseline,model)
        self.assertEqual(after,baseline)

    def test_training_never_learns_from_future_year(self):
        index=V2History(self.history)
        model,diag=fit_btts_model(index)
        self.assertEqual(model.blend,0.)
        self.assertEqual(diag["trained"],0)

    def test_prediction_selects_quoted_btts_if_best_eligible(self):
        items=markets_from_matrix(score_matrix(1.4,1.2))
        yes=next(c for c in items if c.key=="BTTS_YES")
        odds={yes.market_code:1.55}
        model=BTTSModel((1.8,)+(0.,)*(FEATURE_COUNT-1),1.0,100,50)
        pred,reason=predict_v2(self.match,V2History(self.history),
             btts_model=model,odds_by_market=odds,require_odds=True,
             min_odds=1.20,excluded_keys={"UNDER_45"})
        self.assertEqual(reason,"ok")
        self.assertEqual(pred["prediction"]["key"],"BTTS_YES")
        self.assertGreaterEqual(pred["prediction"]["bookmaker_odds"],1.20)


if __name__=="__main__":
    unittest.main()
