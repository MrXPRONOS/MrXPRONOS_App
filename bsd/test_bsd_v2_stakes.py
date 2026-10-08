"""Tests de régression du barème de mises Telegram."""
import unittest
from bsd_v2_stakes import single_stake,combination_stake,gain_potentiel,money

class StakeTiersTests(unittest.TestCase):
    def test_single_boundaries(self):
        cases={
            1.20:500000,1.50:500000,1.99:500000,
            2.00:400000,2.49:400000,
            2.50:300000,2.99:300000,
            3.00:200000,3.99:200000,
            4.00:100000,7.50:100000,100.00:100000,
        }
        for odd,expected in cases.items():
            with self.subTest(odd=odd):
                self.assertEqual(single_stake(odd),expected)
                self.assertTrue(100000<=single_stake(odd)<=500000)

    def test_invalid_quotes_do_not_yield_fake_stakes(self):
        for bad in (None,True,False,0,1.19,101,float("nan"),float("inf"),"1.50"):
            with self.subTest(value=bad):
                self.assertIsNone(single_stake(bad))
        self.assertEqual(money(None),"—")

    def test_combo_amount_fixed_and_gross_returns(self):
        self.assertEqual(combination_stake(),250000)
        self.assertEqual(gain_potentiel(combination_stake(),1.725),431250)
        self.assertEqual(gain_potentiel(single_stake(1.5),1.5),750000)
        self.assertEqual(gain_potentiel(single_stake(2.0),2.0),800000)
        self.assertEqual(gain_potentiel(single_stake(3.0),3.0),600000)

if __name__=="__main__":
    unittest.main()
