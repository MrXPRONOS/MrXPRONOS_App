import unittest
from datetime import datetime, timezone
from scripts.football_bsd_validate_real import native_current, union_with_bsd, measure

AT = datetime(2025, 2, 12, 12, tzinfo=timezone.utc)

def archive():
    result=[]
    for n in range(1, 8):
        for team, away, name in ((101, 300+n, "Arsenal FC"), (202, 500+n, "Chelsea FC")):
            result.append({
                "id": 10000+team*100+n, "status":"finished",
                "league_id": 39, "league_name":"Premier League",
                "home_team_id": team, "away_team_id": away,
                "home_team":{"id":team,"name":name},
                "away_team":{"id":away,"name":"Opponent"},
                "home_score":2,"away_score":1,
                "event_date":f"2025-02-{n:02d}T12:00:00+00:00"
            })
    return result

def feed():
    return {"source":"bsd","matches":[{
        "source":"bsd","id":"bsd:999","is_finished":False,
        "event_date":"2025-02-13T18:00:00Z",
        "home_team":"Arsenal FC","away_team":"Chelsea FC",
        "home_team_id":101,"away_team_id":202,"league":"Premier League","league_id":39,
    }]}

def external():
    return [{
        "fixture_key":"external1","discovered_by":"espn",
        "home_team":"Arsenal","away_team":"Chelsea",
        "kickoff_utc":"2025-02-13T18:00:00Z",
        "league_labels":["Premier League"],"league_verified":True,
        "sources":{"espn":{"id":"es1"}},"status":"prematch",
        "ambiguous_match":False,"league_conflict":False,"scores_conflict":False,
    }]

class RealBSDValidationContract(unittest.TestCase):
    def test_published_rows_are_only_adapted(self):
        current=native_current(feed())
        self.assertEqual(len(current),1)
        self.assertEqual(current[0]["id"],999)
        self.assertEqual(current[0]["home_team_id"],101)

    def test_exact_public_fixture_link_preserves_origin(self):
        combined, counts=union_with_bsd(external(),native_current(feed()))
        self.assertEqual(len(combined),1)
        self.assertEqual(counts["bsd_joined_existing"],1)
        self.assertEqual(combined[0]["discovered_by"],"espn")
        self.assertEqual(combined[0]["sources"]["bsd"]["id"],"999")

    def test_no_match_becomes_standalone_bsd(self):
        combined, counts=union_with_bsd([],native_current(feed()))
        self.assertEqual(len(combined),1)
        self.assertEqual(combined[0]["discovered_by"],"bsd")
        self.assertEqual(counts["bsd_added_from_published"],1)

    def test_actual_private_measure_is_aggregate_and_never_reveals_fixture_ids(self):
        report=measure(external(),feed(),archive(),at=AT)
        self.assertEqual(report["private_historical_coverage"]["added_statistics"],1)
        self.assertEqual(report["private_historical_coverage"]["native_bsd_fixtures"],1)
        self.assertEqual(report["routed_stats"]["goals"],1)
        self.assertEqual(report["future_fixtures_next_36h"],1)
        self.assertEqual(report["private_archive"]["records_restored"],14)
        self.assertNotIn("999",str(report))
        self.assertFalse(report["private_archive_uploaded"])
        self.assertFalse(report["production_model_modified"])

    def test_wrong_feed_source_rejected(self):
        with self.assertRaises(ValueError):
            native_current({"source":"other","matches":[]})

if __name__ == "__main__":
    unittest.main()
