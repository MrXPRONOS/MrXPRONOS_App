import unittest
from aiscore_live_probe import parse_tables, valid_quote, normalized

class AiScoreLiveTests(unittest.TestCase):
    def test_visible_corner_table(self):
        table={"rows":[
            ["1","X","2","Asian Handicap","Goals","Over","Under","Corners","Over","Under"],
            ["2.62","3.00","2.70","0","1.87","1.92","2","1.77","2.02","8.5","1.72","2.00"],
            ["2.80","3.00","2.62","0","1.97","1.82","2/2.5","1.95","1.85","9.5","2.10","1.66"]
        ]}
        self.assertEqual(parse_tables([table]),[
            {"total_corners":8.5,"over":1.72,"under":2.0},
            {"total_corners":9.5,"over":2.1,"under":1.66}
        ])
    def test_not_confuse_goal_totals(self):
        self.assertEqual(parse_tables([{"rows":[["Goals","Over","Under"],["2.5","1.80","2.02"]]}]),[])
    def test_no_empty_odds(self):
        self.assertEqual(valid_quote("8.5","-","-"),None)
        self.assertIsNone(valid_quote("8.5","1.00","2.15"))
        self.assertIsNone(valid_quote("9.5","abc","1.75"))
    def test_unicode(self):
        self.assertEqual(normalized("Águilas"),"aguilas")
if __name__=="__main__":unittest.main()
