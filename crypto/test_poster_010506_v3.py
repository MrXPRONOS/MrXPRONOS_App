"""Offline regression for premium posters 01/05/06: actual chart provenance.

Never send or edit Telegram messages. Check split provider fallback and captions.
"""
import unittest
from unittest.mock import patch
from crypto.test_channel_premium import get_sparkline
from crypto.production_seed_v1 import caption_for

class Response:
    def __init__(self,payload):
        self.payload=payload
    def raise_for_status(self):return None
    def json(self):return self.payload

class Poster010506Tests(unittest.TestCase):
    def chart(self):
        return [{"close":str(100+i*0.125)} for i in range(49)]
    def test_cryptocompare_source_and_backward_compat(self):
        with patch("crypto.test_channel_premium.requests.get",
                   return_value=Response({"Response":"Success","Data":{"Data":self.chart()}})) as req:
            found=get_sparkline("BTC",with_source=True)
            self.assertEqual(found[1],"CryptoCompare")
            self.assertEqual(len(found[0]),49)
            self.assertIsInstance(get_sparkline("BTC"),list)
        self.assertTrue(req.called)
    def test_coinbase_fallback_exact_source(self):
        candles=[[1800000000+i*3600,1,2,3,100+i*.12,1] for i in range(49)]
        def get(url,**kw):
            if "cryptocompare" in url:
                return Response({"Response":"Error"})
            return Response(list(reversed(candles)))
        with patch("crypto.test_channel_premium.requests.get",side_effect=get):
            found=get_sparkline("ETH",with_source=True)
        self.assertEqual(found[1],"Coinbase")
        self.assertEqual(len(found[0]),49)
    def test_no_history_not_faked(self):
        with patch("crypto.test_channel_premium.requests.get",
                   return_value=Response({"Response":"Error"})):
            with patch("crypto.test_channel_premium.os.getenv",return_value=""):
                self.assertIsNone(get_sparkline("SOL",with_source=True))
    def test_caption_contains_real_sources_and_periods(self):
        rows=[{"symbol":s,"price":100.1,"change":.8,"sparkline_source":v}
          for s,v in [("BTC","Coinbase"),("ETH","CryptoCompare"),
                      ("SOL","Coinbase"),("BNB","CoinGecko"),("XRP","Coinbase")]]
        rows[0]["fear_greed"]=59
        caption=caption_for(1,{"provider":"CoinPaprika","rows":rows})
        for phrase in ("CoinPaprika","Coinbase","CryptoCompare","CoinGecko",
                       "CoinLore","Alternative.me","24 h","48 h"):
            self.assertIn(phrase,caption)
        self.assertLessEqual(len(caption),1024)

if __name__=="__main__":
    unittest.main()
