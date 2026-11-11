"""Reproducible retrospective replay of the EXACT Social Top10 production selector.

No social posting. Historical ESPN event snapshots are used ONLY to reconstruct
pre-kickoff fixtures and, separately, evaluate final scores. The historical
schedule as it was visible at that time is NOT independently archived here.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from .daily_espn import ALLOWED, ESPNProvider, parse_event
from .daily_pipeline import run_daily
from .daily_rank import rank_fixtures
from .domain import utc_datetime

UTC = timezone.utc
BLOCKED_STATUSES = {"STATUS_CANCELED", "STATUS_POSTPONED", "STATUS_ABANDONED"}


def retrospectively_unplayed(event: dict) -> dict:
    """Strip both teams' result scores and terminal status before fixture ranking."""
    view = deepcopy(event)
    status = view.setdefault("status", {}).setdefault("type", {})
    status["completed"] = False
    status["name"] = "STATUS_SCHEDULED"
    for comp in view.get("competitions") or []:
        for side in comp.get("competitors") or []:
            side.pop("score", None)
    return view


class RetrospectiveESPN(ESPNProvider):
    def __init__(self, *, shared_fetch: dict | None = None, session=None):
        super().__init__(session=session)
        # Shared network cache only; day-specific historical model cache is
        # intentionally NEVER shared (would freeze training at October 1).
        if shared_fetch is not None:
            self._cache = shared_fetch
        self.truth: dict[str, tuple[int, int]] = {}
        self.raw_seen = 0
        self.source_errors: list[str] = []

    def discover(self, target_date: date, now: datetime):
        now = utc_datetime(now)
        if target_date <= now.date() or (target_date - now.date()).days != 1:
            raise ValueError("Replay expects 20:00 UTC on the preceding day")
        self.truth = {}
        self.raw_seen = 0
        self.discovery_counts = {}
        fixtures = []
        warnings = []
        for league in self.leagues:
            label = f"ESPN/{league}"
            try:
                events = self._fetch(league, target_date.strftime("%Y%m%d"))
            except Exception as exc:
                msg = f"{label}: {type(exc).__name__}: {exc}"
                warnings.append(msg)
                self.source_errors.append(msg)
                self.discovery_counts[label] = 0
                continue
            self.raw_seen += len(events)
            count = 0
            for event in events:
                if not isinstance(event, dict):
                    continue
                state = str((event.get("status") or {}).get("type", {}).get("name", "")).upper()
                if state in BLOCKED_STATUSES:
                    continue
                # Post-match truth is kept separate from prediction inputs.
                if (event.get("status") or {}).get("type", {}).get("completed") is True:
                    actual, _ = parse_event(event, league, now=datetime(2026, 12, 1, tzinfo=UTC))
                    if actual:
                        self.truth[actual.id] = (actual.home_goals, actual.away_goals)
                _, item = parse_event(retrospectively_unplayed(event), league, now=now)
                if item is not None and item.kickoff.date() == target_date:
                    fixtures.append(item)
                    count += 1
            self.discovery_counts[label] = count
        return fixtures, warnings


def prediction_row(item: dict, outcome: tuple[int, int] | None, day: date) -> dict:
    forecast = item["forecast"]
    actual = (f"{outcome[0]}-{outcome[1]}" if outcome is not None else None)
    top5 = [row["score"] for row in forecast["top_5"]]
    probs = forecast["outcomes_1x2"]
    pred_1x2 = max(("home", "draw", "away"), key=lambda k: probs[k])
    real_1x2 = ("home" if outcome[0] > outcome[1] else
                "away" if outcome[0] < outcome[1] else "draw") if outcome else None
    return {
        "date": day.isoformat(), "id": item["id"],
        "competition": item["competition_name"],
        "home": item["home"], "away": item["away"],
        "importance": item["importance"],
        "importance_reasons": item["importance_reasons"],
        "ranked_by_popularity": True,
        "kickoff_utc": item["kickoff_utc"],
        "predicted_exact": forecast["most_likely_score"],
        "predicted_exact_probability": forecast["most_likely_probability"],
        "top_5": top5,
        "real_exact": actual,
        "top1_hit": int(actual == top5[0]) if actual is not None else None,
        "top3_hit": int(actual in top5[:3]) if actual is not None else None,
        "top5_hit": int(actual in top5) if actual is not None else None,
        "predicted_1x2": pred_1x2,
        "real_1x2": real_1x2,
        "one_x_two_hit": int(pred_1x2 == real_1x2) if real_1x2 else None,
        "naive_1_1_hit": int(actual == "1-1") if actual else None,
        "training_matches": item["training_matches"],
        "last_known_result": item["training_last_result"],
        "history_days_old": item["result_age_days"],
    }


def statistics(matches: list[dict], days: list[dict]) -> dict:
    observed = [r for r in matches if r["real_exact"] is not None]
    total = len(observed)
    rate = lambda k: round(100 * sum(x[k] for x in observed) / total, 2) if total else None
    expected = sum(x["predicted_exact_probability"] for x in observed)
    counts = Counter(r["competition"] for r in observed)
    return {
        "days": len(days),
        "days_with_candidates": sum(d["discovered"] > 0 for d in days),
        "days_with_10_selected": sum(d["selected"] == 10 for d in days),
        "video_ready_days": sum(d["ready_for_video"] for d in days),
        "total_candidates": sum(d["discovered"] for d in days),
        "total_ranked_eligible": sum(d["eligible"] for d in days),
        "total_selected": len(matches),
        "results_observed": total,
        "results_missing": len(matches) - total,
        "selected_competitions": dict(counts),
        "top1_exact_hits": sum(x["top1_hit"] for x in observed),
        "top1_exact_hit_rate_percent": rate("top1_hit"),
        "top3_exact_hits": sum(x["top3_hit"] for x in observed),
        "top3_exact_hit_rate_percent": rate("top3_hit"),
        "top5_exact_hits": sum(x["top5_hit"] for x in observed),
        "top5_exact_hit_rate_percent": rate("top5_hit"),
        "one_x_two_hits": sum(x["one_x_two_hit"] for x in observed),
        "one_x_two_hit_rate_percent": rate("one_x_two_hit"),
        "naive_1_1_hits": sum(x["naive_1_1_hit"] for x in observed),
        "naive_1_1_hit_rate_percent": rate("naive_1_1_hit"),
        "expected_top1_hits_given_model_probabilities": round(expected, 2),
        "actual_minus_expected_top1_hits": round(sum(x["top1_hit"] for x in observed) - expected, 2),
    }


