import tempfile,unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_git import seal,atomic_bytes
from single_ml_v2_2024_union import combine
from single_ml_v2_openfootball2024 import SCHEMA as OF_SCHEMA
from single_ml_v2_bsd_sportscore_2024 import SCHEMA as BSD_SCHEMA

def record(month,src,home="Alpha",away="Beta",hg=1,ag=2):
    return {"id":src+str(month),"date":f"2024-{month:02d}-09",
            "home_team":home,"away_team":away,"home_score":hg,"away_score":ag,
            "sportId":1,"is_finished":True,"competition":"League","source":src}
class UnionTests(unittest.TestCase):
    def test_verified_archive_dedup_and_conflicting_score_quarantine(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);k=b"m"*32
            path=root/"openfootball/2024.enc"
            atomic_bytes(path,seal({"year":2024,"schema":OF_SCHEMA,"matches":[
                record(1,"openfootball_football_json_cc0")]},k,
                "openfootball-cc0-calendar-2024"))
            for month in range(1,13):
                r=[record(month,"bsd_v2_2024")]
                if month==1:
                    r.append(record(month,"sportscore_2024",home="Other",away="More"))
                if month==2:
                    r.append(record(month,"sportscore_2024",hg=9,ag=9))
                audit={"sportscore":{"days_failed":0,"days_at_200_cap_incomplete":1}}
                dest=root/f"bsd_sportscore/2024/{month:02d}.enc"
                atomic_bytes(dest,seal({"schema":BSD_SCHEMA,"month":month,
                         "year":2024,"matches":r,"audit":audit},
                         k,"bsd-sportscore-2024-month:"+str(month)))
            matches,report=combine(k,root=root)
            self.assertEqual(len(matches),12)
            self.assertEqual(report["months_verified"],12)
            self.assertEqual(report["duplicates_same_identity_same_score"],1)
            self.assertEqual(report["conflicting_outcome_identities_quarantined"],1)
            self.assertEqual(report["sportscore_at_cap_days"],12)
            self.assertEqual(len({(m["date"],m["home_team"],m["away_team"]) for m in matches}),12)
if __name__=="__main__":unittest.main()
