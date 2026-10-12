"""Régressions phase 2 hors réseau."""
import json,os,tempfile,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from PIL import Image
from scripts import editorial_bsd_bridge,editorial_queue,editorial_telegram,editorial_facebook,editorial_metrics,editorial_cleanup_audit
import fetch_foot_news

class EditorialPhase2Tests(unittest.TestCase):
    def test_bsd_filters_only_authentic_source(self):
        now=datetime(2026,10,12,12,tzinfo=timezone.utc)
        fixture={"id":"bsd:123","source":"bsd","event_date":"2026-10-13T18:30:00Z",
            "home_team":"Arsenal","away_team":"Chelsea","status":"notstarted",
            "prediction":{"selection_key":"OVER_15","label":"Plus de 1,5 buts"}}
        good={"source":"bsd","model_version":"bsd-v2-isolated","matches":[fixture]}
        self.assertEqual(len(editorial_bsd_bridge.select_matches(good,now)),1)
        self.assertEqual(editorial_bsd_bridge.select_matches({**good,"source":"legacy"},now),[])
        article=editorial_bsd_bridge.factual_article(fixture,now)
        self.assertIn("Arsenal",article["title"])
        self.assertNotIn("Score final BSD",article["content"])
        self.assertEqual(article["source"],"bsd")
    def test_match_bridge_is_idempotent(self):
        now=datetime(2026,10,12,10,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"data.json").write_text(json.dumps({"source":"bsd","model_version":"bsd-v2-isolated","matches":[
                {"source":"bsd","id":"bsd:42","event_date":"2026-10-13T19:00:00Z",
                 "home_team":"Togo","away_team":"Ghana","status":"notstarted"}]}),encoding="utf-8")
            (root/"articles.json").write_text("[]",encoding="utf-8")
            self.assertEqual(editorial_bsd_bridge.run(root,now,limit=4)["created"],1)
            self.assertEqual(editorial_bsd_bridge.run(root,now,limit=4)["created"],0)
            self.assertEqual(len(json.loads((root/"articles.json").read_text())),1)
    def test_preserve_news_visuals_after_refresh(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"news.json"
            p.write_text(json.dumps([{"link":"https://example.com/article","title":"Ancien",
             "image_url":"assets/images/editorial/test-og.webp","social_image":"assets/images/editorial/test-social.webp"}]),encoding="utf-8")
            with patch.object(fetch_foot_news,"NEWS_FILE",str(p)):
                fetch_foot_news.save_news([{"link":"https://example.com/article","title":"Nouveau",
                     "image":"assets/images/preview.jpg"}])
            item=json.loads(p.read_text())[0]
            self.assertEqual(item["image"],"assets/images/editorial/test-og.webp")
            self.assertIn("social_image",item)
    def test_telegram_never_reposts_or_queues_old_content(self):
        now=datetime(2026,10,12,12,tzinfo=timezone.utc)
        fresh={"id":"good","kind":"article","title":"Texte",
               "url":editorial_telegram.BASE+"articles/test/",
               "image":"assets/images/editorial/a.webp",
               "source_date":(now-timedelta(hours=2)).isoformat(),
               "platform_status":{"telegram":"not_requested"}}
        self.assertTrue(editorial_telegram.eligible(fresh,now))
        self.assertFalse(editorial_telegram.eligible({**fresh,"source_date":"2026-01-01T00:00:00Z"},now))
        self.assertFalse(editorial_telegram.eligible({**fresh,"platform_status":{"telegram":"sent"}},now))
        self.assertEqual(editorial_telegram.choose([fresh,fresh],now,1),[fresh])
        self.assertIn("utm_source=telegram",editorial_telegram.tagged_url(fresh))
    def test_telegram_send_succeeds_and_persists_ack(self):
        now=datetime(2026,10,12,12,tzinfo=timezone.utc)
        class Response:
            def raise_for_status(self):return None
            def json(self):return {"ok":True,"result":{"message_id":98}}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            im_path=root/"assets/images/editorial/test.webp";im_path.parent.mkdir(parents=True)
            Image.new("RGB",(1200,630),(2,22,33)).save(im_path,"WEBP")
            q=root/"queue.json"
            q.write_text(json.dumps([{"id":"good","kind":"article","title":"Un vrai article",
              "url":editorial_telegram.BASE+"articles/test/","image":"assets/images/editorial/test.webp",
              "source_date":now.isoformat(),"platform_status":{"telegram":"not_requested"}}]))
            with patch.dict(os.environ,{"EDITORIAL_TELEGRAM_BOT_TOKEN":"test","EDITORIAL_TELEGRAM_CHAT_ID":"-1"}):
                result=editorial_telegram.publish(q,root,True,now=now,request_post=lambda *a,**k:Response())
            self.assertEqual(result["sent"],1)
            self.assertEqual(json.loads(q.read_text())[0]["platform_status"]["telegram"],"sent")
    def test_facebook_requires_fresh_and_not_sent(self):
        now=datetime(2026,10,12,12,tzinfo=timezone.utc)
        item={"id":"test","kind":"conseil","title":"Conseil","source_date":now.isoformat(),
              "url":editorial_telegram.BASE+"conseils/test/","platform_status":{"facebook":"not_requested"}}
        self.assertTrue(editorial_facebook.eligible(item,now))
        self.assertFalse(editorial_facebook.eligible({**item,"platform_status":{"facebook":"sent"}},now))
    def test_facebook_post_ack_and_dedup(self):
        now=datetime(2026,10,12,12,tzinfo=timezone.utc)
        class Response:
            def raise_for_status(self):return None
            def json(self):return {"id":"page_123"}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);queue=root/"queue.json"
            queue.write_text(json.dumps([{"id":"test","title":"Nouvel article","kind":"article",
                "url":editorial_telegram.BASE+"articles/test/",
                "source_date":now.isoformat(),"platform_status":{"facebook":"not_requested"}}]))
            with patch.dict(os.environ,{"META_PAGE_ID":"1","META_PAGE_ACCESS_TOKEN":"token"}):
                sent=editorial_facebook.publish(queue,True,now,request_post=lambda *a,**k:Response())
            self.assertEqual(sent["sent"],1)
            self.assertEqual(json.loads(queue.read_text())[0]["platform_status"]["facebook"],"sent")
            second=editorial_facebook.publish(queue,False,now)
            self.assertEqual(second["sent"],0)

    def test_metrics_no_fictitious_traffic(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/"articles.json").write_text('[{"title":"Test"}]')
            result=editorial_metrics.collect(root)
            self.assertIsNone(result["real_clicks"])
            self.assertIn("articles.json",result["contents"])
    def test_prune_never_deletes_recent_or_referenced_image(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/"assets/images/editorial";folder.mkdir(parents=True)
            p=folder/"article-test-123-og.webp";p.write_bytes(b"test")
            (root/"articles.json").write_text(json.dumps([{"image_url":"assets/images/editorial/article-test-123-og.webp"}]))
            summary=editorial_cleanup_audit.scan(root,top=1,prune=True,min_age_days=30)
            self.assertTrue(p.exists())
            self.assertEqual(summary["deleted_count"],0)

if __name__=="__main__":unittest.main()
