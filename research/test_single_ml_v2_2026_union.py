"""2026 encrypted union: 10 verified months, no current/future fixtures."""
import sys,tempfile,unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_git import seal,atomic_bytes
from single_ml_v2_2024_union import combine

class YearToDate2026(unittest.TestCase):
    def test_ten_months_and_october_24_cutoff(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            key=b"J"*32
            for month in range(1,11):
                row={"id":f"bsd_v2_2026:{month}",
                     "date":f"2026-{month:02d}-12",
                     "source":"bsd_v2_2026",
                     "home_team":"A "+str(month),"away_team":"B "+str(month),
                     "home_score":2,"away_score":1,
                     "sportId":1,"is_finished":True,"competition":"League"}
                record={"year":2026,"month":month,"cutoff_date":"2026-10-24",
                    "schema":"bsd_sportscore_2026_private_verified_v1",
                    "matches":[row],
                    "audit":{"sportscore":{"days_failed":0,
                         "days_at_200_cap_incomplete":0}}}
                p=root/f"bsd_sportscore/2026/{month:02d}.enc"
                atomic_bytes(p,seal(record,key,f"bsd-sportscore-2026-month:{month}"))
            rows,report=combine(key,root=root,year=2026,through=date(2026,10,24))
            self.assertEqual(report["year"],2026)
            self.assertEqual(report["cutoff_utc_day"],"2026-10-24")
            self.assertEqual(report["months_verified"],10)
            self.assertEqual(report["distinct_safe_matches"],10)
            self.assertEqual(len(rows),10)
            self.assertTrue(all(r["date"]<="2026-10-24" for r in rows))
            with self.assertRaises(ValueError):
                combine(key,root=root,year=2026,through=date(2026,10,23))
            with self.assertRaises(ValueError):
                combine(key,root=root,year=2026)
    def test_different_score_same_day_team_bsd_ids_are_quarantined(self):
        from single_ml_v2_2026_bsd_reconcile import AAD
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            key=b"K"*32
            for month in range(1,11):
                original={"id":f"bsd_v2_2026:{month}",
                    "date":f"2026-{month:02d}-12","source":"bsd_v2_2026",
                    "home_team":f"Home {month}","away_team":f"Away {month}",
                    "home_score":2,"away_score":1,"sportId":1,
                    "is_finished":True,"competition":"League"}
                sealed={"schema":"bsd_sportscore_2026_private_verified_v1",
                    "year":2026,"month":month,"cutoff_date":"2026-10-24",
                    "matches":[original],
                    "audit":{"sportscore":{"days_failed":0,"days_at_200_cap_incomplete":0}}}
                p=root/f"bsd_sportscore/2026/{month:02d}.enc"
                atomic_bytes(p,seal(sealed,key,f"bsd-sportscore-2026-month:{month}"))
            # Separate provider IDs but same normalized fixture date/team names.
            # The different score must disqualify the entire identity.
            extras=[
                {"id":"bsd_v2_2026:jan-alt","date":"2026-01-12",
                 "source":"bsd_v2_2026","home_team":"Home 1",
                 "away_team":"Away 1","home_score":8,"away_score":4,
                 "sportId":1,"is_finished":True,"competition":"Other League"},
                {"id":"bsd_v2_2026:feb-alt","date":"2026-02-12",
                 "source":"bsd_v2_2026","home_team":"Home 2",
                 "away_team":"Away 2","home_score":2,"away_score":1,
                 "sportId":1,"is_finished":True,"competition":"Other League"},
            ]
            recon={"schema":AAD,"year":2026,"through":"2026-10-24",
                "audit":{"omitted_distinct_bsd_source_ids":2},
                "omitted_bsd_source_records":extras}
            atomic_bytes(root/"bsd_sportscore/2026_bsd_reconcile.enc",
                    seal(recon,key,AAD))
            rows,report=combine(key,root=root,year=2026,through="2026-10-24")
            self.assertEqual(report["distinct_safe_matches"],9)
            self.assertEqual(report["conflicting_outcome_identities_quarantined"],1)
            self.assertEqual(report["duplicates_same_identity_same_score"],1)
            self.assertEqual(report["bsd_reconciled_source_id_observations"],2)
            self.assertFalse(any(x["date"]=="2026-01-12" for x in rows))
            self.assertTrue(any(x["date"]=="2026-02-12" for x in rows))
if __name__=="__main__":unittest.main()
