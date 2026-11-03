"""Demonstrate identical real 11x11 Hybrid V3 grids from optimized training.

Heavy unrelated candidate fitting is stubbed equally in both paths, while
the genuine FormState, HistGB-grid, DC and past-OOS calibrations are exercised.
"""
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import numpy as np
import single_ml_v2 as ml
from single_ml_v3_checkpoint import load_checkpoint, forecast_from_checkpoint


class FixedPredictor:
    def __init__(self, value):
        self.value = value

    def predict(self, X):
        return np.full(X.shape[0], self.value, dtype=float)


class HybridV3Parity(unittest.TestCase):
    def test_native_grid_equals_fast_checkpoint(self):
        today = datetime.now(timezone.utc).date()
        yesterday = today - timedelta(days=1)
        start_day = yesterday - timedelta(days=480)
        historical = []
        for i in range(481):
            d = start_day + timedelta(days=i)
            historical.append(ml.Match(
                f"synthetic:{i}", d, "Parity league",
                "Parity home", "Parity away", i % 4, (i // 3) % 3))
        now = datetime.now(timezone.utc)
        kickoff = now + timedelta(hours=2)
        fixture = [{
            "id": "verified-fixture-parity",
            "league": "Parity league",
            "home": "Parity home", "away": "Parity away",
            "kickoff_utc": kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }]
        begin = max(date(2026, 10, 1), yesterday-timedelta(days=65))
        # Keep identical native V3 estimators in both runs to isolate the
        # production-only elimination of unrelated fits and scoring.
        def v3_fit(*args, **kwargs):
            return (FixedPredictor(1.5), FixedPredictor(1.05))
        with tempfile.TemporaryDirectory() as tmp, (
            patch.object(ml, "fit_hist_v3", side_effect=v3_fit),
            patch.object(ml, "train_ml", return_value=None),
            patch.object(ml, "train_direct_score", return_value=None),
            patch.object(ml, "fit_direct_v3", return_value=None),
            patch.object(ml, "fit_pair", return_value=None)
        ):
            original = Path(tmp) / "original"
            optimized = Path(tmp) / "optimized"
            kwargs = dict(max_eval=0, auto_tune=False, retrain_days=30,
                          v3_models=True, prospective_fixtures=fixture)
            ml.backtest(historical, begin, yesterday, str(original), **kwargs)
            key = os.urandom(32)
            checkpoint_path = Path(tmp) / "checkpoint.enc"
            ml.backtest(historical, begin, yesterday, str(optimized),
                        **kwargs, production_v3_only=True,
                        checkpoint_path=checkpoint_path, checkpoint_key=key)
            a = json.loads((original / "v3_prospective_raw.json").read_text())
            b = json.loads((optimized / "v3_prospective_raw.json").read_text())
            self.assertEqual(len(a["fixtures"]), 1)
            self.assertEqual(len(b["fixtures"]), 1)
            for name in ("model_fit_latest_day", "history_latest_day"):
                self.assertEqual(a["fixtures"][0][name], b["fixtures"][0][name])
            np.testing.assert_allclose(
                a["fixtures"][0]["grid"], b["fixtures"][0]["grid"],
                rtol=0, atol=1e-12)
            saved = load_checkpoint(checkpoint_path, key, expected_day=yesterday)
            from_checkpoint = forecast_from_checkpoint(saved, fixture)
            np.testing.assert_allclose(
                a["fixtures"][0]["grid"],
                from_checkpoint["fixtures"][0]["grid"],
                rtol=0, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
