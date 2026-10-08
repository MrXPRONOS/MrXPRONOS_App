"""Ticket image, validation gagnant/perdant, et cote BSD : tests sans réseau."""
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

from PIL import Image
from bsd_v2_card import render,BALL
from bsd_v2_verify_telegram import verdict,validate
from bsd_v2_publish import to_site


def sample_match():
    return {
        "id":"bsd:77","source":"bsd","source_event_id":77,
        "event_date":"2026-10-08T12:00:00+00:00","date":"2026-10-08",
        "home_team":"Equipe A","away_team":"Equipe B","league":"Test League",
        "status":"notstarted",
        "prediction":{"selection_key":"UNDER_45","type":"Moins de 4,5 buts",
                      "confidence":85,"odds":1.18,"odds_source":"bsd_consensus"},
    }


class CardAndSettlement(unittest.TestCase):
    def test_real_png_asset_installed(self):
        self.assertTrue(BALL.is_file())
        self.assertEqual(Image.open(BALL).format,"PNG")
        self.assertIn("A",Image.open(BALL).getbands())

    def test_both_cards_render_as_png(self):
        m=sample_match()
        with tempfile.TemporaryDirectory() as d:
            for winner in (False,True):
                saved=render({**m,"home_score":2,"away_score":1},
                    Path(d)/("win.png" if winner else "preview.png"),win=winner,
                    now=datetime(2026,10,8,10,tzinfo=timezone.utc))
                with Image.open(saved) as im:
                    self.assertEqual(im.size,(1080,1260))
                    self.assertEqual(im.format,"PNG")

    def test_false_odd_hidden_instead_of_invented(self):
        m=sample_match();m["prediction"].pop("odds_source")
        with tempfile.TemporaryDirectory() as d:
            render(m,Path(d)/"no_odds.png")
            self.assertTrue((Path(d)/"no_odds.png").stat().st_size>1000)

    def test_market_win_and_loss(self):
        m=sample_match()
        time=datetime(2026,10,9,10,tzinfo=timezone.utc)
        result={"status":"finished","event_date":m["event_date"],"home_score":2,"away_score":1}
        self.assertEqual(verdict(m,result,time),(True,2,1))
        result["home_score"]=3
        self.assertEqual(verdict(m,result,time),(False,3,1))

    def test_lost_coupon_never_sends_a_photo(self):
        m=sample_match()
        record={"id":15,"ref_id":"-100123:bsd:77","ref_date":"2026-10-08"}
        official={"77":{"status":"finished","event_date":m["event_date"],
                        "home_score":3,"away_score":2}}
        class Stub:
            def __init__(self):self.calls=[]
            def patch(self,*a,**kw):
                self.calls.append(("patch",a,kw))
                class Response:
                    def raise_for_status(self):pass
                return Response()
            def post(self,*a,**kw):
                raise AssertionError("Telegram must not receive a loss")
        client=Stub()
        result=validate({"matches":[m]},[record],official,
                 datetime(2026,10,9,tzinfo=timezone.utc),
                 client,"x","https://example.supabase.co","secret")
        self.assertEqual(result["losses_silent"],1)
        self.assertEqual(len(client.calls),1)
        self.assertEqual(client.calls[0][0],"patch")

    def test_unfinished_not_validated(self):
        m=sample_match()
        self.assertIsNone(verdict(m,{"status":"notstarted","event_date":m["event_date"]},
                          datetime(2026,10,9,tzinfo=timezone.utc)))


if __name__=="__main__":
    unittest.main()
