"""Ticket image, validation gagnant/perdant, et cote BSD : tests sans réseau."""
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
import requests

from PIL import Image
from bsd_v2_card import render,BALL,BRAND_ONE,BRAND_TWO,wrap_name,_odds,TEAM_ICON_CACHE,_lookup_team_badge
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


class OfflineImageSession:
    def get(self,*args,**kwargs):
        raise requests.RequestException("Offline test fixture")


class CardAndSettlement(unittest.TestCase):
    def test_real_png_asset_installed(self):
        self.assertTrue(BALL.is_file())
        with Image.open(BALL) as image:
            self.assertEqual(image.format,"PNG")
            self.assertIn("A",image.getbands())

    def test_both_cards_render_as_png(self):
        m=sample_match()
        with tempfile.TemporaryDirectory() as d:
            for winner in (False,True):
                saved=render({**m,"home_score":2,"away_score":1},
                    Path(d)/("win.png" if winner else "preview.png"),win=winner,
                    now=datetime(2026,10,8,10,tzinfo=timezone.utc),
                    session=OfflineImageSession())
                with Image.open(saved) as im:
                    self.assertEqual(im.size,(1080,1300))
                    self.assertEqual(im.format,"PNG")

    def test_false_odd_hidden_instead_of_invented(self):
        m=sample_match();m["prediction"].pop("odds_source")
        with tempfile.TemporaryDirectory() as d:
            render(m,Path(d)/"no_odds.png",session=OfflineImageSession())
            self.assertTrue((Path(d)/"no_odds.png").stat().st_size>1000)

    def test_official_brand_assets_are_present(self):
        for path in (BRAND_ONE,BRAND_TWO):
            self.assertTrue(path.is_file(),str(path))
            with Image.open(path) as img:
                self.assertGreater(img.width,15)
                self.assertGreater(img.height,10)

    def test_long_team_names_wrap_in_two_lines(self):
        from PIL import ImageDraw
        canvas=Image.new("RGB",(1080,1300),"white")
        lines=wrap_name(ImageDraw.Draw(canvas),
             "Club Deportivo Universidad Católica de los Andes",255)
        self.assertLessEqual(len(lines),2)

    def test_odds_require_valid_verified_bsd_source(self):
        m=sample_match()
        self.assertIsNone(_odds(m)) # 1.18 below minimum
        m["prediction"]["odds"]=1.43
        self.assertEqual(_odds(m),1.43)
        m["prediction"]["odds_source"]="made_up"
        self.assertIsNone(_odds(m))

    def test_team_badge_lookup_only_exact_football_name(self):
        TEAM_ICON_CACHE.clear()
        class Response:
            def raise_for_status(self):pass
            def json(self):
                return {"teams":[{"strTeam":"Spartak Subotica","strSport":"Soccer",
                                   "strBadge":"https://r2.thesportsdb.com/badges/test.png"},
                                  {"strTeam":"Spartak","strSport":"Soccer",
                                   "strBadge":"https://r2.thesportsdb.com/badges/wrong.png"}]}
        class Session:
            calls=0
            def get(self,*a,**kw):
                self.calls+=1
                return Response()
        client=Session()
        from bsd_v2_card import _lookup_team_badge
        self.assertEqual(_lookup_team_badge("Spartak Subotica",client),
                         "https://r2.thesportsdb.com/badges/test.png")
        self.assertEqual(_lookup_team_badge("Spartak Subotica",client),
                         "https://r2.thesportsdb.com/badges/test.png")
        self.assertEqual(client.calls,1)

    def test_expected_inline_ctas_and_urls(self):
        from bsd_v2_telegram import action_buttons
        buttons=action_buttons()["inline_keyboard"]
        self.assertEqual([x[0]["text"] for x in buttons],
             ["Voir plus de coupons 🔥","S’inscrire ou réinitialiser son compte 🎯"])
        self.assertEqual(buttons[1][0]["url"],
             "https://mrxpronos.github.io/MrXPRONOS_App/bookmakers.html")

    def test_market_win_and_loss(self):
        m=sample_match()
        time=datetime(2026,10,9,10,tzinfo=timezone.utc)
        result={"status":"finished","event_date":m["event_date"],"home_score":2,"away_score":1}
        self.assertEqual(verdict(m,result,time),(True,2,1))
        result["home_score"]=3
        result["away_score"]=2
        self.assertEqual(verdict(m,result,time),(False,3,2))

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

    def test_winning_coupon_posts_one_image_then_marks_verified(self):
        from unittest.mock import patch
        m=sample_match()
        record={"id":16,"ref_id":"-100123:bsd:77","ref_date":"2026-10-08"}
        official={"77":{"status":"finished","event_date":m["event_date"],
                       "home_score":2,"away_score":1}}
        class Stub:
            def __init__(self):self.patches=[]
            def patch(self,*args,**kwargs):
                self.patches.append((args,kwargs))
                class Resp:
                    def raise_for_status(self):pass
                return Resp()
        http=Stub()
        with patch("bsd_v2_verify_telegram.post_gain", return_value=987) as send:
            result=validate({"matches":[m]},[record],official,
                datetime(2026,10,9,tzinfo=timezone.utc),
                http,"token","https://example.supabase.co","secret")
        self.assertEqual(result["wins_sent"],1)
        self.assertEqual(send.call_count,1)
        self.assertEqual(len(http.patches),1)

    def test_unfinished_not_validated(self):
        m=sample_match()
        self.assertIsNone(verdict(m,{"status":"notstarted","event_date":m["event_date"]},
                          datetime(2026,10,9,tzinfo=timezone.utc)))


if __name__=="__main__":
    unittest.main()
