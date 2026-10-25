import tempfile,unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_git import seal,atomic_bytes
from single_ml_v2_2024_union import combine
def game(month,source,h=2,a=1,home="Alpha",away="Beta"):
    return {"id":source+":"+str(month),"date":f"2025-{month:02d}-14",
            "home_team":home,"away_team":away,"home_score":h,"away_score":a,
            "source":source,"sportId":1,"is_finished":True,
            "competition":"League"}
class Union2025Tests(unittest.TestCase):
    def test_safe_year_scope_and_conflicts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);key=b"J"*32
            for m in range(1,13):
                records=[game(m,"bsd_v2_2025")]
                if m==1:records.append(game(m,"sportscore_2025"))
                if m==2:records.append(game(m,"sportscore_2025",h=1,a=1))
                if m==3:records.append(game(m,"sportscore_2025",
                                            home="Other",away="Visitors"))
                doc={"year":2025,"month":m,
                    "schema":"bsd_sportscore_2025_private_verified_v1",
                    "matches":records,
                    "audit":{"sportscore":{"days_failed":0,
                                            "days_at_200_cap_incomplete":0}}}
                dest=root/f"bsd_sportscore/2025/{m:02d}.enc"
                atomic_bytes(dest,seal(doc,key,"bsd-sportscore-2025-month:"+str(m)))
            matches,audit=combine(key,root=root,year=2025)
            self.assertEqual(audit["year"],2025)
            self.assertEqual(audit["months_verified"],12)
            self.assertEqual(audit["conflicting_outcome_identities_quarantined"],1)
            self.assertEqual(audit["duplicates_same_identity_same_score"],1)
            self.assertEqual(len(matches),12)
            self.assertEqual(len({m["id"] for m in matches}),12)
            self.assertTrue(all(x["date"].startswith("2025-") for x in matches))
if __name__=="__main__":unittest.main()
