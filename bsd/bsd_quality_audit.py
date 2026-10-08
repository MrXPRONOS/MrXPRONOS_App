#!/usr/bin/env python3
"""Audit sans réseau de l'historique BSD déchiffré par bsd_archive.py restore.

Aucune donnée brute n'est affichée, écrite dans les artifacts ou publiée.
Le but est de mesurer la couverture réelle 2024-2026 et les H2H exploitables.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

from bsd_archive import MATCHES_FILE, STATE_FILE, _read_json
from bsd_h2h import _team_id, _valid_score, _utc, local_h2h


def audit(matches: List[Dict[str, Any]], state: Dict[str, Any], samples: int = 12) -> Dict[str, Any]:
    if not isinstance(matches, list) or not isinstance(state, dict):
        raise ValueError("Archive BSD incorrecte")
    if not (0 <= samples <= 50):
        raise ValueError("Nombre d'exemples hors limites")
    years = Counter()
    issues = Counter()
    per_team = Counter()
    pairs = Counter()
    seen_ids = set()
    valid_events = []
    dates = []

    for match in matches:
        if not isinstance(match, dict):
            issues["invalid_object"] += 1
            continue
        mid = match.get("id")
        if mid is None:
            issues["missing_event_id"] += 1
            continue
        if str(mid) in seen_ids:
            issues["duplicate_id"] += 1
            continue
        seen_ids.add(str(mid))
        if str(match.get("status", "")).lower() != "finished":
            issues["not_finished"] += 1
            continue
        try:
            dt = _utc(str(match.get("event_date") or ""))
        except (ValueError, TypeError):
            issues["invalid_date"] += 1
            continue
        year = dt.year
        years[str(year)] += 1
        dates.append(dt)
        if not 2024 <= year <= 2026:
            issues["out_of_target_dates"] += 1
        hid, aid = _team_id(match, "home"), _team_id(match, "away")
        if hid is None or aid is None or hid == aid or min(hid, aid) <= 0:
            issues["invalid_team_ids"] += 1
            continue
        hs = _valid_score(match.get("home_score"))
        aws = _valid_score(match.get("away_score"))
        if hs is None or aws is None:
            issues["invalid_final_score"] += 1
            continue
        per_team[hid] += 1
        per_team[aid] += 1
        pairs[tuple(sorted((hid, aid)))] += 1
        valid_events.append(match)

    # Échantillon reproductible : choisir les paires les plus fréquentes pour
    # vérifier que le calcul H2H historique ignore le match en cours et le futur.
    representative = []
    pair_events = {}
    for event in valid_events:
        pair = tuple(sorted((_team_id(event, "home"), _team_id(event, "away"))))
        pair_events.setdefault(pair, []).append(event)
    for pair, items in sorted(pair_events.items(), key=lambda pair_item: (-len(pair_item[1]), pair_item[0])):
        if len(representative) >= samples:
            break
        if len(items) < 2:
            continue
        last = max(items, key=lambda e: str(e.get("event_date") or ""))
        report = local_h2h(
            items, _team_id(last, "home"), _team_id(last, "away"), str(last["event_date"])
        )
        if report["total_matches"] < 1:
            continue
        representative.append({
            "history_for_sample": len(items),
            "prior_h2h_in_3_years": report["total_matches"],
            "local_only": report["source"] == "local",
        })
    planned = state.get("season_tasks", [])
    completed = state.get("completed_seasons", [])
    return {
        "provider": "BSD",
        "stored_matches": len(matches),
        "valid_events_for_analysis": len(valid_events),
        "counts_by_actual_match_year": dict(sorted(years.items())),
        "earliest_event_utc": min(dates).date().isoformat() if dates else None,
        "latest_event_utc": max(dates).date().isoformat() if dates else None,
        "issues": dict(sorted(issues.items())),
        "distinct_teams": len(per_team),
        "teams_with_at_least_5_matches": sum(n >= 5 for n in per_team.values()),
        "pairs_with_at_least_2_meetings": sum(n >= 2 for n in pairs.values()),
        "pairs_with_at_least_3_meetings": sum(n >= 3 for n in pairs.values()),
        "h2h_samples": representative,
        "seasons_done": len(completed) if isinstance(completed, list) else None,
        "seasons_planned": len(planned) if isinstance(planned, list) else None,
        "catalog_complete": state.get("catalog_complete"),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--samples", type=int, default=12)
    args = p.parse_args()
    matches = _read_json(MATCHES_FILE, None)
    state = _read_json(STATE_FILE, None)
    result = audit(matches, state, samples=args.samples)
    print("BSD_QUALITY_AUDIT:", json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result["stored_matches"] == 0:
        print("ÉCHEC : historique vide.")
        return 2
    if result["valid_events_for_analysis"] == 0:
        print("ÉCHEC : aucun match exploitable.")
        return 3
    if result["issues"].get("duplicate_id", 0) or result["issues"].get("invalid_object", 0):
        print("ÉCHEC : doublons ou objets invalides.")
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
