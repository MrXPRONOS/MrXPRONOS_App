"""No fake diversity gain; correction requires chronological accuracy validation."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from single_exact_score_debias_study import choose,tally,frozen_fit,ONE_ONE,BASE
class TestOneOneDebias(unittest.TestCase):
    def test_penalty_only_impacts_one_one_odds(self):
        d={(1,1):.35,(1,0):.32,(0,0):.16,(0,1):.17}
        parts=(d,.68,.68)
        self.assertEqual(choose(parts,1.,1.)[0],ONE_ONE)
        self.assertEqual(choose(parts,1.,.8)[0],(1,0))
        with self.assertRaises(ValueError):choose(parts,1.,-2)
    def test_diversity_alone_cannot_mean_better_accuracy(self):
        d={(1,1):.35,(1,0):.32,(0,0):.16,(0,1):.17}
        rows=[((d,.68,.68),(1,1))]*10
        self.assertLess(tally(rows,(1.,.7))["one_one_predictions"],
                        tally(rows,BASE)["one_one_predictions"])
        self.assertLess(tally(rows,(1.,.7))["wins"],tally(rows,BASE)["wins"])
    def test_no_2024_means_no_activation(self):
        model=frozen_fit([])
        self.assertFalse(model["activated"])
        self.assertEqual(model["parameters"]["one_one_factor"],1.)
    def test_only_2024_training_and_validation(self):
        from datetime import datetime,timezone
        d={(1,1):.35,(1,0):.32,(0,0):.16,(0,1):.17}
        year24=[(datetime(2024,1,5,tzinfo=timezone.utc),
                 (d,.68,.68),(1,0)) for _ in range(140)]
        model=frozen_fit(year24)
        self.assertFalse(model["activated"])
if __name__=="__main__":unittest.main()
