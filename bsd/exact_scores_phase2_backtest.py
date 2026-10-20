"""Phase 2 walk-forward evaluation on every finished 2026 fixture.

Predictive model is fitted entirely on 2024/2025. All 2026 decisions use only
data settled before the kickoff. No odds, publishing, or profit statements.
"""
import argparse,json
from collections import Counter,defaultdict
from pathlib import Path
from bsd_v2_core import V2History,estimate_goals,fixture_datetime,outcome_scores
from exact_scores import feature_rows,fit_rho_2024,fit_goal_scales_2025,matrix_for
from exact_scores_under25 import train_under25,probability_under25
from exact_scores_under25_v2 import train,features
from exact_scores_h2h import H2HIndex,h2h_signal

def bucket():return {"n":0,"wins":0,"brier":0.,"p_total":0.}
def append(b,p,y):
    b["n"]+=1;b["wins"]+=y;b["brier"]+=(p-y)**2;b["p_total"]+=p
def metrics(b):
    n=b["n"]
    if not n:return {"n":0}
    return {"n":n,"under25_hit_rate":round(b["wins"]/n,5),
            "predicted_rate":round(b["p_total"]/n,5),
            "brier":round(b["brier"]/n,6)}

def run(events):
    index=V2History(events);hindex=H2HIndex(index)
    train24,_=feature_rows(index,2024,650);train25,_=feature_rows(index,2025,900)
    rho,_=fit_rho_2024(train24);sh,sa,_=fit_goal_scales_2025(train25,rho)
    params={"rho":rho,"scale_home":sh,"scale_away":sa}
    old,info=train_under25(index,params)
    model,training=train(index,old,params)
    groupnames=("all","h2h","under25_priority","h2h_and_under25")
    buckets={g:{k:bucket() for k in ("v1","v2")} for g in groupnames}
    byhalf={half:{g:{k:bucket() for k in ("v1","v2")} for g in groupnames}
            for half in ("H1","H2")}
    skips=Counter()
    fixtures=sorted((e for _,e in index.global_games if fixture_datetime(e).year==2026),
                    key=lambda e:(fixture_datetime(e),str(e["id"])))
    for e in fixtures:
        est,reason=estimate_goals(e,index)
        if est is None:skips[reason]+=1;continue
        matrix=matrix_for(est["home"]*sh,est["away"]*sa,rho=rho)
        o=old.predict(e,index,matrix)
        x=features(e,index,probability_under25(matrix))
        v2=model.predict(x,o["probability"])
        y=int(sum(outcome_scores(e))<=2)
        selected=["all"]
        h2h=h2h_signal(hindex.past_scores(e))["prioritized"]
        if h2h:selected.append("h2h")
        if o["priority"]:selected.append("under25_priority")
        if h2h and o["priority"]:selected.append("h2h_and_under25")
        half="H1" if fixture_datetime(e).month<=6 else "H2"
        for g in selected:
            for label,p in (("v1",o["probability"]),("v2",v2)):
                append(buckets[g][label],p,y)
                append(byhalf[half][g][label],p,y)
    return {
        "format":"mrx-exact-score-phase2-under25-full-2026-v1",
        "finished":len(fixtures),"eligible":buckets["all"]["v1"]["n"],
        "skips":dict(skips),"trained_years":[2024,2025],
        "training":training,"legacy_training":info,
        "groups":{g:{k:metrics(v) for k,v in rows.items()} for g,rows in buckets.items()},
        "halves":{h:{g:{k:metrics(v) for k,v in groups.items()} for g,groups in hs.items()}
                  for h,hs in byhalf.items()},
        "published":False,"retrospective":True,"odds_available":False,
        "warning":"The 2026 archive has been inspected before. This is exploratory comparison, not genuinely unseen prospective validation."
    }

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--history",default="bsd/all_matches_bsd.json")
    a.add_argument("--out",default="tmp/exact-scores/phase2-under25-report.json")
    args=a.parse_args()
    rows=json.loads(Path(args.history).read_text(encoding="utf-8"))
    result=run(rows)
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("PHASE2_UNDER25_2026",json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
