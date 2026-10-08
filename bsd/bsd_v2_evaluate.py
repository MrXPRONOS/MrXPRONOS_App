#!/usr/bin/env python3
"""Evaluation walk-forward V2, entrainement 2024, calibration 2025, test 2026."""
import argparse
import json
from collections import Counter
from datetime import timedelta
from pathlib import Path
from bsd_archive import MATCHES_FILE, _read_json
from bsd_v2_core import V2History, estimate_goals, score_matrix, markets_from_matrix, fit_rho_2024, predict_v2, fixture_datetime, outcome_scores, league_key
from bsd_markets import MarketCalibrator, candidates_from_goals, realized
from bsd_backtest import wilson_interval
from bsd_recent_backtest import paired_comparison
from bsd_calibrate import fit_calibration
from bsd_predict import HistoryIndex, predict_fixture
from bsd_v2_policies import fit_policy
from bsd_v2_btts import fit_btts_model
from bsd_v2_over_under import fit_total_model
from bsd_v2_double_chance import fit_model as fit_dc_model, adjust_candidates


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


BASELINE_KEYS = ("12", "1X", "X2", "OVER_15", "OVER_25", "UNDER_35", "UNDER_45", "BTTS_YES", "BTTS_NO")


def _group_summary(stats):
    n = stats["selected"]
    if not n:
        return {"selected": 0, "wins": 0, "hit_rate": None}
    predicted = stats["probability_sum"] / n
    observed = stats["wins"] / n
    return {
        "selected": n,
        "wins": stats["wins"],
        "hit_rate": round(observed, 4),
        "mean_predicted_probability": round(predicted, 4),
        "prediction_minus_actual": round(predicted - observed, 4),
        "brier": round(stats["brier_sum"] / n, 5),
        "wilson_95": wilson_interval(stats["wins"], n),
        "under45_same_selected": {
            "wins": stats["under45_wins"],
            "hit_rate": round(stats["under45_wins"] / n, 4),
        },
        "small_sample": n < 30,
    }


def _update_group(stats, win, probability, brier, under45_win):
    stats["selected"] += 1
    stats["wins"] += win
    stats["probability_sum"] += probability
    stats["brier_sum"] += brier
    stats["under45_wins"] += under45_win


