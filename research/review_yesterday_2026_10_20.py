#!/usr/bin/env python3
"""Display audited football match-by-match results from immutable Oct 20 action artifact."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("--input",required=True);a=p.parse_args()
rows=json.loads(Path(a.input).read_text(encoding="utf8"))
def clean(r):
    d=r["vote_thresholds"]["5"]
    return {"match":r["home"]+" - "+r["away"],"league":r["league"],
            "actual":r["actual_score"],"consensus":d["score"],
            "votes":r["highest_votes"],"selected_5":d["status"]=="SELECTED",
            "correct_5":r["result_5"],
            "individual_votes":r["six_picks"]}
ucl=[r for r in rows if "UEFA Champions League" in r["league"] or r["league"] in ("Champions League","UCL")]
correct5=[r for r in rows if r["result_5"] is True]
correct6=[r for r in rows if r["result_6"] is True]
examples=[r for r in rows if r["highest_votes"]>=5 and r["result_5"] is False]
print("YESTERDAY_FOOTBALL_UCL",json.dumps([clean(r) for r in ucl],ensure_ascii=False),flush=True)
print("YESTERDAY_FOOTBALL_CORRECT5",json.dumps([clean(r) for r in correct5][:20],ensure_ascii=False),flush=True)
print("YESTERDAY_FOOTBALL_CORRECT6",json.dumps([clean(r) for r in correct6][:20],ensure_ascii=False),flush=True)
print("YESTERDAY_FOOTBALL_WRONG",json.dumps([clean(r) for r in examples if "UEFA Champions League" in r["league"]][:15],ensure_ascii=False),flush=True)
