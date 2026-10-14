#!/usr/bin/env python3
"""Suggest team-name aliases from independent historical scores.

Candidate proposals are NEVER automatically merged into an archive or
approved for use in model features. Require independent review.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from difflib import SequenceMatcher
import json
from pathlib import Path

from scripts.football_history_shadow import canonical_key, canonical_team, normalized, valid


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, canonical_team(a), canonical_team(b)).ratio()


def propose(records: list[dict]) -> dict:
    by_group = defaultdict(lambda: {"openfootball": [], "football_data": []})
    for row in records:
        if not valid(row):
            continue
        key = (row["season"], normalized(row["league"]), row["match_date"], row["home_score"], row["away_score"])
        by_group[key][row["source"]].append(row)
    matches = []
    for key, group in by_group.items():
        open_rows, csv_rows = group["openfootball"], group["football_data"]
        for row in open_rows:
            possible = []
            for other in csv_rows:
                if canonical_key(row) == canonical_key(other):
                    continue
                home = similarity(row["home_team"], other["home_team"])
                away = similarity(row["away_team"], other["away_team"])
                if home >= 0.47 and away >= 0.47:
                    possible.append((round((home + away) / 2, 4), other))
            possible.sort(key=lambda p: p[0], reverse=True)
            if not possible or possible[0][0] < 0.58:
                continue
            best, other = possible[0]
            if len(possible) > 1 and (best - possible[1][0]) < 0.08:
                continue  # multiple plausible teams; suppress speculation
            matches.append({
                "season": key[0], "league": row["league"],
                "date": row["match_date"], "score": [row["home_score"], row["away_score"]],
                "openfootball": [row["home_team"], row["away_team"]],
                "football_data": [other["home_team"], other["away_team"]],
                "similarity": best, "approved": False,
                "reason": "Same date/score and plausible two-team names; may still be coincidental",
            })
    # Group recurring name mappings so each pair can be reviewed once.
    grouped = {}
    for m in matches:
        key = (m["league"], *m["openfootball"], *m["football_data"])
        if key not in grouped:
            grouped[key] = {
                "league": m["league"], "openfootball": m["openfootball"],
                "football_data": m["football_data"], "examples": [],
                "support_count": 0, "approved": False,
            }
        grouped[key]["support_count"] += 1
        if len(grouped[key]["examples"]) < 3:
            grouped[key]["examples"].append({"date": m["date"], "score": m["score"], "similarity": m["similarity"]})
    proposals = sorted(grouped.values(), key=lambda m: (-m["support_count"], m["league"], m["openfootball"], m["football_data"]))
    return {
        "total_candidate_fixtures": len(matches),
        "distinct_alias_proposals": len(proposals),
        "automatic_aliases_applied": 0,
        "proposals": proposals,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    rows = []
    for line in Path(a.input).read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    report = propose(rows)
    dest = Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "proposals"}))
    for item in report["proposals"][:10]:
        print("ALIAS_REVIEW_REQUIRED", item["support_count"], item["openfootball"], "->", item["football_data"])


if __name__ == "__main__":
    main()
