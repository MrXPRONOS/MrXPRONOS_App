"""Independent two-provider strict corroboration beyond eight CC0 league files."""
import unittest
from datetime import datetime,timezone
from scripts.football_cc0_calendar_verification import corroborate,strict_two_provider_fixture
from scripts.football_native_bsd_identity_probe import prove

AT=datetime(2026,10,20,12,tzinfo=timezone.utc)
KICK="2026-10-20T18:45:00+00:00"
def ext():
    return {"home_team":"Arsenal","away_team":"Chelsea",
        "kickoff_utc":KICK,"status":"prematch","discovered_by":"espn",
        "league_labels":["Premier League"],"league_verified":True,
        "source_count":2,"ambiguous_match":False,"scores_conflict":False,
        "league_conflict":False,
        "sources":{"espn":{"id":"1","kickoff_utc":KICK,"state":"pre","league":"Premier League"},
                   "sportscore":{"id":"2","kickoff_utc":"2026-10-20T18:48:00+00:00","state":"pre","league":"Premier League"}}}
class DualSourceTests(unittest.TestCase):
    def test_independent_verification_and_real_native_one_to_one(self):
        item=ext()
        self.assertTrue(strict_two_provider_fixture(item,at=AT))
        rows,health=corroborate([item],[],as_of=AT)
        self.assertEqual(health["schedule_matches_confirmed"],1)
        self.assertEqual(health["two_provider_matches_confirmed"],1)
        self.assertEqual(health["cc0_matches_confirmed"],0)
        self.assertEqual(rows[0]["_schedule_verified_by"],"two_independent_providers")
        native=[{"id":123,"league_id":8,"league_name":"Premier League",
            "home_team_id":7,"away_team_id":9,"home_team":"Arsenal",
            "away_team":"Chelsea","event_date":KICK,"status":"notstarted"}]
        self.assertEqual(prove(rows,native,at=AT)["one_to_one_native_event_links"],1)
    def test_both_providers_must_independently_verify_league(self):
        r=ext();r["sources"]["sportscore"]["league"]=""
        self.assertFalse(strict_two_provider_fixture(r,at=AT))
        r=ext();r["sources"]["sportscore"]["league"]="FA Cup"
        self.assertFalse(strict_two_provider_fixture(r,at=AT))

    def test_rejects_single_provider(self):
        r=ext();r["sources"].pop("sportscore");r["source_count"]=1
        self.assertFalse(strict_two_provider_fixture(r,at=AT))
    def test_rejects_large_kickoff_disagreement(self):
        r=ext();r["sources"]["sportscore"]["kickoff_utc"]="2026-10-20T19:01:00+00:00"
        self.assertFalse(strict_two_provider_fixture(r,at=AT))
    def test_rejects_conflicts_ambiguous_unknown_providers(self):
        for override in [
            {"league_labels":["Premier League","Bundesliga"]},
            {"league_conflict":True},{"ambiguous_match":True},
            {"source_count":3},
            {"sources":{"espn":{"id":"1","kickoff_utc":KICK,"state":"pre"},
                        "untrusted":{"id":"x","kickoff_utc":KICK,"state":"pre"}}},
        ]:
            with self.subTest(override=override):
                self.assertFalse(strict_two_provider_fixture({**ext(),**override},at=AT))
    def test_cc0_precedence(self):
        rows,health=corroborate([ext()],[
            {"day":"2026-10-20","league":"Premier League","home":"Arsenal","away":"Chelsea"}
        ],as_of=AT)
        self.assertEqual(rows[0]["_schedule_verified_by"],"openfootball_cc0")
        self.assertEqual(health["cc0_matches_confirmed"],1)
        self.assertEqual(health["two_provider_matches_confirmed"],0)
if __name__=="__main__":unittest.main()
