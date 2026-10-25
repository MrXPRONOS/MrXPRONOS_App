import sys,unittest
from datetime import date
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_bsd_sportscore_2024 import parse_bsd,parse_sportscore,bsd_month,score_month
class Response:
    status_code=200
    content=b'fake'
    def __init__(self,payload):self.payload=payload
    def json(self):return self.payload
class Session:
    def __init__(self):self.calls=[]
    def get(self,url,*,params,**kwargs):
        self.calls.append((url,dict(params)))
        day=str(params.get('date') or params.get('date_from'))
        if 'bzzoiro' in url:
            return Response({'count':1,'results':[{
                 'id':22,'status':'finished','event_date':'2025-01-02T11:00:00Z',
                 'home_team':{'name':'A'},'away_team':{'name':'B'},
                 'league_id':10,'home_team_id':21,'away_team_id':22,
                 'home_score':2,'away_score':0}]})
        return Response({'count':1,'matches':[{
             'time':day+'T11:00:00Z','status':'finished','home':'C',
             'away':'D','home_score':0,'away_score':3,
             'competition':'League','url':'/m/C-D'}]})
class Tests(unittest.TestCase):
    def test_bsd_full_page_2025_id_and_year(self):
        sess=Session();record,status=bsd_month(sess,1,'FAKE',{'total':0},year=2025)
        self.assertEqual(len(record),1)
        self.assertEqual(record[0]['source_year'],2025)
        self.assertEqual(record[0]['source'],'bsd_v2_2025')
        self.assertEqual(status['pages'],1)
        self.assertEqual(sess.calls[0][1]['date_from'],'2025-01-01')
        self.assertEqual(sess.calls[0][1]['date_to'],'2025-01-31')
    def test_sportscore_scoped_all_january_2025(self):
        sess=Session()
        with mock.patch('single_ml_v2_bsd_sportscore_2024.time.sleep',return_value=None):
            rows,status=score_month(sess,1,{'total':0},year=2025)
        self.assertEqual(len(rows),31)
        self.assertEqual(status['days_failed'],0)
        self.assertEqual(status['days_queried'],31)
        self.assertEqual(rows[0]['source_year'],2025)
        self.assertEqual(rows[0]['source'],'sportscore_2025')
        self.assertEqual(sess.calls[-1][1]['date'],'2025-01-31')
if __name__=='__main__':unittest.main()
