"""Isolated real-pricing refresh invariants; no API calls or secrets."""
from datetime import datetime, timedelta, timezone
import unittest
from bsd.bsd_v2_montante_refresh import refresh_prices

NOW=datetime(2026,11,14,9,0,tzinfo=timezone.utc)

def fixture(*,code='OU_1.5_OVER_FT',key='OVER_15',odds=1.25,age_hours=8):
    return {'id':'bsd:123','source_event_id':123,'source':'bsd','category':'vip',
            'recommendation_eligible':True, 'status':'notstarted','is_finished':False,
            'event_date':(NOW+timedelta(hours=4)).isoformat(),
            'prediction':{'selection_key':key,'market_code':code,'market':'over_under_15',
                'odds':odds,'odds_source':'bsd_consensus','estimated_odds':False,
                'odds_updated_at':(NOW-timedelta(hours=age_hours)).isoformat(),
                'confidence':90,'conservative_probability':88,'model_probability':90,
                'recommendation_eligible':True}}

def real_quote():
    return {'OU_1.5_OVER_FT':{'odds':1.4,'origin':'bsd_consensus',
                             'updated_at':(NOW-timedelta(minutes=20)).isoformat(),
                             'bookmaker':'consensus'}}

class RefreshTests(unittest.TestCase):
    def test_exact_market_price_refreshed_without_changing_prediction(self):
        src={'matches':[fixture()]}
        ret,stats=refresh_prices(src,now=NOW,fetcher=lambda *args:real_quote())
        self.assertEqual(stats['exact_real_quotes_refreshed'],1)
        self.assertEqual(ret['matches'][0]['prediction']['odds'],1.4)
        self.assertEqual(src['matches'][0]['prediction']['odds'],1.25)
        self.assertEqual(ret['matches'][0]['prediction']['selection_key'],'OVER_15')
    def test_other_market_never_substituted(self):
        ret,stats=refresh_prices({'matches':[fixture()]},now=NOW,
            fetcher=lambda *args:{'BTTS_YES_FT':real_quote()['OU_1.5_OVER_FT']})
        self.assertEqual(stats['exact_real_quotes_refreshed'],0)
        self.assertEqual(ret['matches'][0]['prediction']['odds'],1.25)
    def test_unknown_and_stale_quotes_rejected(self):
        for origin,offset in [('mrxpronos_model',20),('bsd_consensus',400)]:
            with self.subTest(origin=origin,offset=offset):
                q=real_quote();q['OU_1.5_OVER_FT'].update({'origin':origin,
                    'updated_at':(NOW-timedelta(minutes=offset)).isoformat()})
                ret,stats=refresh_prices({'matches':[fixture()]},now=NOW,
                    fetcher=lambda *args:q)
                self.assertEqual(stats['exact_real_quotes_refreshed'],0)
    def test_match_started_and_future_day_not_probed(self):
        m=fixture();m['status']='live'
        ret,stats=refresh_prices({'matches':[m]},now=NOW,
            fetcher=lambda *args:self.fail('should not fetch'))
        self.assertEqual(stats['events_queried'],0)
        m=fixture();m['event_date']=(NOW+timedelta(days=1)).isoformat()
        _,stats=refresh_prices({'matches':[m]},now=NOW,
            fetcher=lambda *args:self.fail('should not fetch'))
        self.assertEqual(stats['events_queried'],0)
    def test_frozen_day_skips_provider_calls(self):
        _,stats=refresh_prices({'matches':[fixture()]},now=NOW,
            days={NOW.date().isoformat():{'selection_key':'OVER_15'}},
            fetcher=lambda *args:self.fail('should not fetch'))
        self.assertTrue(stats['already_selected'])
    def test_fetch_errors_never_turn_into_priced_prediction(self):
        ret,stats=refresh_prices({'matches':[fixture()]},now=NOW,
            fetcher=lambda *args: (_ for _ in ()).throw(ValueError('no odds')))
        self.assertEqual(stats['quote_errors'],1)
        self.assertEqual(ret['matches'][0]['prediction']['odds'],1.25)
    def test_limit_and_confidence_ordering(self):
        first=fixture();first['source_event_id']=123;first['id']='bsd:123'
        second=fixture();second['source_event_id']=456;second['id']='bsd:456'
        second['prediction']['conservative_probability']=94
        ids=[]
        _,stats=refresh_prices({'matches':[first,second]},now=NOW,limit=1,
            fetcher=lambda ident,*unused: (ids.append(ident) or real_quote()))
        self.assertEqual(ids,[456])
        self.assertEqual(stats['events_eligible_for_quote_probe'],2)

if __name__=='__main__': unittest.main()