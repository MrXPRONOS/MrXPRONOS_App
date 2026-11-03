"""Unit and integration-like synthetic tests for preregistered group mass ranking B."""
from __future__ import annotations
import csv
import copy
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ml_v3_group_probability import grid_group_mass, FROZEN_GROUPS
from ml_v3_group_rank_b_2026 import (
    KS, WINDOWS, ARMS, load_pairs, rank_candidates, settle_day, month, pool, aggregate
)
from ml_v3_grouped_top1_top2 import GROUPS, month as old_month, totals as old_totals
from test_ml_v3_grouped_scores import records, make


def mass_for(record):
    pred=record["predicted_score"]
    group=next((name for name,scores in FROZEN_GROUPS.items() if pred in scores),"")
    # Group probability is a predeclared synthetic PREMATCH ranking feature,
    # deliberately higher for DRAW_LOW despite a lower modal confidence.
    mass={"H_LOW":.28, "H_HIGH":.26, "A_LOW":.33, "A_HIGH":.26, "DRAW_LOW":.46}.get(group,0.)
    modal=float(record["top_probability"])
    if group:mass=max(mass,modal)
    return {
        "date":record["date"], "id":record["id"],
        "predicted_score":pred,"modal_probability":modal,
        "group":group,"group_probability":mass,
        "history_latest_day":record["history_latest_day"],
        "model_fit_latest_day":record["model_fit_latest_day"],
    }


def sources(folder,start,end,*,flip=False):
    rows=list(records(start,end))
    # Make high-modal confidence fixture lose while lower-modal DRAW score wins.
    for row in rows:
        if row["id"].endswith("f000"):
            row["actual_score"] = "9:9"
            row["hit"] = 0
            row["top3_hit"] = 0
        if flip:
            row["actual_score"] = "9:9"
            row["hit"] = 0
            row["top3_hit"] = 0
    pred=folder/"all_predictions.csv"
    make(pred,rows)
    pm=folder/"hybrid_v3_group_mass.csv"
    masses=[mass_for(r) for r in rows]
    with pm.open("w",encoding="utf8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(masses[0]))
        writer.writeheader()
        writer.writerows(masses)
    return pred,pm


class TestGroupMassRankingB(unittest.TestCase):
    def test_native_grid_group_mass_without_outcome(self):
        self.assertEqual(GROUPS,FROZEN_GROUPS)
        p=np.full((11,11),.00001)
        p[1,0]=.45;p[2,0]=.30;p[2,1]=.20;p[0,0]=.08
        p/=p.sum()
        r=grid_group_mass(p,"1:0")
        self.assertEqual(r["group"],"H_LOW")
        self.assertAlmostEqual(r["group_probability"],float(p[1,0]+p[2,0]+p[2,1]))
        self.assertGreater(r["group_probability"],r["modal_probability"])
        with self.assertRaisesRegex(ValueError,"disagrees"):
            grid_group_mass(p,"2:0")
        with self.assertRaisesRegex(ValueError,"normalized"):
            grid_group_mass(p*2,"1:0")

    def test_pairing_a_reproduces_existing_historical_ranking(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=WINDOWS[0];f,m=sources(Path(tmp),a,b)
            report=month(f,m,start=a,end=b)
            old=old_month(f,start=a,end=b)
            for k in KS:
                new=aggregate(report["daily"][str(k)],k)["A_MODAL"]
                legacy=old_totals(old["daily"][str(k)])
                self.assertEqual(new["exact_hits"],legacy["exact_score_hits"])
                self.assertEqual(new["grouped_hits"],legacy["grouped_hits"])
                self.assertEqual(new["days_group_ge1"],legacy["days_group_ge1"])
            # Most days A picks rank-1 f000 and B selects f002 with draw mass .46.
            self.assertLess(report["daily"]["1"][0]["selection_overlap"],1)
            self.assertEqual(report["daily"]["1"][0]["A_MODAL"]["grouped_hits"],0)
            self.assertEqual(report["daily"]["1"][0]["B_GROUP_MASS"]["grouped_hits"],1)

    def test_prediction_rank_selection_cannot_depend_on_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=WINDOWS[0];p,m=sources(Path(tmp),a,b)
            byday=load_pairs(p,m,start=a,end=b)
            day=a
            original=rank_candidates(byday[day])
            changed=copy.deepcopy(byday[day])
            for r in changed:r["actual_score"]="9:9"
            after=rank_candidates(changed)
            for arm in ARMS:
                self.assertEqual([r["id"] for r in original[arm]],
                                 [r["id"] for r in after[arm]])

    def test_outcome_field_in_probability_export_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=WINDOWS[0];p,m=sources(Path(tmp),a,b)
            with m.open("r",encoding="utf8",newline="") as fh:
                reader=csv.DictReader(fh);rows=list(reader)
            q=Path(tmp)/"leaky.csv"
            with q.open("w",encoding="utf8",newline="") as fh:
                writer=csv.DictWriter(fh,fieldnames=[*rows[0].keys(),"actual_score"])
                writer.writeheader()
                writer.writerows([dict(r,actual_score="1:1") for r in rows])
            with self.assertRaisesRegex(ValueError,"Outcome labels"):
                load_pairs(p,q,start=a,end=b)

    def test_no_future_provenance_or_wrong_modal_probability(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=WINDOWS[0];p,m=sources(Path(tmp),a,b)
            with m.open("r",encoding="utf8",newline="") as fh:
                reader=csv.DictReader(fh);rows=list(reader)
            rows[0]["model_fit_latest_day"]=a
            wrong=Path(tmp)/"future.csv"
            with wrong.open("w",encoding="utf8",newline="") as fh:
                w=csv.DictWriter(fh,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            with self.assertRaisesRegex(ValueError,"future-dated"):
                load_pairs(p,wrong,start=a,end=b)
            rows[0]["model_fit_latest_day"] = records(a,b).__next__()["model_fit_latest_day"]
            rows[0]["modal_probability"]=".99"
            rows[0]["group_probability"]=".99"  # Keep mass>=modal; isolate mismatch check
            wrong2=Path(tmp)/"not_modal.csv"
            with wrong2.open("w",encoding="utf8",newline="") as fh:
                w=csv.DictWriter(fh,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            with self.assertRaisesRegex(ValueError,"disagrees"):
                load_pairs(p,wrong2,start=a,end=b)

    def test_exactly_ten_windows_no_full_october_and_baseline_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=[]
            for i,(a,b) in enumerate(WINDOWS):
                folder=Path(tmp)/str(i);folder.mkdir()
                p,m=sources(folder,a,b)
                report=month(p,m,start=a,end=b)
                result=folder/"month.json";result.write_text(json.dumps(report),encoding="utf8")
                paths.append(result)
            with self.assertRaisesRegex(ValueError,"Exactly ten"):
                pool(paths[:9])
            with self.assertRaisesRegex(ValueError,"Baseline A mismatch"):
                pool(paths)
            result=pool(paths,enforce_frozen_a=False)
            for k in KS:
                self.assertEqual(result["primary"][str(k)]["A_MODAL"]["selection_slots"],273*k)
                self.assertEqual(result["october_partial_1_to_24"][str(k)]["B_GROUP_MASS"]["selection_slots"],24*k)
                self.assertEqual(result["all_available_2026_descriptive"][str(k)]["A_MODAL"]["selection_slots"],297*k)


if __name__=="__main__":
    unittest.main()
