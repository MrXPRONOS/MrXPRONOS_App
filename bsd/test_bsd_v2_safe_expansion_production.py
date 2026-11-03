"""Production regression tests: safe price fallback and six binary FT market roll-out."""
import unittest
from datetime import datetime,timedelta,timezone

from bsd_markets import candidates_from_goals,realized
from bsd_v2_core import score_matrix,markets_from_matrix
from bsd_v2_market_expansion import candidates as all_extra,ALL_KEYS
from bsd_v2_new_market_model import (
    PUBLISHABLE_KEYS, RESEARCH_ONLY_KEYS,ExtraMarketModel,to_candidate,settlement_candidates
)
from bsd_v2_policies import V2Calibration
from bsd_v2_pricing_fallback import try_next_qualified_market
from bsd_v2_publish import update_settlement
from bsd_v2_audit import settle_entry,KEYS
from bsd_v2_labels import market_label

NOW=datetime(2026,11,3,12,tzinfo=timezone.utc)
FEATURES={'home':1.4,'away':1.1,'league_samples':120,'home_recent_matches':12,
          'away_recent_matches':12,'home_venue_matches':7,'away_venue_matches':7}

def item(key,p,cp,*,market='double_chance',code=None,valid=True):
    return {'key':key,'name':key,'market':market,'outcome':key,'line':None,
            'market_code':code or ('DC_1X_FT' if key=='1X' else 'OU_2.5_UNDER_FT'),
            'probability':p,'conservative_probability':cp,'fair_odds':round(1/p,4),
            'calibration_samples':130,'passes_quality_policy':valid}

def raw_prediction(primary,ranked):
    return {'category':'pro','estimated_goals':FEATURES,
            'prediction':{'key':primary['key'],'internal_market_code':primary['market_code'],
                          'probability':primary['probability'],
                          'conservative_probability':primary['conservative_probability']},
            'ranked_candidates':ranked}

class ProductionNewMarkets(unittest.TestCase):
    def test_catalog_contains_nine_but_only_six_binary_ft_publishable(self):
        self.assertEqual(len(ALL_KEYS),9)
        self.assertEqual(len(PUBLISHABLE_KEYS),6)
        self.assertEqual(set(ALL_KEYS),set(PUBLISHABLE_KEYS)|set(RESEARCH_ONLY_KEYS))
        self.assertEqual(RESEARCH_ONLY_KEYS,{'DNB_HOME','DNB_AWAY','HT_UNDER_15'})
    def test_separate_market_model_never_ranks_refund_or_ht(self):
        model=ExtraMarketModel(V2Calibration(),PUBLISHABLE_KEYS,{},ht_ratio=.40)
        choices=model.candidates({'id':1},FEATURES,score_matrix(1.4,1.1))
        self.assertEqual({r.key for r in choices},PUBLISHABLE_KEYS)
        self.assertEqual(len({r.market_code for r in choices}),6)
    def test_new_score_settlement_resolves_six_ft_keys(self):
        cases=[((1,0),{'HOME_OVER_05':1,'AWAY_OVER_05':0,'HOME_UNDER_15':1,
                        'AWAY_UNDER_15':1,'AH_HOME_PLUS_15':1,'AH_AWAY_PLUS_15':1}),
               ((0,3),{'HOME_OVER_05':0,'AWAY_OVER_05':1,'HOME_UNDER_15':1,
                        'AWAY_UNDER_15':0,'AH_HOME_PLUS_15':0,'AH_AWAY_PLUS_15':1})]
        for scores,expected in cases:
            for key,won in expected.items():
                with self.subTest(scores=scores,key=key):
                    self.assertEqual(realized(KEYS[key],*scores),won)
                    self.assertEqual(realized(settlement_candidates()[key],*scores),won)
    def test_new_market_labels_are_explicit(self):
        for key in PUBLISHABLE_KEYS:
            self.assertNotEqual(market_label(key),key)
    def test_fallback_from_unpriceable_90pct_to_prequalified_80pct(self):
        primary=item('1X',.90,.88)
        second=item('UNDER_25',.80,.785,market='over_under_25',code='OU_2.5_UNDER_FT')
        # Under the default 6% model margin, a qualified 80% model quote
        # is below 1.20. A verified real offer can still pass as fallback.
        verified={'OU_2.5_UNDER_FT':{'odds':1.36,'origin':'bsd_consensus',
                                    'updated_at':NOW.isoformat()}}
        chosen,category,log=try_next_qualified_market(
            raw_prediction(primary,[primary,second]),verified,now=NOW)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen['key'],'UNDER_25')
        self.assertEqual(chosen['odds_source'],'bsd_consensus')
        self.assertEqual(chosen['odds'],1.36)
        self.assertIn(category,('pro','vip'))
    def test_fallback_cannot_fabricate_minimum_model_quote(self):
        primary=item('1X',.90,.88)
        second=item('UNDER_25',.80,.785,market='over_under_25',code='OU_2.5_UNDER_FT')
        chosen,category,log=try_next_qualified_market(
            raw_prediction(primary,[primary,second]),{},now=NOW)
        self.assertIsNone(chosen)
        self.assertTrue(any(x['reason']=='no_publishable_quote' for x in log))
    def test_fallback_cannot_publish_weak_or_unqualified_pick(self):
        primary=item('1X',.95,.93)
        low=item('UNDER_25',.78,.75,market='over_under_25',code='OU_2.5_UNDER_FT')
        bad=item('BTTS_YES',.83,.81,market='btts',code='BTTS_YES_FT',valid=False)
        chosen,cat,log=try_next_qualified_market(raw_prediction(primary,[primary,low,bad]),
                                                   {},now=NOW)
        self.assertIsNone(chosen)
        self.assertTrue(any(x['reason']=='category_or_confidence_below_79' for x in log))
        self.assertTrue(any(x['reason']=='football_quality_rejected' for x in log))
    def test_fallback_never_fabricates_better_quote_from_rejected_real(self):
        primary=item('1X',.90,.89)
        second=item('UNDER_25',.82,.795,market='over_under_25',code='OU_2.5_UNDER_FT')
        quotes={'OU_2.5_UNDER_FT':{'odds':1.10,'origin':'bsd_consensus',
                                   'updated_at':NOW.isoformat()}}
        chosen,_,log=try_next_qualified_market(raw_prediction(primary,[primary,second]),
                                               quotes,now=NOW)
        self.assertIsNone(chosen)
    def test_update_settlement_does_not_rewrite_market_identity(self):
        event={'id':901,'event_date':(NOW+timedelta(hours=2)).isoformat(),
               'status':'finished','home_score':0,'away_score':3}
        row={'id':'bsd:901','event_date':event['event_date'],'status':'notstarted',
             'prediction':{'selection_key':'AH_HOME_PLUS_15','confidence':80.,
                           'odds_source':'mrxpronos_model','odds':1.20}}
        settled=update_settlement(row,event)
        self.assertEqual(settled['prediction']['selection_key'],'AH_HOME_PLUS_15')
        self.assertFalse(settled['verified_prediction'])
        self.assertTrue(settled['is_finished'])
    def test_immutable_ledger_new_market_settlement(self):
        event={'id':901,'source_event_id':901,'event_date':NOW.isoformat(),
               'status':'finished','home_score':0,'away_score':3}
        key='901|'+NOW.isoformat()
        entry={'key':key,'original_pick':{'selection_key':'AH_HOME_PLUS_15'},
               'secondary_picks':[],'settlement':{'status':'pending'}}
        self.assertTrue(settle_entry(entry,event))
        self.assertFalse(entry['settlement']['primary_won'])

if __name__=='__main__':
    unittest.main()
