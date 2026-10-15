import unittest
from datetime import datetime, timezone
from scripts.football_cc0_bsd_canary import (
    clean, ident, extract_calendar, candidate_leagues, corroborate,
)

AT=datetime(2026,10,15,1,20,tzinfo=timezone.utc)

def event(ident_num=123,league_id=44,home="Arsenal",away="Chelsea",time="2026-10-16T19:00:00Z"):
    return {"id":ident_num,"league_id":league_id,
            "home_team":{"name":home,"id":7},"away_team":{"name":away,"id":8},
            "event_date":time,"status":"notstarted"}

def calendar():
    return extract_calendar({"matches":[{"date":"2026-10-16",
            "team1":"Arsenal","team2":"Chelsea"}]},"en.1")


class BSDCC0CanaryTests(unittest.TestCase):
    def test_canonical_identity_and_strict_native_id(self):
        self.assertEqual(clean("  Équipe–A  "), "equipe a")
        self.assertEqual(ident("123"),123)
        for invalid in (0,"0123",True,"",7_500_000_000_000_000,None):
            self.assertIsNone(ident(invalid))

    def test_valid_unique_native_match_only(self):
        rows=calendar()
        result=corroborate(rows,[event()],{44:"Premier League"},at=AT)
        self.assertEqual(result["officially_corrobated_unique_native_matches"],1)
        self.assertEqual(result["cc0_day_team_pairs_matched"],1)
        self.assertFalse(result["production_publication_enabled"])
        self.assertFalse(result["raw_match_data_or_ids_exported"])
        self.assertNotIn("Arsenal",str(result))
        self.assertNotIn("123",str(result))

    def test_league_id_never_implies_name(self):
        rows=calendar()
        self.assertEqual(candidate_leagues(rows,[event()],at=AT),[44])
        empty=corroborate(rows,[event()],{},at=AT)
        self.assertEqual(empty["officially_corrobated_unique_native_matches"],0)
        wrong=corroborate(rows,[event()],{44:"Bundesliga"},at=AT)
        self.assertEqual(wrong["officially_corrobated_unique_native_matches"],0)

    def test_inverted_teams_or_kickoff_day_refused(self):
        for row in (event(home="Chelsea",away="Arsenal"),
                    event(time="2026-10-17T19:00:00Z")):
            self.assertEqual(corroborate(calendar(),[row],{44:"Premier League"},at=AT)["officially_corrobated_unique_native_matches"],0)

    def test_duplicate_native_ids_and_competing_events_are_quarantined(self):
        row=event()
        duplicates=corroborate(calendar(),[row,dict(row)],{44:"Premier League"},at=AT)
        self.assertEqual(duplicates["officially_corrobated_unique_native_matches"],0)
        conflicting=corroborate(calendar(),[row,event(ident_num=555)],{44:"Premier League"},at=AT)
        self.assertEqual(conflicting["officially_corrobated_unique_native_matches"],0)
        self.assertEqual(conflicting["duplicate_native_fixture_conflicts"],1)

    def test_invalid_status_or_nonfuture_no_matches(self):
        old=event(time="2026-10-14T19:00:00Z")
        live=event()
        live["status"]="live"
        result=corroborate(calendar(),[old,live],{44:"Premier League"},at=AT)
        self.assertEqual(result["officially_corrobated_unique_native_matches"],0)

    def test_unexpected_calendar_fails_closed(self):
        for payload in ({"matches":"broken"},{"matches":[2]},{"matches":[],"wrong":True}):
            if payload.get("matches") == []:
                self.assertEqual(extract_calendar(payload,"en.1"),[])
            else:
                with self.assertRaises(ValueError):
                    extract_calendar(payload,"en.1")
        with self.assertRaises(ValueError):
            extract_calendar({"matches":[]},"random-provider")

if __name__=="__main__":
    unittest.main()
