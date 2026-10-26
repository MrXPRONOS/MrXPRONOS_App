"""Synthetic-only regression tests for private multisource identity downgrade."""
import unittest
from single_ml_v2_multisource import safe_source_identities

def row(day, home, hid, away="Away", aid="900", competition="League", cid="1",source="bsd_v2_2026"):
    return {
        "date": day, "home_team": home, "away_team": away,
        "source": source, "source_home_team_id": hid,
        "source_away_team_id": aid,
        "competition": competition, "source_competition_id": cid,
    }

class SourceIdentitySafety(unittest.TestCase):
    def test_conflicting_team_id_falls_back_but_no_match_removed(self):
        examples = [row("2026-01-02","Alpha","123"),
                    row("2026-02-02","Beta","123",away="Other",aid="901")]
        safe_source_identities(examples)
        self.assertEqual(len(examples), 2)
        self.assertIsNone(examples[0]["source_home_team_id"])
        self.assertIsNone(examples[1]["source_home_team_id"])
        self.assertEqual(examples[0]["source_away_team_id"],"bsd_900")
        self.assertEqual(examples[1]["source_away_team_id"],"bsd_901")
    def test_same_team_id_stays_cross_competition_when_name_verified(self):
        examples = [row("2025-01-02","Alphá","44",competition="Cup",cid="66",source="bsd_v2_2025"),
                    row("2026-01-02","Alpha","44",competition="League",cid="67")]
        safe_source_identities(examples)
        self.assertEqual([x["source_home_team_id"] for x in examples], ["bsd_44","bsd_44"])
    def test_competition_id_collision_reverts_to_name(self):
        examples = [row("2026-01-01","Alpha","41",competition="Cup",cid="3"),
                    row("2026-02-01","Beta","42",competition="League",cid="3")]
        safe_source_identities(examples)
        self.assertIsNone(examples[0]["source_competition_id"])
        self.assertIsNone(examples[1]["source_competition_id"])
    def test_provider_namespace_prevents_cross_source_ids(self):
        examples = [row("2026-01-01","Alpha","44",source="bsd_v2_2026"),
                    row("2026-02-01","Beta","44",source="different_provider")]
        safe_source_identities(examples)
        self.assertEqual(examples[0]["source_home_team_id"],"bsd_44")
        self.assertEqual(examples[1]["source_home_team_id"],"src_different_provider_44")

if __name__=="__main__":
    unittest.main()
