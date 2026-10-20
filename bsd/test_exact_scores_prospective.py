"""Prospective score snapshot tests — no live API access, no production writes."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).parent))
from exact_scores_prospective import (MODEL, empty_ledger, read_ledger,
                                     write_ledger, record_fixtures,
                                     reconcile_results, report,
                                     make_snapshot)
from bsd_v2_core import V2History

NOW=datetime(2026,10,20,12,tzinfo=timezone.utc)

def fixture(i,dt,home=1,away=2,status="notstarted",score=None):
    return {"id":i,"event_date":dt.isoformat(),"home_team_id":home,
            "away_team_id":away,"status":status,
            "home_score":score[0] if score else None,
            "away_score":score[1] if score else None,
            "league_id":101}

def history():
    events=[]
    for i in range(6):
        start=NOW-timedelta(days=80-i*10)
        events.append(fixture(110+i,start,home=1,away=3,status="finished",score=(1,0)))
        events.append(fixture(210+i,start,home=4,away=2,status="finished",score=(0,1)))
    for i in range(3):
        events.append(fixture(310+i,NOW-timedelta(days=70-i*16),status="finished",
                              score=(1,0)))
    return V2History(events)

class ProspectiveTests(unittest.TestCase):
    def test_pre_kickoff_only(self):
        idx=history()
        from exact_scores_h2h import H2HIndex
        h=H2HIndex(idx)
        old=fixture(900,NOW+timedelta(minutes=20))
        row,why=make_snapshot(old,idx,h,NOW)
        self.assertIsNone(row)
        self.assertEqual(why,"too_close_or_started")
        upcoming=fixture(901,NOW+timedelta(days=1))
        row,why=make_snapshot(upcoming,idx,h,NOW)
        self.assertEqual(why,"ok")
        self.assertEqual(row["status"],"pending")
        self.assertEqual(len(row["top3"]),3)
        self.assertGreater(row["under25"]["probability"],0)
        self.assertTrue(row["forecast_sha256"])

    def test_first_seen_immutable_and_no_premature_settlement(self):
        idx=history()
        f=fixture(901,NOW+timedelta(days=1))
        led=empty_ledger()
        n=record_fixtures(led,[f],idx,NOW)
        self.assertEqual(n["added"],1)
        key=next(iter(led["predictions"]))
        original=json.dumps(led["predictions"][key],sort_keys=True)
        repeat=record_fixtures(led,[f],idx,NOW+timedelta(hours=2))
        self.assertEqual(repeat["added"],0)
        self.assertEqual(original,json.dumps(led["predictions"][key],sort_keys=True))
        done=fixture(901,NOW+timedelta(days=1),status="finished",score=(1,0))
        self.assertEqual(reconcile_results(led,[done],NOW+timedelta(days=1,hours=3)),{})
        self.assertEqual(led["predictions"][key]["status"],"pending")
        r=reconcile_results(led,[done],NOW+timedelta(days=1,hours=5))
        self.assertEqual(r,{"settled":1})
        self.assertEqual(led["predictions"][key]["status"],"settled")
        self.assertEqual(led["predictions"][key]["actual_score"],[1,0])
        self.assertEqual(reconcile_results(led,[done],NOW+timedelta(days=1,hours=6)),{})
        self.assertEqual(report(led,NOW)["all"]["n"],1)

    def test_wrong_fixture_identity_cannot_settle(self):
        idx=history()
        f=fixture(950,NOW+timedelta(days=1))
        led=empty_ledger();record_fixtures(led,[f],idx,NOW)
        altered=fixture(950,NOW+timedelta(days=1),home=1,away=77,
                        status="finished",score=(1,0))
        out=reconcile_results(led,[altered],NOW+timedelta(days=2))
        self.assertEqual(out["identity_mismatch"],1)
        self.assertEqual(next(iter(led["predictions"].values()))["status"],"pending")

    def test_encrypted_archive_roundtrip_no_plaintext(self):
        key=Fernet(Fernet.generate_key())
        led=empty_ledger()
        led["predictions"]["example"]={"secret_test_content":"do_not_publish"}
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"forecasts.enc.json"
            write_ledger(led,p,key)
            self.assertNotIn("do_not_publish",p.read_text(encoding="utf-8"))
            self.assertEqual(read_ledger(p,key),led)

    def test_archive_rejects_model_version_change(self):
        key=Fernet(Fernet.generate_key())
        ledger=empty_ledger()
        ledger["model"]["scale_home"]=9
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                write_ledger(ledger,Path(folder)/"x.enc.json",key)

    def test_empty_report_has_no_fake_performance(self):
        r=report(empty_ledger(),NOW)
        self.assertIsNone(r["all"]["top1_rate"])
        self.assertEqual(r["priority"]["n"],0)


    def test_overdue_pending_is_not_fake_loss(self):
        idx=history()
        future=fixture(999,NOW+timedelta(days=1))
        led=empty_ledger()
        record_fixtures(led,[future],idx,NOW)
        r=report(led,NOW+timedelta(days=10))
        self.assertEqual(r["overdue_unsettled"],1)
        self.assertEqual(r["all"]["n"],0)
        self.assertEqual(r["all"]["top3_rate"],None)
    def test_bad_external_event_does_not_corrupt_reconciliation(self):
        self.assertEqual(reconcile_results(empty_ledger(),
                        [{"id": 9,"event_date": None}],NOW),{})

if __name__=="__main__":
    unittest.main()
