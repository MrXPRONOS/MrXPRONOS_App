"""Independent historical diagnosis for the 25 Popularity V2 La Liga picks.

The cohort is FROZEN from the October 2026 V2 backtest. Score results are
retrieved only after forecast generation. All fitting and goal calibration
excludes any post-cutoff result. Does not change the production channel.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta, time, timezone
import csv
import json
from math import log
from pathlib import Path

from .daily_espn import ESPNProvider, parse_event
from .domain import utc_datetime
from .goal_calibration import select_goal_multiplier
from .model import fit, forecast, p_score

UTC = timezone.utc

# IDs and TOP-1 predictions frozen from the original 131-pick October report.
# The October actual scores are deliberately NOT stored as model inputs.
SAMPLE = {
    "2026-10-09": {"401882851": "0-1"},
    "2026-10-10": {"401882856": "1-1", "401882853": "2-0", "401882848": "2-1"},
    "2026-10-11": {"401882847": "1-1", "401882855": "1-0", "401882850": "1-1"},
    "2026-10-12": {"401882852": "1-1"},
    "2026-10-16": {"401882844": "2-1"},
    "2026-10-17": {"401882843": "1-1", "401882846": "1-2", "401882838": "1-1"},
    "2026-10-18": {"401882841": "0-1", "401882839": "2-0"},
    "2026-10-19": {"401882842": "0-0"},
    "2026-10-21": {"401882870": "1-1"},
    "2026-10-23": {"401882836": "1-0"},
    "2026-10-24": {"401882827": "1-1", "401882834": "2-0"},
    "2026-10-25": {"401882832": "2-1"},
    "2026-10-26": {"401882828": "1-1"},
    "2026-10-30": {"401882817": "2-0"},
    "2026-10-31": {"401882820": "1-1", "401882825": "2-0", "401882822": "3-0"},
}


def pre_match_view(event: dict) -> dict:
    result = deepcopy(event)
    result.setdefault("status", {}).setdefault("type", {}).update(
        {"completed": False, "name": "STATUS_SCHEDULED"})
    for comp in result.get("competitions", ()):
        for team in comp.get("competitors", ()):
            team.pop("score", None)
    return result


def _outcome(forecast_: dict) -> str:
    p = forecast_["one_x_two"]
    return max(("home", "draw", "away"), key=p.get)


def _real_outcome(home: int, away: int) -> str:
    return "home" if home > away else "away" if home < away else "draw"


def run(*, out_dir: Path):
    provider = ESPNProvider(leagues=["esp.1"])
    rows: list[dict] = []
    dates: list[dict] = []
    for day, sample in sorted(SAMPLE.items()):
        match_day = date.fromisoformat(day)
        as_of = datetime.combine(match_day - timedelta(days=1), time(20), UTC)
        todays_events = provider._fetch("esp.1", match_day.strftime("%Y%m%d"))
        selected = {str(e.get("id")): e for e in todays_events if str(e.get("id")) in sample}
        if len(selected) != len(sample):
            raise ValueError(f"Missing October comparison fixtures {day}: {set(sample) - set(selected)}")
        fixture_map = {}
        ground_truth = {}
        for event_id, event in selected.items():
            truth, _ = parse_event(event, "esp.1", now=datetime(2026, 12, 1, tzinfo=UTC))
            _, fixture = parse_event(pre_match_view(event), "esp.1", now=as_of)
            if truth is None or fixture is None:
                raise ValueError(f"Unverifiable historical fixture {event_id}")
            fixture_map[event_id] = fixture
            ground_truth[event_id] = truth
        example = next(iter(fixture_map.values()))
        hist, errors = provider.history(example, as_of)
        if errors:
            raise ValueError(f"Historical source issue on {day}: {errors}")
        model = fit(hist, as_of=as_of, min_games=80, regularization=.15, maxiter=650)
        calibrate = select_goal_multiplier(hist, as_of=as_of)
        n_same, n_changed = 0, 0
        for event_id, fixture in fixture_map.items():
            truth = ground_truth[event_id]
            home, away = truth.home_goals, truth.away_goals
            baseline = forecast(model, fixture.home_id, fixture.away_id, top_n=5,
                                neutral_venue=fixture.neutral_venue is True)
            candidate = forecast(model, fixture.home_id, fixture.away_id, top_n=5,
                                 neutral_venue=fixture.neutral_venue is True,
                                 goal_multiplier=calibrate.multiplier)
            old_score = baseline["top_scores"][0]["score"]
            if old_score != sample[event_id]:
                raise ValueError(f"DRIFT: {event_id} original {sample[event_id]}, current {old_score}")
            expected = baseline["expected_home_goals"] + baseline["expected_away_goals"]
            adjusted = candidate["expected_home_goals"] + candidate["expected_away_goals"]
            actual = home + away
            raw_prob = p_score(baseline["expected_home_goals"],
                               baseline["expected_away_goals"], model.rho, home, away)
            cal_prob = p_score(candidate["expected_home_goals"],
                               candidate["expected_away_goals"], model.rho, home, away)
            calibrated_score = candidate["top_scores"][0]["score"]
            real = f"{home}-{away}"
            line = {
                "date": day, "id": event_id,
                "home": fixture.home_name, "away": fixture.away_name,
                "real_score": real, "actual_total_goals": actual,
                "predicted_expected_goals": round(expected, 4),
                "calibrated_expected_goals": round(adjusted, 4),
                "baseline_score": old_score,
                "calibrated_score": calibrated_score,
                "baseline_hit": int(old_score == real),
                "calibrated_hit": int(calibrated_score == real),
                "baseline_top5_hit": int(real in {r["score"] for r in baseline["top_scores"]}),
                "calibrated_top5_hit": int(real in {r["score"] for r in candidate["top_scores"]}),
                "baseline_1x2_hit": int(_outcome(baseline) == _real_outcome(home, away)),
                "calibrated_1x2_hit": int(_outcome(candidate) == _real_outcome(home, away)),
                "baseline_nll": round(-log(raw_prob), 6),
                "calibrated_nll": round(-log(cal_prob), 6),
                "baseline_p11": round(baseline["score_1_1_probability"], 6),
                "calibrated_p11": round(candidate["score_1_1_probability"], 6),
                "calibration_multiplier": calibrate.multiplier,
                "calibration_estimate": calibrate.estimate,
                "calibration_status": calibrate.status,
                "calibration_train_count": calibrate.train_count,
                "calibration_valid_count": calibrate.validation_count,
                "validation_baseline_nll": calibrate.validation_baseline_nll,
                "validation_candidate_nll": calibrate.validation_candidate_nll,
            }
            rows.append(line)
            n_same += (calibrated_score == old_score)
            n_changed += (calibrated_score != old_score)
        dates.append({"date": day, "calibration": calibrate.as_json(),
                      "same_scores": n_same, "changed_scores": n_changed})
        provider._history.clear()  # critical: refit as of each preceding day, never reuse later models
        print("LALIGA_DIAGNOSTIC_DATE",day,calibrate.status,
              "multiplier",calibrate.multiplier,
              "validation_games",calibrate.validation_count,
              "selected",len(sample),flush=True)
    if len(rows)!=25:
        raise ValueError("Frozen 25-game cohort incomplete")
    def metric(name):
        return round(sum(float(row[name]) for row in rows), 4)
    out = {
        "period": "2026-10-09..2026-10-31", "league": "Liga", "matches": len(rows),
        "calibration_rules": {
            "type":"Time-separated training, calibration, validation within history as of 20:00 previous day",
            "candidate_range":[0.85,1.20], "accepted_only_if_independent_validation_improved": True,
            "october_score_used_for_calibration": False,
        },
        "summary": {
            "baseline_exact_hits": int(metric("baseline_hit")),
            "calibrated_exact_hits": int(metric("calibrated_hit")),
            "baseline_top5_hits": int(metric("baseline_top5_hit")),
            "calibrated_top5_hits": int(metric("calibrated_top5_hit")),
            "baseline_1x2_hits": int(metric("baseline_1x2_hit")),
            "calibrated_1x2_hits": int(metric("calibrated_1x2_hit")),
            "actual_total_goals": metric("actual_total_goals"),
            "baseline_expected_total_goals": metric("predicted_expected_goals"),
            "calibrated_expected_total_goals": metric("calibrated_expected_goals"),
            "baseline_mean_nll": round(metric("baseline_nll")/25, 4),
            "calibrated_mean_nll": round(metric("calibrated_nll")/25, 4),
            "baseline_expected_1_1_count": metric("baseline_p11"),
            "calibrated_expected_1_1_count": metric("calibrated_p11"),
            "actual_1_1_count": sum(r["real_score"]=="1-1" for r in rows),
            "validated_adjustment_dates": sum(d["calibration"]["status"]=="VALIDATED_ADJUSTMENT" for d in dates),
            "validation_failed_dates": sum(d["calibration"]["status"]=="BASELINE_VALIDATION_REJECTED" for d in dates),
        },
        "days": dates, "matches": rows,
        "limits": [
            "ESPN reconstructed historical scores/fixtures, not archived past predictions",
            "October outcomes evaluated AFTER forecast and never used for tuning",
            "Use multiple unseen months and other leagues before generalizing a calibration",
            "No bookmaker odds: profitability cannot be inferred",
        ],
    }
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/"laliga_oct2026_goal_diagnostics.json").write_text(
        json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (out_dir/"laliga_oct2026_goal_diagnostics.csv").open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("LALIGA_DIAGNOSTIC_FINAL",json.dumps(out["summary"],ensure_ascii=False),flush=True)
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,default=Path("results/diagnostics/laliga_oct2026"))
    args=p.parse_args()
    run(out_dir=args.out)


if __name__=="__main__":
    main()
