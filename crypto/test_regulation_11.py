"""Offline safety and source-scope tests for Actu Crypto #11 Africa TEST ONLY."""
import copy
import unittest
from datetime import datetime,timedelta,timezone
from crypto import export_regulation_11 as a

UTC=timezone.utc

class AfricaRegulation11Tests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(UTC)
    def article(self,title="Nigeria proposes a crypto asset licensing regulation for VASPs",
                source="CoinDesk",hours=2):
        domain=a.FEEDS[source][1]
        return a.parse_entry({
            "title":title,
            "link":"https://www."+domain+"/news/crypto-africa-regulation-2026",
            "published_parsed":(self.now-timedelta(hours=hours)).timetuple()
        },source,self.now)

    def test_8_existing_free_rss_feeds(self):
        self.assertEqual(len(a.FEEDS),8)
        self.assertNotIn("SIMULATION QA",a.FEEDS)
    def test_country_and_region_detection(self):
        samples=[
          ("Nigeria adopts a framework for crypto asset license requirements","NIGÉRIA"),
          ("BCEAO consults on new stablecoin regulation for banks","BCEAO"),
          ("UEMOA proposes a stablecoin licensing framework","UEMOA"),
          ("CEMAC launches crypto regulation for financial service providers","CEMAC"),
          ("Togo develops a crypto asset regulation framework","TOGO"),
          ("Ghana updates licensing regulation of virtual assets","GHANA"),
          ("Cameroon considers new regulation for virtual assets","CAMEROUN"),
          ("Senegal plans regulation for crypto service providers","SÉNÉGAL"),
          ("Niger approves digital asset regulation for financial institutions","NIGER"),
          ("ECOWAS consults on crypto regulation for cross border services","CEDEAO"),
        ]
        for title,region in samples:
            with self.subTest(region=region):
                self.assertEqual(a.regions_of(title),region)
    def test_niger_and_nigeria_do_not_mix(self):
        self.assertEqual(a.regions_of("Nigeria crypto license"),"NIGÉRIA")
        self.assertEqual(a.regions_of("Niger crypto license"),"NIGER")
    def test_non_africa_crypto_news_excluded(self):
        with self.assertRaises(ValueError):
            self.article("SEC proposes crypto asset licensing regulation for exchanges")
    def test_africa_non_crypto_not_selected(self):
        with self.assertRaises(ValueError):
            self.article("Ghana regulator announces new banking sector licensing policy")
    def test_africa_crypto_no_regulation_not_selected(self):
        with self.assertRaises(ValueError):
            self.article("Nigeria Bitcoin traders celebrate higher crypto market prices")
    def test_no_future_or_expired_rss(self):
        with self.assertRaises(ValueError):
            self.article(hours=120)
        with self.assertRaises(ValueError):
            self.article(hours=-2)
    def test_cannot_impersonate_whitelisted_publisher(self):
        with self.assertRaises(ValueError):
            a.parse_entry({"title":"Nigeria introduces cryptocurrency licensing regulation",
             "link":"https://coindesk.com.evil.example/news/nigeria-regulation",
             "published":(self.now-timedelta(hours=1)).isoformat()},
             "CoinDesk",self.now)
    def test_press_article_cannot_certify_crypto_legality(self):
        bad=self.article("Nigeria bans crypto asset transactions under new regulation")
        self.assertTrue(bad["high_impact"])
        with self.assertRaises(ValueError):
            a.build(bad,self.now)
    def test_real_source_is_attributed_and_reverified(self):
        article=self.article()
        doc=a.build(article,self.now)
        self.assertTrue(a.validate_real(doc,self.now))
        self.assertEqual(doc["source_count"],1)
        self.assertFalse(doc["legal_status_confirmed"])
        self.assertIn("NIGÉRIA",doc["main"]["region"])
        bad=copy.deepcopy(doc)
        bad["status"]="verified_legal_status"
        with self.assertRaises(ValueError):a.validate_real(bad,self.now)
        bad=copy.deepcopy(doc)
        bad["main"]["source"]="SEC"
        with self.assertRaises(ValueError):a.validate_real(bad,self.now)
    def test_tampered_country_or_fingerprint_is_rejected(self):
        d=a.build(self.article(),self.now)
        for key,value in [("fingerprint","fake")]:
            bad=copy.deepcopy(d)
            bad[key]=value
            with self.assertRaises(ValueError):a.validate_real(bad,self.now)
        bad=copy.deepcopy(d)
        bad["main"]["region"]="GHANA"
        with self.assertRaises(ValueError):a.validate_real(bad,self.now)
    def test_only_fresh_qualified_no_duplicates(self):
        candidate=self.article()
        chosen=a.select([candidate],{"sent_urls":[]},self.now)
        self.assertIsNotNone(chosen)
        self.assertIsNone(a.select([candidate],{"sent_urls":[a.fingerprint(candidate)]},self.now))
    def test_demo_must_never_validate_as_real(self):
        d=a.demo_report(self.now)
        self.assertTrue(d["is_demo"])
        self.assertIn("SIMULATION",d["main"]["source"])
        with self.assertRaises(ValueError):a.validate_real(d,self.now)
    def test_no_fabrication_when_rss_empty(self):
        self.assertIsNone(a.select([],{"sent_urls":[]},self.now))

if __name__=="__main__":
    unittest.main()
