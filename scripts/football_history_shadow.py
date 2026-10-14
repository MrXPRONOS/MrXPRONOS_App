#!/usr/bin/env python3
"""Canonical, auditable historical-data staging for Mr XPRONOS.

This tool NEVER modifies the private BSD archive or public data.json. It builds
a separate, deterministic historical index, refusing fuzzy merges and score conflicts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import re
import unicodedata

SOURCES = {"openfootball", "football_data"}
FIELDS = ("match_date", "league", "home_team", "away_team")


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def canonical_key(row: dict) -> tuple:
    return tuple(normalized(str(row[key])) for key in FIELDS)


def valid(row: object) -> bool:
    if not isinstance(row, dict) or row.get("source") not in SOURCES:
        return False
    if not isinstance(row.get("source_id"), str) or len(row["source_id"]) != 64:
        return False
    try:
        date.fromisoformat(row["match_date"])
        for field in ("league", "home_team", "away_team"):
            if not isinstance(row[field], str) or not normalized(row[field]):
                return False
        if normalized(row["home_team"]) == normalized(row["away_team"]):
            return False
        return all(type(row.get(field)) is int and 0 <= row[field] <= 30 for field in ("home_score", "away_score"))
    except (KeyError, ValueError, TypeError):
        return False


def build(rows: list) -> tuple[list[dict], dict]:
    unique: dict[tuple, dict] = {}
    conflicts = []
    source_counts = Counter()
    invalid = 0
    for row in rows:
        if not valid(row):
            invalid += 1
            continue
        source_counts[row["source"]] += 1
        key = canonical_key(row)
        if key not in unique:
            unique[key] = {
                "date": row["match_date"],
                "competition": row["league"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "home_score": row["home_score"],
                "away_score": row["away_score"],
                "providers": [{"source": row["source"], "id": row["source_id"]}],
                "verified_by_sources": 1,
                "status": "confirmed_single_source",
                "time_precision": "day",
                "for_training": False,
            }
            continue
        current = unique[key]
        if current["home_score"] != row["home_score"] or current["away_score"] != row["away_score"]:
            current["status"] = "source_conflict"
            current["for_training"] = False
            conflicts.append({"key": list(key), "existing": [current["home_score"], current["away_score"]], "source": row["source"], "incoming": [row["home_score"], row["away_score"]]})
        if not any(p["source"] == row["source"] for p in current["providers"]):
            current["providers"].append({"source": row["source"], "id": row["source_id"]})
        current["verified_by_sources"] = len(current["providers"])
    for row in unique.values():
        if row["status"] != "source_conflict" and row["verified_by_sources"] >= 2:
            row["status"] = "multi_source_agreement"
        # Shadow archive is not automatically admitted to production training.
        row["for_training"] = False
        row["providers"].sort(key=lambda p: (p["source"], p["id"]))
    result = sorted(unique.values(), key=lambda r: (r["date"], normalized(r["competition"]), normalized(r["home_team"]), normalized(r["away_team"])))
    report = {
        "input_rows": len(rows), "invalid_rows": invalid,
        "unique_fixtures": len(result), "provider_rows": dict(sorted(source_counts.items())),
        "multi_source_agreement": sum(r["status"] == "multi_source_agreement" for r in result),
        "conflicted_fixtures": sum(r["status"] == "source_conflict" for r in result),
        "conflicts": conflicts[:100],
        "training_enabled": False, "publication_enabled": False,
        "warning": "Exact normalized-name matches are provisional: verify stable team and competition IDs before use in BSD V2.",
    }
    return result, report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--report", required=True)
    args = p.parse_args()
    rows = []
    with open(args.input, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    rows.append(None)
    records, report = build(rows)
    for name, payload in ((args.output, records), (args.report, report)):
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "conflicts"}, ensure_ascii=False))
    if not records:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
