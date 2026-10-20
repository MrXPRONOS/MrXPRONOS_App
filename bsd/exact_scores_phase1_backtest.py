"""Phase 1: ablation of H2H V2 gates on ALL finished BSD matches in 2026.

Exact-score engine and Under 2.5 threshold are frozen from existing research.
The only variable between the comparison groups is H2H V2 match selection.
Report selection coverage AND outcomes to prevent selective reporting.
"""
import argparse,json
from collections import Counter,defaultdict
from math import sqrt
from pathlib import Path
from bsd_v2_core import V2History,estimate_goals,fixture_datetime,outcome_scores
from exact_scores import matrix_for,feature_rows,fit_rho_2024,fit_goal_scales_2025,top_scores
from exact_scores_h2h import H2HIndex
from exact_scores_h2h_v2 import profile
from exact_scores_under25 import train_under25,reweight_scores

VARIANTS=("legacy","recency","venue","strength","reliability","combined","v2_standalone")
def bucket():return {"n":0,"top1":0,"top3":0,"under":0,"sum_p_under":0.0,"brier":0.0,"quality_sum":0.0}

def update(b,actual,matrix,p_under,quality):
    top=top_scores(matrix)
    y=int(sum(actual)<=2)
    b["n"]+=1
    b["top1"]+=int(top[0][0]==actual)
    b["top3"]+=int(actual in (t[0] for t in top))
    b["under"]+=y
    b["sum_p_under"]+=p_under
    b["brier"]+=(p_under-y)**2
    b["quality_sum"]+=quality

def wilson(k,n):
    if not n:return None
    z=1.96;p=k/n;den=1+z*z/n
    c=(p+z*z/(2*n))/den
    e=z*sqrt((p*(1-p)+z*z/(4*n*n)))/den
    return [round(max(0,c-e),5),round(min(1,c+e),5)]

def stats(b):
    n=b["n"]
    if not n:return {"n":0}
    return {"n":n,"top1_hits":b["top1"],"top3_hits":b["top3"],
        "top1_rate":round(b["top1"]/n,5),"top3_rate":round(b["top3"]/n,5),
        "under25_rate":round(b["under"]/n,5),
        "mean_predicted_under25":round(b["sum_p_under"]/n,5),
        "under25_brier":round(b["brier"]/n,6),
        "mean_stability_quality":round(b["quality_sum"]/n,2),
        "top3_wilson95":wilson(b["top3"],n)}

def evaluate(events):
    index=V2History(events);hindex=H2HIndex(index)
    sample24,_=feature_rows(index,2024,650)
    sample25,_=feature_rows(index,2025,900)
    rho,_=fit_rho_2024(sample24)
    sh,sa,_=fit_goal_scales_2025(sample25,rho)
    model,model_training=train_under25(index,{"rho":rho,"scale_home":sh,"scale_away":sa})
    totals=Counter()
    outcomes={key:bucket() for key in VARIANTS}
    halves={half:{key:bucket() for key in VARIANTS} for half in ("2026_H1","2026_H2")}
    months=defaultdict(lambda:{key:bucket() for key in VARIANTS})
    saved=[]
    fixtures=sorted((e for _,e in index.global_games if fixture_datetime(e).year==2026),
                    key=lambda e:(fixture_datetime(e),str(e.get("id"))))
    for event in fixtures:
        totals["finished"]+=1
        exp,reason=estimate_goals(event,index)
        if exp is None:
            totals["rejected_"+str(reason)]+=1
            continue
        totals["model_eligible"]+=1
        # Cheap pre-screen: no specialist prediction for a match with <3 H2H.
        hp=profile(event,index,hindex)
        if not hp.get("candidate"):continue
        totals["h2h_with_three_matches"]+=1
        variants=hp["variants"]
        if variants["legacy"]:totals["legacy_h2h"]+=1
        original=matrix_for(exp["home"]*sh,exp["away"]*sa,rho=rho)
        under=model.predict(event,index,original)
        if not under["priority"]:continue
        if variants["legacy"]:totals["legacy_h2h_with_under25"]+=1
        if variants["v2_standalone"]:totals["v2_standalone_with_under25"]+=1
        matrix=reweight_scores(original,under["probability"])
        actual=outcome_scores(event)
        kickoff=fixture_datetime(event)
        half="2026_H1" if kickoff.month<=6 else "2026_H2"
        quality=hp["features"]["stability_quality_index"]
        row={"id":str(event["id"]),"kickoff":kickoff.isoformat(),
             "h2h_v2_features":hp["features"],"h2h_gates":hp["gates"],
             "under25_probability":round(under["probability"],5),
             "score_actual":list(actual),"top3_predicted":[list(x) for x,_ in top_scores(matrix)]}
        saved.append(row)
        for key in VARIANTS:
            if variants[key]:
                update(outcomes[key],actual,matrix,under["probability"],quality)
                update(halves[half][key],actual,matrix,under["probability"],quality)
                update(months[kickoff.strftime("%Y-%m")][key],actual,matrix,
                       under["probability"],quality)
    report={"format":"mrx-h2h-v2-phase1-2026-research-v2",
            "published":False,"experimental":True,"odds_used":False,
            "model_parameters":{"rho":rho,"scale_home":sh,"scale_away":sa,
                                "under25_blend":model.blend,"under25_threshold":model.threshold},
            "under25_training":model_training,
            "finished_2026":totals["finished"],"model_eligible":totals["model_eligible"],
            "coverage":dict(totals),
            "variants":{k:stats(v) for k,v in outcomes.items()},
            "halves":{h:{k:stats(v) for k,v in d.items()} for h,d in halves.items()},
            "months":{m:{k:stats(v) for k,v in d.items()}
                      for m,d in sorted(months.items())},
            "selection_experiment":{"recency":"weighted H2H totals vs old unweighted",
                                    "venue":"same home/away orientation",
                                    "strength":"current pre-match attacking strength vs league",
                                    "reliability":"shrunken low-goals estimate with n_eff",
                                    "combined":"all four gates AND legacy signal",
                                    "v2_standalone":"all four gates WITHOUT legacy preselection"},
            "warning":"EXPLORATORY: 2026 outcomes have been inspected in prior research. No final unseen test or implied profitability.",
            "minimum_samples_for_comparison":60,
            "decision_guidance":"Never prefer a lower-sample variant on historical hit-rate alone; require prospective verification."}
    return report,saved

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--history",default="bsd/all_matches_bsd.json")
    parser.add_argument("--out-dir",default="tmp/exact-scores")
    a=parser.parse_args()
    path=Path(a.history)
    if not path.exists():parser.error("Restore encrypted BSD archive first")
    events=json.loads(path.read_text(encoding="utf-8"))
    report,rows=evaluate(events)
    out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
    (out/"phase1-h2h-report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    (out/"phase1-h2h-private-audit.json").write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
    print("PHASE1_H2H_2026",json.dumps({"coverage":report["coverage"],"variants":report["variants"],
                                     "halves":report["halves"]},ensure_ascii=False))

if __name__=="__main__":main()
