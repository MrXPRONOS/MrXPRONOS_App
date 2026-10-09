"""Reference-screen ticket regression checks without BSD or Telegram network."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image
import requests

from bsd_v2_ticket_ui import (
    competition_name,competition_line,public_ref,render_single,render_combined,
    WIDTH,SINGLE_HEIGHT,COMBO_HEIGHT,WHITE,NAVY,ACCENT,
)
from bsd_v2_publish import league_name


class Offline:
    def get(self,*args,**kwargs):
        raise requests.RequestException("offline")


def game(num=4,league="Football",home="Club of Very Long Home Name",
         away="FC Very Long Away Team"):
    return {
        "id":f"bsd:{num}","source_event_id":num,
        "event_date":"2026-10-09T22:30:00+00:00",
        "home_team":home,"away_team":away,"league":league,
        "league_id":9,"status":"notstarted",
        "prediction":{"type":"1X","selection_key":"1X",
                      "odds":1.5,"odds_source":"bsd_consensus"}
    }


class ReferenceTicketTests(unittest.TestCase):
    def test_missing_league_does_not_duplicate_football(self):
        match=game()
        self.assertEqual(competition_name(match),"Compétition n° 9")
        self.assertEqual(competition_line(match),"Football · Compétition n° 9")
        match["league"]="Ligue Europa de l'UEFA"
        self.assertEqual(competition_line(match),"Football · Ligue Europa de l'UEFA")
        self.assertEqual(league_name({"league":"Football"}),None)
        self.assertEqual(league_name({"league_name":"Liga Portugal"}),"Liga Portugal")

    def test_public_reference_has_no_provider_prefix(self):
        self.assertEqual(public_ref({"id":"bsd:7279"}),"7279")
        self.assertEqual(public_ref({"id":"combo:123456789abcdef"}),"123456789ab")

    def test_all_four_ticket_variants_use_light_reference_layout(self):
        first=game()
        second=game(5,"Premier League","Another Extremely Long Team",
                    "Opponent United")
        combo={"id":"combo:123456789abcdef","legs":[first,second],
               "combined_odds":1.89,"event_date":first["event_date"]}
        with tempfile.TemporaryDirectory() as temp:
            from bsd_v2_card import render
            from bsd_v2_combo_card import render_combo
            cases=[
                (lambda p:render(first,p,session=Offline()),(WIDTH,SINGLE_HEIGHT)),
                (lambda p:render(first,p,session=Offline(),win=True),
                 (WIDTH,SINGLE_HEIGHT)),
                (lambda p:render({**first,"night_coupon":True},p,
                                 session=Offline()),(WIDTH,SINGLE_HEIGHT)),
                (lambda p:render_combo(combo,p,session=Offline()),
                 (WIDTH,COMBO_HEIGHT)),
            ]
            for index,(call,dimensions) in enumerate(cases):
                path=call(Path(temp)/f"coupon-{index}.png")
                with Image.open(path) as image:
                    self.assertEqual(image.format,"PNG")
                    self.assertEqual(image.size,dimensions)
                    self.assertEqual(image.getpixel((540,25)),(255,255,255))
                    self.assertGreater(path.stat().st_size,7000)

    def test_verified_football_badge_and_green_gain_rendered(self):
        from bsd_v2_ticket_ui import _verified_football_badge, SUCCESS, FOOTBALL_PNG
        self.assertEqual(SUCCESS,"#28A65A")
        with tempfile.TemporaryDirectory() as temp:
            from PIL import ImageDraw
            image=Image.new("RGB",(230,230),"#FFFFFF")
            draw=ImageDraw.Draw(image)
            _verified_football_badge(image,draw,100,100,58)
            self.assertEqual(image.getpixel((146,132)),(76,152,216))
            self.assertNotEqual(image.getpixel((100,100)),(255,255,255))
            with Image.open(FOOTBALL_PNG) as source:
                self.assertIn(source.mode,("RGBA","P"))
                self.assertTrue(source.info.get("transparency") is not None or source.mode=="RGBA")
            file=render_single({**game(),"home_score":2,"away_score":1},
                               Path(temp)/"winning.png",win=True,session=Offline())
            with Image.open(file) as final:
                green=(40,166,90)
                self.assertIn(green,final.crop((900,540,1080,660)).getdata())
                self.assertIn(green,final.crop((900,990,1080,1080)).getdata())

    def test_winning_and_upcoming_coupon_labels(self):
        from unittest.mock import patch
        import bsd_v2_ticket_ui as ui

        captions=[]
        def fake_write(_draw,text,_x,_y,**kwargs):
            captions.append(str(text))
        with patch.object(ui,"_draw",return_value=(fake_write,None,None,None)):
            ui._summary(None,price=1.75,stake=100000,won=True,paid=False)
            self.assertIn("Payé",captions)
            self.assertNotIn("Accepté",captions)
            captions.clear()
            ui._summary(None,price=1.75,stake=100000,won=True,paid=True)
            self.assertIn("Payé",captions)
            self.assertNotIn("Gagnant",captions)
            captions.clear()
            ui._summary(None,price=1.75,stake=100000,won=False,paid=False)
            self.assertIn("Accepté",captions)
            self.assertNotIn("Payé",captions)

    def test_expected_palette_and_no_bookmaker_acceptance_claim(self):
        import inspect
        import bsd_v2_ticket_ui as ui
        source=inspect.getsource(ui)
        self.assertIn("MR XPRONOS · PRONOSTIC",source)
        self.assertNotIn("Versé:",source)
        self.assertIn("Cotes:",source)
        self.assertIn("Gains potentiels:",source)
        self.assertIn("Accepté",source)
        self.assertIn('"Accepté"',source)
        self.assertIn('"Payé"',source)
        self.assertIn('payment_confirmed',source)
        self.assertEqual(WHITE,"#FFFFFF")
        self.assertEqual(NAVY,"#12375A")
        self.assertEqual(ACCENT,"#4C98D8")


if __name__=="__main__":
    unittest.main()
