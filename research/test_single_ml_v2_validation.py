import csv,sys,tempfile,unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_validation import (split_validate,wilson,independent_report)

class AuditTests(unittest.TestCase):
    def test_period_order(self):
        with self.assertRaises(ValueError):
            split_validate("2026-10-20","2026-10-10","2026-10-23")
        self.assertEqual(split_validate("2026-08-01","2026-09-01","2026-09-30")[1],date(2026,9,1))
    def test_wilson(self):
        self.assertEqual(wilson(0,0),None)
        lower,upper=wilson(5,10)
        self.assertLess(lower,50)
        self.assertGreater(upper,50)
    def test_identical_games_comparison_and_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"predictions.csv"
            keys=["model","date","id","actual_score","predicted_score","hit",
                  "top3_hit","top_probability","actual_probability","log_loss",
                  "history_latest_day","model_fit_latest_day","quoted_odds"]
            rows=[]
            import math
            for i in range(8):
                for name in ("machine_learning","machine_learning_direct"):
                    day=f"2026-09-{i+1:02d}"
                    correct=i%3==0 if name=="machine_learning" else i%2==0
                    rows.append(dict(model=name,date=day,id=str(i),actual_score="1:0",
                        predicted_score="1:0" if correct else "0:0",
                        hit=int(correct),top3_hit=int(correct),top_probability=.15,
                        actual_probability=.15 if correct else .04,
                        log_loss=-math.log(.15 if correct else .04),
                        history_latest_day=f"2026-08-{i+1:02d}",
                        model_fit_latest_day="2026-08-01",quoted_odds=""))
            with path.open("w",newline="") as f:
                w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
            result=independent_report(path,validation_start="2026-08-01",
                test_start="2026-09-01",test_end="2026-09-08",bootstrap_resamples=100)
            pair=result["paired_test_comparisons"]["machine_learning_direct"]
            self.assertEqual(pair["shared_games"],8)
            self.assertEqual(pair["paired_day_bootstrap"]["status"],"EVALUATED")
            self.assertIsNone(pair["reference"]["flat_stake_roi_pct"])
            with path.open("w",newline="") as f:
                w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
                rows[0]["history_latest_day"]="2026-09-01"
                w.writerows(rows)
            with self.assertRaisesRegex(ValueError,"LEAKAGE"):
                independent_report(path,validation_start="2026-08-01",
                    test_start="2026-09-01",test_end="2026-09-08")
if __name__=="__main__":unittest.main()
