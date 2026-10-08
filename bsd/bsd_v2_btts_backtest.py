"""Audit BTTS indépendant 2026 sur les mêmes matchs, y compris non sélectionnés.

Les cotes contemporaines ne sont pas présentes dans l'archive historique:
ne pas inférer la rentabilité d'un backtest sans prix pré-match.
"""
from __future__ import annotations
import argparse,json
from collections import Counter,defaultdict
from pathlib import Path
from bsd_archive import MATCHES_FILE,_read_json
from bsd_backtest import wilson_interval
from bsd_v2_core import V2History,fit_rho_2024,estimate_goals,score_matrix,markets_from_matrix,fixture_datetime,outcome_scores,league_key
from bsd_v2_btts import fit_btts_model,btts_candidates
from bsd_v2_policies import fit_policy
from bsd_v2_evaluate import get_sample


def _statistics(rows):
    count=len(rows)
    if not count:return {"n":0,"wins":0,"hit_rate":None,"brier":None}
    successes=sum(row[1] for row in rows)
    return {
        "n":count,"wins":successes,
        "hit_rate":round(successes/count,4),
        "average_predicted":round(sum(row[0] for row in rows)/count,4),
        "brier":round(sum((row[0]-row[1])**2 for row in rows)/count,5),
        "wilson_95":wilson_interval(successes,count),
    }


def audit(index,model,calibration,rho,*,year=2026,max_matches=2000):
    by_group=defaultdict(list)
    by_league=defaultdict(list)
    baseline=defaultdict(list)
    counters=Counter()
    for match in get_sample(index,year,max_matches):
        counters["checked"]+=1
        expected,reason=estimate_goals(match,index)
        if expected is None:
            counters["skipped_"+reason]+=1
            continue
        original={c.key:c for c in markets_from_matrix(score_matrix(expected["home"],expected["away"],rho))}
        updated={c.key:c for c in btts_candidates(match,index,list(original.values()),model)}
        scores=outcome_scores(match)
        win_yes=int(scores[0]>0 and scores[1]>0)
        for key,win in (("BTTS_YES",win_yes),("BTTS_NO",1-win_yes)):
            _,p,n=calibration.score(updated[key])
            by_group[key].append((p,win))
            baseline[key].append((original[key].probability,win))
            by_league[(league_key(match),key)].append((p,win))
        counters["evaluated"]+=1
    results={
        "year":year,"checked":counters["checked"],"eligible":counters["evaluated"],
        "skips":{k:v for k,v in counters.items() if k.startswith("skipped_")},
        "specialized_calibrated":{k:_statistics(v) for k,v in by_group.items()},
        "poisson_dixon_coles_baseline":{k:_statistics(v) for k,v in baseline.items()},
        "by_league":{k+"|"+side:_statistics(rows) for (k,side),rows in by_league.items()
                     if len(rows)>=20},
        "limitations":"Historical holdout, not a real-odds backtest. No inferred ROI. "
                      "BTTS calibration and classifier were trained only on previous years.",
    }
    return results


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--max-test",type=int,default=2000)
    parser.add_argument("--output",default="bsd/v2_btts_backtest.json")
    args=parser.parse_args()
    if not 1<=args.max_test<=5000:parser.error("Invalid match limit")
    matches=_read_json(MATCHES_FILE,None)
    if not isinstance(matches,list) or not matches:parser.error("BSD archive not restored")
    index=V2History(matches)
    rho,_=fit_rho_2024(index)
    model,training=fit_btts_model(index,rho=rho)
    cal,policy,periods=fit_policy(index,rho=rho,btts_model=model)
    result={"model":"btts-specialized-v1","fit":training,"calibration":periods,
            "test":audit(index,model,cal,rho,max_matches=args.max_test)}
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("BSD_BTTS_BACKTEST:",json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    main()
