#!/usr/bin/env python3
"""2026 authentic Hybrid V3 retrospective study, comparing three score policies.

No production changes, no per-match publishing, no betting profitability claims.
Every candidate is selected from a PREMATCH grid; outcomes are checked afterwards.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

STUDY_START = date(2026, 1, 1)
LAST_CERTIFIED_ARCHIVE_DAY = date(2026, 10, 24)
STUDY_VERSION = "mrx-v3-no-11-20261103"


def percentage(a, b):
    return round(100.0 * a / b, 4) if b else None


def aggregate(observations):
    """Three genuinely separate policies evaluated against same prior-day grids.

    - base: modal 11x11 score on all fixtures;
    - discard: remove the WHOLE fixture when modal equals 1:1;
    - replace: retain fixtures and take best NON-1:1 score on those fixtures.
    """
    total = len(observations)
    if not total:
        raise ValueError("No authenticated 2026 backtest forecasts")
    base_hits = kept = kept_hits = replacement_hits = replaced = 0
    chosen_11_hits = actual_11 = replacement_changed_hits = 0
    months = defaultdict(lambda: [0, 0, 0, 0, 0])
    alternative_scores = Counter()
    for row in observations:
        day, bh, ba, ah, aa, gh, ga, prob, alternative_prob = row
        assert isinstance(day, str) and len(day) == 10
        assert all(isinstance(x, int) and 0 <= x <= 10 for x in (bh, ba, ah, aa, gh, ga))
        assert 0 <= prob <= 1 and 0 <= alternative_prob <= 1
        assert (ah, aa) != (1, 1)
        original_hit = int((bh, ba) == (gh, ga))
        base_hits += original_hit
        actual_11 += int((gh, ga) == (1, 1))
        record = months[day[:7]]
        record[0] += 1
        record[1] += original_hit
        if (bh, ba) == (1, 1):
            replaced += 1
            chosen_11_hits += original_hit
            alt_hit = int((ah, aa) == (gh, ga))
            replacement_hits += alt_hit
            replacement_changed_hits += alt_hit
            alternative_scores[f"{ah}-{aa}"] += 1
            record[4] += alt_hit
        else:
            kept += 1
            kept_hits += original_hit
            replacement_hits += original_hit
        record[2] += int((bh, ba) == (1, 1))
        record[3] += int((ah, aa) == (gh, ga)) if (bh, ba) == (1, 1) else original_hit
    assert kept + replaced == total
    assert replacement_hits == kept_hits + replacement_changed_hits
    months_result = {
        k: {
            "eligible": vals[0],
            "baseline_hits": vals[1],
            "baseline_accuracy_pct": percentage(vals[1], vals[0]),
            "discard_1_1_count": vals[2],
            "discard_1_1_coverage_pct": percentage(vals[0]-vals[2], vals[0]),
            "replacement_hits": vals[3],
            "replacement_accuracy_pct": percentage(vals[3], vals[0]),
            "replacement_hits_on_1_1_cases": vals[4],
        }
        for k, vals in sorted(months.items())
    }
    return {
        "version": STUDY_VERSION,
        "model": "machine_learning_v3_hybrid",
        "source": "verified_prior_day_chronological_predictions",
        "comparison": "all predicted matches; no bookmaker prices, no ROI",
        "baseline": {
            "predictions": total, "hits": base_hits,
            "exact_hit_rate_pct": percentage(base_hits, total),
        },
        "scenario_1_remove_entire_1_1_modal_matches": {
            "predictions": kept, "excluded": replaced,
            "coverage_pct": percentage(kept, total),
            "hits": kept_hits,
            "exact_hit_rate_pct": percentage(kept_hits, kept),
            "hit_delta_vs_baseline_percentage_points":
                round(percentage(kept_hits, kept) - percentage(base_hits, total), 4)
                if kept else None,
        },
        "scenario_2_replace_modal_1_1_with_best_other_score": {
            "predictions": total, "replaced": replaced,
            "coverage_pct": 100.0,
            "hits": replacement_hits,
            "exact_hit_rate_pct": percentage(replacement_hits, total),
            "hit_delta_vs_baseline_percentage_points":
                round(percentage(replacement_hits, total) - percentage(base_hits, total), 4),
            "alternative_successes_on_replaced_matches": replacement_changed_hits,
            "best_alternative_score_distribution": dict(alternative_scores.most_common(20)),
        },
        "diagnostics": {
            "modal_1_1_predictions": replaced,
            "modal_1_1_share_pct": percentage(replaced, total),
            "modal_1_1_correct": chosen_11_hits,
            "modal_1_1_accuracy_pct": percentage(chosen_11_hits, replaced),
            "actual_1_1_results": actual_11,
            "actual_1_1_share_pct": percentage(actual_11, total),
            "removed_winning_predictions": chosen_11_hits,
            "replacement_lost_1_1_hits": chosen_11_hits,
            "replacement_gained_non_1_1_hits": replacement_changed_hits,
            "net_additional_hits_scenario_2": replacement_changed_hits - chosen_11_hits,
        },
        "monthly": months_result,
    }


def run(site_root, model_root, *, end, out):
    began = time.monotonic()
    site_root = Path(site_root).resolve()
    model_root = Path(model_root).resolve()
    if not (model_root / "research/single_ml_v2.py").is_file():
        raise RuntimeError("Authentic V3 research checkout is missing")
    if not (STUDY_START <= end < datetime.now(timezone.utc).date()):
        raise ValueError("Backtests require an already-completed UTC date in 2026")
    if end > date(2026, 12, 31):
        raise ValueError("This experiment concerns the 2026 calendar year only")
    previous = Path.cwd()
    sys.path.insert(0, str(model_root))
    sys.path.insert(0, str(model_root / "research"))
    sys.path.insert(0, str(site_root / "scripts"))
    try:
        os.chdir(model_root)
        from single_ml_v2_git import key_from_environment, seal, open_sealed
        from single_ml_v2_multisource import certified_rows, check_ml_loader
        from single_ml_v2 import load_matches, backtest
        from single_ml_v2_data import day_snapshot
        from sportdata_api import fetch_games
        from run_exact_scores_v3_daily import historical_daily_rows, DAILY_HISTORY_SUBDIR
        key = key_from_environment()
        raw = certified_rows(key)
        history = check_ml_loader(raw)
        print("V3_NO_11_PHASE", "certified_corpus_loaded", len(history), flush=True)
        cache_dir = site_root / DAILY_HISTORY_SUBDIR
        if end > LAST_CERTIFIED_ARCHIVE_DAY:
            fresh, counts = historical_daily_rows(
                cache_dir, end, fetcher=fetch_games, normalizer=day_snapshot,
                sealer=seal, opener=open_sealed, key=key)
            import tempfile
            with tempfile.TemporaryDirectory(prefix="mrx-v3-no11-") as td:
                source = Path(td) / "verified_completed.json"
                source.write_text(json.dumps(fresh, ensure_ascii=False), encoding="utf8")
                extra = load_matches(str(source), end)
            if len(extra) != len(fresh):
                raise ValueError("Actual native loader rejected completed-day source data")
            history = sorted([*history, *extra], key=lambda m: (m.day, m.key))
            print("V3_NO_11_PHASE", "incremental_certified_utc_days", len(counts), flush=True)
        if not history or history[-1].day != end:
            raise ValueError("Backtest history incomplete up to requested date")
        import tempfile
        with tempfile.TemporaryDirectory(prefix="mrx-v3-no11-eval-") as td:
            result = backtest(history, STUDY_START, end,
                              str(Path(td) / "original_hybrid"),
                              max_eval=0, retrain_days=30, auto_tune=False,
                              v3_models=True, production_v3_only=True,
                              no_11_study=True)
        observations = result.get("observations")
        report = aggregate(observations)
        report["evaluation_start"] = STUDY_START.isoformat()
        report["evaluation_end"] = end.isoformat()
        report["historical_training_start"] = history[0].day.isoformat()
        report["historical_training_latest"] = history[-1].day.isoformat()
        report["certified_total_matches_loaded"] = len(history)
        report["elapsed_seconds"] = round(time.monotonic() - began, 2)
        # Only aggregates; never upload per-match predictions, scores or corpus.
        output = Path(out).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
        print("V3_NO_11_AGGREGATE_REPORT", json.dumps({
            "interval": [report["evaluation_start"], report["evaluation_end"]],
            "observations": report["baseline"]["predictions"],
            "baseline": report["baseline"]["exact_hit_rate_pct"],
            "exclude": report["scenario_1_remove_entire_1_1_modal_matches"]["exact_hit_rate_pct"],
            "replace": report["scenario_2_replace_modal_1_1_with_best_other_score"]["exact_hit_rate_pct"],
            "elapsed_seconds": report["elapsed_seconds"],
        }), flush=True)
        return report
    finally:
        os.chdir(previous)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-root", default="site")
    ap.add_argument("--model-root", default="model")
    ap.add_argument("--end", default=(datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat())
    ap.add_argument("--out", default="/tmp/mrx-v3-no11-2026-report.json")
    args = ap.parse_args()
    run(args.site_root, args.model_root, end=date.fromisoformat(args.end), out=args.out)


if __name__ == "__main__":
    main()
