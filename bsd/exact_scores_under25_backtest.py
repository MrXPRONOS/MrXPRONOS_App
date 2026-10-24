"""Full 2026 comparison: Under 2.5 specialist, stable H2H, exact-score fusion."""
import argparse,json
from collections import Counter,defaultdict
from math import sqrt
from pathlib import Path
from bsd_v2_core import V2History,estimate_goals,fixture_datetime,outcome_scores
from exact_scores import matrix_for,feature_rows,fit_rho_2024,fit_goal_scales_2025,top_scores
from exact_scores_h2h import H2HIndex,h2h_signal
from exact_scores_under25 import train_under25,reweight_scores

def wilson(hits,n):
    if not n:return None
    z=1.96;p=hits/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return [round(max(0,center-half),5),round(min(1,center+half),5)]

def summary(rows):
    n=len(rows)
    if not n:return {"n":0}
    return {"n":n,"under25_hits":sum(x["under_hit"] for x in rows),
            "under25_hit_rate":round(sum(x["under_hit"] for x in rows)/n,5),
            "under25_brier":round(sum((x["p_under"]-x["under_hit"])**2 for x in rows)/n,6),
            "top1_hits":sum(x["top1_hit"] for x in rows),
            "top3_hits":sum(x["top3_hit"] for x in rows),
            "top1_rate":round(sum(x["top1_hit"] for x in rows)/n,5),
            "top3_rate":round(sum(x["top3_hit"] for x in rows)/n,5),
            "under25_wilson95":wilson(sum(x["under_hit"] for x in rows),n),
            "top1_wilson95":wilson(sum(x["top1_hit"] for x in rows),n),
            "top3_wilson95":wilson(sum(x["top3_hit"] for x in rows),n),
            "mean_forecast_under25":round(sum(x["p_under"] for x in rows)/n,5)}

def evaluate(events):
    index=V2History(events);hindex=H2HIndex(index)
    a,_=feature_rows(index,2024,650);b,_=feature_rows(index,2025,900)
    rho,_=fit_rho_2024(a);sh,sa,_=fit_goal_scales_2025(b,rho)
    model,training=train_under25(index,{"rho":rho,"scale_home":sh,"scale_away":sa})
    groups={name:{"base":[],"fused":[]} for name in
            ("all","h2h","under25","h2h_and_under25","not_selected")}
    counters=Counter()
    monthly=defaultdict(lambda:{"all":[],"selected":[]})
    half_year={"2026_H1":{"all":[],"selected":[]},"2026_H2":{"all":[],"selected":[]}}
    fixtures=sorted((e for _,e in index.global_games if fixture_datetime(e).year==2026),
                    key=lambda e:(fixture_datetime(e),str(e["id"])))
    for event in fixtures:
        f,reason=estimate_goals(event,index)
        if f is None:counters[reason]+=1;continue
        original=matrix_for(f["home"]*sh,f["away"]*sa,rho=rho)
        under=model.predict(event,index,original)
        h2h=h2h_signal(hindex.past_scores(event))
        fused=reweight_scores(original,under["probability"])
        actual=outcome_scores(event)
        applicable=[ "all", "h2h" if h2h["prioritized"] else "not_selected"]
        if under["priority"]:applicable.append("under25")
        if h2h["prioritized"] and under["priority"]:applicable.append("h2h_and_under25")
        y=int(sum(actual)<=2)
        date=fixture_datetime(event)
        month=date.strftime("%Y-%m")
        half="2026_H1" if date.month<=6 else "2026_H2"
        for name,matrix,p in (("base",original,under["baseline"]),
                              ("fused",fused,under["probability"])):
            top=top_scores(matrix)
            row={"under_hit":y,"p_under":p,"top1_hit":int(top[0][0]==actual),
                 "top3_hit":int(actual in [sc for sc,_ in top])}
            for category in applicable:groups[category][name].append(row)
            if name=="fused":
                monthly[month]["all"].append(row)
                half_year[half]["all"].append(row)
                if "h2h_and_under25" in applicable:
                    monthly[month]["selected"].append(row)
                    half_year[half]["selected"].append(row)
    result={
        "format":"mrx-under25-h2h-exact-full-2026-v1","finished_2026":len(fixtures),
        "eligible_2026":len(groups["all"]["base"]),"skipped":dict(counters),
        "under25_model":{"blend":model.blend,"variance_scale":model.variance_scale,
                         "threshold":model.threshold},"training":training,
        "comparisons":{g:{name:summary(rows) for name,rows in models.items()}
                       for g,models in groups.items()},
        "by_month":{month:{tag:summary(v) for tag,v in stats.items()}
                    for month,stats in sorted(monthly.items())},
        "by_half":{period:{tag:summary(v) for tag,v in stats.items()}
                   for period,stats in half_year.items()},
        "experimental":True,"published":False,"used_odds":False,
        "note":"2026 retrospective, each forecast uses only settled past matches. Selection changes coverage. No profit claims."
    }
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument("--history",default="bsd/all_matches_bsd.json")
    p.add_argument("--out",default="tmp/exact-scores/under25-full-2026-report.json")
    a=p.parse_args();events=json.loads(Path(a.history).read_text(encoding="utf-8"))
    result=evaluate(events)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("UNDER25_FULL_2026",json.dumps(result,ensure_ascii=False))

if __name__=="__main__":main()
