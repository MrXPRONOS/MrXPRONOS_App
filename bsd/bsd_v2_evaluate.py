#!/usr/bin/env python3
"""Evaluation walk-forward V2, entrainement 2024, calibration 2025, test 2026."""
import argparse
import json
from collections import Counter
from datetime import timedelta
from pathlib import Path
from bsd_archive import MATCHES_FILE, _read_json
from bsd_v2_core import V2History, estimate_goals, score_matrix, markets_from_matrix, fit_rho_2024, predict_v2, fixture_datetime, outcome_scores
from bsd_markets import MarketCalibrator, realized
from bsd_backtest import wilson_interval


def get_sample(index, year, max_matches):
    matches = []
    for _, event in index.global_games:
        if fixture_datetime(event).year == year:
            matches.append(event)
    matches.sort(key=lambda e: (e["event_date"], str(e["id"])))
    if len(matches)>max_matches:
        matches = [matches[int(i*len(matches)/max_matches)] for i in range(max_matches)]
    return matches


def fit_calibration_v2(index, rho, max_matches=1800):
    cal = MarketCalibrator()
    trained = 0
    for event in get_sample(index, 2025, max_matches):
        features, _ = estimate_goals(event,index)
        if features is None: continue
        trained+=1
        for c in markets_from_matrix(score_matrix(features["home"],features["away"],rho)):
            cal.observe(c, realized(c,*outcome_scores(event)))
    return cal, trained


def run_evaluation(index, calibration, rho, year=2026, max_matches=1000):
    counters = Counter()
    by_market = {}
    baselines = Counter()
    brier = 0.
    for event in get_sample(index,year,max_matches):
        counters["tested"]+=1
        fixture = dict(event,status="notstarted",home_score=None,away_score=None)
        prediction, reason = predict_v2(fixture,index,calibration=calibration,rho=rho,
                                        clock=fixture_datetime(event)-timedelta(seconds=1))
        if prediction is None:
            counters["skip_"+reason]+=1
            continue
        choice = prediction["prediction"]
        feat=prediction["estimated_goals"]
        markets={c.key:c for c in markets_from_matrix(score_matrix(feat["home"],feat["away"],rho))}
        correct=realized(markets[choice["key"]],*outcome_scores(event))
        counters["selected"]+=1
        counters["wins"]+=correct
        brier+=(choice["probability"]-correct)**2
        market=by_market.setdefault(choice["key"],Counter())
        market["selected"]+=1
        market["wins"]+=correct
        for key in ("12","1X","X2","OVER_15","UNDER_35","BTTS_YES"):
            baselines[(key,"total")]+=1
            baselines[(key,"wins")]+=realized(markets[key],*outcome_scores(event))
    n=counters["selected"]
    return {
        "year":year,"checked":counters["tested"],"selected":n,"wins":counters["wins"],
        "hit_rate":round(counters["wins"]/n,4) if n else None,
        "brier":round(brier/n,5) if n else None,
        "wilson_95":wilson_interval(counters["wins"],n),
        "coverage":round(n/counters["tested"],4) if counters["tested"] else None,
        "skips":{k:v for k,v in counters.items() if k.startswith("skip_")},
        "by_market":{k:{"selected":v["selected"],"wins":v["wins"],
                        "hit_rate":round(v["wins"]/v["selected"],4)} for k,v in sorted(by_market.items())},
        "fixed_baselines_same_fixtures":{k:{"selected":baselines[(k,"total")],
                                         "wins":baselines[(k,"wins")],
                                         "hit_rate":round(baselines[(k,"wins")]/baselines[(k,"total")],4)}
                                         for k in ("12","1X","X2","OVER_15","UNDER_35","BTTS_YES") if baselines[(k,"total")]},
        "warning":"Retrospective; not prospective and no real odds, so no ROI."
    }


def evaluate(history, *, max_test=1000, max_train=1800):
    index=V2History(history)
    rho,rho_info=fit_rho_2024(index)
    cal,trained=fit_calibration_v2(index,rho,max_train)
    results=run_evaluation(index,cal,rho,max_matches=max_test)
    return {"model":"bsd-v2-isolated", "history_eligible":len(index.global_games),
            "training":{"rho":rho_info,"calibration_year":2025,"calibration_games":trained},
            "test":results},cal,rho


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--max-test",type=int,default=1000)
    p.add_argument("--max-train",type=int,default=1800)
    p.add_argument("--output",default="bsd/v2_backtest_report.json")
    args=p.parse_args()
    if not 1<=args.max_test<=5000 or not 1<=args.max_train<=5000:
        p.error("Invalid sample size")
    history=_read_json(MATCHES_FILE,None)
    if not isinstance(history,list) or not history: p.error("Restore archive first")
    result,cal,rho=evaluate(history,max_test=args.max_test,max_train=args.max_train)
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    Path("bsd/v2_calibration.json").write_text(json.dumps({"rho":rho,"calibration":cal.to_dict()}),encoding="utf-8")
    print("BSD_V2_EVALUATION:",json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    main()
