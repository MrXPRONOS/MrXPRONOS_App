"""Read-only grouped correct-score performance by league, season and period.
No publishing, no odds assumptions, no parameter searches. Research branch only.
Historical results are exploratory because 2025/2026 have been examined.
"""
import argparse, json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from bsd_v2_core import V2History, fixture_datetime, outcome_scores, league_key
from exact_scores import year_sample
from exact_scores_h2h import H2HIndex
from grouped_correct_score_engine import fit_direction, analyze, selection_summary
from grouped_correct_score import group_hit

POLICIES=("baseline","with_double_chance","with_h2h_under","ceiling_under_25","ceiling_under_35")
def league_name(e):
    lg=e.get("league")
    if isinstance(lg,dict): return str(lg.get("name") or e.get("league_name") or league_key(e))
    return str(e.get("league_name") or (lg if isinstance(lg,str) else None) or league_key(e))
def bucket():
    return {"n":0,"won":0,"p_sum":0.0,"brier_sum":0.0}
def add(target,selection,actual):
    if selection is None:return
    hit=int(group_hit(selection["scores"],actual))
    target["n"]+=1;target["won"]+=hit
    p=selection["probability"]
    target["p_sum"]+=p;target["brier_sum"]+=(p-hit)**2
def rounded(r):
    n=r["n"]
    return {"n":n,"wins":r["won"],"rate":round(r["won"]/n,5) if n else None,
            "mean_model_probability":round(r["p_sum"]/n,5) if n else None,
            "brier":round(r["brier_sum"]/n,5) if n else None}
def run(history,years,cap):
    idx=V2History(history);hindex=H2HIndex(idx);dc,train=fit_direction(idx)
    groups=defaultdict(bucket); leagues=defaultdict(bucket)
    periods=defaultdict(bucket);counts=defaultdict(int)
    all_groups_league=defaultdict(bucket);all_groups_half=defaultdict(bucket)
    all_groups_month=defaultdict(bucket);funnel=defaultdict(lambda:defaultdict(int))
    labels={}
    for year in years:
        for event in year_sample(idx,year,cap if year==2026 else 0):
            now=fixture_datetime(event)
            try:
                record,reason=analyze(event,idx,hindex,dc,now=now,require_prematch=False,evaluate_form_shift=False)
            except Exception as exc:
                counts["errors_"+type(exc).__name__]+=1
                continue
            if record is None:
                counts["skipped_"+reason]+=1;continue
            result=outcome_scores(event)
            if result is None:continue
            key=league_key(event) or "unknown"
            labels[key]=league_name(event)
            choices=selection_summary(record)
            counts[str(year)]+=1
            half="H1" if now.month<=6 else "H2"
            month=now.strftime("%Y-%m")
            f=funnel[str(year)]
            f["eligible"]+=1
            h2h_ok=bool(record.get("h2h_priority"))
            under_ok=bool(record.get("under25_priority"))
            f["h2h_yes" if h2h_ok else "h2h_no"]+=1
            f["under25_yes" if under_ok else "under25_no"]+=1
            if h2h_ok and under_ok: f["both_h2h_under25"]+=1
            if choices.get("with_h2h_under") is not None:
                f["both_plus_direction"]+=1
            for g in record["groups"]:
                # Same fixtures for all nine groups. These are observed
                # RESEARCH TEMPLATES, not evidence of bookmaker offers.
                gid=g["group_id"]
                add(all_groups_league[(year,key,gid)],g,result)
                add(all_groups_half[(year,half,gid)],g,result)
                add(all_groups_month[(year,month,gid)],g,result)
            for name in POLICIES:
                selected=choices.get(name)
                if selected is None:continue
                gid=selected["group_id"]
                add(groups[(year,name,gid)],selected,result)
                add(leagues[(year,key,name,gid)],selected,result)
                add(leagues[(year,key,name,"ALL")],selected,result)
                add(periods[(year,half,name,gid)],selected,result)
                add(periods[(year,half,name,"ALL")],selected,result)
    def asrows(d,keynames):
        return [{**dict(zip(keynames,key)),**rounded(v)} for key,v in d.items() if v["n"]]
    output={"generated_utc":datetime.utcnow().isoformat()+"Z","experimental":True,"published":False,
            "bookmaker_prices":False,"history_explored":True,"model_training":train,
            "counts":dict(counts),"league_labels":labels,
            "filter_funnel":{year:dict(row) for year,row in funnel.items()},
            "all_nine_groups_on_same_fixtures_by_league":asrows(all_groups_league,["year","league","group"]),
            "all_nine_groups_on_same_fixtures_by_half":asrows(all_groups_half,["year","half","group"]),
            "all_nine_groups_on_same_fixtures_by_month":asrows(all_groups_month,["year","month","group"]),
            "by_group":asrows(groups,["year","policy","group"]),
            "by_league":asrows(leagues,["year","league","policy","group"]),
            "by_half":asrows(periods,["year","half","policy","group"]),
            "disclaimer":"Descriptive historical segmentation, NOT independent holdout or bookmaker ROI."}
    return output
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--history",default="bsd/all_matches_bsd.json")
    parser.add_argument("--out",default="tmp/grouped-correct-score/league-review.json")
    parser.add_argument("--cap-2026",type=int,default=0)
    args=parser.parse_args()
    report=run(json.loads(Path(args.history).read_text(encoding="utf-8")),(2025,2026),args.cap_2026)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("GROUPED_LEAGUE_COUNTS",json.dumps(report["counts"]))
    print("GROUPED_LEAGUE_LABELS",len(report["league_labels"]))
    print("GROUPED_FILTER_FUNNEL",json.dumps(report["filter_funnel"]))
    for year in (2025,2026):
        top=sorted((r for r in report["all_nine_groups_on_same_fixtures_by_league"]
                    if r["year"]==year and r["n"]>=30),
                   key=lambda r:(-r["n"],r["group"]))[:10]
        print("GROUPED_FIXED_FIXTURE_LEAGUE",year,json.dumps(top,ensure_ascii=False))
    print("GROUPED_LEAGUE_TOP",json.dumps(sorted((r for r in report["by_league"] if r["policy"]=="ceiling_under_25" and r["group"]=="ALL" and r["n"]>=15),key=lambda r:(r["year"],-r["n"]))[:30],ensure_ascii=False))
if __name__=="__main__":main()
