#!/usr/bin/env python3
"""Paired chronological research-only evaluation on private BSD archived results.

Compares a SIMPLE five-game-or-more form Poisson against BSD V2 RAW GOAL
model using exactly the same historic fixtures. Not full calibrated/policy
production BSD V2. Does not fit on future results, fetch odds, or post picks.
Print only aggregate scoring rules and counts, never plaintext match rows.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
from math import log
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "bsd") not in sys.path:
    sys.path.insert(0, str(ROOT / "bsd"))
from bsd_v2_core import V2History, estimate_goals, score_matrix
from scripts.football_bsd_private_history import build_private_index, recent_team, team_id, league_id
from scripts.football_match_source_router import aware_time
from scripts.football_prematch_probability_shadow import baseline


def score(m: dict, h: int, a: int) -> dict:
    result = "home" if h>a else "away" if h<a else "draw"
    yc = int(h>0 and a>0)
    yo = int(h+a>=3)
    return {
        "1x2_brier": sum((m[k]-int(result==k))**2 for k in ("home","draw","away")),
        "1x2_logloss": -log(max(1e-9, m[result])),
        "btts_brier": (m["btts_yes"]-yc)**2,
        "over25_brier": (m["over_2_5"]-yo)**2,
    }


def probabilities(xh: float, xa: float) -> dict:
    mat = score_matrix(xh, xa, rho=0)
    return {
        "home": sum(v for (h,a),v in mat.items() if h>a),
        "draw": sum(v for (h,a),v in mat.items() if h==a),
        "away": sum(v for (h,a),v in mat.items() if h<a),
        "btts_yes": sum(v for (h,a),v in mat.items() if h>0 and a>0),
        "over_2_5": sum(v for (h,a),v in mat.items() if h+a>=3),
    }


def evaluate(archive: list[dict], *, max_fixtures: int = 400) -> dict:
    if max_fixtures < 10 or max_fixtures > 3000:
        raise ValueError("max_fixtures must be between 10 and 3000")
    candidates = []
    for row in archive:
        if not isinstance(row,dict) or str(row.get("status") or "").lower() != "finished":
            continue
        when = aware_time(row.get("event_date"))
        h, a = row.get("home_score"), row.get("away_score")
        if (when is None or when.year != 2026 or not (1 <= when.month <= 10)
                or type(h) is not int or type(a) is not int
                or h < 0 or a < 0 or h > 30 or a > 30
                or not league_id(row) or not team_id(row,"home") or not team_id(row,"away")):
            continue
        if when >= datetime(2026,10,14,tzinfo=timezone.utc):
            continue
        candidates.append((when,row))
    candidates.sort(key=lambda x: (x[0],str(x[1].get("id") or "")))
    # Deterministic spaced sample of the final 2026 archive (no cherry-picking winners).
    if len(candidates)>max_fixtures:
        step = len(candidates)/max_fixtures
        candidates = [candidates[int(i*step)] for i in range(max_fixtures)]
    private_index, _, quality = build_private_index(archive)
    bsd_index = V2History(archive)
    records = {"simple_form":Counter(), "bsd_v2_raw_goals":Counter()}
    skipped = Counter()
    n=0
    for kickoff,row in candidates:
        lid, hid, aid = league_id(row), team_id(row,"home"), team_id(row,"away")
        at = kickoff - timedelta(seconds=1)
        h = recent_team(private_index,lid,hid,at,kickoff)
        a = recent_team(private_index,lid,aid,at,kickoff)
        if not h or not a:
            skipped["simple_no_prior_data"]+=1
            continue
        bsd, reason = estimate_goals(row,bsd_index)
        if not bsd:
            skipped["bsd_"+str(reason)[:48]]+=1
            continue
        m={
            "home_goals_for":h["gf"],"home_goals_against":h["ga"],
            "away_goals_for":a["gf"],"away_goals_against":a["ga"],
        }
        try:
            one=baseline(m)["probabilities_uncalibrated"]
            two=probabilities(bsd["home"],bsd["away"])
            for k,v in score(one,row["home_score"],row["away_score"]).items():
                records["simple_form"][k]+=v
            for k,v in score(two,row["home_score"],row["away_score"]).items():
                records["bsd_v2_raw_goals"][k]+=v
            n+=1
        except (ValueError,ZeroDivisionError,OverflowError):
            skipped["invalid_prediction_inputs"]+=1
    return {
        "date_scope":"2026-01-01_to_2026-10-13",
        "candidate_matches":len(candidates),
        "identical_fixtures_evaluated":n,
        "insufficient_samples":n<200,
        "skipped_by_reason":dict(sorted(skipped.items())),
        "metrics":{
            k:{
                "simple_form_poisson":round(records["simple_form"][k]/n,6) if n else None,
                "bsd_v2_raw_goal_poisson":round(records["bsd_v2_raw_goals"][k]/n,6) if n else None,
            } for k in ("1x2_brier","1x2_logloss","btts_brier","over25_brier")
        },
        "compared_to_production_calibrated_bsd_v2":False,
        "raw_goal_baseline_comparison_only":True,
        "as_of_rule":"No historical event after fixture kickoff, 4-hour settlement delay",
        "archive_rows_seen":len(archive),
        "publication_enabled":False,
        "strategy_change_authorized":False,
        "private_match_rows_exposed":False,
        "live_model_modified":False,
    }


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--history",required=True)
    p.add_argument("--report",required=True)
    p.add_argument("--max-fixtures",type=int,default=400)
    a=p.parse_args()
    history=json.loads(Path(a.history).read_text(encoding="utf-8"))
    if not isinstance(history,list):
        p.error("History must be a list")
    result=evaluate(history,max_fixtures=a.max_fixtures)
    dest=Path(a.report)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("BSD_CHRONOLOGICAL_PAIRED_RAW_BENCHMARK",json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    main()
