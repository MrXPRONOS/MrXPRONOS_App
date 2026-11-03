"""Public exact-score archive allowlist and prospective-proof regression tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_public_site as builder

BASE = {
    "schema_version": "mrx-exact-top5-v1",
    "model": "machine_learning_v3_hybrid",
    "origin": "prospective_prematch",
    "status": "published",
    "date": "2026-11-04",
    "generated_at": "2026-11-03T21:00:00Z",
    "simple": [{
        "id": "sportsapipro:123", "home": "Home FC", "away": "Away FC",
        "league": "League", "kickoff_utc": "2026-11-04T15:00:00Z",
        "score": "1:0", "probability": 0.23,
    }],
    "grouped": [],
}


class PublicExactScoreArchiveTests(unittest.TestCase):
    def publish(self, entry):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            directory=root/"scores-exacts-daily"
            directory.mkdir()
            (directory/(entry["date"]+".json")).write_text(
                json.dumps(entry),encoding="utf8")
            with patch.object(builder,"ROOT",root):
                builder.copy_public_exact_scores(root/"published")
            return json.loads((root/"published"/"scores-exacts-daily"/
                               (entry["date"]+".json")).read_text(encoding="utf8"))

    def test_tomorrow_verified_at_previous_utc_day_is_allowed(self):
        copy=self.publish(BASE)
        self.assertEqual(copy["simple"][0]["id"],"sportsapipro:123")
        self.assertEqual(copy["generated_at"],"2026-11-03T21:00:00Z")

    def test_started_fixture_rejected_if_predicted_after_kickoff(self):
        bad=json.loads(json.dumps(BASE))
        bad["simple"][0]["kickoff_utc"]="2026-11-04T15:00:00Z"
        bad["generated_at"]="2026-11-04T17:00:00Z"
        with self.assertRaisesRegex(ValueError,"not prospectively"):
            self.publish(bad)

    def test_private_and_outcome_fields_rejected(self):
        bad=json.loads(json.dumps(BASE))
        bad["simple"][0]["actual_score"]="1:0"
        with self.assertRaisesRegex(ValueError,"Private"):
            self.publish(bad)

    def test_unavailable_publication_never_claims_picks(self):
        bad=json.loads(json.dumps(BASE))
        bad["status"]="unavailable"
        with self.assertRaisesRegex(ValueError,"invented"):
            self.publish(bad)


if __name__ == "__main__":
    unittest.main()
