# BSD V2 retrospective BTTS threshold audit, 2026-01-01..2026-11-02 (UTC)
# Train 2024 / calibrate 2025. No production changes; no ROI without real odds.
import json, math
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from bsd_archive import MATCHES_FILE, _read_json
from bsd_v2_core import (
    V2History, fit_rho_2024, estimate_goals, score_matrix,
    markets_from_matrix, fixture_datetime, outcome_scores, league_key
)
from bsd_v2_btts import fit_btts_model, btts_candidates
from bsd_v2_policies import fit_policy

START, END = date(2026,1,1), date(2026,11,2)
data = _read_json(MATCHES_FILE, None)
if not isinstance(data, list) or len(data) < 100:
    raise RuntimeError("BSD archive unavailable or insufficient")

index = V2History(data)
rho, rho_info = fit_rho_2024(index)
model, model_info = fit_btts_model(index, rho=rho)
cal, policy, periods = fit_policy(index, rho=rho, btts_model=model)
baseline_cal, _, _ = fit_policy(index, rho=rho, btts_model=None)
results = defaultdict(list)
by_league = defaultdict(list)
by_month = defaultdict(list)
skipped = Counter()
days = Counter()
finished = 0
min_day = max_day = None

for _, event in index.global_games:
    try:
        match_day = fixture_datetime(event).date()
        if not (START <= match_day <= END):
            continue
        scores = outcome_scores(event)
        if scores is None:
            skipped["unsettled"] += 1
            continue
        finished += 1
        min_day = min(min_day, match_day) if min_day else match_day
        max_day = max(max_day, match_day) if max_day else match_day
        expected, reason = estimate_goals(event, index)
        if expected is None:
            skipped[reason] += 1
            continue
        original = {c.key:c for c in markets_from_matrix(
            score_matrix(expected["home"], expected["away"], rho))}
        specialized = {c.key:c for c in btts_candidates(
            event, index, list(original.values()), model)}
        y = int(scores[0] > 0 and scores[1] > 0)
        lg = league_key(event) or "unknown"
        month = match_day.isoformat()[:7]
        days[match_day.isoformat()] += 1
        for name, target in (("BTTS_YES",y), ("BTTS_NO",1-y)):
            raw = original[name].probability
            old_cal = baseline_cal.score(original[name])[1]
            new_cal = cal.score(specialized[name])[1]
            row = {"outcome":target, "month":match_day.isoformat()[:7], "raw":raw, "baseline_calibrated":old_cal,
                   "specialized_calibrated":new_cal}
            results[name].append(row)
            if name == "BTTS_YES":
                by_league[lg].append(row)
                by_month[month].append(row)
    except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
        skipped[type(exc).__name__] += 1

def metrics(rows, key):
    n = len(rows)
    if n == 0:
        return {"n":0}
    p = [min(.999999,max(.000001,float(x[key]))) for x in rows]
    ys = [x["outcome"] for x in rows]
    return {"n":n,
       "btts_true":sum(ys),
       "observed_rate":round(sum(ys)/n,6),
       "mean_forecast":round(sum(p)/n,6),
       "calibration_gap":round((sum(p)-sum(ys))/n,6),
       "brier":round(sum((a-b)**2 for a,b in zip(p,ys))/n,6),
       "log_loss":round(-sum(b*math.log(a)+(1-b)*math.log(1-a) for a,b in zip(p,ys))/n,6),
       "accuracy_at_50pct":round(sum((a >= .5)==bool(b) for a,b in zip(p,ys))/n,6)}
def group_stats(rows):
    return {k:metrics(rows,k) for k in
       ("raw","baseline_calibrated","specialized_calibrated")}
report={
 "period":"2026-01-01..2026-11-02",
 "generated_with":"bsd-v2-current-main-code-in-branch-audit",
 "method":"holdout month: fit 2024, calibrate 2025, test all eligible matches October 2026; historical index point-in-time",
 "source_matches":len(data),
 "ytd_finished_matches_in_history":finished,
 "eligible":len(results["BTTS_YES"]),
 "ytd_first_seen":min_day.isoformat() if min_day else None,
 "ytd_last_seen":max_day.isoformat() if max_day else None,
 "days_with_eligible_matches":len(days),
 "skips":dict(skipped),
 "rho":rho,
 "btts_training":model_info,
 "calibration_periods":periods,
 "btts_yes":group_stats(results["BTTS_YES"]),
 "btts_no":group_stats(results["BTTS_NO"]),
 "by_month":{month:group_stats(rows) for month,rows in sorted(by_month.items())},
 "by_league_at_least_20":{k:group_stats(v) for k,v in
    sorted(by_league.items(),key=lambda x:-len(x[1])) if len(v)>=20},
 "limitations":[
   "Retrospective archived match results may include later corrections",
   "Not a historical betting returns test; contemporary BTTS odds unavailable",
   "This evaluates probabilities for all eligible games, not only actually published BTTS selections"
 ]
}
def wilson(wins, n):
    if n == 0:
        return None
    z = 1.96
    p = wins / n
    denom = 1 + z*z/n
    center = (p + z*z/(2*n))/denom
    delta = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/denom
    return [round(center-delta,4), round(center+delta,4)]
