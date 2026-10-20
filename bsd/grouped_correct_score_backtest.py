"""Retrospective walk-forward experiment for real 1xBet group compositions.

No simulated bookmaker odds. Compare the same match population:
base-most-probable group, double-chance direction, H2H+Under filter.
Only evaluate full-time scores after the 4h settlement delay.
"""
from __future__ import annotations
import argparse,json
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from math import sqrt
from bsd_v2_core import V2History,fixture_datetime,outcome_scores
from exact_scores import year_sample
from exact_scores_h2h import H2HIndex
from grouped_correct_score import group_hit
from grouped_total_goals import CEILINGS
from grouped_correct_score_engine import fit_direction,analyze,selection_summary

FORM_RULES=("legacy","recent_attack","recent_defence","historical_h2h_context","venue_shift","model_agreement","combined","strict")
POLICIES=("baseline","with_double_chance","with_h2h_under","with_verified_price")+tuple("form_"+k for k in FORM_RULES)+tuple(f"ceiling_under_{n}5" for n in CEILINGS)
def new_bucket():return {"n":0,"hits":0,"sum_p":0.,"brier":0.,"ev_count":0}
def record(bucket,selection,score):
    if selection is None:return
    y=int(group_hit(selection["scores"],score))
    p=selection["probability"]
    bucket["n"]+=1;bucket["hits"]+=y;bucket["sum_p"]+=p
    bucket["brier"]+=(p-y)**2
    bucket["ev_count"]+=int(selection["expected_value"] is not None)
def wilson95(hits,n):
    if not n:return None
    z=1.96;p=hits/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den
    rad=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [round(max(0.,mid-rad),5),round(min(1.,mid+rad),5)]

def metrics(rows,eligible):
    n=rows["n"]
    return {"n":n,"coverage":round(n/eligible,6) if eligible else None,
        "wins":rows["hits"],"hit_rate":round(rows["hits"]/n,6) if n else None,
        "mean_probability":round(rows["sum_p"]/n,6) if n else None,
        "group_brier":round(rows["brier"]/n,6) if n else None,
        "priced_selections":rows["ev_count"],
        "small_sample":n<100,
        "wilson95":wilson95(rows["hits"],n),
        "calibration_gap":round(rows["hits"]/n-rows["sum_p"]/n,6) if n else None}
