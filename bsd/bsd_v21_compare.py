#!/usr/bin/env python3
"""Read-only V2 vs V2.1 retrospective audit; NEVER trains or changes outcomes."""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bsd_v2_guardrails import v21_accept_priced, v21_league_market_performance

def simulate(rows):
    by_group=defaultdict(list)
    groups=v21_league_market_performance(rows)
    for row in rows:
        if not row.get("is_finished") or "verified_prediction" not in row:
            continue
        pred=row.get("prediction") or {}
        p=pred.get("conservative_probability", pred.get("confidence",0))
        if not isinstance(p,(int,float)):
            continue
        p=float(p)/100 if p>1 else float(p)
        choice={"key":pred.get("selection_key"), "conservative_probability":p,
                "bookmaker_odds":pred.get("odds"),"odds_source":pred.get("odds_source")}
        # Do not use retrospective future results to trigger shadows: only
        # evaluate fixed price/confidence criteria in this offline snapshot.
        ok,reason=v21_accept_priced(choice)
        by_group["baseline"].append(row)
        if ok:
            by_group["v21_candidate"].append(row)
        else:
            by_group["blocked_"+reason].append(row)
    result={}
    for key,items in by_group.items():
        priced=[x for x in items if type((x.get("prediction") or {}).get("odds")) in (int,float) and x["prediction"]["odds"]>1]
        won=sum(bool(x["verified_prediction"]) for x in items)
        profit=sum(x["prediction"]["odds"]-1 if x["verified_prediction"] else -1 for x in priced)
        result[key]={"n":len(items),"wins":won,"hit_rate":round(won/len(items),4) if items else None,
                     "flat_units":round(profit,4),"flat_roi":round(profit/len(priced),4) if priced else None}
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--data",default="data.json")
    parser.add_argument("--output",default="bsd-v21-audit.json")
    args=parser.parse_args()
    data=json.loads(Path(args.data).read_text(encoding="utf-8"))
    report={"note":"Retrospective non-causal subset; not a prospective 100-200-pick validation",
            "source":args.data,"model_version":data.get("model_version"),
            "comparison":simulate(data.get("matches",[]))}
    Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=="__main__":
    main()
