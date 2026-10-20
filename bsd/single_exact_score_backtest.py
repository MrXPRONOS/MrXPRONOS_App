"""Walk-forward audit: exactly one score per match, paired model variants.

2025 and 2026 are historical research. Previously studied 2026 is NOT a
blind test. Single exact score Top-1 != 'one of three scores' success.
No bookmaker prices, ROI, publishing or Telegram sends.
"""
import argparse,json,math
from collections import Counter,defaultdict
from pathlib import Path
from bsd_v2_core import V2History,fixture_datetime,outcome_scores
from exact_scores import year_sample
from exact_scores_h2h import H2HIndex
from single_exact_score_engine import forecast,train_dc
from single_exact_score_research import audit
from single_exact_score_distributions import candidates

LABELS=("original","under25_fusion","optional_dc_fusion")

def bucket():
    return {"n":0,"hits":0,"sum_predicted_p":0.,"brier":0.,"logloss":0.}
def add(b,choice,truth):
    if choice is None:return
    score=tuple(choice["score"]);p=choice["probability"]
    y=int(score==truth)
    b["n"]+=1;b["hits"]+=y;b["sum_predicted_p"]+=p
    b["brier"]+=(p-y)**2
    b["logloss"]+=-math.log(max(p,1e-12)) if y else -math.log(max(1-p,1e-12))
def wilson95(k,n):
    if not n:return None
    z=1.96;p=k/n;d=1+z*z/n
    mid=(p+z*z/(2*n))/d
    rad=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [round(max(0.,mid-rad),5),round(min(1.,mid+rad),5)]
def summary(b,all_n):
    n=b["n"];wins=b["hits"]
    return {"matches":n,"wins":wins,"top1_rate":round(wins/n,6) if n else None,
            "coverage":round(n/all_n,6) if all_n else None,
            "mean_predicted_p":round(b["sum_predicted_p"]/n,6) if n else None,
            "single_score_brier":round(b["brier"]/n,6) if n else None,
            "binary_logloss":round(b["logloss"]/n,6) if n else None,
            "wilson95":wilson95(wins,n),"small_sample":n<100}
def compare(events,year=2026,cap=0,*,dc_model=None):
    index=V2History(events)
    hindex=H2HIndex(index)
    training=None
    if dc_model is None:
        dc_model,training=train_dc(index)
    variants={k:bucket() for k in LABELS}
    groups={label:{k:bucket() for k in LABELS} for label in (
        "priority","other","h2h_under","high_total_goals","top_score_zero")}
    months=defaultdict(lambda:{k:bucket() for k in LABELS})
    score_frequency=Counter();reasons=Counter();direction_changes=Counter()
    total_finished=0
    research_rows=[]
    distributions=defaultdict(lambda:{"n":0,"wins":0,"nll":0.,"brier":0.})
    for event in year_sample(index,year,cap):
        truth=outcome_scores(event)
        if truth is None:continue
        total_finished+=1
        at=fixture_datetime(event)
        pred,why=forecast(event,index,hindex,now=at,dc_model=dc_model,
                          require_prematch=False,compute_form=False)
        if pred is None:
            reasons[why]+=1;continue
        picked=tuple(pred["score"])
        research_rows.append({"id":str(event["id"]),"kickoff":at.isoformat(),
            "actual":list(truth),"variants":pred["ablation"],
            "league":event.get("league_id") or event.get("league_name"),
            "total_expected_goals":pred["total_expected_goals"],
            "quality":pred["data_quality"],"context":pred["prematch_context"]})
        for name,mat in candidates(pred["expected_goals"]["home"],pred["expected_goals"]["away"]).items():
            b=distributions[name];actual_p=max(mat.get(truth,0.),1e-12)
            b["n"]+=1;b["wins"]+=int(max(mat,key=mat.get)==truth)
            b["nll"]+=-math.log(actual_p)
            b["brier"]+=1+sum(p*p for p in mat.values())-2*actual_p
        score_frequency[f"{picked[0]}-{picked[1]}"]+=1
        names=["priority" if pred["research_priority"] else "other"]
        if pred["h2h_low_stable"] and pred["under25_probability"]>=.62:
            names.append("h2h_under")
        if pred["total_expected_goals"]>=3.0:
            names.append("high_total_goals")
        if 0 in picked:
            names.append("top_score_zero")
        monthly=months[at.strftime("%Y-%m")]
        for k in LABELS:
            ablation=pred["ablation"][k]
            add(variants[k],ablation,truth)
            add(monthly[k],ablation,truth)
            for name in names:add(groups[name][k],ablation,truth)
        if pred["ablation"]["optional_dc_fusion"] is not None and (
                pred["ablation"]["optional_dc_fusion"]["score"]!=pred["score"]):
            direction_changes["changed"]+=1
            direction_changes["baseline_correct_when_changed"]+=int(
                pred["score"]==list(truth))
            direction_changes["dc_correct_when_changed"]+=int(
                pred["ablation"]["optional_dc_fusion"]["score"]==list(truth))
    n=variants["under25_fusion"]["n"]
    return {"format":"mrx-single-score-historical-backtest-v1",
            "year":year,"finished":total_finished,"eligible":n,
            "sample_cap":cap or None,"dc_training":training,
            "experimental":True,"published":False,
            "variants":{k:summary(b,n) for k,b in variants.items()},
            "groups":{g:{k:summary(b,n) for k,b in policies.items()} for g,policies in groups.items()},
            "monthly":{m:{k:summary(b,n) for k,b in v.items()} for m,v in sorted(months.items())},
            "selected_score_frequency":dict(score_frequency.most_common(15)),
            "dc_changes":dict(direction_changes),
            "not_evaluated":dict(reasons),
            "distribution_experiments":{k:{"matches":v["n"],"wins":v["wins"],
                 "top1_rate":round(v["wins"]/v["n"],6) if v["n"] else None,
                 "multiclass_logloss":round(v["nll"]/v["n"],6) if v["n"] else None,
                 "multiclass_brier":round(v["brier"]/v["n"],6) if v["n"] else None}
                for k,v in distributions.items()},
            **audit(research_rows),
            "note":"One actual score only. Previously examined 2026 is exploratory, not a blind out-of-sample test. No bookmaker odds or ROI."}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--history",default="bsd/all_matches_bsd.json")
    parser.add_argument("--year",type=int,choices=(2025,2026),default=2026)
    parser.add_argument("--cap",type=int,default=0)
    parser.add_argument("--output",default="tmp/single-exact-score/historical-report.json")
    args=parser.parse_args()
    index=json.loads(Path(args.history).read_text(encoding="utf-8"))
    result=compare(index,args.year,args.cap)
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print("SINGLE_EXACT_SCORE_BACKTEST",json.dumps({
        "year":args.year,"finished":result["finished"],
        "eligible":result["eligible"],"variants":result["variants"],
        "groups":{name:{key:{"matches":m["matches"],"wins":m["wins"],
                           "top1_rate":m["top1_rate"]}
                        for key,m in metrics.items()}
                  for name,metrics in result["groups"].items()},
        "dc_changes":result["dc_changes"]},ensure_ascii=False))
if __name__=="__main__":main()
