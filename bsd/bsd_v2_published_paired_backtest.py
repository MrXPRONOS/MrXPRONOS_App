"""BSD V2 paired validation on the exact first-observed published fixture population.

Compares archived original selections with point-in-time model replay. The 2024-26
history is used strictly for pre-2026 model fitting and past-only match features,
NOT as the evaluation population. No odds and no odds-based filtering.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bsd_archive import MATCHES_FILE, _read_json
from bsd_v2_core import (
    V2History, estimate_goals, fit_rho_2024, fixture_datetime, markets_from_matrix,
    outcome_scores, predict_v2, score_matrix,
)
from bsd_v2_over_under import fit_total_model, adjust_candidates
from bsd_v2_btts import fit_btts_model, btts_candidates
from bsd_v2_double_chance import fit_model, adjust_candidates as dc_adjust
from bsd_v2_policies import fit_policy
from bsd_markets import realized
from bsd_v2_market_expansion import ALL_KEYS, candidates, outcome, first_half_scores, half_time_share
from bsd_v2_all_markets_backtest import ExperimentalCalibrator, metrics


def utc(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return None
        return stamp.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def primary_market_prob(candidate, calibration):
    if candidate.family in ("result", "double_chance") and getattr(calibration, "outcome_calibration", None) is not None:
        return candidate.probability
    return calibration.score(candidate)[1]


def annual_market_training(index, rho, halftime_share):
    """Calibrate new binomial markets on Jan-Aug 2025 only."""
    cal = ExperimentalCalibrator()
    n = 0
    for _, item in index.global_games:
        dt = fixture_datetime(item)
        if dt.year != 2025 or dt.month > 8:
            continue
        feat, _ = estimate_goals(item, index)
        if feat is None:
            continue
        mat = score_matrix(feat["home"], feat["away"], rho)
        scores = outcome_scores(item)
        for cand in candidates(mat, home_xg=feat["home"], away_xg=feat["away"], halftime_share=halftime_share):
            y = outcome(cand.key, *scores, half_time=first_half_scores(item))
            cal.observe(cand.key, cand.probability, y)
        n += 1
    return cal, n


def grouped_rows(rows):
    return {key: metrics(v) for key, v in sorted(rows.items())}


def run(history, ledger):
    index = V2History(history)
    lookup = {}
    for _, item in index.global_games:
        lookup[(str(item["id"]), fixture_datetime(item).isoformat())] = item

    rho, rho_fit = fit_rho_2024(index)
    totals, _ = fit_total_model(index, rho=rho)
    btts, _ = fit_btts_model(index, rho=rho)
    dc, _ = fit_model(index, rho=rho)
    calibration, policy, training = fit_policy(index, rho=rho, total_model=totals,
                                                btts_model=btts, dc_model=dc)
    ht_share, ht_fit = half_time_share(
        [item for _, item in index.global_games if fixture_datetime(item).year == 2024]
    )
    experiment, new_train_count = annual_market_training(index, rho, ht_share)

    counts = Counter()
    published = defaultdict(list)
    reproduced = defaultdict(list)
    published_by_market = defaultdict(list)
    reproduced_by_market = defaultdict(list)
    published_by_category = defaultdict(list)
    observed_windows = defaultdict(list)
    options = defaultdict(list)
    refunds = Counter()
    missing = Counter()
    option_by_category = defaultdict(lambda: defaultdict(list))
    pre_first_observed = []
    all_first_observed = []
    original_probability_errors = []
    same_choice = Counter()
    model_choices = defaultdict(Counter)
    selected_rows = defaultdict(list)
    published_pre_rows = defaultdict(list)
    published_post_rows = defaultdict(list)
    publication_start = None
    publication_end = None
    checked_ids = set()

    for record in ledger.get("entries", []):
        if not isinstance(record, dict):
            counts["malformed_entry"] += 1
            continue
        event_id = str(record.get("source_event_id") or "")
        kickoff = utc(record.get("event_date"))
        observed = utc(record.get("first_observed_at"))
        selection = (record.get("original_pick") or {}).get("selection_key")
        if not event_id or kickoff is None or not selection:
            counts["malformed_entry"] += 1
            continue
        ident = (event_id, kickoff.isoformat())
        if ident in checked_ids:
            counts["duplicate_ledger_identity"] += 1
            continue
        checked_ids.add(ident)
        counts["ledger_entries"] += 1
        publication_start = kickoff if publication_start is None or kickoff < publication_start else publication_start
        publication_end = kickoff if publication_end is None or kickoff > publication_end else publication_end
        pre = observed is not None and observed < kickoff
        counts["first_observed_prematch" if pre else "first_observed_at_or_after_kickoff"] += 1
        if record.get("settlement", {}).get("status") != "finished":
            counts["pending_settlement"] += 1
            continue
        counts["settled_ledger"] += 1
        if not pre:
            counts["settled_first_observed_after_kickoff"] += 1
        else:
            counts["settled_first_observed_prematch"] += 1

        event = lookup.get(ident)
        if event is None:
            counts["archived_match_not_found"] += 1
            continue
        scored = outcome_scores(event)
        if scored is None:
            counts["archived_score_unavailable"] += 1
            continue
        h, a = scored
        saved = record["settlement"]
        if (saved.get("home_score"), saved.get("away_score")) != (h, a):
            counts["settlement_score_mismatch"] += 1
            continue
        counts["verified_identical_scores"] += 1
        observed_key = (record.get("original_pick") or {}).get("selection_key")
        ledger_won = bool(saved.get("primary_won"))
        # Immutable winning status is compared to independently settled original key.
        feat, why = estimate_goals(event, index)
        if feat is None:
            counts["model_fixture_ineligible"] += 1
            continue
        counts["replay_features_available"] += 1
        mat = score_matrix(feat["home"], feat["away"], rho)
        old = markets_from_matrix(mat)
        old = adjust_candidates(event, index, old, totals)
        old = btts_candidates(event, index, old, btts)
        old = dc_adjust(event, index, old, dc, getattr(calibration, "outcome_calibration", None))
        by_key = {o.key: o for o in old}
        archived_choice = by_key.get(observed_key)
        if archived_choice is None:
            counts["published_market_unknown"] += 1
            continue
        actual_won = bool(realized(archived_choice, h, a))
        if actual_won == ledger_won:
            counts["original_market_settlement_agrees"] += 1
        else:
            counts["original_market_settlement_disagrees"] += 1
        archived_p = (record.get("original_pick") or {}).get("confidence")
        replay_p = primary_market_prob(archived_choice, calibration)
        if isinstance(archived_p, (float, int)) and 0 <= archived_p <= 1:
            counts["original_probability_matched"] += 1
            original_probability_errors.append(abs(replay_p - float(archived_p)))
            published["all"].append((float(archived_p), int(actual_won)))
        reproduced["all"].append((replay_p, int(actual_won)))
        category = str(record.get("category_original") or "unknown")
        published_by_market[observed_key].append((float(archived_p) if isinstance(archived_p, (float, int)) else replay_p, int(actual_won)))
        reproduced_by_market[observed_key].append((replay_p, int(actual_won)))
        published_by_category[category].append((replay_p, int(actual_won)))
        observed_windows["prematch" if pre else "late_recorded"].append((replay_p, int(actual_won)))
        (published_pre_rows if pre else published_post_rows)[observed_key].append((replay_p, int(actual_won)))

        # New markets evaluated on the EXACT same fixed set of published fixtures.
        for candidate in candidates(mat, home_xg=feat["home"], away_xg=feat["away"], halftime_share=ht_share):
            y = outcome(candidate.key, h, a, half_time=first_half_scores(event))
            if y is None or candidate.probability is None:
                missing[candidate.key] += 1
                continue
            if y == -1:
                refunds[candidate.key] += 1
                continue
            if candidate.family == "dnb":
                # Use specialist full-time result model, not independent Poisson probabilities.
                den = 1 - by_key["X"].probability
                p = by_key["1" if candidate.key == "DNB_HOME" else "2"].probability / den if den > 1e-12 else None
            else:
                p = experiment.score(candidate.key, candidate.probability)
            if p is None:
                missing[candidate.key] += 1
                continue
            p = max(0., min(1., p))
            options[candidate.key].append((p, y))
            option_by_category["prematch" if pre else "late_recorded"][candidate.key].append((p, y))

        # For published first observations we use the actual recorded timestamp.
        # For late records: a counterfactual at kickoff-1s, never call it observed-pregame.
        clock = observed if pre else kickoff - timedelta(seconds=1)
        fixture = {**event, "status": "notstarted", "home_score": None, "away_score": None}
        candidate_prediction, reason = predict_v2(
            fixture, index, calibration=calibration, rho=rho, clock=clock,
            quality_policy=policy, total_model=totals, btts_model=btts, dc_model=dc,
            excluded_keys=frozenset({"12", "UNDER_45"}),
            selection_conservative_minimums={"OVER_15": .85},
        )
        tag = "prematch_first_observed" if pre else "counterfactual_late_record"
        same_choice[(tag, "checked")] += 1
        if candidate_prediction is None:
            same_choice[(tag, "no_choice")] += 1
            model_choices[tag]["none:" + str(reason)] += 1
            continue
        pred = candidate_prediction["prediction"]
        model_choices[tag][pred["key"]] += 1
        choice_win = bool(realized(by_key[pred["key"]], h, a))
        selected_rows[tag].append((float(pred["probability"]), int(choice_win)))
        same_choice[(tag, "has_choice")] += 1
        if pred["key"] == observed_key:
            same_choice[(tag, "same_choice")] += 1
        else:
            same_choice[(tag, "different_choice")] += 1

    for market, candidate in ((c.key, c) for c in markets_from_matrix(score_matrix(1.25, 1.1))):
        if market not in reproduced_by_market:
            reproduced_by_market[market] = []
    # Also evaluate all 16 original options on the same population, including
    # original options that the published model did not choose.
    for rec in (ledger.get("entries") or []):
        if rec.get("settlement", {}).get("status") != "finished":
            continue
        key = (str(rec.get("source_event_id") or ""), str(rec.get("event_date") or ""))
        ev = lookup.get(key)
        if ev is None or outcome_scores(ev) is None:
            continue
        feat, _ = estimate_goals(ev, index)
        if feat is None:
            continue
        mat = score_matrix(feat["home"], feat["away"], rho)
        cand = dc_adjust(ev, index,
                          btts_candidates(ev, index,
                                          adjust_candidates(ev, index, markets_from_matrix(mat), totals),
                                          btts),
                          dc, getattr(calibration, "outcome_calibration", None))
        for option in cand:
            p = primary_market_prob(option, calibration)
            options[option.key].append((p, int(realized(option, *outcome_scores(ev)))))

    result = {
        "version": "bsd-v2-published-fixture-paired-validation-1",
        "evaluation_population": "Only matches in original immutable publication ledger",
        "kickoff_from": publication_start.isoformat() if publication_start else None,
        "kickoff_to": publication_end.isoformat() if publication_end else None,
        "counts": dict(counts),
        "protocol": {
            "train": "2024", "calibrate": "2025 Jan-Aug", "validate": "2025 Sep-Dec",
            "test": "2026 original published fixture IDs only",
            "prematch_rule": "first_observed_at < kickoff",
            "late_record_rule": "retrospective only; not evidence of genuine pre-match publication",
            "replay_clock": "original first_observed_at when earlier than kickoff",
            "price_used": False,
            "fixtures_joined": "BSD event ID + exact kickoff timestamp",
        },
        "training": {"rho": rho_fit, "policy": training, "halftime": ht_fit,
                     "new_market_training": new_train_count},
        "original_publication": grouped_rows(published),
        "replay_same_original_market": grouped_rows(reproduced),
        "original_published_market_breakdown": grouped_rows(published_by_market),
        "replay_on_original_market_breakdown": grouped_rows(reproduced_by_market),
        "original_market_by_category": grouped_rows(published_by_category),
        "original_market_by_registration_time": grouped_rows(observed_windows),
        "original_market_prematch_breakdown": grouped_rows(published_pre_rows),
        "original_market_late_record_breakdown": grouped_rows(published_post_rows),
        "market_recomputed_all_on_same_published_fixtures": grouped_rows(options),
        "new_markets_prematch_vs_late": {label: grouped_rows(group) for label, group in option_by_category.items()},
        "new_market_refunds": dict(refunds),
        "new_market_missing": dict(missing),
        "choice_replay": {
            phase: {
                "checked": same_choice[(phase, "checked")],
                "with_choice": same_choice[(phase, "has_choice")],
                "no_choice": same_choice[(phase, "no_choice")],
                "same_market": same_choice[(phase, "same_choice")],
                "different_market": same_choice[(phase, "different_choice")],
                "model_choice_performance": metrics(selected_rows[phase]),
                "keys": dict(model_choices[phase]),
            } for phase in ("prematch_first_observed", "counterfactual_late_record")
        },
        "replay_original_probability_error": {
            "n": len(original_probability_errors),
            "mean_absolute_error": round(sum(original_probability_errors) / len(original_probability_errors), 6) if original_probability_errors else None,
            "max_absolute_error": round(max(original_probability_errors), 6) if original_probability_errors else None,
        },
        "limitations": [
            "Market re-settlement on the same fixtures is independent; it is not independent evidence of predictive skill.",
            "Only first observations before kickoff are timestamp-verified prematch in this ledger.",
            "Late-first-observed entries may have been published before kickoff, but ledger alone cannot prove it.",
            "This uses current replay code against an immutable original ledger; code and training may differ from historical publication.",
            "2026 ledger is a publication-selected subset, not a randomized independent evaluation population.",
            "No odds, ROI or bookmaker availability inferred.",
        ],
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="bsd/v2_published_paired_backtest_report.json")
    args = parser.parse_args()
    historical = _read_json(MATCHES_FILE, None)
    if not isinstance(historical, list) or not historical:
        parser.error("Restore the BSD encrypted history before this paired test.")
    ledger = _read_json(Path("bsd/publication_ledger.json"), {})
    if ledger.get("schema") != "bsd-v2-publication-ledger-1":
        parser.error("Immutable BSD publication ledger missing or invalid.")
    result = run(historical, ledger)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("BSD_PAIRED_PUBLISHED_BACKTEST",
          json.dumps({"counts": result["counts"],
                      "original_accuracy": result["original_publication"]["all"]["rate"],
                      "replayed_accuracy": result["replay_same_original_market"]["all"]["rate"],
                      "replay": result["choice_replay"],
                      "probability_error": result["replay_original_probability_error"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
