"""Migration BSD V2 : tests anti-régression pour site et calendrier Telegram."""
import unittest
from datetime import datetime, timezone, timedelta

from bsd_v2_publish import assemble, to_site, update_settlement
from bsd_v2_telegram import due


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,8,10,0,tzinfo=timezone.utc)

    def prediction(self, at, n=1):
        return {
            "id":"bsd:"+str(n),"source":"bsd","source_event_id":n,
            "date":at.date().isoformat(),"event_date":at.isoformat(),
            "home_team":"A","away_team":"B","status":"notstarted",
            "prediction":{"type":"Moins de 4.5 buts","selection_key":"UNDER_45","confidence":85},
        }

    def test_hourly_window_and_no_started_games(self):
        now=self.now
        a=self.prediction(now+timedelta(minutes=60),1)
        b=self.prediction(now+timedelta(minutes=119),2)
        c=self.prediction(now+timedelta(minutes=120),3)
        d=self.prediction(now+timedelta(minutes=59),4)
        e=self.prediction(now-timedelta(minutes=1),5)
        selected=due([a,b,c,d,e],now)
        self.assertEqual([m["id"] for m in selected],["bsd:1","bsd:2"])

    def test_all_eligible_picks_no_limit(self):
        fixtures=[self.prediction(self.now+timedelta(minutes=90),i) for i in range(35)]
        self.assertEqual(len(due(fixtures,self.now)),35)

    def test_settlement_follows_selected_market(self):
        m=self.prediction(self.now,11)
        m["status"]="notstarted"
        event={"status":"finished","event_date":m["event_date"],"home_score":3,"away_score":2}
        updated=update_settlement(m,event)
        self.assertTrue(updated["is_finished"])
        self.assertFalse(updated["verified_prediction"])
        self.assertEqual(updated["prediction"]["selection_key"],"UNDER_45")

    def test_wrong_kickoff_ignored(self):
        m=self.prediction(self.now,11)
        e={"status":"finished","event_date":(self.now+timedelta(hours=1)).isoformat(),
           "home_score":1,"away_score":0}
        self.assertIs(update_settlement(m,e),m)


if __name__=="__main__":
    unittest.main()
