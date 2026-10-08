"""Audit tous les seuils Over/Under contre Poisson/Dixon-Coles, sans cotes inventées."""
import argparse, json
from collections import defaultdict
from pathlib import Path
from bsd_archive import MATCHES_FILE, _read_json
from bsd_v2_core import V2History, fit_rho_2024, estimate_goals, score_matrix, markets_from_matrix, fixture_datetime, outcome_scores, league_key
from bsd_v2_over_under import fit_total_model,adjust_candidates
from bsd_v2_evaluate import get_sample
from bsd_v2_policies import fit_policy

KEYS=("OVER_15","UNDER_15","OVER_25","UNDER_25","OVER_35","UNDER_35","OVER_45")
def summarize(items):
    if not items:return {"samples":0}
    n=len(items)
    successes=sum(y for p,y in items)
    brier=sum((p-y)**2 for p,y in items)/n
    return {"samples":n,"hits":successes,
            "hit_rate":round(successes/n,5),
            "predicted_rate":round(sum(p for p,y in items)/n,5),
            "brier":round(brier,6),
            "calibration_gap":round(sum(p for p,y in items)/n-successes/n,5)}

def audit(index,model,calibration,rho,year=2026,max_matches=1800,baseline_calibration=None):
    base=defaultdict(list);changed=defaultdict(list)
    baseline_calibrated=defaultdict(list)
    by_league=defaultdict(list)
    buckets=defaultdict(list)
    tested=0
    for match in get_sample(index,year,max_matches):
        expected,reason=estimate_goals(match,index)
        if expected is None:continue
        tested+=1
        originals=markets_from_matrix(score_matrix(expected["home"],expected["away"],rho))
        adjusted=adjust_candidates(match,index,originals,model)
        before={c.key:c for c in originals}
        after={c.key:c for c in adjusted}
        a,b=outcome_scores(match)
        for key in KEYS:
            y=int(a+b>float(after[key].line)) if key.startswith("OVER") else int(a+b<float(after[key].line))
            baseline=before[key].probability
            _,p,_n=calibration.score(after[key])
            base[key].append((baseline,y))
            if baseline_calibration is not None:
                _low,base_calibrated,_n=baseline_calibration.score(before[key])
                baseline_calibrated[key].append((base_calibrated,y))
            changed[key].append((p,y))
            lk=league_key(match) or "unknown"
            by_league[(lk,key)].append((p,y))
            buckets[(key,int(p*10))].append((p,y))
    return {"year":year,"matches":tested,
            "baseline":{k:summarize(v) for k,v in base.items()},
            "baseline_calibrated":{k:summarize(v) for k,v in baseline_calibrated.items()},
            "specialized_calibrated":{k:summarize(v) for k,v in changed.items()},
            "by_league":{a+"|"+b:summarize(v) for (a,b),v in by_league.items() if len(v)>=25},
            "by_probability_bucket":{k+"|"+str(b):summarize(v)
                                     for (k,b),v in buckets.items() if len(v)>=20},
            "odds_warning":"Historical odds unavailable: no ROI, no speculative prices."}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--max-test",type=int,default=1000)
    parser.add_argument("--output",default="bsd/v2_totals_backtest.json")
    a=parser.parse_args()
    history=_read_json(MATCHES_FILE,None)
    if not isinstance(history,list) or not history:parser.error("Restore BSD history")
    index=V2History(history)
    rho,_=fit_rho_2024(index)
    model,diagnostics=fit_total_model(index,rho=rho)
    calibration,quality,_=fit_policy(index,rho=rho,total_model=model)
    calibration_reference,_,_=fit_policy(index,rho=rho,total_model=None)
    result={"model":"bsd-over-under-1","training":diagnostics,
            "test":audit(index,model,calibration,rho,max_matches=a.max_test,
                         baseline_calibration=calibration_reference)}
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("BSD_TOTALS_BACKTEST:",json.dumps({"tested":result["test"]["matches"],
          "baseline":result["test"]["baseline"],
          "baseline_calibrated":result["test"]["baseline_calibrated"],
          "specialized_calibrated":result["test"]["specialized_calibrated"]},ensure_ascii=False))
if __name__=="__main__":main()
