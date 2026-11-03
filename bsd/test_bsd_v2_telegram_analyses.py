"""Offline Telegram Safe / 1.50+ publication and clean image tests."""
import tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from bsd_v2_public_tiers import SAFE,COTES15
from bsd_v2_telegram_analyses import (
    KIND, due,valid_analysis,caption,action_buttons,process
)
from bsd_v2_tier_visual import render_ultra,render_analysis

NOW=datetime(2026,11,3,13,57,tzinfo=timezone.utc)

def analysis(id,p,tier):
    return {
        "id":f"bsd-market-analysis:{id}:BTTS_YES",
        "event_date":(NOW+timedelta(minutes=90+id)).isoformat(),
        "date":NOW.date().isoformat(),
        "home_team":f"F.C. A & <{id}>","away_team":"Deuxième club",
        "league":"Test Liga","market_label":"Les deux équipes marquent : Oui",
        "selection_key":"BTTS_YES","model_probability":p,
        "odds":round(1/(p*1.06),3),"display_tier":tier,
        "analysis_telegram_opt_in":True,"analysis_only":True,
        "recommendation_eligible":False,"prediction_eligible":False,
        "do_not_send_to_telegram":True,"estimated_odds":True,
        "not_an_executable_bookmaker_quote":True,
        "overround_assumption":.06,
        "price_method":"probability_calibrated_plus_fixed_6pct",
        "odds_source":"mrxpronos_model","status":"upcoming",
    }

class LedgerStub:
    def __init__(self):self.claimed=set();self.marked=[]
    def claim(self,kind,ref,day):
        key=kind,ref,day
        if key in self.claimed:return False
        self.claimed.add(key);return True
    def mark(self,kind,ref,day,*,message_id):
        self.marked.append((kind,ref,day,message_id))

class AnalysisTelegramTests(unittest.TestCase):
    def test_two_category_due_and_legacy_optout(self):
        safe=analysis(1,.69,SAFE)
        plus=analysis(2,.60,COTES15)
        self.assertEqual([x["id"] for x in due([safe,plus],NOW)],
                         [safe["id"],plus["id"]])
        self.assertTrue(valid_analysis(safe,NOW))
        self.assertTrue(valid_analysis(plus,NOW))
        for patchfield in ({'recommendation_eligible':True},
                           {'analysis_telegram_opt_in':False},
                           {'do_not_send_to_telegram':False},
                           {'odds':1.20},{'odds_source':'bsd_consensus'},
                           {'model_probability':.70},{'status':'finished'}):
            self.assertFalse(valid_analysis({**safe,**patchfield},NOW))
    def test_custom_captions_are_public_and_do_not_show_internal_info(self):
        for item,title in [(analysis(1,.69,SAFE),'SAFE DU JOUR'),
                           (analysis(2,.60,COTES15),'COTES 1,50+ DU JOUR')]:
            text=caption(item)
            self.assertIn(title,text)
            self.assertIn('Cote théorique',text)
            self.assertIn('non proposée par un bookmaker',text)
            self.assertIn('&amp; &lt;',text)
            for forbidden in ('API_KEY','mrxpronos_model','BSD','mise','gains potentiels',
                              'calibration_samples','source_event_id','telegram_opt_in'):
                self.assertNotIn(forbidden,text)
        self.assertEqual(len(action_buttons()['inline_keyboard']),1)
    def test_dedup_and_counter_are_independent_from_existing_picks(self):
        rows=[analysis(1,.69,SAFE),analysis(2,.60,COTES15)]
        feed={"source":"bsd","model_version":"bsd-v2-isolated",
              "generated_at":NOW.isoformat(),"market_odds_analyses":rows,
              "matches":[{"category":"vip"}]}
        ledger=LedgerStub()
        with patch("bsd_v2_telegram_analyses.send_one",return_value=813) as send:
            first=process(feed,NOW,session=None,token="mock",chat_ids=["@test"],ledger=ledger)
            second=process(feed,NOW,session=None,token="mock",chat_ids=["@test"],ledger=ledger)
        self.assertEqual(first["sent"],2)
        self.assertEqual(first["safe_sent"],1)
        self.assertEqual(first["cotes15_sent"],1)
        self.assertEqual(second["sent"],0)
        self.assertEqual(second["already_claimed"],2)
        self.assertEqual(len(ledger.marked),2)
        self.assertTrue(all(row[0]==KIND for row in ledger.marked))
        self.assertEqual(send.call_count,2)
    def test_png_card_has_no_payment_or_internal_ledger(self):
        a=analysis(1,.69,SAFE)
        ultra={"category":"vip","recommendation_eligible":True,
            "home_team":"Club 1","away_team":"Club 2","league":"League",
            "event_date":a["event_date"],"prediction":{
                "type":"Moins de 3,5 buts","odds":1.20,"confidence":83.,
                "estimated_odds":True,"recommendation_eligible":True}}
        with tempfile.TemporaryDirectory() as folder:
            for fn,r in [(render_ultra,ultra),(render_analysis,a)]:
                target=fn(r,Path(folder)/("ultra.png" if fn==render_ultra else "safe.png"))
                self.assertGreater(target.stat().st_size,18000)
                with Image.open(target) as im:
                    self.assertEqual(im.size,(1080,1120))
                    self.assertEqual(im.format,"PNG")
if __name__=='__main__':unittest.main()
