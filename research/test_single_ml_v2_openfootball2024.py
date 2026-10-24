import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_openfootball2024 import (YEAR,SCHEMA,SEASON_CODES,
    parse_match,build,store,export)
from single_ml_v2_git import open_sealed
from single_ml_v2 import load_matches

class OpenFootballYearTests(unittest.TestCase):
    def test_date_only_is_not_invented_utc(self):
        row=parse_match({"date":"2024-01-02","team1":"Alpha",
            "team2":"Beta","time":"18:00","score":{"ft":[2,0]}},
            "2023-24","en.1","en.1")
        self.assertEqual(row["sportId"],1)
        self.assertEqual(row["date"],"2024-01-02")
        self.assertNotIn("start_time",row)
        self.assertEqual(row["source_date_precision"],"calendar_date_only_no_utc")
        self.assertIsNone(row["source_home_team_id"])
        self.assertEqual(row["source_local_time_unverified_tz"],"18:00")
        self.assertIsNone(parse_match({"date":"2023-12-30",
            "team1":"A","team2":"B","score":{"ft":[1,1]}},
            "2023-24","en.1","en.1"))
        self.assertIsNone(parse_match({"date":"2024-01-02",
            "team1":"A","team2":"B","score":{"ft":[True,1]}},
            "2023-24","en.1","en.1"))

    def test_one_year_complete_calendar_and_cryptographic_integrity(self):
        def fake(season,code):
            matches=[]
            for i in range(35):
                mm=i%12+1
                day=i%28+1
                matches.append({"date":f"2024-{mm:02d}-{day:02d}",
                    "team1":f"Home Team {i}",
                    "team2":f"Away Team {i}",
                    "score":{"ft":[i%5,(i+1)%4]},
                    "time":"18:30"})
            return {"name":season+"/"+code,"matches":matches},"a"*64,"https://example.invalid/"+season+"/"+code
        year=build(fetcher=fake)
        self.assertEqual(year["year"],2024)
        self.assertEqual(year["schema"],SCHEMA)
        self.assertEqual(len(year["matches"]),sum(len(c) for c in SEASON_CODES.values())*35)
        self.assertEqual(year["audit"]["calendar_days"],366)
        self.assertEqual(len(year["audit"]["by_month"]),12)
        self.assertEqual(year["audit"]["season_files_failed"],0)
        with tempfile.TemporaryDirectory(dir="/tmp") as folder:
            path=Path(folder)/"year.enc"
            key=b"J"*32
            self.assertTrue(store(year,key,path=path))
            self.assertFalse(store(year,key,path=path))
            encrypted=path.read_bytes()
            self.assertNotIn(b"Home Team",encrypted)
            unsealed=open_sealed(encrypted,key,"openfootball-cc0-calendar-2024")
            self.assertEqual(unsealed["audit"]["matches"],len(year["matches"]))
            destination=str(Path(folder)/"plain_export.json")
            self.assertEqual(export(key,path=path,destination=destination),
                             len(year["matches"]))
            loaded=load_matches(destination,date(2024,12,31))
            self.assertEqual(len(loaded),len(year["matches"]))
            self.assertTrue(all(m.xgh is None and m.xga is None for m in loaded))
            self.assertTrue(all(m.day.year==2024 for m in loaded))
            with self.assertRaises(Exception):
                open_sealed(encrypted[:-1]+bytes([encrypted[-1]^1]),
                            key,"openfootball-cc0-calendar-2024")

    def test_incomplete_source_is_not_claimed_as_global(self):
        def empty(season,code):
            return {"matches":[]},"a"*64,"https://example.invalid"
        with self.assertRaises(RuntimeError):
            build(fetcher=empty)

if __name__=="__main__":
    unittest.main()