def selective(rows_yes, rows_no, field, threshold):
    picks = []
    for yes, no in zip(rows_yes,rows_no):
        p_yes, p_no = yes[field], no[field]
        side = "BTTS_YES" if p_yes >= p_no else "BTTS_NO"
        p = max(p_yes,p_no)
        if p >= threshold:
            hit = yes["outcome"] if side == "BTTS_YES" else no["outcome"]
            picks.append((side,hit,p))
    n = len(picks)
    total = len(rows_yes)
    wins = sum(p[1] for p in picks)
    side_counts={}
    for side in ("BTTS_YES","BTTS_NO"):
        values=[p for p in picks if p[0]==side]
        if values:
            count=len(values); w=sum(p[1] for p in values)
            side_counts[side]={"n":count,"wins":w,"hit_rate":round(w/count,4),
                 "wilson_95":wilson(w,count)}
    return {"threshold":threshold,"selected":n,"coverage":round(n/total,4) if total else 0,
          "wins":wins,"hit_rate":round(wins/n,4) if n else None,
          "wilson_95":wilson(wins,n),
          "mean_confidence":round(sum(p[2] for p in picks)/n,4) if n else None,
          "by_side":side_counts}
report["selective_thresholds"]={
 field:[selective(results["BTTS_YES"],results["BTTS_NO"],field,threshold)
        for threshold in [round(t/100,2) for t in range(50,96)]]
 for field in ("raw","baseline_calibrated","specialized_calibrated")}
report["yes_no_calibration_consistency"]={
 field:round(sum(abs(y[field]+n[field]-1) for y,n in
       zip(results["BTTS_YES"],results["BTTS_NO"]))/len(results["BTTS_YES"]),6)
       if results["BTTS_YES"] else None
 for field in ("raw","baseline_calibrated","specialized_calibrated")}
print("BSD_BTTS_SELECTIVE_2026_YTD="+json.dumps({
 "period":report["period"],"eligible":report["eligible"],
 "selective_thresholds":report["selective_thresholds"],
 "yes_no_calibration_consistency":report["yes_no_calibration_consistency"]
},ensure_ascii=False))


def _filter_period(period):
    if period=="jan_jun": return lambda row: row["month"] <= "2026-06"
    if period=="jul_nov": return lambda row: row["month"] >= "2026-07"
    return lambda row: True

report["period_comparisons"]={}
for pname in ("jan_jun","jul_nov"):
    selectrow = _filter_period(pname)
    ylist=[r for r in results["BTTS_YES"] if selectrow(r)]
    nlist=[r for r in results["BTTS_NO"] if selectrow(r)]
    report["period_comparisons"][pname]={
        "eligible":len(ylist),
        "thresholds":{field:[
            selective(ylist,nlist,field,round(t/100,2)) for t in range(50,96)]
            for field in ("baseline_calibrated","specialized_calibrated")}
    }
def _first_over(rows,minimum_n,require_lower=False):
    qualifying=[r for r in rows if r["selected"]>=minimum_n and
       r["hit_rate"] is not None and r["hit_rate"] > .70 and
       (not require_lower or (r["wilson_95"] and r["wilson_95"][0]>.70))]
    return qualifying[0] if qualifying else None
report["threshold_findings"]={}
for label,by_model in (("all_2026",report["selective_thresholds"]),
                       *((p,v["thresholds"]) for p,v in report["period_comparisons"].items())):
    report["threshold_findings"][label]={
        field:{
          "first_over_70_any_sample":_first_over(rows,1),
          "first_over_70_100plus":_first_over(rows,100),
          "first_over_70_200plus":_first_over(rows,200),
          "first_over_70_wilson_lower_100plus":_first_over(rows,100,True),
          "first_over_70_wilson_lower_200plus":_first_over(rows,200,True)
        }
        for field,rows in by_model.items()
    }
print("BSD_BTTS_2026_YTD_THRESHOLD_FINDINGS="+json.dumps({
    "period":report["period"],"eligible":report["eligible"],
    "threshold_findings":report["threshold_findings"],
    "counts_by_period":{k:v["eligible"] for k,v in report["period_comparisons"].items()},
    "sample_thresholds":{field:[
        x for x in rows if int(round(x["threshold"]*100)) in (50,55,60,65,70,75,80,85,90)]
        for field,rows in report["selective_thresholds"].items()},
    "by_month_counts":{k:v["raw"]["n"] for k,v in report["by_month"].items()}
},ensure_ascii=False))

if report["eligible"] == 0:
    raise RuntimeError("No BTTS eligible matches in 2026 YTD; archive coverage insufficient")
out=Path("bsd/btts_backtest_2026_ytd.json")
out.write_text(json.dumps(report,ensure_ascii=False,indent=2))
short={k:report[k] for k in
 ("period","source_matches","ytd_finished_matches_in_history","eligible",
  "ytd_first_seen","ytd_last_seen","days_with_eligible_matches",
  "skips","rho","btts_training","btts_yes","btts_no","by_month","limitations")}
print("BSD_BTTS_2026_YTD_REPORT="+json.dumps(short,ensure_ascii=False))
print("BACKTEST_OUTPUT="+str(out))
