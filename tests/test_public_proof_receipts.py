"""Non-regression tests for first-publication proof receipts."""
import importlib.util
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "public_proof_receipts.py"
SPEC = importlib.util.spec_from_file_location("public_proof_receipts", MODULE)
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def feed(start_hours=3, result=False):
    kickoff = NOW + timedelta(hours=start_hours)
    return {"matches": [
        {
            "id": "match-opaque123456", "category": "pro",
            "home_team": "A", "away_team": "B", "league": "L1",
            "event_date": kickoff.isoformat(),
            "is_finished": result,
            "prediction": {
                "selection_key": "1X", "type": "1X", "confidence": 82,
                "odds": 1.44, "estimated_odds": True,
            },
        }
    ]}


class PublicProofTests(TestCase):
    def test_first_public_archive_and_later_settlement(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first"
            self.assertEqual(proof.build_proofs(first, None, feed(), NOW), 1)
            index = json.loads((first / "proofs/index.json").read_text())
            key = "match-opaque123456:1X"
            self.assertIn(key, index["receipts"])
            entry = index["receipts"][key]
            self.assertIn("/commits/gh-pages/proofs/receipts/", entry["github_history_url"])
            receipt = first / entry["receipt_url"]
            content = receipt.read_bytes()
            self.assertEqual(proof.validate_receipt(json.loads(content)), key)

            # A result never rewrites the original published selection.
            later = root / "later"
            self.assertEqual(proof.build_proofs(later, first, feed(result=True), NOW + timedelta(hours=5)), 1)
            copied = later / entry["receipt_url"]
            self.assertEqual(copied.read_bytes(), content)

    def test_cannot_backdate_finished_or_last_minute_predictions(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(proof.build_proofs(root, None, feed(start_hours=-1), NOW), 0)
            self.assertEqual(proof.build_proofs(root, None, feed(start_hours=0.1), NOW), 0)

    def test_tampered_existing_receipt_refuses_publish(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first"
            proof.build_proofs(first, None, feed(), NOW)
            receipt = next((first / "proofs/receipts").glob("*.json"))
            altered = json.loads(receipt.read_text())
            altered["snapshot"]["selection"]["confidence"] = 99
            receipt.write_text(json.dumps(altered))
            with self.assertRaises(ValueError):
                proof.build_proofs(root / "later", first, feed(), NOW + timedelta(hours=1))

    def test_missing_or_naive_publication_time_cannot_validate(self):
        record = {
            "schema": "mx-public-proof-v1",
            "snapshot": {
                "id": "match-opaque:1X",
                "recorded_at_utc": "2026-10-29T12:00:00",
                "kickoff_utc": "2026-10-29T14:00:00+00:00",
                "selection": {},
            },
        }
        record["sha256"] = proof.digest(record["snapshot"])
        with self.assertRaises(ValueError):
            proof.validate_receipt(record)
