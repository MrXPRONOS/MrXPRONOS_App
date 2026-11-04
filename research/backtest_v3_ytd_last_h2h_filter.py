#!/usr/bin/env python3
"""Research: keep 2026 V3 daily modal-score leaders only if latest PRIOR H2H won.

A prediction is kept only if the LAST verified archived direct encounter
(2024 onward) ended with the same exact score from the selected match's
home/away perspective. Reversed home/away encounters are normalized.

No reranking, no alternative score and no production modifications.
The selection CSV comes from an already certified chronological native V3
backtest (GitHub run 41862691713); no model is refitted or pick replaced.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from backtest_v3_2026_ytd_modal_score_leaders import (
    START, END, percent, summarize as summarize_baseline,
    prepare_history,
)
from single_ml_v2_opponents import canonical_name, identifier

SOURCE_RUN_ID = 41862691713
SOURCE_SHA256 = "79bf973dbf9607c36895096bab62c4af916f5aea04ac501a84270c9242be8558"
SOURCE_PICK_COUNT = 3534
SOURCE_SUCCESS_COUNT = 396
OUT_FIELDS = (
    "day","score","match_id","league","home","away","probability",
    "actual_score","hit","h2h_status","h2h_source","last_h2h_day",
    "last_h2h_match_id","last_h2h_home","last_h2h_away",
    "last_h2h_original_score","last_h2h_normalized_score",
    "last_h2h_age_days",
)


def _id_pair(m):
    h = identifier(getattr(m, "home_id", None))
    a = identifier(getattr(m, "away_id", None))
    if not h or not a or h == a:
        return None
    return tuple(sorted((h, a)))


def _names(m):
    h, a = canonical_name(m.home), canonical_name(m.away)
    if h == a:
        raise ValueError("Ambiguous club names in historical H2H")
    return h, a


def _league_pair(m):
    h, a = _names(m)
    return canonical_name(m.league), *sorted((h, a))


def _orientation(selected, prior):
    """Return prior score from CURRENT selected fixture's home/away view.

    Prefer exact verified provider IDs; a textual fallback is allowed only
    within the SAME named league and if both provider-id pairs do not conflict.
    No fuzzy name/club alias guessing is ever used.
    """
    selected_ids, prior_ids = _id_pair(selected), _id_pair(prior)
    if selected_ids and prior_ids and selected_ids == prior_ids:
        return ((prior.hg, prior.ag) if selected.home_id == prior.home_id
                else (prior.ag, prior.hg)), "verified_provider_ids"
    if selected_ids and prior_ids and selected_ids != prior_ids:
        return None  # two different supposedly verified identities
    if _league_pair(selected) != _league_pair(prior):
        return None
    current_h, current_a = _names(selected)
    previous_h, previous_a = _names(prior)
    if current_h == previous_h and current_a == previous_a:
        return (prior.hg, prior.ag), "same_league_exact_club_names"
    if current_h == previous_a and current_a == previous_h:
        return (prior.ag, prior.hg), "same_league_exact_club_names"
    return None


class CompletedPriorH2H:
    """Incrementally ingests only days strictly BEFORE the predicted day."""
    def __init__(self):
        self.by_global_ids = defaultdict(list)
        self.by_league_names = defaultdict(list)
        self.last_day = None
        self.seen_ids = set()

    def add(self, m):
        if self.last_day is not None and m.day < self.last_day:
            raise ValueError("Out of chronological order in H2H history")
        if m.key in self.seen_ids:
            raise ValueError("Duplicate historical match")
        self.seen_ids.add(m.key)
        self.last_day = m.day
        pair = _id_pair(m)
        if pair:
            self.by_global_ids[pair].append(m)
        self.by_league_names[_league_pair(m)].append(m)

    def last(self, fixture):
        if self.last_day is not None and self.last_day >= fixture.day:
            raise ValueError("H2H future/same-day result would leak into selection")
        candidates = {}
        pair = _id_pair(fixture)
        if pair:
            for row in self.by_global_ids.get(pair, ()):
                candidates[row.key] = row
        for row in self.by_league_names.get(_league_pair(fixture), ()):
            candidates[row.key] = row
        eligible = []
        for previous in candidates.values():
            if not previous.day < fixture.day or previous.key == fixture.key:
                raise ValueError("Future/self H2H in pregame evidence")
            aligned = _orientation(fixture, previous)
            if aligned:
                result, identity_scope = aligned
                eligible.append((previous, result, identity_scope))
        if not eligible:
            return "no_prior_h2h", None, None, None
        latest_day = max(x[0].day for x in eligible)
        latest = [x for x in eligible if x[0].day == latest_day]
        # If two distinct games on the most recent UTC day have conflicting
        # goals, exact latest kickoff is unknown; fail closed for this pair.
        if len({x[1] for x in latest}) > 1:
            return "ambiguous_last_h2h", None, None, None
        latest.sort(key=lambda x:(x[2] != "verified_provider_ids",x[0].key))
        prior, goals, scope = latest[0]
        return "verified", prior, goals, scope


def load_certified_picks(path):
    source = Path(path)
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("2026 native V3 selection artifact hash differs from certified run")
    with source.open(newline="", encoding="utf8") as fh:
        original = list(csv.DictReader(fh))
    rows = []
    for record in original:
        row = dict(record)
        try:
            row["hit"] = int(row["hit"])
            row["probability"] = float(row["probability"])
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError("Corrupt verified V3 score row") from e
        if row["hit"] not in (0, 1):
            raise ValueError("Invalid binary settlement in source")
        rows.append(row)
    result = summarize_baseline(rows, count_all_matches=80052)
    if (len(rows) != SOURCE_PICK_COUNT or
            result["total_hits_across_independent_scores"] != SOURCE_SUCCESS_COUNT or
            result["days_with_completed_history"] != 307 or
            result["by_month"]["2026-10"]["selections"] != 279 or
            result["by_month"]["2026-10"]["hits"] != 42 or
            result["days_with_at_least_one_hit"] != 226):
        raise RuntimeError("Baseline 2026 backtest integrity check failed")
    return rows, result


def apply_h2h_filter(picks, history):
    """Return audited per-pick H2H decisions from strict previous-day history."""
    if any(history[i].day > history[i+1].day for i in range(len(history)-1)):
        raise ValueError("Historical H2H matches must be sorted")
    matches = {}
    for m in history:
        if m.key in matches:
            raise ValueError("Certified historical fixture repeated")
        matches[m.key] = m

    state = CompletedPriorH2H()
    cursor = 0
    audited = []
    for original in sorted(picks, key=lambda x: (x["day"], x["score"])):
        day = date.fromisoformat(original["day"])
        while cursor < len(history) and history[cursor].day < day:
            state.add(history[cursor])
            cursor += 1
        m = matches.get(original["match_id"])
        if m is None:
            raise ValueError("A native V3 selected match is absent from certified archive")
        if (m.day != day or m.league != original["league"] or
                m.home != original["home"] or m.away != original["away"] or
                f"{m.hg}:{m.ag}" != original["actual_score"]):
            raise ValueError("Selected fixture identity and archived settlement disagree")
        status, last, goals, scope = state.last(m)
        rec = dict(original)
        rec["h2h_status"] = (
            "kept_last_h2h_exact_win" if status == "verified" and
            f"{goals[0]}:{goals[1]}" == original["score"] else
            "rejected_last_h2h_different_score" if status == "verified" else status
        )
        rec["h2h_source"] = scope or ""
        rec["last_h2h_day"] = str(last.day) if last else ""
        rec["last_h2h_match_id"] = last.key if last else ""
        rec["last_h2h_home"] = last.home if last else ""
        rec["last_h2h_away"] = last.away if last else ""
        rec["last_h2h_original_score"] = f"{last.hg}:{last.ag}" if last else ""
        rec["last_h2h_normalized_score"] = f"{goals[0]}:{goals[1]}" if goals else ""
        rec["last_h2h_age_days"] = (m.day - last.day).days if last else ""
        if last and not last.day < m.day:
            raise ValueError("Last H2H history was not genuinely prior")
        audited.append(rec)
    if len(audited) != len(picks):
        raise RuntimeError("H2H decisions missing original scores")
    return audited


def summarize_h2h(audited, baseline):
    kept = [r for r in audited if r["h2h_status"] == "kept_last_h2h_exact_win"]
    result_types = Counter(r["h2h_status"] for r in audited)
    scopes = Counter(r["h2h_source"] for r in audited if r["h2h_source"])
    scores = sorted(set(r["score"] for r in audited), key=lambda x:tuple(map(int,x.split(":"))))
    days = [(START + __import__("datetime").timedelta(days=i)).isoformat()
            for i in range((END-START).days+1)]
    by_day = {}
    for day in days:
        original = [r for r in audited if r["day"] == day]
        retained = [r for r in original if r["h2h_status"] == "kept_last_h2h_exact_win"]
        by_day[day] = {
            "original_selections":len(original),
            "original_hits":sum(r["hit"] for r in original),
            "retained_selections":len(retained),
            "retained_hits":sum(r["hit"] for r in retained),
        }
    monthly = {}
    for m in sorted(set(day[:7] for day in days)):
        selected = [r for r in audited if r["day"].startswith(m)]
        retained = [r for r in selected if r["h2h_status"] == "kept_last_h2h_exact_win"]
        days_in_month = [d for d in days if d.startswith(m)]
        monthly[m] = {
            "days":len(days_in_month),
            "original_selections":len(selected),
            "original_hits":sum(r["hit"] for r in selected),
            "retained_selections":len(retained),
            "retained_hits":sum(r["hit"] for r in retained),
            "coverage_pct":percent(len(retained),len(selected)),
            "retained_hit_rate_pct":percent(sum(r["hit"] for r in retained),len(retained)),
            "retained_winning_days":sum(by_day[d]["retained_hits"]>0 for d in days_in_month),
            "retained_days_with_picks":sum(by_day[d]["retained_selections"]>0 for d in days_in_month),
        }
    by_score = {}
    for score in scores:
        original=[r for r in audited if r["score"]==score]
        selected=[r for r in original if r["h2h_status"]=="kept_last_h2h_exact_win"]
        by_score[score] = {
            "baseline_selections":len(original),
            "baseline_hits":sum(r["hit"] for r in original),
            "retained":len(selected),
            "retained_hits":sum(r["hit"] for r in selected),
            "coverage_pct":percent(len(selected),len(original)),
            "retained_hit_rate_pct":percent(sum(r["hit"] for r in selected),len(selected)),
        }
    hits=sum(r["hit"] for r in kept)
    original_count=len(audited)
    kept_count=len(kept)
    if sum(result_types.values()) != original_count:
        raise ValueError("Unreconciled H2H status counts")
    return {
        "version":"v3_2026_ytd_last_h2h_same_score_filter_v1",
        "selection_rule":"keep_if_last_prior_certified_head_to_head_normalized_score_equals_original_v3_modal_prediction",
        "selection_order":"original_one_modal_score_one_match_per_utc_day_then_last_prior_h2h_filter",
        "h2h_window":"certified_2024_2026_results_before_target_utc_day_only",
        "venue_reversal":"prior_score_normalized_to_current_home_away_team_order",
        "unknown_h2h":"reject_no_verified_prior_encounter",
        "no_reranking_or_score_substitution":True,
        "no_production_change":True,
        "baseline_run_id":SOURCE_RUN_ID,
        "evaluation_start":START.isoformat(),
        "evaluation_end":END.isoformat(),
        "days_evaluated":len(days),
        "baseline_selections":original_count,
        "baseline_hits":sum(r["hit"] for r in audited),
        "baseline_hit_rate_pct":percent(sum(r["hit"] for r in audited),original_count),
        "baseline_winning_days":baseline["days_with_at_least_one_hit"],
        "h2h_retained":kept_count,
        "h2h_retained_hits":hits,
        "h2h_retained_hit_rate_pct":percent(hits,kept_count),
        "h2h_coverage_pct":percent(kept_count,original_count),
        "h2h_days_with_picks":sum(v["retained_selections"]>0 for v in by_day.values()),
        "h2h_winning_days":sum(v["retained_hits"]>0 for v in by_day.values()),
        "h2h_status_counts":dict(result_types),
        "h2h_identity_source_counts":dict(scopes),
        "by_score":by_score,
        "by_month":monthly,
        "by_day":by_day,
    }


def run(site_root, model_root, baseline_csv, out_dir):
    start_time=time.monotonic()
    site_root=Path(site_root).resolve()
    model_root=Path(model_root).resolve()
    out_dir=Path(out_dir).resolve()
    if not (model_root/"research/single_ml_v2.py").is_file():
        raise RuntimeError("Missing authentic native V3 research checkout")
    previous=Path.cwd()
    sys.path.insert(0,str(model_root))
    sys.path.insert(0,str(model_root/"research"))
    sys.path.insert(0,str(site_root/"scripts"))
    try:
        os.chdir(model_root)
        picks,baseline=load_certified_picks(baseline_csv)
        print("V3_H2H_SOURCE_VERIFIED",len(picks),baseline["total_hits_across_independent_scores"],flush=True)
        history=prepare_history(site_root,model_root)
        audited=apply_h2h_filter(picks,history)
        summary=summarize_h2h(audited,baseline)
        summary["historical_rows_loaded"]=len(history)
        summary["duration_seconds"]=round(time.monotonic()-start_time,2)
        out_dir.mkdir(parents=True,exist_ok=True)
        (out_dir/"2026-h2h-filter-summary.json").write_text(
            json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
        for name,source in (("2026-h2h-filter-all-picks.csv",audited),
                            ("2026-h2h-filter-retained-only.csv",
                             [r for r in audited if r["h2h_status"]=="kept_last_h2h_exact_win"])):
            with (out_dir/name).open("w",newline="",encoding="utf8") as fh:
                writer=csv.DictWriter(fh,fieldnames=OUT_FIELDS,extrasaction="ignore")
                writer.writeheader()
                writer.writerows(source)
        print("V3_H2H_FILTER_VERIFIED",json.dumps({
            "original":summary["baseline_selections"],"original_hits":summary["baseline_hits"],
            "retained":summary["h2h_retained"],"retained_hits":summary["h2h_retained_hits"],
            "retained_hit_rate_pct":summary["h2h_retained_hit_rate_pct"],
            "winning_days":summary["h2h_winning_days"],
            "reasons":summary["h2h_status_counts"],
            "elapsed_seconds":summary["duration_seconds"]
        }),flush=True)
        return summary
    finally:
        os.chdir(previous)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--site-root",default="site")
    ap.add_argument("--model-root",default="model")
    ap.add_argument("--baseline-csv",required=True)
    ap.add_argument("--output-dir",default="/tmp/mrx-v3-h2h-2026")
    x=ap.parse_args()
    run(x.site_root,x.model_root,x.baseline_csv,x.output_dir)


if __name__=="__main__":
    main()
