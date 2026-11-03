#!/usr/bin/env python3
"""Aggregated, read-only 2026 BTTS losses diagnosis. Never exports private match history."""
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import mean

from bsd_archive import MATCHES_FILE, _read_json
from bsd_v2_core import (
    V2History, fit_rho_2024, estimate_goals, score_matrix,
    markets_from_matrix, fixture_datetime, outcome_scores, league_key,
)
from bsd_v2_btts import fit_btts_model, btts_candidates, btts_features, FEATURE_LABELS
from bsd_v2_policies import fit_policy

START, END = date(2026, 1, 1), date(2026, 11, 2)
history = _read_json(MATCHES_FILE, None)
if not isinstance(history, list) or len(history) < 100:
    raise RuntimeError("Decrypted BSD history unavailable")
index = V2History(history)
rho, _ = fit_rho_2024(index)
model, training = fit_btts_model(index, rho=rho)
cal, quality, calibration = fit_policy(index, rho=rho, btts_model=model)
baseline_cal, _, _ = fit_policy(index, rho=rho, btts_model=None)

rows = []
skips = Counter()
for _, fixture in index.global_games:
    try:
        day = fixture_datetime(fixture).date()
        if not START <= day <= END:
            continue
        scores = outcome_scores(fixture)
        if scores is None:
            skips["no_finished_score"] += 1
            continue
        expected, reason = estimate_goals(fixture, index)
        if expected is None:
            skips[reason] += 1
            continue
        baseline = {c.key: c for c in markets_from_matrix(
            score_matrix(expected["home"], expected["away"], rho))}
        updated = {c.key: c for c in btts_candidates(
            fixture, index, list(baseline.values()), model)}
        p_yes = cal.score(updated["BTTS_YES"])[1]
        p_base = baseline_cal.score(baseline["BTTS_YES"])[1]
        side = "YES" if p_yes >= .5 else "NO"
        confidence = p_yes if side=="YES" else 1.-p_yes
        actual_yes = bool(scores[0] > 0 and scores[1] > 0)
        correct = bool(actual_yes if side=="YES" else not actual_yes)
        family = league_key(fixture) or "unknown"
        nm = fixture.get("league_name") or ""
        if not nm and isinstance(fixture.get("league"),dict):
            nm = fixture["league"].get("name") or ""
        features = btts_features(fixture,index)
        rows.append(dict(
            date=day.isoformat(), month=day.isoformat()[:7],league=family,
            league_name=str(nm)[:70], home_goals=scores[0],away_goals=scores[1],
            actual_yes=actual_yes,side=side,p_yes=p_yes,p_base=p_base,
            confidence=confidence,correct=correct,
            lambda_home=expected["home"],lambda_away=expected["away"],
            league_samples=expected["league_samples"],
            min_recent=min(expected["home_recent_matches"],expected["away_recent_matches"]),
            min_venue=min(expected["home_venue_matches"],expected["away_venue_matches"]),
            max_age=expected["max_last_match_age_days"],
            fallback=(features is None),
            quality_pass=quality.check_fixture(expected) is None,
        ))
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
        skips["diagnostic_error_"+type(exc).__name__] += 1

def summarize(a):
    n=len(a)
    if not n: return {"n":0}
    wins=sum(x["correct"] for x in a)
    yes=sum(x["side"]=="YES" for x in a)
    return {"n":n,"wins":wins,"losses":n-wins,"hit_rate":round(wins/n,4),
        "mean_confidence":round(mean(x["confidence"] for x in a),4),
        "overconfidence_pp":round(100*(mean(x["confidence"] for x in a)-wins/n),2),
        "selected_yes":yes,"selected_no":n-yes,
        "actual_btts_yes_rate":round(mean(x["actual_yes"] for x in a),4)}
def bin_value(x, ranges, labels):
    for bound,label in zip(ranges,labels):
        if x<bound:return label
    return labels[-1]

def group_summary(records,func,min_n=1):
    groups=defaultdict(list)
    for x in records:
        groups[str(func(x))].append(x)
    return {key:summarize(value) for key,value in sorted(groups.items())
        if len(value)>=min_n}

def brier(a, key="p_yes"):
    if not a:return None
    return round(mean((r[key]-r["actual_yes"])**2 for r in a),6)

def error_type(r):
    if r["correct"]:return "correct"
    h,a=r["home_goals"],r["away_goals"]
    if r["side"]=="NO":
        if h==1 and a==1:return "btts_no_lost_1_1"
        if (h,a) in ((1,2),(2,1)):return "btts_no_lost_1_2_or_2_1"
        if h>=2 and a>=2:return "btts_no_lost_both_2plus"
        return "btts_no_lost_other_both_scored"
    if h==0 and a==0:return "btts_yes_lost_0_0"
    if h==0:return "btts_yes_lost_home_blank"
    if a==0:return "btts_yes_lost_away_blank"
    return "unexpected"

periods={"jan_jun":[r for r in rows if r["month"]<="2026-06"],
         "jul_nov":[r for r in rows if r["month"]>="2026-07"]}
ranges={"all":rows,
        "confidence_ge_55":[r for r in rows if r["confidence"]>=.55],
        "confidence_ge_60":[r for r in rows if r["confidence"]>=.60],
        "confidence_ge_65":[r for r in rows if r["confidence"]>=.65],
        "confidence_ge_66":[r for r in rows if r["confidence"]>=.66],
        "confidence_ge_70":[r for r in rows if r["confidence"]>=.70]}

