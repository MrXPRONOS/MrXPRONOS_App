#!/usr/bin/env python3
"""Publish two daily Top5 from authentic PREMATCH Hybrid V3 11x11 probability grids.

This does NOT train V3 or fetch fixtures. Its input must come from an
independently audited prospective Hybrid V3 forecaster, not historic backtests.
Never publish a historical outcome, odds claim, or fake fixture.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone, date, timedelta
from pathlib import Path

SCHEMA = "mrx-exact-top5-v1"
MODEL = "machine_learning_v3_hybrid"
GROUPS = {
    "H_LOW": ("1:0", "2:0", "2:1"),
    "H_HIGH": ("3:0", "3:1", "3:2"),
    "A_LOW": ("0:1", "0:2", "1:2"),
    "A_HIGH": ("0:3", "1:3", "2:3"),
    "DRAW_LOW": ("0:0", "1:1", "2:2"),
}
SCORE_GROUP = {score: group for group, scores in GROUPS.items() for score in scores}
assert len(SCORE_GROUP) == 15
# Research-tested scenario 1: EXCLUDE whole fixtures whose original modal score
# is 1:1; never promote an alternative or alter the 11x11 forecast grid.
EXCLUDED_MODAL_SCORES = frozenset({"1:1"})

FORBIDDEN = {"actual_score", "home_score", "away_score", "hit", "win", "result",
             "settled", "is_finished", "final_score", "actual_probability"}


def parse_utc(value):
    if not isinstance(value, str) or not value.endswith("Z") or "T" not in value:
        raise ValueError("Only explicit UTC ISO timestamps are accepted")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid UTC ISO timestamp") from exc
    if parsed.utcoffset().total_seconds() != 0:
        raise ValueError("Timestamp must be UTC")
    return parsed


def day_before(value, timestamp):
    if not isinstance(value, str):
        raise ValueError("Missing past-only model provenance")
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Bad model provenance date") from exc
    if d >= timestamp.date():
        raise ValueError("Model fit and previous match history MUST predate publication UTC day")


def grid_summary(grid):
    if not isinstance(grid, list) or len(grid) != 11:
        raise ValueError("Expected an original Hybrid V3 11x11 grid")
    p = []
    for row in grid:
        if not isinstance(row, list) or len(row) != 11:
            raise ValueError("Every exact-score grid row needs eleven probabilities")
        vals = []
        for v in row:
            if type(v) not in (int, float) or not math.isfinite(v) or v < 0 or v > 1:
                raise ValueError("Invalid probability matrix cell")
            vals.append(float(v))
        p.append(vals)
    if abs(math.fsum(math.fsum(row) for row in p) - 1.) > 2e-5:
        raise ValueError("Exact-score probability matrix is not normalized")
    ih, ia = max(((h, a) for h in range(11) for a in range(11)), key=lambda xy: p[xy[0]][xy[1]])
    score = f"{ih}:{ia}"
    modal = p[ih][ia]
    group = SCORE_GROUP.get(score)
    group_mass = math.fsum(p[int(s.split(":")[0])][int(s.split(":")[1])] for s in GROUPS[group]) if group else 0.
    if group and (group_mass + 1e-12 < modal or group_mass > 1 + 1e-10):
        raise ValueError("Frozen three-score group does not include original modal score")
    return score, modal, group, group_mass


def validated_forecast(raw, generated, target_date=None):
    target_date = target_date or generated.date()
    if not isinstance(raw, dict) or FORBIDDEN.intersection(raw):
        raise ValueError("Results/postmatch fields are NOT allowed in the prematch feed")
    if raw.get("model") != MODEL:
        raise ValueError("Source must identify the prospective Hybrid V3 engine")
    ident = raw.get("id")
    home, away = raw.get("home"), raw.get("away")
    league = raw.get("league", "")
    if (not isinstance(ident, str) or not (1 <= len(ident) <= 150)
            or not isinstance(home, str) or not home.strip() or len(home) > 120
            or not isinstance(away, str) or not away.strip() or len(away) > 120
            or not isinstance(league, str) or len(league) > 140):
        raise ValueError("Invalid fixture identity or team labels")
    kickoff_raw = raw.get("kickoff_utc")
    kickoff = parse_utc(kickoff_raw)
    if kickoff.date() != target_date or kickoff <= generated:
        return None  # Started/earlier fixtures never appear as new picks.
    day_before(raw.get("model_fit_latest_day"), generated)
    day_before(raw.get("history_latest_day"), generated)
    score, prob, group, group_mass = grid_summary(raw.get("grid"))
    if "predicted_score" in raw and raw["predicted_score"] != score:
        raise ValueError("Original model modal score does not match the raw grid")
    if score in EXCLUDED_MODAL_SCORES:
        return None  # Discard this match from both Top5, without substituting a score.
    base = {"id": ident, "league": league, "home": home, "away": away,
            "kickoff_utc": kickoff_raw, "score": score}
    simple = dict(base, probability=round(prob, 8))
    # A three-score group containing 1:1 must not sneak the excluded score
    # back into the public feed, even when its original modal is 0:0 or 2:2.
    grouped = (dict(base, probability=round(group_mass, 8),
                    group=group, group_scores=list(GROUPS[group]))
               if group and not EXCLUDED_MODAL_SCORES.intersection(GROUPS[group]) else None)
    return simple, grouped, prob, group_mass


def build_feed(source, *, generated_at, target_date=None):
    when = parse_utc(generated_at)
    target_date = target_date or when.date()
    if target_date not in (when.date(), when.date()+timedelta(days=1)):
        raise ValueError("Only the current and next UTC date may be forecast prospectively")
    if not isinstance(source, dict) or source.get("model") != MODEL:
        raise ValueError("Input must declare exact Hybrid V3 model")
    # Prevent rebranding a settled or synthetic archive as a prospective feed.
    if source.get("origin") != "prospective_prematch" or FORBIDDEN.intersection(source):
        raise ValueError("Only an audited prospective pre-result forecast source is allowed")
    if source.get("generated_at") != generated_at:
        raise ValueError("Prospective source generation timestamp differs from publication timestamp")
    fixtures = source.get("fixtures")
    if not isinstance(fixtures, list):
        raise ValueError("A real list of prospective fixtures is required")
    ids = set()
    # PHASE 1 — Check every prospective fixture, then filter ALL 1:1 modal
    # matches before computing any Top5 ranking. Never take Top5 first and
    # remove 1:1 afterwards (that would leave valid replacements unranked).
    eligible = []
    for raw in fixtures:
        if not isinstance(raw, dict):
            raise ValueError("Invalid fixture record")
        if raw.get("id") in ids:
            raise ValueError("Duplicate fixture id")
        ids.add(raw.get("id"))
        row = validated_forecast(raw, when, target_date=target_date)
        if row is not None:
            eligible.append(row)

    # PHASE 2 — Independently rank all remaining eligible matches for A and B.
    # Drawing candidates from the full filtered pool keeps both lists filled
    # up to five when at least five eligible choices actually exist.
    simple_candidates = [(simple, score_prob)
                         for simple, grouped, score_prob, group_prob in eligible]
    group_candidates = [(grouped, group_prob, score_prob)
                        for simple, grouped, score_prob, group_prob in eligible
                        if grouped is not None]
    top_a = sorted(simple_candidates, key=lambda p: (-p[1], p[0]["id"]))[:5]
    top_b = sorted(group_candidates, key=lambda p: (-p[1], -p[2], p[0]["id"]))[:5]
    return {
        "schema_version": SCHEMA, "model": MODEL,
        "status": "published" if top_a or top_b else "unavailable",
        "date": target_date.isoformat(), "generated_at": generated_at,
        "origin": "prospective_prematch",
        "selection_simple": "A_MODAL",
        "selection_grouped": "B_GROUP_MASS",
        "group_definition": "research_only_three_score_proxy_not_verified_bookmaker_market",
        "simple": [item[0] for item in top_a],
        "grouped": [item[0] for item in top_b],
    }


def main():
    parser = argparse.ArgumentParser(description="Publish real prospective V3 Top5 scores, fail closed")
    parser.add_argument("--input", required=True, type=Path,
                        help="Authenticated/prematch source file generated by independent V3 forecaster")
    parser.add_argument("--out", default="scores-exacts.json", type=Path)
    parser.add_argument("--asof", help="Explicit UTC ISO timestamp, useful for verified research tests")
    args = parser.parse_args()
    src = json.loads(args.input.read_text(encoding="utf8"))
    now = datetime.now(timezone.utc)
    generated_at = args.asof or src.get("generated_at")
    timestamp = parse_utc(generated_at)
    if not args.asof and (timestamp > now or timestamp.date() != now.date()):
        raise ValueError("Only forecasts generated today in UTC may be published")
    result = build_feed(src, generated_at=generated_at)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(args.out.suffix + ".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    tmp.replace(args.out)
    print("MRX_EXACT_TOP5_PUBLICATION", json.dumps({
        "day":result["date"],"status":result["status"],
        "simple":len(result["simple"]),"grouped":len(result["grouped"]),
        "fake_fixtures":False,"odds_or_roi":False
    }), flush=True)


if __name__ == "__main__":
    main()
