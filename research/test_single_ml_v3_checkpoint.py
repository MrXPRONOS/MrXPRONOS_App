"""Checks for private V3 model checkpoints (no SportsData network calls)."""
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from cryptography.exceptions import InvalidTag
from single_ml_v2 import FormState
from single_ml_v3_checkpoint import save_checkpoint, load_checkpoint


class CheckpointSecurityTests(unittest.TestCase):
    def test_roundtrip_and_cutoff(self):
        # A fake fitted-model object is sufficient for testing encryption
        # and serialization; numerical equivalence is tested in CI separately.
        key = os.urandom(32)
        day = date(2026, 11, 2)
        state = FormState()
        state.last_ingested_day = day
        model = ("fitted-home", "fitted-away")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.enc"
            save_checkpoint(path, key, state=state, hist_model=model,
                            eleven_history=[], hybrid_history=[],
                            hybrid_weight=0.25, dc_rho=-0.04,
                            history_day=day, fit_day=day)
            result = load_checkpoint(path, key, expected_day=day)
            self.assertEqual(result["hist_model"], model)
            self.assertEqual(result["history_day"], day)
            self.assertEqual(result["state"].last_ingested_day, day)
            with self.assertRaises(InvalidTag):
                load_checkpoint(path, key, expected_day=date(2026, 11, 1))
            with self.assertRaises(InvalidTag):
                load_checkpoint(path, os.urandom(32), expected_day=day)
            blob = bytearray(path.read_bytes())
            blob[-1] ^= 1
            path.write_bytes(blob)
            with self.assertRaises(InvalidTag):
                load_checkpoint(path, key, expected_day=day)

    def test_invalid_key_and_history_day(self):
        key = os.urandom(32)
        state = FormState()
        state.last_ingested_day = date(2026, 11, 2)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                save_checkpoint(Path(tmp) / "bad.enc", b"bad", state=state,
                                hist_model=("a", "b"), eleven_history=[],
                                hybrid_history=[], hybrid_weight=0.25,
                                dc_rho=-0.04, history_day=date(2026, 11, 2),
                                fit_day=date(2026, 11, 2))
            with self.assertRaises(ValueError):
                save_checkpoint(Path(tmp) / "bad.enc", key, state=state,
                                hist_model=("a", "b"), eleven_history=[],
                                hybrid_history=[], hybrid_weight=0.25,
                                dc_rho=-0.04, history_day=date(2026, 11, 1),
                                fit_day=date(2026, 11, 1))


if __name__ == "__main__":
    unittest.main()
