"""Strict public tier names: avoid 1.50 boundary errors or a fake Ultra Safe."""
import unittest
from bsd_v2_public_tiers import (
    ULTRA,SAFE,COTES15,tier_for_record,tier_for_price,public_category_title,
)
class PublicTierTests(unittest.TestCase):
    def test_odds_boundaries(self):
        for odds,tier in [(1.20,None),(1.30,None),(1.301,SAFE),
                          (1.40,SAFE),(1.50,SAFE),(1.501,COTES15),
                          (2.0,COTES15),(2.001,None),(float('nan'),None)]:
            with self.subTest(odds=odds):
                self.assertEqual(tier_for_price(odds),tier)
    def test_existing_pro_vip_are_ultra_even_at_120(self):
        for cat in ('pro','vip'):
            record={"category":cat,"recommendation_eligible":True,
                    "prediction":{"recommendation_eligible":True,
                                  "confidence":79,"odds":1.20}}
            self.assertEqual(tier_for_record(record),ULTRA)
            self.assertIsNone(tier_for_record({**record,"recommendation_eligible":False}))
    def test_analyses_never_ultra(self):
        for price,tier in [(1.35,SAFE),(1.5,SAFE),(1.75,COTES15)]:
            r={"analysis_only":True,"recommendation_eligible":False,
               "odds":price}
            self.assertEqual(tier_for_record(r),tier)
            self.assertIsNone(tier_for_record({**r,"recommendation_eligible":True}))
    def test_user_titles(self):
        self.assertEqual(public_category_title(ULTRA),'ULTRA SAFE DU JOUR')
        self.assertEqual(public_category_title(SAFE),'SAFE DU JOUR')
        self.assertEqual(public_category_title(COTES15),'COTES 1,50+ DU JOUR')
        self.assertIn('DE LA NUIT',public_category_title(ULTRA,night=True))
if __name__=='__main__':unittest.main()
