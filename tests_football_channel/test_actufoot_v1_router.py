"""No-network tests for Actu Foot V1 topical distribution and D1 isolation."""
import json
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import actu_foot_d1_news as main_pub
import actufoot_v1_router as m

NOW=datetime(2026,11,22,11,37,tzinfo=timezone.utc)


class Classifier(unittest.TestCase):
    def story(self,title,category="Actualité",score=4):
        return {"title":title,"content":"Article de football confirmé par une source publique.","category":category,
                "editorial_score":score}
    def test_transfer_real_madrid_multilabel(self):
        self.assertGreaterEqual(m.destinations_for(self.story(
            "Officiel : le Real Madrid confirme le transfert de son attaquant","Mercato")),
            {"mercato","liga","flash"})
    def test_champions_context(self):
        self.assertIn("champions",m.destinations_for(self.story(
            "Ligue des champions : le PSG se qualifie pour la finale")))
    def test_premier_league(self):
        self.assertIn("premier",m.destinations_for(self.story(
            "Liverpool décroche une victoire en Premier League")))
    def test_liga(self):
        self.assertIn("liga",m.destinations_for(self.story(
            "Liga : le Real Madrid gagne contre le FC Barcelone")))
    def test_ligue1(self):
        self.assertIn("ligue1",m.destinations_for(self.story(
            "Ligue 1 : Marseille bat Monaco")))
    def test_africa_and_national(self):
        self.assertGreaterEqual(m.destinations_for(self.story(
            "CAN : le Sénégal bat le Maroc en qualification")),
            {"africa","national"})
    def test_national_europe(self):
        self.assertIn("national",m.destinations_for(self.story(
            "Équipe de France : liste de sélection pour le Mondial")))
    def test_scores(self):
        self.assertIn("scores",m.destinations_for(self.story(
            "Résultat final : Liverpool 2-1 Chelsea")))
    def test_debrief(self):
        self.assertIn("debrief",m.destinations_for(self.story(
            "Débrief du match Arsenal Chelsea : analyse de la possession")))
    def test_minor_official_not_flash(self):
        self.assertNotIn("flash",m.destinations_for(self.story(
            "Officiel : modification des horaires d'entraînement",score=1)))
    def test_rumour_not_flash(self):
        self.assertNotIn("flash",m.destinations_for(self.story(
            "Rumeur : le PSG pourrait officialiser une arrivée",score=5)))
    def test_minor_psg_injury_no_false_mercato(self):
        self.assertNotIn("mercato",m.destinations_for(self.story(
            "Blessure du PSG : le club devra s'activer au mercato",category="Mercato")))


