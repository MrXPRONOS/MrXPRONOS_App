"""Offline safety/regression checks for V3 fast inference wiring."""
import inspect
import unittest
from pathlib import Path
from scripts import run_exact_scores_v3_daily as daily


class FastInferenceContractTests(unittest.TestCase):
    def test_fast_inference_never_calls_backtest_or_retraining(self):
        source = inspect.getsource(daily.fast_produce)
        self.assertIn("forecast_from_checkpoint(", source)
        self.assertIn("load_checkpoint(", source)
        self.assertNotIn("backtest(", source)
        self.assertNotIn("certified_rows(", source)
        self.assertNotIn("historical_daily_rows(", source)
        self.assertNotIn("fit_hist_v3(", source)

    def test_checkpoint_preparation_is_separate(self):
        text = Path("scripts/prepare_hybrid_v3_checkpoint.py").read_text(encoding="utf8")
        self.assertIn("production_v3_only=True", text)
        self.assertIn("checkpoint_path=path", text)
        self.assertIn("checkpoint_key=key", text)
        self.assertNotIn("scores-exacts.json", text)

    def test_training_scheduled_before_publication(self):
        prep = Path(".github/workflows/prepare-hybrid-v3-checkpoint.yml").read_text(encoding="utf8")
        publish = Path(".github/workflows/exact-scores-v3-daily.yml").read_text(encoding="utf8")
        self.assertIn("17 2 * * *", prep)
        self.assertIn("17 5,12 * * *", publish)
        self.assertIn("--fast-inference", publish)
        self.assertNotIn("lightgbm==", publish)
        self.assertNotIn("catboost==", publish)
        self.assertIn("score_v3_model_checkpoints/*.enc", prep)
        self.assertNotIn("score_v3_model_checkpoints/*.enc", publish)

    def test_private_checkpoint_never_added_to_public_builder(self):
        source = Path("scripts/build_public_site.py").read_text(encoding="utf8")
        self.assertNotIn("score_v3_model_checkpoints", source)


if __name__ == "__main__":
    unittest.main()
