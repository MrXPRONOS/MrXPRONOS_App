"""Integration contract against the real immutable research V3 opponent module.

This file is intentionally NOT named test_*.py because generic site checks do
not check out the research branch. The isolated CI workflow supplies model/.
No network requests or private historical datasets are required.
"""
from datetime import date
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "model" / "research"
if not RESEARCH.is_dir():
    raise RuntimeError("Genuine research model checkout required; never fake a model")
sys.path.insert(0, str(RESEARCH))
sys.path.insert(0, str(ROOT))

from single_ml_v2 import Match
from single_ml_v2_opponents import OpponentStrengthState, canonical_name
from scripts.run_exact_scores_v3_daily import quarantine_conflicting_provider_identities


class RealV3ProviderIdentityContract(unittest.TestCase):
    def test_real_opponent_model_rejects_raw_conflict_but_accepts_quarantine(self):
        original = Match(
            key="model:verified-first", day=date(2026, 11, 10),
            league="Premier League", home="Club A", away="Club B",
            hg=2, ag=1, home_id="src_sportsapipro_v1_allscores_40",
            away_id="src_sportsapipro_v1_allscores_59",
            competition_id="src_sportsapipro_v1_allscores_55")
        conflicting = Match(
            key="model:verified-next", day=date(2026, 11, 11),
            league="Different League", home="Unrelated Club", away="Club C",
            hg=1, ag=0, home_id="src_sportsapipro_v1_allscores_40",
            away_id="src_sportsapipro_v1_allscores_60",
            competition_id="src_sportsapipro_v1_allscores_55")

        unprotected = OpponentStrengthState()
        unprotected.add_day([original])
        with self.assertRaisesRegex(ValueError, "Conflicting provider ID"):
            unprotected.features(conflicting)

        rows, audit = quarantine_conflicting_provider_identities(
            [original, conflicting], normalizer=canonical_name)
        self.assertEqual(audit["total_matches"], 2)
        self.assertEqual(audit["ambiguous_club_ids"], 1)
        self.assertEqual(audit["ambiguous_competition_ids"], 1)
        self.assertEqual(audit["match_records_removed"], 0)
        self.assertIsNone(rows[0].home_id)
        self.assertIsNone(rows[1].home_id)
        self.assertIsNone(rows[0].competition_id)
        self.assertIsNone(rows[1].competition_id)
        self.assertEqual(original.home_id, "src_sportsapipro_v1_allscores_40")
        self.assertEqual(conflicting.home_id, "src_sportsapipro_v1_allscores_40")
        self.assertEqual(rows[0].hg, original.hg)
        self.assertEqual(rows[1].ag, conflicting.ag)

        protected = OpponentStrengthState()
        protected.add_day([rows[0]])
        features, quality = protected.features(rows[1])
        self.assertEqual(quality["home"]["verified_global_id"], False)
        self.assertEqual(quality["away"]["verified_global_id"], True)
        self.assertGreater(features.size, 0)

    def test_unchanged_verified_identity_keeps_cross_competition_history(self):
        first = Match(
            key="verified:a", day=date(2026, 11, 10),
            league="Premier League", home="Same Club", away="Club B",
            hg=2, ag=1, home_id="src_sportsapipro_v1_allscores_40",
            away_id="src_sportsapipro_v1_allscores_59",
            competition_id="src_sportsapipro_v1_allscores_55")
        second = Match(
            key="verified:b", day=date(2026, 11, 11),
            league="Premier League", home="Same Club", away="Club C",
            hg=1, ag=0, home_id="src_sportsapipro_v1_allscores_40",
            away_id="src_sportsapipro_v1_allscores_60",
            competition_id="src_sportsapipro_v1_allscores_55")
        rows, audit = quarantine_conflicting_provider_identities(
            [first, second], normalizer=canonical_name)
        self.assertEqual(rows, [first, second])
        self.assertEqual(audit["matches_using_local_fallback"], 0)


if __name__ == "__main__":
    unittest.main()
