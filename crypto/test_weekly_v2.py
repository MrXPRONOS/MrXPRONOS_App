"""Tests offline publication #07 — pas d'API ni d'envoi Telegram."""
import copy
import unittest
from datetime import datetime, timedelta, timezone
from crypto.export_weekly_v2 import (demo_report, from_paprika, from_lore, select_assets,
                                    parse_fear, validate_real, build_report)
UTC=timezone.utc

class WeeklyV2Tests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,18,10,tzinfo=UTC)

    def real(self):
        d=demo_report()
        d.update(status="real_data",is_demo=False,provider="CoinPaprika",
                 market_source="https://api.coinpaprika.com/v1/global")
        d["collected_at"]=self.now.isoformat()
        d["market_source_updated_at"]=self.now.isoformat()
        d["fear"]["observed_at"]=self.now.replace(hour=0).isoformat()
        return d

    def test_complete_report(self):
        validate_real(self.real(),self.now)

    def test_demo_is_never_publishable(self):
        with self.assertRaises(ValueError):
            validate_real(demo_report(),self.now)

    def test_staleness_rejected(self):
        d=self.real()
        d["collected_at"]=(self.now-timedelta(hours=3)).isoformat()
        with self.assertRaises(ValueError):validate_real(d,self.now)

    def test_tampered_sentiment_rejected(self):
        d=self.real()
        d["fear"]["delta_7d"]+=1
        with self.assertRaises(ValueError):validate_real(d,self.now)

    def test_bad_rank_order_rejected(self):
        d=self.real()
        d["winners"].reverse()
        with self.assertRaises(ValueError):validate_real(d,self.now)

    def test_coinlore_requires_timestamp(self):
        with self.assertRaises(ValueError):
            from_lore({"data":[],"info":{}},self.now)

    def test_paprika_incomplete_is_rejected(self):
        with self.assertRaises(ValueError):
            select_assets(from_paprika([],self.now))

    def test_fear_8_real_days(self):
        hist=[{"value":str(42+i),"timestamp":str(int((self.now.replace(hour=0)-timedelta(days=i)).timestamp()))} for i in range(8)]
        result=parse_fear({"metadata":{"error":None},"data":hist},self.now)
        self.assertEqual(result["delta_7d"],-7)
        rising=[{"value":str(42+i),"timestamp":str(int((self.now.replace(hour=0)-timedelta(days=7-i)).timestamp()))} for i in range(8)]
        self.assertEqual(parse_fear({"metadata":{"error":None},"data":rising},self.now)["delta_7d"],7)
        hist.pop()
        with self.assertRaises(ValueError):
            parse_fear({"metadata":{"error":None},"data":hist},self.now)

if __name__=="__main__":
    unittest.main()
