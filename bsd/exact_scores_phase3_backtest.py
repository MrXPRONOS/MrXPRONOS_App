"""Phase 3 full 2026 walk-forward paired comparison (experimental)."""
import argparse,json
from collections import Counter
from pathlib import Path
from bsd_v2_core import V2History,estimate_goals,fixture_datetime,outcome_scores
from exact_scores import feature_rows,fit_rho_2024,fit_goal_scales_2025,matrix_for,top_scores
from exact_scores_under25 import train_under25
from exact_scores_under25_v2 import train,features
from exact_scores_h2h import H2HIndex,h2h_signal
from exact_scores_phase3 import decision,coherent_fusion

def bucket():return {"n":0,"under":0,"top1":0,"top3":0}
def observe(b,actual,matrix):
    best=top_scores(matrix)
    b["n"]+=1;b["under"]+=int(sum(actual)<=2)
    b["top1"]+=int(best[0][0]==actual)
    b["top3"]+=int(actual in [x for x,_ in best])
def summary(b):
    n=b["n"]
    return {"n":n,"under25_rate":round(b["under"]/n,5) if n else None,
            "top1_rate":round(b["top1"]/n,5) if n else None,
            "top3_rate":round(b["top3"]/n,5) if n else None}
def evaluate(events):
    index=V2History(events);hindex=H2HIndex(index)
    a,_=feature_rows(index,2024,650);b,_=feature_rows(index,2025,900)
    rho,_=fit_rho_2024(a);sh,sa,_=fit_goal_scales_2025(b,rho)
    params={"rho":rho,"scale_home":sh,"scale_away":sa}
    old,_=train_under25(index,params)
    newer,training=train(index,old,params)
    counts=Counter()
    groups={name:{"baseline":bucket(),"fused":bucket()} for name in
            ("all","legacy_h2h_under","phase3_selected")}
    rows=sorted((e for _,e in index.global_games if fixture_datetime(e).year==2026),
                key=lambda e:(fixture_datetime(e),str(e["id"])))
    for event in rows:
        f,why=estimate_goals(event,index)
        if f is None:counts[why]+=1;continue
        old_matrix=matrix_for(f["home"]*sh,f["away"]*sa,rho=rho)
        o=old.predict(event,index,old_matrix)
        x=features(event,index,o["probability"])
        p=newer.predict(x,o["probability"])
        flag=h2h_signal(hindex.past_scores(event))["prioritized"]
        d=decision(old_matrix,under_v1=o["probability"],under_v2=p,h2h_prioritized=flag)
        actual=outcome_scores(event)
        groups_to=["all"]
        if flag and o["priority"]:groups_to.append("legacy_h2h_under")
        if d["selected"]:groups_to.append("phase3_selected")
        else:counts.update({"abstain_"+reason:1 for reason in d["reasons"]})
        for group in groups_to:
            observe(groups[group]["baseline"],actual,old_matrix)
            observe(groups[group]["fused"],actual,d["matrix"])
    return {"format":"mrx-phase3-full-2026-v1","finished":len(rows),
            "eligible":groups["all"]["baseline"]["n"],
            "counts":dict(counts),"training":training,
            "comparison":{k:{m:summary(v) for m,v in gs.items()} for k,gs in groups.items()},
            "experimental":True,"published":False,
            "warning":"2026 has been explored before; the results are not a blind prospective test."}
def main():
    a=argparse.ArgumentParser()
    a.add_argument("--history",default="bsd/all_matches_bsd.json")
    a.add_argument("--out",default="tmp/exact-scores/phase3-report.json")
    args=a.parse_args()
    result=evaluate(json.loads(Path(args.history).read_text(encoding="utf-8")))
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("PHASE3_RESULT",json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