def run_evaluation(index, calibration, rho, year=2026, max_matches=1000,
                   v1_index=None, v1_calibration=None, quality_policy=None,
                   btts_model=None, total_model=None, dc_model=None):
    counters = Counter()
    by_market = {}
    baselines = Counter()
    brier = 0.
    probability_sum = 0.
    per_market_brier = Counter()
    per_market_predicted = Counter()
    by_month = {}
    by_league = {}
    by_confidence_band = {}
    paired_baselines = Counter()
    v1_counts = Counter()
    common_counts = Counter()
    v1_candidates = {item.key: item for item in candidates_from_goals(1.4,1.2)}
    for event in get_sample(index,year,max_matches):
        counters["tested"]+=1
        fixture = dict(event,status="notstarted",home_score=None,away_score=None)
        # Both versions predict the exact same held-out 2026 fixtures.
        v1_pick = None
        if v1_index is not None:
            old_prediction, _ = predict_fixture(
                fixture, v1_index, calibration=v1_calibration,
                clock=fixture_datetime(event)-timedelta(seconds=1),
            )
            if old_prediction is not None:
                v1_key = old_prediction["prediction"]["selection_key"]
                if v1_key in v1_candidates:
                    v1_pick = realized(v1_candidates[v1_key], *outcome_scores(event))
                    v1_counts["selected"] += 1
                    v1_counts["wins"] += v1_pick
        prediction, reason = predict_v2(fixture,index,calibration=calibration,rho=rho,
                                        clock=fixture_datetime(event)-timedelta(seconds=1),
                                        quality_policy=quality_policy,btts_model=btts_model,total_model=total_model,dc_model=dc_model)
        if prediction is None:
            counters["skip_"+reason]+=1
            continue
        choice = prediction["prediction"]
        feat=prediction["estimated_goals"]
        generated=markets_from_matrix(score_matrix(feat["home"],feat["away"],rho))
        if total_model is not None:
            generated=adjust_candidates(event,index,generated,total_model)
        if btts_model is not None:
            generated=btts_candidates(event,index,generated,btts_model)
        if dc_model is not None:
            generated=dc_adjust(event,index,generated,dc_model,getattr(calibration,'outcome_calibration',None))
        markets={c.key:c for c in generated}
        correct=realized(markets[choice["key"]],*outcome_scores(event))
        counters["selected"]+=1
        counters["wins"]+=correct
        this_brier=(choice["probability"]-correct)**2
        brier+=this_brier
        probability_sum+=choice["probability"]
        per_market_brier[choice["key"]]+=this_brier
        per_market_predicted[choice["key"]]+=choice["probability"]
        under45_win = realized(markets["UNDER_45"], *outcome_scores(event))
        month_key = fixture_datetime(event).strftime("%Y-%m")
        league_name = league_key(event) or "unknown"
        low = min(90, int(choice["probability"] * 10) * 10)
        confidence_band = "%02d-%02d%%" % (low, low + 9)
        for group, group_key in ((by_month, month_key),
                                 (by_league, league_name),
                                 (by_confidence_band, confidence_band)):
            _update_group(group.setdefault(group_key, Counter()),
                          correct, choice["probability"], this_brier, under45_win)
        if v1_pick is not None:
            common_counts["selected"]+=1
            common_counts["v1_wins"]+=v1_pick
            common_counts["v2_wins"]+=correct
            if correct and not v1_pick: common_counts["v2_only"]+=1
            if v1_pick and not correct: common_counts["v1_only"]+=1
        market=by_market.setdefault(choice["key"],Counter())
        market["selected"]+=1
        market["wins"]+=correct
        for key in BASELINE_KEYS:
            fixed_won=realized(markets[key],*outcome_scores(event))
            baselines[(key,"total")]+=1
            baselines[(key,"wins")]+=fixed_won
            if correct and not fixed_won: paired_baselines[(key,"model_only")]+=1
            if fixed_won and not correct: paired_baselines[(key,"fixed_only")]+=1
    n=counters["selected"]
    return {
        "year":year,"checked":counters["tested"],"selected":n,"wins":counters["wins"],
        "hit_rate":round(counters["wins"]/n,4) if n else None,
        "brier":round(brier/n,5) if n else None,
        "mean_predicted_probability":round(probability_sum/n,4) if n else None,
        "prediction_minus_actual":round(probability_sum/n-counters["wins"]/n,4) if n else None,
        "wilson_95":wilson_interval(counters["wins"],n),
        "coverage":round(n/counters["tested"],4) if counters["tested"] else None,
        "skips":{k:v for k,v in counters.items() if k.startswith("skip_")},
        "by_market":{k:{"selected":v["selected"],"wins":v["wins"],
                        "hit_rate":round(v["wins"]/v["selected"],4),
                        "mean_predicted_probability":round(per_market_predicted[k]/v["selected"],4),
                        "brier":round(per_market_brier[k]/v["selected"],5),
                        "wilson_95":wilson_interval(v["wins"],v["selected"])} for k,v in sorted(by_market.items())},
        "by_month": {k: _group_summary(v) for k, v in sorted(by_month.items())},
        "by_league": {k: _group_summary(v) for k, v in sorted(by_league.items())},
        "by_confidence_band": {k: _group_summary(v) for k, v in sorted(by_confidence_band.items())},
        "fixed_baselines_same_fixtures":{k:{"selected":baselines[(k,"total")],
                                         "wins":baselines[(k,"wins")],
                                         "hit_rate":round(baselines[(k,"wins")]/baselines[(k,"total")],4)}
                                         for k in BASELINE_KEYS if baselines[(k,"total")]},
        "paired_vs_fixed_baselines_on_same_selected_fixtures":{
            k:paired_comparison(paired_baselines[(k,"model_only")],paired_baselines[(k,"fixed_only")])
            for k in BASELINE_KEYS if baselines[(k,"total")]},
        "v1_same_test_fixtures":{
            "checked":counters["tested"],"selected":v1_counts["selected"],"wins":v1_counts["wins"],
            "hit_rate":round(v1_counts["wins"]/v1_counts["selected"],4) if v1_counts["selected"] else None,
            "coverage":round(v1_counts["selected"]/counters["tested"],4) if counters["tested"] else None
        } if v1_index is not None else None,
        "v1_v2_common_selections":{
            "both_selected":common_counts["selected"],
            "v1_wins":common_counts["v1_wins"],"v2_wins":common_counts["v2_wins"],
            "v1_hit_rate":round(common_counts["v1_wins"]/common_counts["selected"],4) if common_counts["selected"] else None,
            "v2_hit_rate":round(common_counts["v2_wins"]/common_counts["selected"],4) if common_counts["selected"] else None,
            "paired":paired_comparison(common_counts["v2_only"],common_counts["v1_only"])
        } if v1_index is not None else None,
        "warning":"Retrospective, not prospective. Fixed baselines compare the same V2 selected matches; V1 is run on all identical tested fixtures and on the common selection subset. No real odds, so no ROI."
    }


def evaluate(history, *, max_test=1000, max_train=1800):
    index=V2History(history)
    rho,rho_info=fit_rho_2024(index)
    btts_model,btts_info=fit_btts_model(index,rho=rho)
    total_model,total_info=fit_total_model(index,rho=rho)
    dc_model,dc_info=fit_dc_model(index,rho=rho)
    cal,quality_policy,policy_info=fit_policy(index,rho=rho,max_train=max_train,btts_model=btts_model,total_model=total_model,dc_model=dc_model)
    trained=policy_info['training_eligible']
    v1_cal, v1_training = fit_calibration(history, year=2025, max_fixtures=max_train)
    results=run_evaluation(index,cal,rho,max_matches=max_test,
                           v1_index=HistoryIndex(history),v1_calibration=v1_cal,
                           quality_policy=quality_policy,btts_model=btts_model,total_model=total_model,dc_model=dc_model)
    return {"model":"bsd-v2-isolated", "history_eligible":len(index.global_games),
            "training":{"rho":rho_info,"calibration_year":2025,"calibration_games":trained,"quality_policy":policy_info,
                        "btts_training":btts_info,
                        "v1_calibration_games":v1_training.get("fixtures_with_form")},
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
    # Calibration and quality policy are generated per run, never committed in plaintext.
    # Do not serialize the raw per-market training aggregates to a public artifact.
    print("BSD_V2_EVALUATION:",json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    main()
