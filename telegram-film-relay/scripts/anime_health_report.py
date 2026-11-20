"""Read-only health summary for CineX Anime catalogue; never touches Telegram."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from film_relay.anime_identity import consolidate_catalog


def summarize(catalogue):
    catalogue, migration = consolidate_catalog(catalogue)
    series = catalogue.get("series", {}) or {}
    counts = Counter()
    for key, entry in series.items():
        counts["titles"] += 1
        episodes = entry.get("episodes", {}) or {}
        for season, rows in episodes.items():
            counts["seasons"] += 1
            counts["private_episodes"] += len(rows)
            if entry.get("season_status", {}).get(str(season)) == "en_cours":
                counts["ongoing_seasons"] += 1
            if entry.get("season_status", {}).get(str(season)) == "complete":
                counts["completed_seasons"] += 1
            receipts = entry.get("public_episode_posts", {}) or {}
            for episode in rows:
                label = f"S{int(season):02d}E{int(episode):02d}"
                if label in receipts:
                    counts["public_episode_pairs"] += 1
        if entry.get("public_id"):
            counts["public_series_cards"] += 1
    audit = catalogue.get("audit", {}) or {}
    return {
        **dict(counts),
        "active_batch": bool(catalogue.get("active_batch")),
        "last_audit": {
            "checked_at": audit.get("checked_at"),
            "not_yet_indexed_total": audit.get("not_yet_indexed_total", 0),
            "unnumbered_videos_skipped": audit.get("unnumbered_videos_skipped", 0),
            "numbering_gap_seasons": audit.get("numbering_gap_seasons", 0),
            "source_scan_complete": audit.get("source_scan_complete", False),
        },
        "historical_groups_merged": len(migration["merged_groups"]),
        "identity_collisions_quarantined": len(migration["skipped_collisions"]),
        "sources_scanned": len(catalogue.get("scans", {}) or {}),
        "advice": "Les totaux d'audit sont historiques; ils ne prouvent pas la disponibilite ou les droits."
    }


def main():
    parser = argparse.ArgumentParser(description="Rapport Anime en lecture seule")
    parser.add_argument("--catalogue", default="state/anime_catalog.json")
    args = parser.parse_args()
    path = Path(args.catalogue)
    if not path.exists():
        raise SystemExit(f"Catalogue introuvable : {path}")
    report = summarize(json.loads(path.read_text(encoding="utf-8")))
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