def run(events,*,max_2026=0):
    index=V2History(events);h2h=H2HIndex(index)
    dc,dc_training=fit_direction(index)
    samples=year_sample(index,2026,max_2026)
    buckets={k:new_bucket() for k in POLICIES}
    months=defaultdict(lambda:{k:new_bucket() for k in POLICIES})
    halves={"H1":{k:new_bucket() for k in POLICIES},
            "H2":{k:new_bucket() for k in POLICIES}}
    skips=Counter()
    group_stats={policy:{group:new_bucket() for group in ("G1","G2","G3","G4","G5","G6","G7","G8","G9")} for policy in POLICIES}
    pairs={name:{"baseline":new_bucket(),"candidate":new_bucket()} for name in ("dc_selected","priority_selected")}
    form_rejected={name:new_bucket() for name in FORM_RULES}
    risk_counts=Counter()
    goal_tier_counts=Counter()
    goal_actual_counts=Counter()
    paired_direction_changes={"n":0,"baseline_wins":0,"dc_wins":0,
                              "both_won":0,"both_lost":0}
    eligible=0
    for event in samples:
        now=fixture_datetime(event)
        pred,reason=analyze(event,index,h2h,dc,now=now,
                            require_prematch=False,evaluate_form_shift=True)
        if pred is None:skips[reason]+=1;continue
        score=outcome_scores(event)
        if score is None:skips["missing_final_score"]+=1;continue
        eligible+=1
        profile=pred["goals_profile"]
        goal_tier_counts[str(profile["smallest_eligible_max_goals"])]+=1
        total_goals=sum(score)
        goal_actual_counts["0_to_2" if total_goals<=2 else "3_to_4" if total_goals<=4
                          else "5_to_7" if total_goals<=7 else "8_plus"]+=1
        variants=selection_summary(pred)
        selected_old=variants.get("with_h2h_under")
        shift=pred.get("form_shift")
        if selected_old is not None and shift is not None:
            for flag,on in shift.get("flags",{}).items():
                if on:risk_counts[flag]+=1
            for name in FORM_RULES:
                if not shift.get("variant_pass",{}).get(name,False):
                    record(form_rejected[name],selected_old,score)
        month=now.strftime("%Y-%m")
        for key,item in variants.items():
            record(buckets[key],item,score)
            record(months[month][key],item,score)
            record(halves["H1" if now.month<=6 else "H2"][key],item,score)
            if item is not None:
                record(group_stats[key][item["group_id"]],item,score)
        base=variants["baseline"]
        directed=variants["with_double_chance"]
        if directed is not None and base["group_id"]!=directed["group_id"]:
            paired_direction_changes["n"]+=1
            bh=int(group_hit(base["scores"],score))
            dh=int(group_hit(directed["scores"],score))
            paired_direction_changes["baseline_wins"]+=bh
            paired_direction_changes["dc_wins"]+=dh
            paired_direction_changes["both_won"]+=int(bool(bh and dh))
            paired_direction_changes["both_lost"]+=int(not bh and not dh)
        for pair,policy in (("dc_selected","with_double_chance"),
                            ("priority_selected","with_h2h_under")):
            if variants[policy] is not None:
                record(pairs[pair]["baseline"],variants["baseline"],score)
                record(pairs[pair]["candidate"],variants[policy],score)
    return {"format":"mrx-1xbet-grouped-2026-comparison-v2",
       "historical_only":True,"published":False,"bookmaker_prices_available":False,
       "no_live_1xbet_quotes":True,"template_not_guaranteed_book_availability":True,
       "sample_cap":max_2026 if max_2026>0 else None,
       "finished_2026":len(samples),"eligible":eligible,"skipped":dict(skips),
       "dc_training":dc_training,
       "variants":{k:metrics(v,eligible) for k,v in buckets.items()},
       "group_breakdown":{policy:{gid:metrics(bucket,eligible) for gid,bucket in groups.items()}
                          for policy,groups in group_stats.items()},
       "paired_comparisons":{name:{key:metrics(b,eligible) for key,b in groups.items()}
                             for name,groups in pairs.items()},
       "actual_direction_changes":paired_direction_changes,
       "form_rule_rejected":{name:metrics(row,eligible) for name,row in form_rejected.items()},
       "form_shift_flag_frequency":dict(risk_counts),
       "goal_tier_distribution":dict(goal_tier_counts),
       "actual_total_goals_bands":dict(goal_actual_counts),
       "goal_ceiling_policy_note":"Nested total-goal CDFs permit more eligible fixtures; each selected bet still covers exactly one 1xBet 3-score group; price unavailable.",
       "halves":{h:{k:metrics(v,eligible) for k,v in groups.items()}
                 for h,groups in halves.items()},
       "months":{m:{k:metrics(v,eligible) for k,v in d.items()}
                 for m,d in sorted(months.items())},
       "warning":"Exploratory 2026 selection; 2026 already examined and repeatedly revised, not a blind test. Rates do not prove bookmaker availability, betting value or future profit. No 1xBet historical odds."}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--history",default="bsd/all_matches_bsd.json")
    parser.add_argument("--cap",type=int,default=0)
    parser.add_argument("--out",default="tmp/grouped-correct-score/historical-backtest.json")
    args=parser.parse_args()
    if args.cap<0:parser.error("cap must be positive or zero")
    events=json.loads(Path(args.history).read_text(encoding="utf-8"))
    result=run(events,max_2026=args.cap)
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("GROUPED_2026_BACKTEST",json.dumps({"eligible":result["eligible"],
          "dc_training":result["dc_training"],"variants":result["variants"],
          "paired_comparisons":result["paired_comparisons"],
          "actual_direction_changes":result["actual_direction_changes"],
          "group_breakdown":result["group_breakdown"],
          "form_rule_rejected":result["form_rule_rejected"],
          "form_shift_flag_frequency":result["form_shift_flag_frequency"],
          "halves":result["halves"],
          "goal_tier_distribution":result["goal_tier_distribution"],
          "actual_total_goals_bands":result["actual_total_goals_bands"]},ensure_ascii=False))

if __name__=="__main__":main()
