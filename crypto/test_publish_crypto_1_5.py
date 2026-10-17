import unittest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from crypto.publish_crypto_1_5 import (
    clean_row, movers, selected_watch, format_prices, format_movers,
    format_fear, run_alerts, valid_timestamp
)

def sample_rows():
    symbols = ['BTC','ETH','SOL','BNB','XRP','ADA','DOGE','TRX','LINK','AVAX','DOT','UNI']
    return [dict(symbol=s,name=s,rank=i+1,price=100.0+i,change=(i+1)*(-1 if i%2 else 1),
                 volume=2_000_000) for i,s in enumerate(symbols)]

class TestCryptoPublisher(unittest.TestCase):
    def test_invalid_rows_filtered(self):
        self.assertIsNone(clean_row('BTC','Bitcoin',1,0,5,123))
        self.assertIsNone(clean_row('BTC','Bitcoin',1,10,float('nan'),123))
        self.assertIsNone(clean_row('BTC','Bitcoin',1,10,3,123,'2000-01-01T00:00:00Z'))
        self.assertIsNotNone(clean_row('BTC','Bitcoin',1,10,3,123))

    def test_timestamp(self):
        self.assertTrue(valid_timestamp(datetime.now(timezone.utc).isoformat()))
        self.assertFalse(valid_timestamp((datetime.now(timezone.utc)-timedelta(days=5)).isoformat()))

    def test_watch_and_posts(self):
        rows=sample_rows()
        self.assertEqual([r['symbol'] for r in selected_watch(rows)], ['BTC','ETH','SOL','BNB','XRP'])
        self.assertIn('Source : CoinLore',format_prices(rows,'CoinLore',datetime.now(timezone.utc)))
        self.assertIn('Fear & Greed',format_fear(22,datetime.now(timezone.utc),datetime.now(timezone.utc)))

    def test_top_five_and_filter(self):
        rows=sample_rows()
        self.assertEqual(len(movers(rows,'up')),5)
        self.assertEqual(len(movers(rows,'down')),5)
        self.assertIn('24 h',format_movers(rows,'CoinLore',datetime.now(timezone.utc),'up'))

    def test_alert_no_duplicate(self):
        rows=sample_rows()
        rows[0]['change']=6.0
        state={}
        now=datetime.now(timezone.utc)
        calls=[]
        with patch('crypto.publish_crypto_1_5.send',side_effect=lambda msg,dry: calls.append(msg)):
            run_alerts(state,rows,'CoinLore',now,False)
            first=len(calls)
            run_alerts(state,rows,'CoinLore',now,False)
            self.assertEqual(first,len(calls))
            rows[0]['change']=11.0
            run_alerts(state,rows,'CoinLore',now,False)
            self.assertEqual(first+1,len(calls))
        self.assertIn('BTC',state['alerts'])

if __name__=='__main__':
    unittest.main()
