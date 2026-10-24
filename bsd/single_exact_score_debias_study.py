"""A genuine, testable anti-1-1 calibration study. NOT an arbitrary diversity quota.

Candidate parameters are selected solely on chronological 2024 matches.
2025/2026 labels can ONLY be inspected once the parameters are frozen.
No effect on existing prospective picks, no Telegram or publication writes.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from math import isfinite

from bsd_v2_core import V2History,estimate_goals,fixture_datetime,outcome_scores
from exact_scores import year_sample,matrix_for
from exact_scores_under25 import Under25Model,reweight_scores,probability_under25

ONE_ONE=(1,1)
PARAMS=tuple((b,f) for b in (0.,.25,.50,.75,1.)
             for f in (.40,.60,.80,1.))
BASE=(1.,1.)
UNDER=Under25Model(1.,.85,.62)

def matrix_parts(event,index):
    expected,reason=estimate_goals(event,index)
    if expected is None:return None,reason
    base=matrix_for(expected["home"],expected["away"],
                    rho=0.,scale_home=1.10,scale_away=1.)
    est=UNDER.predict(event,index,base)
    return (base,probability_under25(base),est["probability"]),"ok"

def choose(parts,blend=1.,one_one_factor=1.):
    base,under_base,under_special=parts
    blend=float(blend);one_one_factor=float(one_one_factor)
    if not 0<=blend<=1 or not 0<one_one_factor<=1:
        raise ValueError("Invalid blending / 1-1 factor")
    target=(1-blend)*under_base+blend*under_special
    matrix=reweight_scores(base,target)
    # Shrink just one matrix cell then renormalize the WHOLE distribution.
    # Rankings of all OTHER exact scores remain unchanged.
    down=1-(1-one_one_factor)*matrix.get(ONE_ONE,0.)
    pairs=((k,v*(one_one_factor if k==ONE_ONE else 1.))
           for k,v in matrix.items())
    selected=max(pairs,key=lambda x:x[1])[0]
    probability=matrix[selected]*(one_one_factor if selected==ONE_ONE else 1.)/down
    return selected,probability

def tally(rows,config):
    hits=oneone=changes=net=0
    for parts,actual in rows:
        base,_=choose(parts,*BASE)
        candidate,_=choose(parts,*config)
        hits+=int(candidate==actual)
        oneone+=int(candidate==ONE_ONE)
        changes+=int(candidate!=base)
        net+=int(candidate==actual)-int(base==actual)
    n=len(rows)
    return {"n":n,"wins":hits,"accuracy":round(hits/n,6) if n else None,
            "one_one_predictions":oneone,"one_one_share":round(oneone/n,6) if n else None,
            "changed_from_old":changes,"net_wins":net}

def records(index,year,cap=0):
    result=[];skips=Counter()
    for match in year_sample(index,year,cap):
        actual=outcome_scores(match)
        if actual is None:continue
        parts,reason=matrix_parts(match,index)
        if parts is None:
            skips[reason]+=1
            continue
        result.append((fixture_datetime(match),parts,tuple(actual)))
    result.sort(key=lambda x:x[0])
    return result,dict(skips)

def frozen_fit(rows):
    """Train Jan-Aug 2024; VALIDATE Sep-Dec 2024 before 2025/26 inspection."""
    training=[(part,truth) for at,part,truth in rows if at.month<=8]
    validation=[(part,truth) for at,part,truth in rows if at.month>=9]
    basic_train=tally(training,BASE)
    basic_val=tally(validation,BASE)
    candidates=[]
    for candidate in PARAMS:
        tr=tally(training,candidate)
        vl=tally(validation,candidate)
        candidates.append({"blend":candidate[0],"one_one_factor":candidate[1],
                           "train":tr,"validation":vl})
    # Pick the train best, with a soft complexity tie break toward old model.
    best=max(candidates,key=lambda c:(c["train"]["wins"],
         -(1-c["one_one_factor"]),-(1-c["blend"])))
    # An improvement cannot be "smaller share alone". Protect real accuracy.
    activated=(len(training)>=120 and len(validation)>=80 and
               best["train"]["net_wins"]>=3 and
               best["validation"]["net_wins"]>=2 and
               best["validation"]["one_one_share"]<basic_val["one_one_share"])
    return {"format":"mrx-1-1-debias-frozen-2024-v1",
       "selection_basis":"2024 train Jan-Aug; validation Sep-Dec",
       "parameters":{ "under_blend":best["blend"],
                       "one_one_factor":best["one_one_factor"]} if activated else {
                           "under_blend":1.,"one_one_factor":1.},
       "activated":activated,
       "2024_train_baseline":basic_train,"2024_validation_baseline":basic_val,
       "candidate_train":best["train"],"candidate_validation":best["validation"],
       "best_train_candidate":{k:best[k] for k in ("blend","one_one_factor")},
       "2024_train_n":len(training),"2024_validation_n":len(validation),
       "reason":"chronological_2024_win_improvement" if activated else
                 "no_validated_accuracy_gain; preserve baseline",
       "candidate_grid":[{"blend":c["blend"],"factor":c["one_one_factor"],
           "train_net_wins":c["train"]["net_wins"],"validation_net_wins":c["validation"]["net_wins"],
           "validation_one_one_share":c["validation"]["one_one_share"]}
           for c in candidates]}

def evaluate(matches,cap=0):
    idx=V2History(matches)
    rows24,skip24=records(idx,2024,cap)
    model=frozen_fit(rows24)
    conf=model["parameters"]
    params=(conf["under_blend"],conf["one_one_factor"])
    # Explicit user objective is to reduce excessive 1-1 score forecasts.
    # Report the 0.80 policy even if the accuracy-optimal learning gate declines.
    reduction_policy=(1.,.80)
    reports={}
    for year in (2025,2026):
        rows,skips=records(idx,year,cap)
        observations=[(parts,truth) for _,parts,truth in rows]
        reports[str(year)]={
            "baseline":tally(observations,BASE),
            "candidate":tally(observations,params),
            "reduce_one_one_20_percent":tally(observations,reduction_policy),
            "available_fixtures":len(rows),"rejected":skips}
    return {"format":"mrx-1-1-bias-historical-validation-v1",
            "research_only":True,"published":False,
            "backtest_clock":"kickoff; as-of historic 4h result delay",
            "no_true_blind_2026_claim":True,
            "training_2024":model,
            "2024_reduction_policy":{
                "validation":tally([(part,actual) for at,part,actual in rows24
                                    if at.month>=9],reduction_policy),
                "training":tally([(part,actual) for at,part,actual in rows24
                                  if at.month<=8],reduction_policy),
                "policy":reduction_policy},
            "years":reports,"2024_rejected":skip24,
            "warning":"Historical study, not a prospective win guarantee. "
                      "Do not change live predictions solely to reduce 1-1 share."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--history",default="bsd/all_matches_bsd.json")
    p.add_argument("--cap",type=int,default=0)
    p.add_argument("--output",default="tmp/single-exact-score/one-one-debias-study.json")
    args=p.parse_args()
    events=json.loads(Path(args.history).read_text(encoding="utf8"))
    result=evaluate(events,cap=args.cap)
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf8")
    print("ONE_ONE_STUDY",json.dumps({
        "fit":{k:v for k,v in result["training_2024"].items()
               if k!="candidate_grid"},
        "years":result["years"]},ensure_ascii=False))

if __name__=="__main__":
    main()
