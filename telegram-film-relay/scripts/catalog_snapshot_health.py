"""Analyse conservatrice des inventaires enregistrés GitHub, sans accès Telegram.

Les numéros observés dans les catalogues NE PROUVENT PAS que la publication
est autorisée ou possible : cette analyse n'inspecte pas les fichiers médias.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def analyze(catalogue: dict, *, category: str, maximum: int = 12) -> dict:
    observed = catalogue.get("source_observed", {}) or {}
    totals = {"titles_observed": 0, "titles_over_cap": 0,
              "titles_within_cap": 0, "titles_with_numbering_gaps": 0,
              "titles_missing_episode_one": 0, "seasons_observed": 0,
              "historical_episode_numbers": 0}
    for seasons in observed.values():
        totals["titles_observed"] += 1
        all_episodes = set()
        has_gap = False
        missing_one = False
        for season, numbers in seasons.items():
            try:
                season_id = int(season)
            except (ValueError, TypeError):
                continue
            episodes = sorted({int(number) for number in numbers
                               if str(number).isdigit() and int(number) > 0})
            if not episodes:
                continue
            totals["seasons_observed"] += 1
            all_episodes.update((season_id, number) for number in episodes)
            has_gap = has_gap or len(episodes) < episodes[-1] - episodes[0] + 1
            missing_one = missing_one or episodes[0] != 1
        totals["historical_episode_numbers"] += len(all_episodes)
        over = len(all_episodes) > maximum or any(number > maximum for _, number in all_episodes)
        totals["titles_over_cap" if over else "titles_within_cap"] += 1
        totals["titles_with_numbering_gaps"] += int(has_gap)
        totals["titles_missing_episode_one"] += int(missing_one)
    stored = catalogue.get("audit", {}) or {}
    return {
        "category": category,
        "snapshot_checked_at": stored.get("checked_at"),
        "analysis_generated_at": datetime.now(timezone.utc).isoformat(),
        "episode_cap": maximum,
        **totals,
        "last_scan_episode_candidates": stored.get("scanned_episode_candidates"),
        "not_yet_indexed_total": stored.get("not_yet_indexed_total"),
        "unnumbered_videos_skipped": stored.get("unnumbered_videos_skipped"),
        "source_scan_complete_recorded": stored.get("source_scan_complete"),
        "telegram_real_time_verified": False,
        "publication_rights_verified": False,
        "selection_eligibility_verified": False,
        "method": ("Historical source_observed episode numbers only. Missing artwork, "
                   "availability and declared completion require a live source audit. "
                   "Gap detection is suggestive, not proof of missing uploads."),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--state-dir", type=Path, default=Path("telegram-film-relay/state"))
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    reports = {}
    for category in ("series", "anime"):
        path = args.state_dir / f"{category}_catalog.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        reports[category] = analyze(data, category=category)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    for category, report in reports.items():
        print(f"{category}: observed={report['titles_observed']} "
              f"over_cap={report['titles_over_cap']} "
              f"gap_titles={report['titles_with_numbering_gaps']}")
    print("Historical catalog only — no Telegram messages sent or verified.")


if __name__ == "__main__":
    main()