def backtest(start: date, end: date, *, out: Path, session=None):
    if end < start:
        raise ValueError("End date precedes start date")
    if (end - start).days > 62:
        raise ValueError("Backtest accepts up to 63 days")
    shared_fetch: dict = {}
    output_days = []
    selected_rows = []
    day = start
    for i in range((end - start).days + 1):
        day = start + timedelta(days=i)
        cutoff = datetime.combine(day - timedelta(days=1), time(20, 0), UTC)
        provider = RetrospectiveESPN(shared_fetch=shared_fetch, session=session)
        result = run_daily(provider, day=day, as_of=cutoff, limit=10,
                           min_games=80, min_team=4, min_importance=70,
                           max_staleness_days=35, max_per_league=4)
        # Only the top editorial/pre-match selected matches are evaluated.
        for match in result["selected"]:
            selected_rows.append(prediction_row(match, provider.truth.get(match["id"]), day))
        record = {
            "date": day.isoformat(), "cutoff_utc": cutoff.isoformat(),
            "raw_event_count": provider.raw_seen,
            "discovered": result["count_before_quality_checks"],
            "per_competition_discovery": provider.discovery_counts,
            "eligible": result["eligible_count"],
            "selected": result["selected_count"],
            "ready_for_video": result["ready_for_video"],
            "status": result["status"],
            "rejection_reasons": Counter(x["reason"].split("_")[0] for x in result["rejected"]),
            "source_warnings": result["warnings"][:8],
        }
        record["rejection_reasons"] = dict(record["rejection_reasons"])
        output_days.append(record)
        print(f"BACKTEST_DAY {day.isoformat()} found={record['discovered']} "
              f"eligible={record['eligible']} selected={record['selected']} "
              f"video_ready={record['ready_for_video']}", flush=True)
    stats = statistics(selected_rows, output_days)
    all_warnings = [w for d in output_days for w in d["source_warnings"]]
    result = {
        "title": "Mr XPRONOS - October 2026 exact score popularity-weighted replay",
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "model": "Production: dcscore.daily_pipeline.run_daily + Dixon-Coles",
        "source": "ESPN public scoreboard (uefa.wchampions + eng.trophy only)",
        "ranking": "Production editorial ranking, then quota max four per league before fill",
        "settings": {
            "as_of": "20:00 UTC day before each fixture date",
            "limit": 10, "min_games": 80, "min_team": 4,
            "min_importance": 70, "max_staleness_days": 35,
            "max_per_league": 4,
        },
        "stats": stats, "days": output_days, "matches": selected_rows,
        "data_quality": {
            "source_warnings_count": len(all_warnings),
            "source_warnings_examples": sorted(set(all_warnings))[:12],
            "fixture_visibility_bias": (
                "Historical fixtures reconstructed from today's ESPN scoreboards, "
                "not independent archived snapshots of the schedules available at each cutoff."
            ),
            "temporal_leakage_control": (
                "Final scores removed from fixture view; the production history and "
                "model fitting filter training results to strictly before the cutoff."
            ),
            "report_scope": (
                "Backtest of the current ESPN-only SOCIAL production feed; not "
                "a general test of all prominent men's competitions."
            ),
            "no_odds_no_roi": "No bookmaker odds: ROI, profitability and value cannot be calculated.",
            "no_predictions_invented": True,
        },
    }
    # Mark insufficient/failed source coverage; do not report 0% success from empty data.
    if stats["results_observed"] == 0:
        result["status"] = "NO_VERIFIABLE_BACKTEST_SAMPLE"
    elif all_warnings:
        result["status"] = "PARTIAL_SOURCE_COVERAGE"
    else:
        result["status"] = "COMPLETED_WITH_RETROSPECTIVE_FIXTURE_LIMITATION"
    out.mkdir(parents=True, exist_ok=True)
    (out / "backtest_oct2026.json").write_text(json.dumps(
        result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    if selected_rows:
        fields = ["date", "competition", "home", "away", "importance",
                  "predicted_exact", "predicted_exact_probability", "real_exact",
                  "top1_hit", "top3_hit", "top5_hit", "predicted_1x2", "real_1x2",
                  "one_x_two_hit", "naive_1_1_hit", "training_matches"]
        with (out / "backtest_oct2026_matches.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(selected_rows)
    print("BACKTEST_FINAL_REPORT", json.dumps(
        {"status": result["status"], "stats": stats,
         "sample_matches": selected_rows[:4],
         "data_quality": result["data_quality"]}, ensure_ascii=False), flush=True)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description="ESPN-only October 2026 pre-match popular exact-score backtest")
    p.add_argument("--start", default="2026-10-01")
    p.add_argument("--end", default="2026-10-31")
    p.add_argument("--out", type=Path, default=Path("results/backtests/oct2026"))
    args = p.parse_args(argv)
    backtest(date.fromisoformat(args.start), date.fromisoformat(args.end), out=args.out)


if __name__ == "__main__":
    main()
