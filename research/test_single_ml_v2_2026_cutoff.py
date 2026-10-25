"""Offline validations of October 2026 historical cutoff and source records."""
import sys,unittest
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_bsd_sportscore_2024 import bsd_month,score_month,collect
class Response:
    status_code=200
    content=b'fixture'
    def __init__(self,payload):self.payload=payload
    def json(self):return self.payload
class FakeSession:
    def __init__(self):self.calls=[]
    def get(self,url,*,params,**kwargs):
        self.calls.append((url,dict(params)))
        if 'bzzoiro' in url:
            return Response({'count':1,'results':[{
                'id':9101,'status':'finished',
                'event_date':'2026-10-24T16:00:00Z',
                'home_team':{'name':'Club A'},'away_team':{'name':'Club B'},
                'league_id':71,'home_score':3,'away_score':1
            }]})
        day=params['date']
        return Response({'count':1,'matches':[{
            'time':day+'T12:00:00Z','home':'Team C','away':'Team D',
            'home_score':1,'away_score':0,'competition':'National League',
            'status':'finished','url':'/match/team-c-d'
        }]})
class Historical2026Tests(unittest.TestCase):
    def test_bsd_october_does_not_request_25th_and_beyond(self):
        s=FakeSession()
        rows,a=bsd_month(s,10,'TEST',{'total':0},year=2026,through=date(2026,10,24))
        self.assertEqual(s.calls[0][1]['date_to'],'2026-10-24')
        self.assertEqual(rows[0]['date'],'2026-10-24')
        self.assertEqual(rows[0]['source'],'bsd_v2_2026')
        self.assertEqual(a['pages'],1)
    def test_sportscore_october_queries_exactly_24_days(self):
        s=FakeSession()
        with mock.patch('single_ml_v2_bsd_sportscore_2024.time.sleep',return_value=None):
            records,audit=score_month(s,10,{'total':0},year=2026,
                            through=date(2026,10,24))
        self.assertEqual(audit['days_queried'],24)
        self.assertEqual(audit['days_failed'],0)
        self.assertEqual(len(records),24)
        self.assertTrue(all(x['date']<='2026-10-24' for x in records))
        self.assertEqual(s.calls[-1][1]['date'],'2026-10-24')
        self.assertEqual(records[0]['source'],'sportscore_2026')
    def test_reject_no_cutoff_and_todays_date_without_api_calls(self):
        with self.assertRaises(ValueError):
            collect(year=2026)
        with self.assertRaises(ValueError):
            collect(year=2026,through=datetime.now(timezone.utc).date())
if __name__=="__main__":unittest.main()
