"""BSD V2 volume optimisation and multi-pick public-feed regression tests."""
import unittest
from datetime import datetime,timedelta,timezone

from bsd_v2_core import V2History,choose_market,markets_from_matrix,score_matrix,estimate_goals
from bsd_v2_policies import V2QualityPolicy
from bsd_v2_publish import to_site

NOW=datetime(2026,10,8,12,tzinfo=timezone.utc)

def event(i,day,score=(1,1)):
    when=NOW-timedelta(days=day)
    return {"id":i,"event_date":when.isoformat(),"league_id":3,
            "status":"finished","home_team_id":1 if i%2 else 2,
            "away_team_id":2 if i%2 else 1,"home_score":score[0],
            "away_score":score[1]}

class MarketCapacityTests(unittest.TestCase):
    def test_four_games_are_enough_for_base_calculation(self):
        history=V2History([event(i,15+i) for i in range(1,5)])
        match={"id":200,"status":"notstarted","event_date":(NOW+timedelta(days=1)).isoformat(),
               "league_id":3,"home_team_id":1,"away_team_id":2}
        feat,reason=estimate_goals(match,history)
        self.assertEqual(reason,"ok")
        self.assertEqual(feat["home_recent_matches"],4)
        self.assertEqual(feat["away_recent_matches"],4)

    def test_quality_requires_five_matches(self):
        policy=V2QualityPolicy()
        self.assertEqual(policy.min_form,5)
        self.assertEqual(policy.min_league,15)
        data={"home_recent_matches":4,"away_recent_matches":4,
              "league_samples":20,"max_last_match_age_days":10}
        self.assertEqual(policy.check_fixture(data),"quality_short_form")
        data["home_recent_matches"]=data["away_recent_matches"]=5
        self.assertIsNone(policy.check_fixture(data))

    def test_market_audit_gives_reasons_for_absent_prices(self):
        candidates=markets_from_matrix(score_matrix(1.4,1.2))
        audit=[]
        top,rows=choose_market(candidates,odds_by_market={},
                               require_odds=True,market_audit=audit,
                               excluded_keys={"UNDER_45"})
        self.assertIsNone(top)
        self.assertTrue(any(row["result"]=="missing_or_low_bsd_odds" for row in audit))
        self.assertTrue(any(row["result"]=="excluded_market" for row in audit))

    def test_price_120_not_automatic_acceptance(self):
        item=next(c for c in markets_from_matrix(score_matrix(1.6,1.3))
                  if c.key=="OVER_15")
        from dataclasses import replace
        weak=replace(item,probability=.74)
        denied,_=choose_market([weak],odds_by_market={weak.market_code:1.20},
            require_odds=True)
        self.assertIsNone(denied)
        strong=replace(item,probability=.95)
        accepted,_=choose_market([strong],odds_by_market={strong.market_code:1.20},
            require_odds=True)
        self.assertEqual(accepted["candidate"].key,"OVER_15")

    def test_low_bsd_odds_are_combo_only_with_strict_confidence(self):
        from dataclasses import replace
        candidate=next(c for c in markets_from_matrix(score_matrix(1.6,1.1))
                       if c.key=="OVER_15")
        high_confidence=replace(candidate,probability=.98)
        pick,_=choose_market([high_confidence],
            odds_by_market={candidate.market_code:1.12},
            require_odds=True,min_odds=1.01,allow_combo_prices=True)
        self.assertIsNotNone(pick)
        self.assertEqual(pick["bookmaker_odds"],1.12)
        excluded,_=choose_market([high_confidence],
            odds_by_market={candidate.market_code:1.12},
            require_odds=True,min_odds=1.20)
        self.assertIsNone(excluded)
        low_confidence=replace(candidate,probability=.80)
        unsafe,_=choose_market([low_confidence],
            odds_by_market={candidate.market_code:1.12},
            require_odds=True,min_odds=1.01,allow_combo_prices=True)
        self.assertIsNone(unsafe)

    def test_second_estimated_selection_keeps_source_marker(self):
        from bsd_v2_estimated_odds import valid_standalone_prediction
        fixture={"id":78,"home_team":"Alpha","away_team":"Beta",
                 "event_date":(NOW+timedelta(hours=5)).isoformat(),"league_id":3}
        base={"id":"bsd:78","home_team_id":1,"away_team_id":2,
              "category":"simple","model_version":"bsd-v2-isolated",
              "prediction":{"key":"1X","name":"1X","market":"double_chance",
                  "outcome":"1X","line":None,"internal_market_code":"DC_1X_FT",
                  "probability":.82,"fair_odds":1.2195,
                  "bookmaker_odds":1.26,"odds_source":"bsd_consensus"},
              "secondary_selections":[{
                  "key":"OVER_15","name":"Over 1.5","market":"goals",
                  "outcome":"over","line":1.5,"market_code":"OU_1.5_OVER_FT",
                  "probability":.76,"odds":1.24,
                  "odds_source":"mrxpronos_model",
                  "odds_method":"hypothese_6pct",
                  "overround_assumption":.06}]}
        output=to_site(base,fixture)
        self.assertEqual(output["predictions"][1]["odds_source"],"mrxpronos_model")
        self.assertTrue(output["predictions"][1]["estimated_odds"])
        self.assertTrue(valid_standalone_prediction(output["predictions"][1]))
        self.assertEqual(output["predictions"][1]["odds_method"],"hypothese_6pct")

    def test_two_selections_serialize_to_site(self):
        fixture={"id":77,"home_team":"Alpha","away_team":"Beta",
                 "event_date":(NOW+timedelta(hours=5)).isoformat(),"league_id":3}
        prediction={"id":"bsd:77","home_team_id":1,"away_team_id":2,
                    "category":"simple","model_version":"bsd-v2-isolated",
                    "prediction":{"key":"1X","name":"Double chance 1X",
                        "market":"double_chance","outcome":"1X","line":None,
                        "internal_market_code":"DC_1X_FT",
                        "probability":.84,"fair_odds":1.19,
                        "bookmaker_odds":1.34,"odds_source":"bsd_consensus",
                        "odds_updated_at":NOW.isoformat()},
                    "secondary_selections":[{
                        "key":"OVER_15","name":"Plus de 1.5 buts",
                        "market":"goals","outcome":"over","line":1.5,
                        "market_code":"OU_1.5_OVER_FT","probability":.78,
                        "odds":1.45,"odds_source":"bsd_consensus",
                        "odds_updated_at":NOW.isoformat()}]}
        result=to_site(prediction,fixture)
        self.assertEqual(len(result["predictions"]),2)
        self.assertEqual(result["prediction"]["selection_key"],"1X")
        self.assertEqual(result["predictions"][1]["selection_key"],"OVER_15")
        self.assertNotEqual(result["predictions"][0]["market"],result["predictions"][1]["market"])
        self.assertEqual(result["predictions"][1]["odds"],1.45)

if __name__=="__main__":
    unittest.main()
