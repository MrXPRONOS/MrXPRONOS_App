import unittest
from aiscore_grid_parser import extract_corner_grid

class VisualGridTests(unittest.TestCase):
    def test_finds_corner_triplets_by_geometry(self):
        nodes = [
          {"text":"Goals","x":610,"y":400},{"text":"Over","x":730,"y":400},{"text":"Under","x":835,"y":400},
          {"text":"Corners","x":925,"y":400},{"text":"Over","x":995,"y":400},{"text":"Under","x":1082,"y":400},
          {"text":"2","x":610,"y":430},{"text":"1.77","x":730,"y":430},{"text":"2.02","x":835,"y":430},
          {"text":"8.5","x":925,"y":430},{"text":"1.72","x":995,"y":430},{"text":"2.00","x":1082,"y":430},
          {"text":"9.5","x":925,"y":470},{"text":"2.10","x":995,"y":470},{"text":"1.66","x":1082,"y":470},
        ]
        self.assertEqual(extract_corner_grid(nodes),[
          {"total_corners":8.5,"over":1.72,"under":2.0},
          {"total_corners":9.5,"over":2.1,"under":1.66}
        ])
    def test_do_not_read_goal_prices_as_corners(self):
        nodes=[{"text":"Goals","x":600,"y":400},{"text":"Over","x":700,"y":400},
               {"text":"Under","x":800,"y":400},{"text":"2.5","x":600,"y":430},
               {"text":"1.85","x":700,"y":430},{"text":"2.00","x":800,"y":430}]
        self.assertEqual(extract_corner_grid(nodes),[])
    def test_no_fake_rows(self):
        self.assertEqual(extract_corner_grid([{"text":"Corners","x":900,"y":400},
          {"text":"Over","x":970,"y":400},{"text":"Under","x":1050,"y":400},
          {"text":"8.5","x":900,"y":430},{"text":"-","x":970,"y":430},
          {"text":"-","x":1050,"y":430}]),[])
if __name__=="__main__":unittest.main()
