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

    def test_opponent_scoring_features_change_when_opponent_history_changes(self):
        base=btts_features(self.match,V2History(self.history))
        opponent_games=[]
        for i in range(8):
            opponent_games.append({
                "id":1000+i,"event_date":(self.now-timedelta(days=100-i)).isoformat(),
                "status":"finished","home_team_id":50+i,"away_team_id":11,
                "home_score":0,"away_score":1,"league_id":9})
        modified=btts_features(self.match,V2History(self.history+opponent_games))
        self.assertNotEqual(base,modified)

    def test_priced_btts_uses_conservative_break_even_margin(self):
        from bsd_v2_core import choose_market
        item=next(c for c in markets_from_matrix(score_matrix(1.4,1.2))
                  if c.key=="BTTS_YES")
        weak=replace(item,probability=.72)
        picked,_=choose_market([weak],odds_by_market={item.market_code:1.50},
            require_odds=True,league_samples=10,form_samples=6)
        self.assertIsNone(picked)
        good=replace(item,probability=.86)
        picked,_=choose_market([good],odds_by_market={item.market_code:1.50},
            require_odds=True,league_samples=10,form_samples=6)
        self.assertEqual(picked["candidate"].key,"BTTS_YES")

    def test_btts_never_uses_unquoted_price(self):
        from bsd_v2_core import choose_market
        item=next(c for c in markets_from_matrix(score_matrix(1.4,1.2))
                  if c.key=="BTTS_NO")
        picked,_=choose_market([replace(item,probability=.95)],require_odds=True)
        self.assertIsNone(picked)

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


    def test_two_team_scoring_challenger_is_complementary_and_point_in_time(self):
        from bsd_v2_btts_team import team_scoring_probabilities
        index=V2History(self.history)
        data=team_scoring_probabilities(self.match,index)
        self.assertIsNotNone(data)
        self.assertGreater(data["home_scores"],0)
        self.assertLess(data["home_scores"],1)
        self.assertGreater(data["away_scores"],0)
        self.assertLess(data["away_scores"],1)
        self.assertAlmostEqual(data["away_scores"]+data["away_blank"],1.)
        future=dict(self.match,status="finished",home_score=9,away_score=9)
        second=team_scoring_probabilities(self.match,V2History(self.history+[future]))
        self.assertEqual(data,second)

    def test_league_deviation_needs_historical_evidence(self):
        from bsd_v2_btts_league import league_btts_deviation
        empty=V2History([])
        self.assertEqual(league_btts_deviation(self.match,empty),0.)
        self.assertEqual(league_btts_deviation(self.match,V2History(self.history)),0.)

    def test_btts_abstains_on_sparse_or_fallback_history(self):
        from bsd_v2_btts import btts_quality_rejection
        okay={"home_recent_matches":12,"away_recent_matches":12,
            "home_venue_matches":5,"away_venue_matches":5,
            "league_samples":100,"max_last_match_age_days":5}
        active=BTTSModel((0.,)*FEATURE_COUNT,.75,100,70)
        fallback=BTTSModel((0.,)*FEATURE_COUNT,0.,100,70)
        self.assertEqual(btts_quality_rejection(okay,fallback,.56,.56),"btts_no_active_specialist")
        self.assertIsNone(btts_quality_rejection(okay,active,.56,.60))
        self.assertEqual(btts_quality_rejection(dict(okay,away_venue_matches=2),active,.56,.60),
            "btts_insufficient_venue_form")
        self.assertEqual(btts_quality_rejection(dict(okay,away_recent_matches=4),active,.56,.60),
            "btts_insufficient_team_form")
        self.assertEqual(btts_quality_rejection(okay,active,.40,.70),"btts_models_disagree")

    def test_quality_policy_excludes_btts_without_enough_league_matches(self):
        from bsd_v2_core import predict_v2
        class AlwaysPermit:
            def check_fixture(self,features):return None
            def check_market(self,choice):return None
            def family_uncertainty_adjustments(self):return {}
        baseline=markets_from_matrix(score_matrix(1.4,1.2))
        yes=next(c for c in baseline if c.key=="BTTS_YES")
        model=BTTSModel((1.8,)+(0.,)*(FEATURE_COUNT-1),1.0,150,100)
        audit=[]
        result,reason=predict_v2(self.match,V2History(self.history),quality_policy=AlwaysPermit(),
           btts_model=model,odds_by_market={yes.market_code:1.65},
           require_odds=True,market_audit=audit)
        self.assertIsNone(result)
        self.assertTrue(any(row.get("result")=="btts_insufficient_league_form"
                            for row in audit))


if __name__=="__main__":
    unittest.main()
