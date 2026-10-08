"""Horaires et diffusion 'Coupons nuit' MR XPRONOS : Togo UTC."""
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from bsd_v2_night import night_date,batch_date,is_night_match,matches_for_night
from bsd_v2_telegram import due,combos_due,expand_tickets,process

def when(day,hour,minute=0):
    return datetime(2026,10,day,hour,minute,tzinfo=timezone.utc)

def fixture(num,dt,odd=1.35):
    return {"id":f"bsd:{num}","source":"bsd","source_event_id":num,
            "date":dt.date().isoformat(),"event_date":dt.isoformat(),
            "status":"notstarted","home_team":"A","away_team":"B",
            "prediction":{"type":"Double chance 1X","selection_key":"1X",
                          "odds":odd,"odds_source":"bsd_consensus"}}

class NightScheduleTests(unittest.TestCase):
    def test_cross_midnight_and_boundaries(self):
        self.assertIsNone(night_date(when(8,20,59)))
        self.assertEqual(night_date(when(8,21)),when(8,21).date())
        self.assertEqual(night_date(when(9,0)),when(8,21).date())
        self.assertEqual(night_date(when(9,5)),when(8,21).date())
        self.assertIsNone(night_date(when(9,5,1)))
        self.assertIsNone(night_date(when(9,8)))

    def test_campaign_at_20_only(self):
        night=[fixture(1,when(8,21)),fixture(2,when(8,23,30)),
               fixture(3,when(9,2)),fixture(4,when(9,5)),
               fixture(5,when(9,5,30)),fixture(6,when(8,20,30))]
        self.assertEqual([m["id"] for m in matches_for_night(night,when(8,20,5))],
                         ["bsd:1","bsd:2","bsd:3","bsd:4"])
        self.assertEqual(matches_for_night(night,when(8,19,50)),[])
        self.assertEqual(matches_for_night(night,when(8,21,5)),[])
        self.assertEqual(batch_date(when(8,20,50)),when(8,20).date())

    def test_night_excluded_from_hourly_dispatch(self):
        night=fixture(1,when(8,21,30))
        daytime=fixture(2,when(8,20,45))
        self.assertEqual([m["id"] for m in due([night,daytime],when(8,19,0),0,180)],
                         ["bsd:2"])

    def test_night_combo_pairing_only_within_night(self):
        matches=[fixture(1,when(8,21,30)),fixture(2,when(9,1,0)),
                 fixture(3,when(9,6,0))]
        self.assertEqual(combos_due(matches,when(8,20,35)),[])

    def test_independent_tickets_keep_distinct_ids(self):
        match=fixture(1,when(8,22))
        match["predictions"]=[match["prediction"],{
            "type":"Plus de 1.5 buts","selection_key":"OVER_15","odds":1.38,
            "odds_source":"bsd_consensus"}]
        self.assertEqual(len(expand_tickets(match)),2)

if __name__=="__main__":
    unittest.main()
