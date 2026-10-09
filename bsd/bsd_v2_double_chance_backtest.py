"""Independent 2026 double-chance benchmark: same fixtures and calibrated baseline."""
import argparse,json
from collections import defaultdict
from pathlib import Path
from bsd_archive import MATCHES_FILE,_read_json
from bsd_v2_core import V2History,fit_rho_2024,estimate_goals,markets_from_matrix,score_matrix,outcome_scores,league_key
from bsd_v2_double_chance import fit_model,adjust_candidates,score_probs
from bsd_v2_policies import fit_policy
from bsd_v2_evaluate import get_sample

KEYS=("1X","X2","12")
def stats(rows):
    if not rows:return {"n":0,"brier":None}
    n=len(rows)
    hits=sum(y for p,y in rows)
    return {"n":n,"wins":hits,"hit_rate":round(hits/n,5),
            "predicted_rate":round(sum(p for p,y in rows)/n,5),
            "brier":round(sum((p-y)**2 for p,y in rows)/n,6),
            "calibration_gap":round(sum(p for p,y in rows)/n-hits/n,5)}
def benchmark(index,dc_model,dc_cal,baseline_cal,rho,year=2026,max_matches=1000):
    old=defaultdict(list);standard=defaultdict(list);new=defaultdict(list)
    by_league=defaultdict(list);by_band=defaultdict(list)
    evaluated=0
    for match in get_sample(index,year,max_matches):
        feat,reason=estimate_goals(match,index)
        if feat is None:continue
        baseline={c.key:c for c in markets_from_matrix(score_matrix(feat["home"],feat["away"],rho))}
        adjusted={c.key:c for c in adjust_candidates(match,index,list(baseline.values()),dc_model,
                                    getattr(dc_cal,"outcome_calibration",None))}
        actual=outcome_scores(match)
        if actual is None:continue
        evaluated+=1
        for key in KEYS:
            y=int(actual[0]>=actual[1]) if key=="1X" else (
                int(actual[1]>=actual[0]) if key=="X2" else int(actual[0]!=actual[1]))
            _lo,p_before,_n=baseline_cal.score(baseline[key])
            p_new=adjusted[key].probability
            old[key].append((baseline[key].probability,y))
            standard[key].append((p_before,y))
            new[key].append((p_new,y))
            by_league[(league_key(match),key)].append((p_new,y))
            by_band[(key,int(p_new*10))].append((p_new,y))
    return {"year":year,"eligible":evaluated,
        "baseline_raw":{k:stats(v) for k,v in old.items()},
        "baseline_calibrated":{k:stats(v) for k,v in standard.items()},
        "specialized_calibrated":{k:stats(v) for k,v in new.items()},
        "by_league":{k+"|"+market:stats(rows) for (k,market),rows in by_league.items()
                     if len(rows)>=20},
        "by_probability_band":{market+"|"+str(b):stats(rows)
                               for (market,b),rows in by_band.items() if len(rows)>=20},
        "limitations":"No verified historical BSD odds: no retrospective ROI. "
                      "2024 fit, 2025 calibration, 2026 evaluation."}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--max-test",type=int,default=1000)
    parser.add_argument("--output",default="bsd/v2_double_chance_backtest.json")
    a=parser.parse_args()
    if not 1<=a.max_test<=5000:parser.error("max-test 1..5000")
    history=_read_json(MATCHES_FILE,None)
    if not isinstance(history,list) or not history:parser.error("Restore BSD archive")
    index=V2History(history)
    rho,_=fit_rho_2024(index)
    model,train=fit_model(index,rho)
    cal,_,_=fit_policy(index,rho=rho,dc_model=model)
    cal_base,_,_=fit_policy(index,rho=rho)
    result={"model":"bsd-double-chance-v1","training":train,
            "test":benchmark(index,model,cal,cal_base,rho,max_matches=a.max_test)}
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("BSD_DC_BACKTEST:",json.dumps({"training":train,"results":result["test"]},ensure_ascii=False))
if __name__=="__main__":main()
