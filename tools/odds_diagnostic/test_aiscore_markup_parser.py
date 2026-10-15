import unittest
from aiscore_markup_parser import extract_corner_odds_from_html

class AiScoreMarkupTests(unittest.TestCase):
    def test_three_phases_from_real_markup(self):
        html = """<div class="table flex-1 corner">
          <div class="head"><span>Canto</span><span>Mais de</span><span>Menos de</span></div>
          <div class="row box" style="border-left-color:#2196F3"><div class="flex w100">
          <div class="col"><span>8.5</span></div><div class="col"><span>1.66</span></div><div class="col"><span>2.10</span></div></div></div>
          <div class="row box" style="border-left-color:#FFBA5A"><div class="flex w100">
          <div class="col"><span>9.5</span></div><div class="col"><span>2.00</span></div><div class="col"><span>1.72</span></div></div></div>
          <div class="row box" style="border-left-color:#5DB400"><div class="flex w100">
          <div class="col"><span>8.5</span></div><div class="col"><span>1.83</span></div><div class="col"><span>1.83</span></div></div></div></div>"""
        self.assertEqual(extract_corner_odds_from_html(html), [
          {"phase":"opening","total_corners":8.5,"over":1.66,"under":2.1},
          {"phase":"prematch","total_corners":9.5,"over":2.0,"under":1.72},
          {"phase":"in_play","total_corners":8.5,"over":1.83,"under":1.83}
        ])
    def test_goals_ignored(self):
        self.assertEqual(extract_corner_odds_from_html('<div class="table flex-1 bs"><div class="row box" style="border-left-color:#5DB400"><div class="col">2.5</div><div class="col">1.80</div><div class="col">2.00</div></div></div>'),[])
    def test_missing_quote_ignored(self):
        self.assertEqual(extract_corner_odds_from_html('<div class="table corner"><div class="row box" style="border-left-color:#5DB400"><div class="col">8.5</div><div class="col">-</div><div class="col">-</div></div></div>'),[])

if __name__=="__main__":unittest.main()
