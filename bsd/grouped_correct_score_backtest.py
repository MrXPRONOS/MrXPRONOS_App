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
from bsd_v2_core import V2History,fixture_datetime,outcome_scores
from exact_scores import year_sample
from exact_scores_h2h import H2HIndex
from grouped_correct_score import group_hit
from grouped_correct_score_engine import fit_direction,analyze,selection_summary

POLICIES=("baseline","with_double_chance","with_h2h_under","with_verified_price")
def new_bucket():return {"n":0,"hits":0,"sum_p":0.,"brier":0.,"ev_count":0}
def record(bucket,selection,score):
    if selection is None:return
    y=int(group_hit(selection["scores"],score))
    p=selection["probability"]
    bucket["n"]+=1;bucket["hits"]+=y;bucket["sum_p"]+=p
    bucket["brier"]+=(p-y)**2
    bucket["ev_count"]+=int(selection["expected_value"] is not None)
def metrics(rows,eligible):
    n=rows["n"]
    return {"n":n,"coverage":round(n/eligible,6) if eligible else None,
        "wins":rows["hits"],"hit_rate":round(rows["hits"]/n,6) if n else None,
        "mean_probability":round(rows["sum_p"]/n,6) if n else None,
        "group_brier":round(rows["brier"]/n,6) if n else None,
        "priced_selections":rows["ev_count"]}
def run(events,*,max_2026=0):
    index=V2History(events);h2h=H2HIndex(index)
    dc,dc_training=fit_direction(index)
    samples=year_sample(index,2026,max_2026)
    buckets={k:new_bucket() for k in POLICIES}
    months=defaultdict(lambda:{k:new_bucket() for k in POLICIES})
    skips=Counter()
    eligible=0
    for event in samples:
        now=fixture_datetime(event)
        pred,reason=analyze(event,index,h2h,dc,now=now,
                            require_prematch=False)
        if pred is None:skips[reason]+=1;continue
        score=outcome_scores(event)
        if score is None:skips["missing_final_score"]+=1;continue
        eligible+=1
        variants=selection_summary(pred)
        month=now.strftime("%Y-%m")
        for key,item in variants.items():
            record(buckets[key],item,score)
            record(months[month][key],item,score)
    return {"format":"mrx-1xbet-grouped-2026-comparison-v1",
       "historical_only":True,"published":False,"bookmaker_prices_available":False,
       "no_live_1xbet_quotes":True,"template_not_guaranteed_book_availability":True,
       "sample_cap":max_2026 if max_2026>0 else None,
       "finished_2026":len(samples),"eligible":eligible,"skipped":dict(skips),
       "dc_training":dc_training,
       "variants":{k:metrics(v,eligible) for k,v in buckets.items()},
       "months":{m:{k:metrics(v,eligible) for k,v in d.items()}
                 for m,d in sorted(months.items())},
       "warning":"Exploratory 2026 selection; rates do not prove betting value or future profit. No 1xBet historical odds."}

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
          "dc_training":result["dc_training"],"variants":result["variants"]},ensure_ascii=False))

if __name__=="__main__":main()
