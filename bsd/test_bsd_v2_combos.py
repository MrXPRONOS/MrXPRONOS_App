"""Regression tests for 2-match combined coupons and 2 picks per fixture."""
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import requests
from PIL import Image

from bsd_v2_combos import build_combos,due_combos,combo_ledger_ref,parse_combo_ledger_ref
from bsd_v2_combo_card import render_combo
from bsd_v2_telegram import expand_tickets,combos_due
from bsd_v2_verify_telegram import validate,validate_combos,combo_verdict,COMBO_VALIDATION_KIND

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
    def test_model_quotes_pair_at_both_boundaries_without_singles(self):
        from bsd_v2_telegram import due
        a=match(51,90,1.20)
        b=match(52,105,1.50)
        a["prediction"].update({"odds_source":"mrxpronos_model","estimated_odds":True})
        b["prediction"].update({"odds_source":"mrxpronos_model","estimated_odds":True})
        self.assertEqual(due([a,b],NOW),[])
        self.assertEqual(expand_tickets(a),[])
        coupons=build_combos([a,b])
        self.assertEqual(len(coupons),1)
        self.assertEqual([leg["id"] for leg in coupons[0]["legs"]],["bsd:51","bsd:52"])
        self.assertAlmostEqual(coupons[0]["combined_odds"],1.80)

    def test_under_120_excluded_even_if_model_estimated(self):
        a=match(51,90,1.199)
        b=match(52,105,1.40)
        a["prediction"].update({"odds_source":"mrxpronos_model","estimated_odds":True})
        self.assertEqual(build_combos([a,b]),[])
        self.assertEqual(expand_tickets(a),[])

    def test_over_150_only_individual_and_unpaired_low_pick(self):
        from bsd_v2_telegram import due
        a=match(51,90,1.51)
        b=match(52,105,1.40)
        self.assertEqual([m["id"] for m in due([a,b],NOW)],["bsd:51"])
        self.assertEqual(len(expand_tickets(a)),1)
        self.assertEqual(build_combos([a,b]),[])

    def test_two_different_fixtures_and_product_odds(self):
        a,b=match(1,30,1.25),match(2,50,1.38)
        coupons=build_combos([b,a])
        self.assertEqual(len(coupons),1)
        c=coupons[0]
        self.assertNotEqual(c["legs"][0]["id"],c["legs"][1]["id"])
        self.assertAlmostEqual(c["combined_odds"],1.725)
        self.assertAlmostEqual(c["potential_gain"],431250)
        self.assertEqual(c["id"],build_combos([a,b])[0]["id"])

    def test_due_only_within_hour_before_first_kickoff(self):
        coupons=build_combos([match(1,55),match(2,75)])
        self.assertEqual(len(due_combos(coupons,NOW)),1)
        self.assertEqual(len(due_combos(coupons,NOW-timedelta(minutes=15))),0)
        self.assertEqual(len(due_combos(coupons,NOW+timedelta(minutes=11))),0)

    def test_invalid_under45_low_price_and_missing_prices_refused(self):
        a=match(1,40)
        bad=match(2,55,1.19)
        self.assertEqual(len(build_combos([a,bad])),0)
        bad["prediction"]["odds"]=1.5
        bad["prediction"]["selection_key"]="UNDER_45"
        self.assertEqual(build_combos([a,bad]),[])
        bad["prediction"]["selection_key"]="BTTS_YES"
        bad["prediction"]["odds_source"]=None
        self.assertEqual(build_combos([a,bad]),[])

    def test_strict_upper_limit_and_lower_than_120_allowed(self):
        a=match(1,55,1.12)
        b=match(2,75,1.35)
        self.assertEqual(len(build_combos([a,b])),0)
        a["prediction"]["odds"]=1.20
        self.assertEqual(len(build_combos([a,b])),1)
        b["prediction"]["odds"]=1.50
        self.assertEqual(len(build_combos([a,b])),1)
        b["prediction"]["odds"]=1.75
        self.assertEqual(build_combos([a,b]),[])
        b["prediction"]["odds"]=1.00
        self.assertEqual(build_combos([a,b]),[])

    def test_combo_selection_is_independent_of_primary_single_market(self):
        a=match(1,50,1.88)
        a["combo_prediction"]={"selection_key":"UNDER_35","odds":1.18,
                                "confidence":94.5,"odds_source":"bsd_consensus",
                                "type":"Moins de 3.5 buts","market":"goals"}
        b=match(2,55,1.38)
        coupons=build_combos([a,b])
        self.assertEqual(coupons,[])
        self.assertEqual(a["prediction"]["odds"],1.88)

    def test_no_two_legs_from_same_fixture(self):
        a=match(1,40);b=match(1,55)
        self.assertEqual(build_combos([a,b]),[])

    def test_three_matches_yield_one_disjoint_combo(self):
        a,b,c=match(1,30),match(2,60),match(3,70)
        self.assertEqual(len(build_combos([a,b,c])),1)

    def test_two_independent_markets_have_separate_delivery_ids(self):
        a=match(17,75,1.55)
        a["predictions"]=[a["prediction"],{
            "type":"Les deux équipes marquent",
            "selection_key":"BTTS_YES","market":"btts",
            "odds":1.58,"odds_source":"bsd_consensus"}]
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


    def test_combo_ledger_ref_contains_both_frozen_legs_and_roundtrips(self):
        combo=build_combos([match(1,40),match(2,50)])[0]
        ref=combo_ledger_ref("-10012",combo)
        parsed=parse_combo_ledger_ref(ref)
        self.assertIsNotNone(parsed)
        self.assertFalse(parsed["legacy"])
        self.assertEqual(parsed["chat"],"-10012")
        self.assertEqual(parsed["combo_id"],combo["id"])
        self.assertEqual([x["event_id"] for x in parsed["legs"]],["1","2"])
        self.assertEqual([x["selection_key"] for x in parsed["legs"]],["OVER_15","OVER_15"])

    def test_combo_verdict_waits_for_both_winners(self):
        combo=build_combos([match(1,-120),match(2,-60)])[0]
        first=combo["legs"][0]
        second=combo["legs"][1]
        events={
            "1":{"status":"finished","event_date":first["event_date"],"home_score":1,"away_score":1},
            "2":{"status":"notstarted","event_date":second["event_date"]},
        }
        self.assertIsNone(combo_verdict(combo,events))
        events["2"]={"status":"finished","event_date":second["event_date"],"home_score":2,"away_score":0}
        result=combo_verdict(combo,events)
        self.assertIsNotNone(result)
        self.assertTrue(result[0])
        self.assertTrue(all(type(x.get("home_score")) is int for x in result[1]))

    def test_combo_loss_settles_silently_as_soon_as_one_leg_fails(self):
        combo=build_combos([match(1,-120),match(2,-60)])[0]
        first=combo["legs"][0]
        events={
            "1":{"status":"finished","event_date":first["event_date"],"home_score":0,"away_score":0},
        }
        result=combo_verdict(combo,events)
        self.assertIsNotNone(result)
        self.assertFalse(result[0])

    def test_two_winning_legs_send_one_verified_combo_and_mark_completion(self):
        combo=build_combos([match(1,-120),match(2,-60)])[0]
        ref=combo_ledger_ref("-10012",combo)
        row={"id":55,"ref_id":ref,"ref_date":combo["date"],"validation_sent":False}
        data={"source":"bsd","matches":combo["legs"]}
        events={}
        for leg in combo["legs"]:
            ident=str(leg["source_event_id"])
            events[ident]={"status":"finished","event_date":leg["event_date"],
                           "home_score":2,"away_score":0}
        class Response:
            def __init__(self,payload=None):self.payload=[] if payload is None else payload
            def raise_for_status(self):pass
            def json(self):return self.payload
        class FakeHTTP:
            def __init__(self):self.posts=[];self.patches=[]
            def post(self,*args,**kwargs):
                self.posts.append(kwargs)
                return Response([{"id":99}])
            def patch(self,*args,**kwargs):
                self.patches.append(kwargs)
                return Response([])
        session=FakeHTTP()
        with patch("bsd_v2_verify_telegram.post_combo_gain",return_value=777) as send:
            result=validate_combos(data,[row],events,session,"token",
                                   "https://test.supabase.co","key")
        self.assertEqual(result["combo_wins_sent"],1)
        self.assertEqual(send.call_count,1)
        self.assertEqual(len(session.posts),1)
        self.assertEqual(session.posts[0]["json"]["kind"],COMBO_VALIDATION_KIND)
        self.assertEqual(len(session.patches),1)

    def test_combo_with_one_pending_leg_does_not_send_or_complete(self):
        combo=build_combos([match(1,-120),match(2,-60)])[0]
        row={"id":55,"ref_id":combo_ledger_ref("-10012",combo),
             "ref_date":combo["date"],"validation_sent":False}
        data={"source":"bsd","matches":combo["legs"]}
        first=combo["legs"][0]
        events={"1":{"status":"finished","event_date":first["event_date"],
                     "home_score":2,"away_score":0}}
        class FakeHTTP:
            def post(self,*a,**kw):raise AssertionError("must not complete pending combo")
            def patch(self,*a,**kw):raise AssertionError("must not patch pending combo")
        with patch("bsd_v2_verify_telegram.post_combo_gain") as send:
            result=validate_combos(data,[row],events,FakeHTTP(),"token",
                                   "https://test.supabase.co","key")
        self.assertEqual(result["combo_pending"],1)
        send.assert_not_called()

    def test_combo_dark_image_generated_offline(self):
        combo=build_combos([match(1,40),match(2,50)])[0]
        with TemporaryDirectory() as directory:
            output=render_combo(combo,Path(directory)/"combo.png",
                                now=NOW,session=OfflineSession())
            with Image.open(output) as im:
                self.assertEqual(im.size,(1080,1580))
                self.assertEqual(im.format,"PNG")

if __name__=="__main__":
    unittest.main()
