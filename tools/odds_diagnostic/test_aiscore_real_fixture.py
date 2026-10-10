import pathlib
import unittest
from aiscore_markup_parser import extract_corner_odds_from_html

FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "aiscore_user_captured_odds.html"

class RealAiScoreFixtureTests(unittest.TestCase):
    def test_full_user_html_exact_quotes_and_phases(self):
        html = FIXTURE.read_text(encoding="utf-8")
        self.assertGreater(len(html), 9000)
        self.assertEqual(extract_corner_odds_from_html(html), [
            {"phase":"opening","total_corners":8.5,"over":1.66,"under":2.10},
            {"phase":"prematch","total_corners":9.5,"over":2.00,"under":1.72},
            {"phase":"in_play","total_corners":8.5,"over":1.83,"under":1.83}
        ])

    def test_do_not_mislabel_opening_as_live(self):
        odds = extract_corner_odds_from_html(FIXTURE.read_text(encoding="utf-8"))
        live = [quote for quote in odds if quote["phase"]=="in_play"]
        self.assertEqual(len(live), 1)
        self.assertEqual((live[0]["total_corners"],live[0]["over"],live[0]["under"]),(8.5,1.83,1.83))

    def test_missing_live_phase_is_not_invented(self):
        html=FIXTURE.read_text(encoding="utf-8")
        html=html.replace('border-left-color:#5DB400;', 'border-left-color:#AAAAAA;')
        phases={quote["phase"] for quote in extract_corner_odds_from_html(html)}
        self.assertNotIn("in_play", phases)

if __name__=="__main__":
    unittest.main()
