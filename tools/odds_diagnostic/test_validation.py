import unittest
from validation import validate, compare_snapshots
from diagnostic import sample
class ValidationTests(unittest.TestCase):
    def test_invalid_root(self):
        r=validate("invalid","sportybet")
        self.assertFalse(r["valid"])
        self.assertIn("root_not_object_or_list",r["findings"])
    def test_empty(self):
        r=validate({"Value":[]},"1xbet")
        self.assertFalse(r["valid"])
    def test_numeric_unknown(self):
        r=validate(sample("1xbet"),"1xbet")
        self.assertIn("unmapped_numeric_market_codes",r["findings"])
    def test_live_not_claimed(self):
        r=compare_snapshots(sample("sportybet"),sample("sportybet"),"sportybet",60)
        self.assertFalse(r["freshness_verified"])
    def test_example(self):
        r=validate(sample("sportybet"),"sportybet","prematch")
        self.assertTrue(r["valid"])
        self.assertNotIn("no_verified_target_odds",r["findings"])
if __name__=="__main__":unittest.main()
