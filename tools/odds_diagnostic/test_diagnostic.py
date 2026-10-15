import unittest
from diagnostic import analyze, sample, numeric_odd
class DiagnosticTests(unittest.TestCase):
    def test_sportybet(self):
        r=analyze(sample("sportybet"),"sportybet")
        self.assertEqual(r["counts"],{"corners":1,"shots":1,"fouls":1})
        self.assertEqual([m["valid_odds"] for m in r["markets"]],[2,1,1])
    def test_numeric_xbet_not_mislabelled(self):
        r=analyze(sample("1xbet"),"1xbet")
        self.assertEqual(r["counts"],{"corners":0,"shots":0,"fouls":0})
        self.assertEqual(r["unmapped_numeric_markets"],2)
    def test_odd_validation(self):
        self.assertIsNone(numeric_odd("bad"))
        self.assertIsNone(numeric_odd("1.0"))
        self.assertEqual(numeric_odd("1.87"),1.87)
    def test_empty(self):
        r=analyze({"Value":[]},"1xbet")
        self.assertEqual(r["events"],0)
if __name__=="__main__":unittest.main()
