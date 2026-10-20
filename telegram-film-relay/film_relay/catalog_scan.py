"""Bounded, resumable source-history inspection and episode-number diagnostics.

Only explicit episode numbers are eligible. No episode is ever guessed from a
gap, and scanning alone never publishes anything.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from .desir_matching import is_supported_video
from .matching import filename_of

LOG = logging.getLogger("cinex_catalog_scan")


def _page_size() -> int:
    try:
        return min(300, max(40, int(os.getenv("CINEX_CATALOG_PAGE_SIZE", "160"))))
    except ValueError:
        return 160


def _oldest(messages):
    return min((int(m.id) for m in messages), default=None)


async def read_source_window(client, source, catalogue: dict, source_id: int):
    """Always inspect recent posts plus ONE older history page per execution.

    Cursor is returned as a pending plan and must NOT be committed until all
    numbered episodes of the archive page have been durably receipted.
    A short older lookbehind preserves a poster/season header at page edges.
    """
    size = _page_size()
    source_key = str(source_id)
    scan = (catalogue.get("scans") or {}).get(source_key, {})
    recent = [m async for m in client.iter_messages(source, limit=size)]
    recent_ids = {int(m.id) for m in recent}
    if not recent:
        return [], {"source_id": source_key, "archive_ids": set(),
                    "next_cursor": None, "complete": True, "count": 0, "allowed_ids": set()}

    rescan = os.getenv("CINEX_CATALOG_RESCAN", "").lower() in ("1", "true", "yes")
    if scan.get("complete") and not rescan:
        return recent, None
    cursor = _oldest(recent) if not scan.get("cursor") or rescan else int(scan["cursor"])
    archive = [m async for m in client.iter_messages(source, limit=size, max_id=cursor)]
    archive_ids = {int(m.id) for m in archive}
    if not archive:
        return recent, {"source_id": source_key, "archive_ids": set(),
                        "next_cursor": cursor, "complete": True, "count": 0, "allowed_ids": recent_ids}

    # Older context precedes the archived page, preserving its earliest poster
    # and season label when an episode happens to fall on the page boundary.
    lookbehind = [m async for m in client.iter_messages(
        source, limit=40, max_id=_oldest(archive))]
    combined = {int(m.id): m for m in (*recent, *archive, *lookbehind)}
    ordered = sorted(combined.values(), key=lambda msg: int(msg.id))
    plan = {"source_id": source_key, "archive_ids": archive_ids,
            "allowed_ids": recent_ids | archive_ids,
            "next_cursor": _oldest(archive), "complete": len(archive) < size,
            "count": len(archive), "recent_count": len(recent_ids)}
    LOG.info("scan source: récents=%s archives=%s contexte=%s fin=%s",
             len(recent_ids), len(archive), len(lookbehind), plan["complete"])
    return ordered, plan


def source_window_ids(messages, plan):
    """Return ids eligible for indexing (recent + archived; exclude context)."""
    if plan is None:
        return {int(m.id) for m in messages}
    # The plan includes only recent + archived IDs, not the lookbehind.
    return set(plan["allowed_ids"])


def finalize_scan(catalogue: dict, plans: list, observed: list) -> dict:
    """Commit a page only after EVERY numbered item in that archive page is saved.

    A 6-episode publication cap therefore cannot lose the rest of a page.
    """
    scans = catalogue.setdefault("scans", {})
    receipted = set()
    for entry in catalogue.get("series", {}).values():
        receipted.update(entry.get("source_items", {}))
    done, waiting = 0, 0
    for plan in plans:
        if plan is None:
            continue
        eligible = {row["source_key"] for row in observed
                    if str(row["source_key"]).rsplit(":", 1)[0] == plan["source_id"]
                    and int(row["video"].id) in plan["archive_ids"]}
        outstanding = eligible - receipted
        if outstanding:
            waiting += len(outstanding)
            LOG.info("Historique source : page conservée, %s épisodes restent à publier",
                     len(outstanding))
            continue
        previous = scans.get(plan["source_id"], {})
        scans[plan["source_id"]] = {
            "cursor": plan["next_cursor"],
            "complete": bool(plan["complete"]),
            "pages": int(previous.get("pages", 0)) + (1 if plan["count"] else 0),
            "last_checked": datetime.now(timezone.utc).isoformat(),
        }
        done += 1
    return {"pages_saved": done, "episodes_waiting": waiting,
            "history_complete_sources": sum(1 for s in scans.values() if s.get("complete"))}


def episode_audit(catalogue: dict, observed: list, *, category: str,
                  ignored_unnumbered: int = 0) -> dict:
    """Persist source inventory and report gaps separately from missing uploads.

    Source gaps are suspects until history scanning is complete; no episode
    number is synthesized and no missing file is automatically requested.
    """
    import re
    import unicodedata

    def normalize_title(title):
        name = re.sub(r"(?i)^@[a-z0-9_]{5,32}\s+(?:vf|fv)?\s*", "", str(title))
        name = re.sub(r"(?i)\b(?:s\d{1,2}|saison\s*\d+|mp4|mkv|vf|fv)\b", " ", name)
        name = unicodedata.normalize("NFKD", name.lower()).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "-", name).strip("-")[:55]

    series_catalogue = catalogue.get("series", {})
    alias = {normalize_title(entry.get("title", "")): key
             for key, entry in series_catalogue.items() if entry.get("title")}
    source_inventory = catalogue.setdefault("source_observed", {})
    for row in observed:
        key = row["series"] if row["series"] in series_catalogue else alias.get(row["series"], row["series"])
        season, episode = str(row["season"]), str(row["episode"])
        refs = source_inventory.setdefault(key, {}).setdefault(season, {}).setdefault(episode, [])
        if row["source_key"] not in refs:
            refs.append(row["source_key"])

    indexed = {}
    numbering_gaps = []
    for key, entry in series_catalogue.items():
        for season, episodes in entry.get("episodes", {}).items():
            nums = sorted({int(n) for n in episodes if str(n).isdigit()})
            if not nums:
                continue
            indexed[(key, str(season))] = set(nums)
            gaps = sorted(set(range(nums[0], nums[-1] + 1)) - set(nums))
            if gaps:
                numbering_gaps.append({
                    "series": key, "season": str(season),
                    "missing_between_known": gaps[:40], "truncated": len(gaps) > 40,
                })

    source_gaps = []
    not_indexed = []
    for key, seasons in source_inventory.items():
        for season, numbers in seasons.items():
            nums = sorted(int(n) for n in numbers if str(n).isdigit())
            if not nums:
                continue
            gaps = sorted(set(range(nums[0], nums[-1] + 1)) - set(nums))
            if gaps:
                source_gaps.append({
                    "series": key, "season": str(season),
                    "not_observed_between_known": gaps[:40], "truncated": len(gaps) > 40,
                })
            for number in nums:
                if number not in indexed.get((key, str(season)), set()):
                    not_indexed.append({
                        "series": key, "season": str(season), "episode": number,
                        "source_instances": len(numbers[str(number)]),
                    })

    scans = catalogue.get("scans", {})
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "scanned_episode_candidates": len(observed),
        "source_episode_numbers_observed": sum(
            len(numbers) for seasons in source_inventory.values() for numbers in seasons.values()),
        "not_yet_indexed": not_indexed[:100],
        "not_yet_indexed_total": len(not_indexed),
        "numbering_gaps": numbering_gaps[:100],
        "numbering_gap_seasons": len(numbering_gaps),
        "source_numbering_gaps": source_gaps[:100],
        "source_numbering_gap_seasons": len(source_gaps),
        "unnumbered_videos_skipped": ignored_unnumbered,
        "source_scan_complete": bool(scans) and all(s.get("complete") for s in scans.values()),
        "note": "Les trous de numérotation sont des indices, pas la preuve que la source a omis un épisode.",
    }
    catalogue["audit"] = report
    if source_gaps or numbering_gaps:
        LOG.warning("%s: sources avec trous=%s, index avec trous=%s, couverture historique complète=%s",
                    category, len(source_gaps), len(numbering_gaps), report["source_scan_complete"])
    LOG.info("%s: épisodes sources uniques=%s, trouvés sans index=%s, vidéos non numérotées=%s",
             category, report["source_episode_numbers_observed"],
             len(not_indexed), ignored_unnumbered)
    return report
