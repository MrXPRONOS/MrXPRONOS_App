"""Offline regression tests for fully automatic, conservative #10."""
from __future__ import annotations
import copy
import json
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from crypto import export_regulation_v2 as reg
from crypto import regulation_10_auto as auto
from crypto import production_live_v1 as live

UTC=timezone.utc


class DummyResponse:
    def __init__(self,body,code=200,ctype="text/html",headers=None):
        self.status_code=code
        self.headers={"Content-Type":ctype, **(headers or {})}
        self.body=body.encode("utf8")
    def iter_content(self,chunk_size=8192):
        for i in range(0,len(self.body),chunk_size):
            yield self.body[i:i+chunk_size]
    def raise_for_status(self):
        if self.status_code>=400:
            raise ValueError("HTTP failure")
    def close(self):
        pass


class AutomaticRegulationTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(UTC)
        self.title="SEC proposes new regulation for crypto asset custody rules"
        self.row=reg.parse_entry({
            "title":self.title,
            "link":"https://www.sec.gov/newsroom/press-releases/crypto-custody-announcement",
            "published_parsed":(self.now-timedelta(hours=2)).timetuple(),
        },"SEC",self.now)
        self.html=("<html><head><meta property='og:title' content='"+
            self.title+"'></head><body><h1>"+self.title+
            "</h1><main><p>Official announcement regarding crypto asset custody rules."
            "</p></main></body></html>")
        self.html+= " "*400

    def check(self,url,**kwargs):
        self.assertEqual(url,self.row["url"])
        return DummyResponse(self.html)

    def test_official_rss_and_html_matching_allows_announcement(self):
        doc=auto.verify_publication(self.row,self.now,getter=self.check)
        self.assertEqual(auto.validate_auto(doc,self.now),doc)
        self.assertFalse(doc["legal_status_confirmed"])
        self.assertFalse(doc["auto_check"]["human_approval_required"])
        self.assertEqual(doc["status"],"official_announcement_verified")

    def test_unrelated_page_title_is_blocked(self):
        with self.assertRaises(ValueError):
            auto.verify_publication(self.row,self.now,
                getter=lambda url,**kw:DummyResponse(
                    "<html><h1>SEC appointment of new director</h1></html>"+" "*400))

    def test_editorial_rss_cannot_publish_alone(self):
        x=dict(self.row,source="CoinDesk",official=False)
        with self.assertRaises(ValueError):
            auto.verify_publication(x,self.now,getter=self.check)

    def test_url_schemes_and_attacker_hosts_rejected(self):
        for url in ("https://sec.gov.evil.example/newsroom/crypto-custody",
                    "http://www.sec.gov/newsroom/press-releases/crypto-news",
                    "https://sec.gov@evil.example/newsroom/crypto-announcement",
                    "https://www.sec.gov/"):
            with self.subTest(url=url):
                self.assertFalse(auto.is_authority_url("SEC",url))

    def test_redirects_leaving_regulator_blocked(self):
        def redirect(url,**kw):
            return DummyResponse("",302,headers={"Location":"https://evil.example/crypto"})
        with self.assertRaises(ValueError):
            auto.verify_publication(self.row,self.now,getter=redirect)

    def test_no_pdf_unvalidated_bodies_are_auto_posted(self):
        def pdf(url,**kw):
            return DummyResponse("A"*800,ctype="application/pdf")
        with self.assertRaises(ValueError):
            auto.verify_publication(self.row,self.now,getter=pdf)

    def test_too_old_official_feed_blocked(self):
        stale=dict(self.row,published_at=(self.now-timedelta(hours=52)).isoformat())
        with self.assertRaises(ValueError):
            auto.verify_publication(stale,self.now,getter=self.check)

    def test_wrong_jurisdiction_or_legal_claim_blocked(self):
        d=auto.verify_publication(self.row,self.now,getter=self.check)
        altered=copy.deepcopy(d)
        altered["primary"]["region"]="TOGO"
        with self.assertRaises(ValueError):
            auto.validate_auto(altered,self.now)
        altered=copy.deepcopy(d)
        altered["legal_status_confirmed"]=True
        with self.assertRaises(ValueError):
            auto.validate_auto(altered,self.now)
        altered=copy.deepcopy(d)
        altered["status"]="editorially_approved"
        with self.assertRaises(ValueError):
            auto.validate_auto(altered,self.now)

    def test_expired_html_verification_fails_closed(self):
        d=auto.verify_publication(self.row,self.now,getter=self.check)
        d["verified_at"]=(self.now-timedelta(hours=1)).isoformat()
        with self.assertRaises(ValueError):
            auto.validate_auto(d,self.now)

    def test_selects_next_eligible_official_not_media_or_duplicates(self):
        wrong=reg.parse_entry({
            "title":"EU approves new crypto stablecoin regulation for providers",
            "link":"https://www.coindesk.com/business/crypto-eu-regulation",
            "published_parsed":(self.now-timedelta(hours=1)).timetuple(),
        },"CoinDesk",self.now)
        state={"sent":{}}
        def fetcher(name,url,now):
            return [wrong,self.row] if name=="SEC" else []
        def verifier(row,now):
            return auto.verify_publication(row,now,getter=self.check)
        out=auto.collect(state,self.now,fetcher,verifier)
        self.assertEqual(out["primary"]["source"],"SEC")
        state["sent"]["reg10_official:"+out["fingerprint"]]={"message_id":777}
        self.assertIsNone(auto.collect(state,self.now,fetcher,verifier))

    def test_never_publish_when_no_first_party_announcements(self):
        self.assertIsNone(auto.collect({"sent":{}},self.now,
            fetcher=lambda name,url,now:[]))

    def test_real_production_mode_with_no_official_news_never_checks_bot(self):
        with patch.object(auto,"collect",return_value=None):
            with patch.object(live.seed,"read_state",return_value={"sent":{}}):
                with patch.object(live.seed,"verify_production_route") as route:
                    with patch.object(live,"record_send") as sender:
                        self.assertIsNone(live.execute("legal"))
        route.assert_not_called()
        sender.assert_not_called()

    def test_complete_production_path_uses_only_verified_document_and_dedupes(self):
        with TemporaryDirectory() as temporary:
            from pathlib import Path
            state={"sent":{}}
            doc=auto.verify_publication(self.row,self.now,getter=self.check)
            with patch.object(auto,"collect",return_value=doc) as collect:
                with patch.object(live.seed,"ROOT",Path(temporary)):
                    with patch.object(live.seed,"read_state",return_value=state):
                        with patch.object(live.seed,"verify_production_route",
                                          return_value={"id":-1009988}) as route:
                            with patch.object(live.seed,"run") as render:
                                with patch.object(live.seed,"validate_image") as validate:
                                    with patch.object(live,"record_send",return_value=702) as sender:
                                        with patch.object(live.seed,"write_state") as write:
                                            self.assertTrue(live.publish_automatic_regulation())
                                            self.assertFalse(live.publish_automatic_regulation())
            route.assert_called_once()
            render.assert_called_once_with("node","scripts/render_crypto_regulation_auto_v2.mjs")
            sender.assert_called_once()
            caption=sender.call_args.args[1]
            self.assertIn(self.row["title"],caption)
            self.assertIn(self.row["url"],caption)
            self.assertIn("statut juridique",caption.lower())
            self.assertEqual(len(state["sent"]),1)
            self.assertEqual(next(iter(state["sent"].values()))["message_id"],702)
            write.assert_called_once()
            validate.assert_called_once()
            self.assertTrue(collect.called)

    def test_legal_auto_mode_rejects_human_approval_only(self):
        self.assertNotIn("legal_approved",("legal",)+tuple(live.MODES))
        self.assertIsNone(live.execute.__defaults__)


if __name__=="__main__":
    unittest.main()
