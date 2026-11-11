"""Additional held-out November goal calibration check (not a picking backtest)."""
from __future__ import annotations
from datetime import date, datetime, timedelta, time, timezone
from math import log
from pathlib import Path
import json

from .daily_espn import ESPNProvider, parse_event
from .diagnose_laliga_oct2026 import pre_match_view, _outcome, _real_outcome
from .goal_calibration import select_goal_multiplier
from .model import fit, forecast, p_score, ModelError

UTC = timezone.utc


def backtest_november(out: Path):
    provider=ESPNProvider(leagues=["esp.1"])
    matches=[]
    day=date(2026,11,1)
    while day<=date(2026,11,10):
        as_of=datetime.combine(day-timedelta(days=1),time(20),UTC)
        schedule=provider._fetch("esp.1", day.strftime("%Y%m%d"))
        valid=[]
        for event in schedule:
            truth,_=parse_event(event,"esp.1",now=datetime(2026,11,11,0,tzinfo=UTC))
            _,fixture=parse_event(pre_match_view(event),"esp.1",now=as_of)
            if truth and fixture and fixture.kickoff.date()==day:
                valid.append((truth,fixture))
        if valid:
            hist,issues=provider.history(valid[0][1],as_of)
            if issues:
                raise ValueError(str(issues))
            model=fit(hist,as_of=as_of,min_games=80,regularization=.15,maxiter=650)
            calibration=select_goal_multiplier(hist,as_of=as_of)
            for truth,fixture in valid:
                try:
                    baseline=forecast(model,fixture.home_id,fixture.away_id,
                                      neutral_venue=fixture.neutral_venue is True)
                    candidate=forecast(model,fixture.home_id,fixture.away_id,
                                       neutral_venue=fixture.neutral_venue is True,
                                       goal_multiplier=calibration.multiplier)
                    hs,away=truth.home_goals,truth.away_goals
                    actual=f"{hs}-{away}"
                    bp=p_score(baseline["expected_home_goals"],baseline["expected_away_goals"],
                               model.rho,hs,away)
                    cp=p_score(candidate["expected_home_goals"],candidate["expected_away_goals"],
                               model.rho,hs,away)
                    outcome=_real_outcome(hs,away)
                    matches.append({
                        "date":day.isoformat(),"id":fixture.id,
                        "home":fixture.home_name,"away":fixture.away_name,
                        "actual":actual,
                        "baseline_score":baseline["top_scores"][0]["score"],
                        "calibrated_score":candidate["top_scores"][0]["score"],
                        "baseline_top1":int(baseline["top_scores"][0]["score"]==actual),
                        "calibrated_top1":int(candidate["top_scores"][0]["score"]==actual),
                        "baseline_1x2":int(_outcome(baseline)==outcome),
                        "calibrated_1x2":int(_outcome(candidate)==outcome),
                        "baseline_nll":-log(bp),"calibrated_nll":-log(cp),
                        "baseline_1x2_nll":-log(baseline["one_x_two"][outcome]),
                        "calibrated_1x2_nll":-log(candidate["one_x_two"][outcome]),
                        "baseline_goals":baseline["expected_home_goals"]+baseline["expected_away_goals"],
                        "calibrated_goals":candidate["expected_home_goals"]+candidate["expected_away_goals"],
                        "actual_goals":hs+away,
                        "scale":calibration.multiplier,
                        "calibration_status":calibration.status,
                    })
                except ModelError as exc:
                    print("NOV_MODEL_SKIPPED",fixture.id,type(exc).__name__,flush=True)
            provider._history.clear()
        print("NOV_LIGA_DAY",day.isoformat(),"eligible",len(valid),flush=True)
        day+=timedelta(days=1)
    if not matches:
        raise ValueError("No complete November fixtures")
    n=len(matches)
    keys=("baseline_top1","calibrated_top1","baseline_1x2","calibrated_1x2",
          "baseline_nll","calibrated_nll","baseline_1x2_nll","calibrated_1x2_nll",
          "baseline_goals","calibrated_goals","actual_goals")
    sums={key:round(sum(row[key] for row in matches),5) for key in keys}
    report={
        "period":"2026-11-01 to 2026-11-10",
        "note":"All completed La Liga fixtures, NOT the top10 popularity-selected cohort",
        "sample":n,"summary":sums,"averages":{
            key:round(sums[key]/n,5) for key in
            ("baseline_nll","calibrated_nll","baseline_1x2_nll","calibrated_1x2_nll")
        },"matches":matches,
        "limits":["ESPN reconstructed historical fixtures, not archived daily forecasts",
                  "October performance never used to select the calibration multiplier"]
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("NOV_LIGA_HELDOUT_FINAL",json.dumps({"sample":n,"summary":sums,
        "averages":report["averages"]},ensure_ascii=False),flush=True)
    return report


if __name__=="__main__":
    backtest_november(Path("results/diagnostics/laliga_nov2026.json"))
