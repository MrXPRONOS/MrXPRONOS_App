"""Generate a privacy-limited, static dashboard snapshot from the Anime catalogue.

Only aggregate counts and cleaned anime titles are exported. Never export
Telegram IDs, source IDs, URLs, tokens, source handles or private links.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Supports the workflow invocation from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from film_relay.anime_identity import consolidate_catalog
from film_relay.episode_identity import series_title


def dashboard_snapshot(catalogue):
    catalogue, migration = consolidate_catalog(catalogue)
    series_rows = []
    total_private = 0
    total_public = 0
    total_gaps = 0
    for key, entry in sorted(catalogue.get("series", {}).items()):
        seasons = []
        receipts = entry.get("public_episode_posts", {}) or {}
        statuses = entry.get("season_status", {}) or {}
        for season, episodes in sorted(
                entry.get("episodes", {}).items(), key=lambda x: int(x[0])):
            numbers = sorted(int(n) for n in episodes if str(n).isdigit())
            if not numbers:
                continue
            posted = sum(
                1 for n in numbers
                if f"S{int(season):02d}E{n:02d}" in receipts
            )
            missing = len(set(range(min(numbers), max(numbers) + 1)) - set(numbers))
            total_private += len(numbers)
            total_public += posted
            total_gaps += missing
            seasons.append({
                "season": int(season),
                "private_episodes": len(numbers),
                "public_episode_pairs": posted,
                "numbering_gaps": missing,
                "last_episode": max(numbers),
                "status": statuses.get(str(season), "non_verifie"),
            })
        title = series_title(str(entry.get("title") or "")) or str(entry.get("title") or "")
        series_rows.append({
            "title": title[:90],
            "private_episodes": sum(s["private_episodes"] for s in seasons),
            "public_episode_pairs": sum(s["public_episode_pairs"] for s in seasons),
            "seasons": seasons,
            "has_public_card": bool(entry.get("public_id")),
            "legacy_cards_to_review": len(entry.get("legacy_public_ids", []) or []),
            "index_repair_pending": bool(entry.get("index_repair_pending")),
        })
    audit = catalogue.get("audit", {}) or {}
    scan_date = str(audit.get("checked_at") or "")
    return {
        "schema_version": 1,
        "audit_checked_at": scan_date,
        "data_note": ("Inventaire et reçus enregistrés, pas une preuve de "
                      "disponibilité des vidéos ni des droits."),
        "stats": {
            "titles": len(series_rows),
            "seasons": sum(len(row["seasons"]) for row in series_rows),
            "private_episodes": total_private,
            "public_episode_pairs": total_public,
            "numbering_gaps": total_gaps,
            "pending_historical_candidates": int(audit.get("not_yet_indexed_total") or 0),
            "unnumbered_skipped": int(audit.get("unnumbered_videos_skipped") or 0),
            "source_scan_complete": bool(audit.get("source_scan_complete")),
            "configured_sources_scanned": len(catalogue.get("scans", {}) or {}),
            "active_batch": bool(catalogue.get("active_batch")),
            "fragmented_series_groups_reconciled": len(migration["merged_groups"])
                + sum(bool(e.get("legacy_public_ids")) for e in
                      catalogue.get("series", {}).values()),
            "ambiguous_series_groups": len(migration["skipped_collisions"]),
        },
        "series": series_rows,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--catalogue", default="state/anime_catalog.json")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    data = json.loads(Path(args.catalogue).read_text(encoding="utf-8"))
    snapshot = dashboard_snapshot(data)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    temp.replace(target)


if __name__ == "__main__":
    main()
