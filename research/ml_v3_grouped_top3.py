#!/usr/bin/env python3
"""Research-only grouped correct scores: fixed 1xBet-STYLE proxy, NOT actual offered markets.

Hybrid V3 is selected by its ORIGINAL Top3/5/10/20 exact-score modal confidence.
After selecting the same matches, its modal score is mapped to a disjoint
fixed 3-score group, before reading the actual match outcome. No backfilled
market offerings and no historical odds: hit rate != win rate/ROI in real betting.
Predicted scores outside named groups ABSTAIN; counted in original K denominator.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import date,timedelta
from pathlib import Path
from ml_v3_topk_full_2026 import WINDOWS, days_in_period, _safe_output
KS=(3,5,10,20)  # Top3 added; Top5/10/20 retained to verify nested equivalence
from ml_v2_topk import _check_row
from single_ml_v3 import HYBRID_NAME

VERSION="grouped_exact_score_proxy_frozen_v2_top3_20261102"
# Disjoint scores, all groups contain EXACTLY three elements. Named score
# combinations are RESEARCH PROXIES; actual 1xBet event groups vary by market.
GROUPS={
  "H_LOW":("1:0","2:0","2:1"),
  "H_HIGH":("3:0","3:1","3:2"),
  "A_LOW":("0:1","0:2","1:2"),
  "A_HIGH":("0:3","1:3","2:3"),
  "DRAW_LOW":("0:0","1:1","2:2"),
}
SCORE_TO_GROUP={score:name for name,values in GROUPS.items() for score in values}
if len(SCORE_TO_GROUP)!=3*len(GROUPS):
    raise RuntimeError("Overlapping grouped-score market or duplicate scores")


def result_1x2(score):
    h,a=(int(x) for x in score.split(":"))
    return "H" if h>a else "A" if h<a else "D"


def settle(predicted,actual):
    """Only PREMATCH predicted score determines the group. No actual in selection."""
    if predicted not in SCORE_TO_GROUP:
        return {"group":None,"covered":False,"win":False,"exact":predicted==actual,
                "result_1x2_win":result_1x2(predicted)==result_1x2(actual)}
    group=SCORE_TO_GROUP[predicted]
    return {"group":group,"covered":True,"win":actual in GROUPS[group],
            "exact":predicted==actual,
            "result_1x2_win":result_1x2(predicted)==result_1x2(actual)}


def month(path,*,start,end):
    if (start,end) not in WINDOWS:
        raise ValueError("Only frozen 2026 Jan-Sep and partial Oct windows accepted")
    grouped=defaultdict(dict)
    with open(path,encoding="utf8",newline="") as fh:
        reader=csv.DictReader(fh)
        required={"model","date","id","predicted_score","actual_score",
          "top_probability","model_fit_latest_day","history_latest_day","hit"}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError("Missing frozen research prediction columns")
        for raw in reader:
            if raw["model"]!=HYBRID_NAME:
                continue
            row=_check_row(raw,start=start,end=end,allowed_models=(HYBRID_NAME,))
            if row is None:continue
            key=row["date"]
            if row["id"] in grouped[key]:
                raise ValueError("Duplicate research fixture for Hybrid V3")
            grouped[key][row["id"]]=row
    days=days_in_period(start,end)
    data={str(k):[] for k in KS}
    cohort=[]
    for day in days:
        rows=list(grouped[day].values())
        if len(rows)<max(KS):
            raise ValueError(f"{day}: fewer than 20 prematch Hybrid V3 predictions")
        ordered=sorted(rows,key=lambda r:(-r["confidence"],r["id"]))
        cohort.append({"day":day,"candidates":len(ordered)})
        for k in KS:
            chosen=ordered[:k]
            settled=[settle(r["predicted_score"],r["actual_score"]) for r in chosen]
            mapped=[s for s in settled if s["covered"]]
            wins=sum(int(s["win"]) for s in settled)
            exact=sum(int(s["exact"]) for s in settled)
            covered_exact=sum(int(s["exact"]) for s in mapped)
            gcounts=Counter(s["group"] for s in mapped)
            ghits=Counter(s["group"] for s in mapped if s["win"])
            # The group can NEVER be worse than the original exact score
            # ON A COVERED fixture, but abstentions can lower all-K coverage.
            if wins<covered_exact:
                raise RuntimeError("Logical violation of group inclusion")
            if any(s["win"] and not s["result_1x2_win"] for s in settled):
                raise RuntimeError("Grouped score improperly changed 1X2 outcome")
            data[str(k)].append({
              "day":day,"k":k,"candidates":len(ordered),
              "covered":len(mapped),"abstentions":k-len(mapped),
              "exact_hits_full_k":exact,
              "exact_hits_covered":covered_exact,
              "grouped_hits":wins,
              "group_extra_hits_vs_covered_exact":wins-covered_exact,
              "result_1x2_hits_full_k":sum(s["result_1x2_win"] for s in settled),
              "days_exact_ge1":int(exact>=1),"days_exact_ge2":int(exact>=2),
              "days_group_ge1":int(wins>=1),"days_group_ge2":int(wins>=2),
              "days_group_ge3":int(wins>=3),
              "group_counts":{name:gcounts[name] for name in GROUPS},
              "group_wins":{name:ghits[name] for name in GROUPS},
            })
    report={
        "research_only":True,"version":VERSION,"period":[start,end],
        "model":HYBRID_NAME,"ks":list(KS),"days":days,
        "groups":{key:list(scores) for key,scores in GROUPS.items()},
        "grouping":"EXPERIMENTAL fixed 3-score proxy, not verified 1xBet live or historical offerings",
        "selection":"Top K original unmodified Hybrid V3 modal score confidence; fixed group mapped strictly from predicted score",
        "cohort":cohort,"daily":data,
        "limitations":"No bookmaker historical availability, odds, stake or ROI. More covered scores mechanically increase group event hit chance; abstentions count against original K.",
    }
    validate_month(report)
    return report


def validate_month(report):
    pair=tuple(report.get("period") or [])
    if pair not in WINDOWS or report.get("model")!=HYBRID_NAME or report.get("version")!=VERSION:
        raise ValueError("Not a frozen Hybrid V3 grouping period")
    if report.get("groups")!={key:list(v) for key,v in GROUPS.items()}:
        raise ValueError("Market groups altered after outcomes")
    days=days_in_period(*pair)
    if report.get("days")!=days or [r["day"] for r in report.get("cohort",[])]!=days:
        raise ValueError("Incomplete calendar day coverage")
    for k in KS:
        rows=report["daily"][str(k)]
        if [r["day"] for r in rows]!=days:raise ValueError("Incomplete model TopK days")
        for i,r in enumerate(rows):
            if r["k"]!=k or r["candidates"]!=report["cohort"][i]["candidates"]:
                raise ValueError("Inconsistent common candidate cohort")
            if r["covered"]+r["abstentions"]!=k:
                raise ValueError("Abstention count inconsistency")
            if sum(r["group_counts"].values())!=r["covered"] or sum(r["group_wins"].values())!=r["grouped_hits"]:
                raise ValueError("Groups improperly counted")
            if (not 0<=r["exact_hits_covered"]<=r["grouped_hits"]<=r["covered"]<=k
              or not 0<=r["exact_hits_covered"]<=r["exact_hits_full_k"]<=k
              or not r["grouped_hits"]<=r["result_1x2_hits_full_k"]<=k):
                raise ValueError("Group vs score/1X2 logical inconsistency")
            if r["group_extra_hits_vs_covered_exact"]!=r["grouped_hits"]-r["exact_hits_covered"]:
                raise ValueError("Incorrect extra hits")
            for count,hit in (("days_exact_ge1","exact_hits_full_k"),("days_exact_ge2","exact_hits_full_k"),
                ("days_group_ge1","grouped_hits"),("days_group_ge2","grouped_hits"),
                ("days_group_ge3","grouped_hits")):
                minimum=2 if count.endswith("ge2") else 3 if count.endswith("ge3") else 1
                if r[count]!=int(r[hit]>=minimum):
                    raise ValueError("Contradictory daily successes")


def totals(rows):
    if not rows:raise ValueError("Empty daily grouping records")
    days=len(rows);k=rows[0]["k"];n=k*days
    covered=sum(r["covered"] for r in rows);wins=sum(r["grouped_hits"] for r in rows)
    exact=sum(r["exact_hits_full_k"] for r in rows)
    return {
        "days":days,"selection_slots":n,
        "group_offered_proxy_slots":covered,
        "abstained_slots":n-covered,
        "group_mapping_coverage_pct":round(100*covered/n,4),
        "exact_score_hits":exact,
        "exact_score_hit_rate_pct":round(100*exact/n,4),
        "exact_score_days_ge1":sum(r["days_exact_ge1"] for r in rows),
        "exact_score_days_ge2":sum(r["days_exact_ge2"] for r in rows),
        "grouped_hits":wins,
        "group_hit_rate_all_k_pct":round(100*wins/n,4),
        "group_hit_rate_on_covered_pct":round(100*wins/covered,4) if covered else None,
        "days_group_ge1":sum(r["days_group_ge1"] for r in rows),
        "days_group_ge2":sum(r["days_group_ge2"] for r in rows),
        "days_group_ge3":sum(r["days_group_ge3"] for r in rows),
        "days_group_ge1_pct":round(100*sum(r["days_group_ge1"] for r in rows)/days,4),
        "days_group_ge2_pct":round(100*sum(r["days_group_ge2"] for r in rows)/days,4),
        "days_group_ge3_pct":round(100*sum(r["days_group_ge3"] for r in rows)/days,4),
        "extra_group_hits_vs_covered_exact":sum(r["group_extra_hits_vs_covered_exact"] for r in rows),
        "result_1x2_hits":sum(r["result_1x2_hits_full_k"] for r in rows),
        "group_break_even_decimal_odds_before_fees":round(covered/wins,4) if wins else None,
        "by_group":{name:{
            "predictions":sum(r["group_counts"][name] for r in rows),
            "hits":sum(r["group_wins"][name] for r in rows),
        } for name in GROUPS},
    }


def pool(paths):
    if len(paths)!=len(WINDOWS):
        raise ValueError("Expected exactly 10 frozen periods (Jan-Sep + 1–24 October)")
    reports={}
    for path in paths:
        r=json.loads(Path(path).read_text(encoding="utf8"))
        validate_month(r)
        key=tuple(r["period"])
        if key in reports:raise ValueError("Duplicate evaluation period")
        reports[key]=r
    if set(reports)!=set(WINDOWS):
        raise ValueError("Incomplete 2026 monthly coverage")
    ordered=[reports[period] for period in WINDOWS]
    primary=ordered[:9];october=ordered[9:]
    if sum(map(lambda p:len(p["days"]),primary))!=273 or len(october[0]["days"])!=24:
        raise ValueError("Incorrect 2026 available historical days")
    def aggregate(items):
        return {str(k):totals([day for period in items for day in period["daily"][str(k)]]) for k in KS}
    return {
        "research_only":True,"model":HYBRID_NAME,"version":VERSION,
        "frozen_periods":[list(w) for w in WINDOWS],
        "groups":{key:list(scores) for key,scores in GROUPS.items()},
        "primary_complete_months":"Jan-Sep 2026",
        "primary":aggregate(primary),
        "october_partial_1_to_24":aggregate(october),
        "all_available_2026_descriptive":aggregate(ordered),
        "monthly":[{"month":p["period"][0][:7],
                    "partial":i==9,
                    "days":len(p["days"]),
                    "topk":aggregate([p])} for i,p in enumerate(ordered)],
        "reality_check":"Research proxy group hit rate is mechanically larger than exact score hit rate for covered scores and MUST NOT be interpreted as model learning uplift or as positive expected value. Requires historical offered groups and decimal odds to estimate actual betting yield.",
    }


def main():
    ap=argparse.ArgumentParser()
    cmd=ap.add_subparsers(dest="cmd",required=True)
    m=cmd.add_parser("month")
    for x in ("predictions","start","end","out"):
        m.add_argument("--"+x,required=True)
    p=cmd.add_parser("pool")
    p.add_argument("--inputs",nargs="+",required=True)
    p.add_argument("--out",required=True)
    args=ap.parse_args()
    if args.cmd=="month":
        rep=month(args.predictions,start=args.start,end=args.end)
        _safe_output(args.out).write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf8")
        print("HYBRID_V3_GROUP_MONTH",json.dumps({
           "period":rep["period"],"days":len(rep["days"]),
           "top3":totals(rep["daily"]["3"]),"top5":totals(rep["daily"]["5"]),"top10":totals(rep["daily"]["10"])}),flush=True)
    else:
        rep=pool(args.inputs)
        _safe_output(args.out).write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf8")
        print("HYBRID_V3_GROUP_FULL_2026",json.dumps({
           "primary_top3":rep["primary"]["3"],"primary_top5":rep["primary"]["5"],"october_top3":rep["october_partial_1_to_24"]["3"],
           "limitations":rep["reality_check"]}),flush=True)


if __name__=="__main__":main()
