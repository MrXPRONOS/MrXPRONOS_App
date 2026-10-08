"""Regression tests for 2-match combined coupons and 2 picks per fixture."""
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import requests
from PIL import Image

from bsd_v2_combos import build_combos,due_combos
from bsd_v2_combo_card import render_combo
from bsd_v2_telegram import expand_tickets,combos_due
from bsd_v2_verify_telegram import validate

NOW=datetime(2026,10,8,12,0,tzinfo=timezone.utc)

def match(num,minutes,odd=1.25,market="OVER_15"):
    dt=NOW+timedelta(minutes=minutes)
    return {
        "id":"bsd:"+str(num),"source_event_id":num,"source":"bsd",
        "date":dt.date().isoformat(),"event_date":dt.isoformat(),
        "status":"notstarted","home_team":"Alpha United","away_team":"Beta City",
        "league":"Example League",
        "prediction":{"type":"Plus de 1.5 buts","selection_key":market,
            "odds":odd,"odds_source":"bsd_consensus","market":"goals"},
    }

class OfflineSession:
    def get(self,*a,**kw):
        raise requests.RequestException("No internet required in CI")

class CombosTests(unittest.TestCase):
    def test_two_different_fixtures_and_product_odds(self):
        a,b=match(1,30,1.25),match(2,50,1.58)
        coupons=build_combos([b,a])
        self.assertEqual(len(coupons),1)
        c=coupons[0]
        self.assertNotEqual(c["legs"][0]["id"],c["legs"][1]["id"])
        self.assertAlmostEqual(c["combined_odds"],1.975)
        self.assertAlmostEqual(c["potential_gain"],987500)
        self.assertEqual(c["id"],build_combos([a,b])[0]["id"])

    def test_due_only_within_hour_before_first_kickoff(self):
        coupons=build_combos([match(1,55),match(2,75)])
        self.assertEqual(len(due_combos(coupons,NOW)),1)
        self.assertEqual(len(due_combos(coupons,NOW-timedelta(minutes=15))),0)
        self.assertEqual(len(due_combos(coupons,NOW+timedelta(minutes=11))),0)

    def test_invalid_under45_low_price_and_missing_prices_refused(self):
        a=match(1,40)
        bad=match(2,55,1.19)
        self.assertEqual(build_combos([a,bad]),[])
        bad["prediction"]["odds"]=1.5
        bad["prediction"]["selection_key"]="UNDER_45"
        self.assertEqual(build_combos([a,bad]),[])
        bad["prediction"]["selection_key"]="BTTS_YES"
        bad["prediction"]["odds_source"]=None
        self.assertEqual(build_combos([a,bad]),[])

    def test_no_two_legs_from_same_fixture(self):
        a=match(1,40);b=match(1,55)
        self.assertEqual(build_combos([a,b]),[])

    def test_three_matches_yield_one_disjoint_combo(self):
        a,b,c=match(1,30),match(2,60),match(3,70)
        self.assertEqual(len(build_combos([a,b,c])),1)

    def test_two_independent_markets_have_separate_delivery_ids(self):
        a=match(17,75)
        a["predictions"]=[a["prediction"],{
            "type":"Les deux équipes marquent",
            "selection_key":"BTTS_YES","market":"btts",
            "odds":1.48,"odds_source":"bsd_consensus"}]
        tickets=expand_tickets(a)
        self.assertEqual(len(tickets),2)
        self.assertEqual(tickets[0]["id"],"bsd:17")
        self.assertNotIn("_telegram_selection_ref",tickets[0])
        self.assertEqual(tickets[1]["_telegram_selection_ref"],"bsd:17:BTTS_YES")

    def test_two_market_wins_are_verified_independently(self):
        from unittest.mock import patch
        fixture=match(17,-24*60)
        fixture["status"]="notstarted"
        fixture["predictions"]=[fixture["prediction"],{
            "selection_key":"BTTS_YES","type":"Les deux équipes marquent",
            "market":"btts","odds":1.56,"odds_source":"bsd_consensus"}]
        rows=[{"id":10,"ref_id":"-10012:bsd:17","ref_date":fixture["date"]},
              {"id":11,"ref_id":"-10012:bsd:17:BTTS_YES","ref_date":fixture["date"]}]
        official={"17":{"status":"finished","event_date":fixture["event_date"],
                        "home_score":2,"away_score":0}}
        class FakeHTTP:
            def __init__(self):self.patches=[]
            def patch(self,*args,**kwargs):
                self.patches.append(kwargs)
                class Response:
                    def raise_for_status(self):pass
                return Response()
        session=FakeHTTP()
        with patch("bsd_v2_verify_telegram.post_gain",return_value=411) as post:
            counts=validate({"matches":[fixture]},rows,official,NOW,
                            session,"token","https://test.supabase.co","key")
        self.assertEqual(counts["wins_sent"],1)
        self.assertEqual(counts["losses_silent"],1)
        self.assertEqual(post.call_count,1)
        self.assertEqual(len(session.patches),2)

    def test_combo_dark_image_generated_offline(self):
        combo=build_combos([match(1,40),match(2,50)])[0]
        with TemporaryDirectory() as directory:
            output=render_combo(combo,Path(directory)/"combo.png",
                                now=NOW,session=OfflineSession())
            with Image.open(output) as im:
                self.assertEqual(im.size,(1080,1560))
                self.assertEqual(im.format,"PNG")

if __name__=="__main__":
    unittest.main()
