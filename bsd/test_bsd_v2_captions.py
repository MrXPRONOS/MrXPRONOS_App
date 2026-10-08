"""Offline smoke tests for Telegram styled HTML captions."""
import unittest
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from unittest.mock import patch
from bsd_v2_captions import PARSE_MODE, MAX_CAPTION_LENGTH, single_caption, combo_caption, gain_caption
from bsd_v2_telegram import send_one, send_combo
from bsd_v2_verify_telegram import post_gain


def fixture(home="A & B <FC>",away="O'Connor > United",market="Plus de 1,5 <buts>"):
    return {"id":"bsd:81","home_team":home,"away_team":away,
            "event_date":"2026-10-08T22:15:00+00:00",
            "prediction":{"type":market,"odds":1.55,"selection_key":"CUSTOM_MARKET",
                          "odds_source":"bsd_consensus"}}


class CaptionParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags=[]
    def handle_starttag(self,tag,attrs):
        self.tags.append(tag)


class CaptionTests(unittest.TestCase):
    def test_day_and_night_have_distinct_headlines(self):
        match=fixture()
        day=single_caption(match)
        night=single_caption(match,night=True)
        self.assertIn("Coupon du jour",day)
        self.assertNotIn("Coupons nuit",day)
        self.assertIn("Coupons nuit",night)
        for caption in (day,night):
            self.assertIn("<b>",caption)
            self.assertIn("<i>",caption)
            self.assertIn("<blockquote>",caption)
            self.assertIn("A &amp; B &lt;FC&gt;",caption)
            self.assertIn("O'Connor &gt; United",caption)
            self.assertIn("Plus de 1,5 &lt;buts&gt;",caption)
            self.assertLessEqual(len(unescape(caption)),MAX_CAPTION_LENGTH)
            self.assertEqual(PARSE_MODE,"HTML")

    def test_combo_caption_has_both_legs_with_stake_and_total(self):
        one=fixture()
        two=fixture(home="Deportivo",away="PSG",market="BTTS Oui")
        two["prediction"]["odds"]=1.32
        combo={"legs":[one,two],"combined_odds":2.046,"event_date":one["event_date"]}
        for night in (False,True):
            caption=combo_caption(combo,night=night)
            self.assertIn("250 000 F CFA",caption)
            self.assertIn("2,05",caption)
            self.assertIn("Deportivo",caption)
            self.assertIn("A &amp; B",caption)
            self.assertIn("<blockquote>",caption)
            self.assertLessEqual(len(unescape(caption)),MAX_CAPTION_LENGTH)

    def test_winning_caption_not_claiming_real_cash(self):
        match={**fixture(),"home_score":2,"away_score":0}
        caption=gain_caption(match)
        self.assertIn("PRONOSTIC GAGNANT",caption)
        self.assertIn("2–0",caption)
        self.assertIn("<blockquote>",caption)
        self.assertIn("sans attestation de pari encaissé",caption)

    def test_all_captions_handle_long_escaped_team_names(self):
        match=fixture(home="<Hello>&"*25,away="A & B"*20,market="Over &"*30)
        combo={"legs":[match,match],"combined_odds":1.5,"event_date":match["event_date"]}
        for caption in [single_caption(match),combo_caption(combo),gain_caption(match)]:
            self.assertLessEqual(len(unescape(caption)),MAX_CAPTION_LENGTH)
            parser=CaptionParser()
            parser.feed(caption)
            self.assertTrue(set(("b","i","blockquote")).issubset(set(parser.tags)))

    def test_image_send_paths_apply_telegram_html_parse_mode(self):
        # Source checks protect against omission on any of the three send paths.
        import inspect
        for action in (send_one,send_combo,post_gain):
            source=inspect.getsource(action)
            self.assertIn('"parse_mode":PARSE_MODE',source)


if __name__=="__main__":
    unittest.main()
