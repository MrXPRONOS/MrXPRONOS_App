"""BSD V2 badge origin + visual rendering and topic-based Flash Foot tests."""
import unittest
from unittest.mock import patch
from datetime import datetime,timezone
from PIL import Image,ImageChops
from scripts import editorial_bsd_bridge,content_studio,template_cards

class Phase5EditorialTests(unittest.TestCase):
    def test_badge_url_only_from_matching_bsd_team(self):
        event={
            "id":"bsd:1001","source":"bsd",
            "event_date":"2026-10-13T16:00:00Z",
            "home_team":{"name":"Togo","logo":"https://r2.thesportsdb.com/images/media/team/badge/togo.png"},
            "away_team":{"name":"Ghana","logo_url":"https://images.fotmob.com/image_resources/logo/teamlogo/1121.png"},
            "home_logo":"https://evil.invalid/spoof.png",
        }
        self.assertEqual(editorial_bsd_bridge.badge_url(event,"home"),
                         "https://r2.thesportsdb.com/images/media/team/badge/togo.png")
        self.assertTrue(editorial_bsd_bridge.badge_url(event,"away"))
        now=datetime(2026,10,13,10,tzinfo=timezone.utc)
        article=editorial_bsd_bridge.factual_article(event,now)
        self.assertEqual(article["source"],"bsd")
        self.assertEqual(article["home_logo"],event["home_team"]["logo"])
        self.assertEqual(article["away_logo"],event["away_team"]["logo_url"])
        self.assertNotIn("evil.invalid",str(article))
    def test_reject_spoofed_badges(self):
        bad=[
            "http://r2.thesportsdb.com/badge.png",
            "https://r2.thesportsdb.com.evil.invalid/logo.png",
            "https://r2.thesportsdb.com:444/badge.png",
            "https://127.0.0.1/badge.png",
            "file:///etc/passwd",
            "https://localhost/logo.png",
        ]
        for u in bad:
            self.assertEqual(editorial_bsd_bridge.verified_badge_url(u),"")
            self.assertIsNone(content_studio.team_badge(u))
    def test_match_card_only_uses_verified_badges_when_both_exist(self):
        teamnames=("Togo","Ghana")
        path=("https://r2.thesportsdb.com/test1.png","https://images.fotmob.com/test2.png")
        badge=Image.new("RGBA",(80,80),(235,170,65,255))
        with patch.object(content_studio,"team_badge",return_value=badge) as mocked:
            im=content_studio.draw_cover(
                "Togo vs Ghana : fiche match BSD V2","match",(1200,630),0,
                match_teams=teamnames,match_logos=path)
            self.assertEqual(im.size,(1200,630))
            self.assertEqual(mocked.call_count,2)
        fallback=content_studio.draw_cover("Togo vs Ghana : fiche match BSD V2","match",
            (1200,630),0,match_teams=teamnames)
        self.assertIsNotNone(ImageChops.difference(im,fallback).getbbox())
    def test_flash_topic_classification_and_creative_difference(self):
        self.assertEqual(template_cards._flash_topic("Mercato : nouvelle signature"),"MERCATO")
        self.assertEqual(template_cards._flash_topic("Finale de la coupe"),"COMPÉTITION")
        self.assertEqual(template_cards._flash_topic("Le carton rouge"),"DISCIPLINE")
        names=["Mercato de football","Finale de la coupe","Match du jour","Carton rouge","Autre actualité"]
        arts=[template_cards._flash_editorial_illustration((900,490),name) for name in names]
        for im in arts:self.assertEqual(im.size,(900,490))
        self.assertIsNotNone(ImageChops.difference(arts[0],arts[1]).getbbox())
        self.assertIsNotNone(ImageChops.difference(arts[1],arts[3]).getbbox())

if __name__=="__main__":unittest.main()