class Delivery(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)
        image=self.path/"assets/images/footnews/test.jpg"
        image.parent.mkdir(parents=True)
        Image.new("RGB",(80,80),"blue").save(image)
        self.item={"slug":"news-a","title":"OFFICIEL : le Real Madrid confirme un transfert",
          "content":"Le Real Madrid annonce le recrutement officiel de son attaquant pour la saison. Les dirigeants ont confirmé cet accord.",
          "category":"Mercato","editorial_score":4,
          "published":(NOW-timedelta(minutes=12)).isoformat(),
          "link":"https://source.example/abc","source":"Foot Mercato",
          "image":"assets/images/footnews/test.jpg","image_origin":"source"}
        self.config={role:"@"+role+"NewsTelegram" for role in m.ROLES}
        self.patch_root=patch.object(main_pub,"ROOT",self.path)
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)
        self.ledger=Mock()
        def rows(kind,day,**kwargs):
            if kind==m.MAIN_KIND:
                return [{"ref_id":"-100MAIN:news-a","delivery_status":"sent"}]
            return []
        self.ledger.rows.side_effect=rows
        self.ledger.claim.return_value=True

    def check(self,item=None,*,main_is_sent=True,edits=True,send=None):
        if not main_is_sent:
            self.ledger.rows.side_effect=lambda kind,day,**kwargs: []
        enabled={role:self.config[role] for role in ("mercato","liga","flash")}
        editor=lambda item,**kwargs:item
        with patch.object(m,"verify_channels",return_value=(enabled,[])), \
             patch.object(m,"prepare",side_effect=editor if edits else m.EditorialHold("no_french")), \
             patch.object(m,"send_article",side_effect=send if send is not None else None,return_value=401) as posting:
            result=m.dispatch([item or self.item],NOW,config=self.config,token="test",
                main_chat="-100MAIN",ledger=self.ledger,session=Mock())
        return result,posting

    def test_main_confirmed_reaches_all_matching_specialists(self):
        result,post=self.check()
        self.assertEqual(result["main_confirmed"],1)
        self.assertEqual(result["sent"],3)
        self.assertEqual(post.call_count,3)
        self.assertEqual(set(call.args[2] for call in post.call_args_list),
                         {self.config[k] for k in ("mercato","liga","flash")})
        self.assertEqual(self.ledger.mark.call_count,9)
        self.assertEqual(self.ledger.release.call_count,0)

    def test_only_main_delivered_articles_can_be_multicasted(self):
        result,post=self.check(main_is_sent=False)
        self.assertEqual(result["sent"],0)
        post.assert_not_called()
        self.ledger.claim.assert_not_called()

    def test_per_destination_dedup(self):
        def rows(kind,day,**kwargs):
            if kind==m.MAIN_KIND:
                return [{"ref_id":"-100MAIN:news-a","delivery_status":"sent"}]
            if kind==m.POST_KIND:
                return [{"ref_id":self.config["mercato"]+":news-a",
                         "delivery_status":"sent"}]
            return []
        self.ledger.rows.side_effect=rows
        result,post=self.check()
        self.assertEqual(result["sent"],2)
        self.assertGreaterEqual(result["already_sent"],1)
        self.assertNotIn(self.config["mercato"],[call.args[2] for call in post.call_args_list])

    def test_delivery_timeout_is_never_released_and_other_channels_continue(self):
        def send(session,token,chat,item,image,link):
            if chat==self.config["mercato"]:
                raise TimeoutError("maybe delivered")
            return 402
        result,post=self.check(send=send)
        self.assertEqual(result["errors"],1)
        self.assertEqual(result["sent"],2)
        self.ledger.release.assert_not_called()
        self.assertEqual(self.ledger.claim.call_count,9)

    def test_missing_post_receipt_quarantined(self):
        result,post=self.check(send=lambda *args:None)
        self.assertEqual(result["sent"],0)
        self.assertEqual(result["errors"],3)
        self.ledger.release.assert_not_called()

    def test_editorial_failure_never_claims(self):
        result,post=self.check(edits=False)
        self.assertEqual(result["sent"],0)
        self.assertEqual(result["editorial_skipped"],1)
        self.ledger.claim.assert_not_called()
        post.assert_not_called()

    def test_dryrun_does_not_touch_d1_or_telegram(self):
        with patch.object(m,"D1Ledger",side_effect=AssertionError("network")):
            report=m.dispatch([self.item],NOW,dry_run=True,config=self.config)
        self.assertIn("mercato",report["routes"]["news-a"])

    def test_quotas_are_per_channel_not_global(self):
        def rows(kind,day,**kwargs):
            if kind==m.MAIN_KIND:
                return [{"ref_id":"-100MAIN:news-a","delivery_status":"sent"}]
            if kind==m.DAILY_KIND:
                return [{"ref_id":self.config["mercato"]+f":{i:02d}"}
                         for i in range(m.MAX_POSTS_PER_DAY)]
            return []
        self.ledger.rows.side_effect=rows
        result,post=self.check()
        self.assertEqual(result["sent"],2)
        self.assertNotIn(self.config["mercato"],[call.args[2] for call in post.call_args_list])

    def test_topic_preflight_failure_skips_only_that_channel(self):
        with patch.object(m,"verify_channels",return_value=(
             {x:self.config[x] for x in ("liga","flash")},["mercato"])),\
             patch.object(m,"prepare",side_effect=lambda item,**k:item),\
             patch.object(m,"send_article",return_value=42) as post:
            result=m.dispatch([self.item],NOW,config=self.config,token="bot",
                  main_chat="-100MAIN",ledger=self.ledger,session=Mock())
        self.assertEqual(result["preflight_failed"],["mercato"])
        self.assertEqual(result["sent"],2)

    def test_no_article_url_or_buttons_in_reused_format(self):
        with patch.object(main_pub,"post_photo",return_value=100) as send:
            main_pub.send_article(Mock(),"token","@x",self.item,
                                  self.path/"assets/images/footnews/test.jpg",
                                  self.item["link"])
        caption=send.call_args.args[4]
        self.assertIn("<b>",caption)
        self.assertIn("</b>\n\n<blockquote>",caption)
        self.assertIn("</blockquote>\n\n<i>🏷 Catégorie :",caption)
        self.assertIn("📰 Source : Foot Mercato",caption)
        self.assertNotIn("https://",caption)
        self.assertIsNone(send.call_args.args[5])


class Configuration(unittest.TestCase):
    def test_config_complete_and_disabled_until_real_destinations_verified(self):
        path=ROOT/"config/actufoot_v1_channels.json"
        raw=json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(raw["enabled"],bool)
        channels=m.load_config(path)
        self.assertEqual(set(channels),set(m.ROLES))
        self.assertEqual(len(set(channels.values())),10)
        self.assertNotIn("@actufoot_mrxp",channels.values())

    def test_duplicate_or_unknown_config_refused(self):
        path=ROOT/"config/actufoot_v1_channels.json"
        config=json.loads(path.read_text(encoding="utf-8"))
        config["channels"]["liga"]=config["channels"]["mercato"]
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/"bad.json"
            f.write_text(json.dumps(config),encoding="utf-8")
            with self.assertRaises(RuntimeError):
                m.load_config(f)

if __name__=="__main__":
    unittest.main()