report={
  "period":"2026-01-01..2026-11-02",
  "source_fixtures":len(history),"analyzed":len(rows),"skips":dict(skips),
  "training":training,"calibration":calibration,
  "model_weights":dict(zip(FEATURE_LABELS, [round(v,5) for v in model.weights])),
  "overall":summarize(rows),
  "constant_yes_baseline":{
      "n":len(rows),"wins":sum(x["actual_yes"] for x in rows),
      "hit_rate":round(mean(x["actual_yes"] for x in rows),4)
  },
  "brier":{"specialized":brier(rows),"poisson_calibrated":brier(rows,"p_base")},
  "by_side":group_summary(rows,lambda r:r["side"]),
  "by_period":{p:summarize(v) for p,v in periods.items()},
  "confidence_ranges":{k:summarize(v) for k,v in ranges.items()},
  "confidence_bins":group_summary(rows,lambda r:bin_value(r["confidence"],
    [.55,.60,.65,.70,.75,.80,.85,.90],
    ["50-55","55-60","60-65","65-70","70-75","75-80","80-85","85-90","90+"])),
  "loss_score_types":dict(Counter(error_type(r) for r in rows if not r["correct"])),
  "loss_score_types_by_confidence":{
     k:dict(Counter(error_type(r) for r in v if not r["correct"])) for k,v in ranges.items()},
  "quality_policy_counterfactual":{
     "pass":summarize([r for r in rows if r["quality_pass"]]),
     "reject":summarize([r for r in rows if not r["quality_pass"]])
  },
  "model_feature_fallback":{
     "specialized_available":summarize([r for r in rows if not r["fallback"]]),
     "fallback_to_poisson":summarize([r for r in rows if r["fallback"]])
  },
  "by_data_quality":{},
  "by_league_high_confidence":[],
  "by_league_overall":[],
  "by_month":group_summary(rows,lambda r:r["month"]),
}
for threshold in ("all","confidence_ge_60","confidence_ge_65"):
    a=ranges[threshold]
    report["by_data_quality"][threshold]={
       "min_recent_matches":group_summary(a,lambda r:bin_value(r["min_recent"],
           [5,8,10,12,13],["4","5-7","8-9","10-11","12","13+"])),
       "min_venue_matches":group_summary(a,lambda r:bin_value(r["min_venue"],
           [3,5,8],["0-2","3-4","5-7","8+"])),
       "league_history":group_summary(a,lambda r:bin_value(r["league_samples"],
           [15,40,100,300],["0-14","15-39","40-99","100-299","300+"])),
       "age_days":group_summary(a,lambda r:bin_value(r["max_age"],
           [8,15,31,61,121],["0-7","8-14","15-30","31-60","61-120","121+"])),
       "min_expected_goals":group_summary(a,lambda r:bin_value(min(r["lambda_home"],r["lambda_away"]),
           [.65,.85,1.05,1.25,1.50],["<0.65","0.65-0.85","0.85-1.05","1.05-1.25","1.25-1.5",">=1.5"])),
       "lambda_difference":group_summary(a,lambda r:bin_value(abs(r["lambda_home"]-r["lambda_away"]),
           [.25,.5,1.0,1.5],["<0.25","0.25-0.5","0.5-1.0","1.0-1.5",">=1.5"])),
    }
by_league=defaultdict(list)
by_league_conf=defaultdict(list)
league_names={}
for r in rows:
    by_league[r["league"]].append(r)
    if r["confidence"]>=.60:by_league_conf[r["league"]].append(r)
    if r["league_name"] and r["league"] not in league_names:
       league_names[r["league"]]=r["league_name"]
for key,rs in by_league.items():
    if len(rs)>=100:
        vals=summarize(rs)
        vals.update({"id":key,"name":league_names.get(key) or key,
                     "brier_specialized":brier(rs),"brier_poisson":brier(rs,"p_base"),
                     "delta_brier":round(brier(rs)-brier(rs,"p_base"),6)})
        report["by_league_overall"].append(vals)
for key,rs in by_league_conf.items():
    if len(rs)>=20:
        vals=summarize(rs)
        vals.update({"id":key,"name":league_names.get(key) or key,
                     "league_total":len(by_league[key])})
        report["by_league_high_confidence"].append(vals)
report["by_league_high_confidence"].sort(key=lambda r:(r["hit_rate"],-r["n"]))
report["by_league_overall"].sort(key=lambda r:(-r["delta_brier"],-r["n"]))

out=Path("bsd/btts_2026_loss_diagnostics.json")
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
compact={k:report[k] for k in ("period","analyzed","skips","model_weights","overall",
 "constant_yes_baseline","brier","by_side","by_period","confidence_ranges",
 "confidence_bins","loss_score_types","loss_score_types_by_confidence",
 "quality_policy_counterfactual","model_feature_fallback","by_data_quality")}
compact["worst_leagues_high_confidence"]=report["by_league_high_confidence"][:15]
compact["leagues_specialist_worse_than_poisson"]=report["by_league_overall"][:15]
print("BSD_BTTS_LOSS_DIAG="+json.dumps(compact,ensure_ascii=False))
print("BSD_BTTS_LOSS_DIAG_OUTPUT="+str(out))
