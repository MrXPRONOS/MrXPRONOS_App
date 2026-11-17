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


async def read_source_window(client, source, catalogue: dict, source_id: int, *, archive_pages: int = 1):
    """Inspect recent posts and a bounded number of older pages per execution.

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
    complete_before = bool(scan.get("complete")) and not rescan
    if complete_before and archive_pages == 1:
        return recent, None
    # For large anime batches re-read a bounded historic window even when
    # the archival scan previously finished, without moving its stored cursor.
    cursor = (_oldest(recent) if complete_before or not scan.get("cursor") or rescan
              else int(scan["cursor"]))
    archive = []
    complete = False
    # Some 25-episode series contain text announcements between batches.
    # A bounded multi-page window lets us assemble the whole batch without
    # treating those announcements as episode breaks.
    for _ in range(max(1, min(4, int(archive_pages)))):
        page = [m async for m in client.iter_messages(source, limit=size, max_id=cursor)]
        if not page:
            complete = True
            break
        archive.extend(page)
        cursor = _oldest(page)
        if len(page) < size:
            complete = True
            break
    archive_ids = {int(m.id) for m in archive}
    if not archive:
        return recent, {"source_id": source_key, "archive_ids": set(),
                        "next_cursor": cursor, "complete": True, "count": 0, "allowed_ids": recent_ids}

    # Context preceding the oldest page preserves its opening title/season.
    lookbehind = [m async for m in client.iter_messages(
        source, limit=40, max_id=_oldest(archive))]
    combined = {int(m.id): m for m in (*recent, *archive, *lookbehind)}
    ordered = sorted(combined.values(), key=lambda msg: int(msg.id))
    plan = {"source_id": source_key, "archive_ids": archive_ids,
            "allowed_ids": recent_ids | archive_ids,
            "next_cursor": _oldest(archive), "complete": complete,
            "count": len(archive), "recent_count": len(recent_ids)}
    LOG.info("scan source: récents=%s archives=%s contexte=%s fin=%s",
             len(recent_ids), len(archive), len(lookbehind), plan["complete"])
    return ordered, (None if complete_before else plan)


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
                  ignored_unnumbered: int = 0,
                  eligibility_reasons: dict | None = None) -> dict:
    """Audit unique episodes by canonical title; preserve all historic source IDs.

    Existing source_observed keys are NOT renamed or deleted. Historical keys
    such as Death-Parade-EP05 and Death-Parade-480p are unified only for
    reporting, eligibility and the episode coverage check.
    """
    from .short_series import normalized_key

    indexed_series = catalogue.get("series", {})
    source_inventory = catalogue.setdefault("source_observed", {})
    # Append raw references idempotently, never rewrite existing receipts.
    for row in observed:
        name = str(row["series"])
        season, episode = str(int(row["season"])), str(int(row["episode"]))
        entries = source_inventory.setdefault(name, {}).setdefault(
            season, {}).setdefault(episode, [])
        if row["source_key"] not in entries:
            entries.append(row["source_key"])

    source_by_canonical = {}
    for old_key, seasons in source_inventory.items():
        key = normalized_key(old_key) or old_key
        target = source_by_canonical.setdefault(key, {})
        for season, numbers in seasons.items():
            destination = target.setdefault(str(int(season)), {})
            for number, refs in numbers.items():
                group = destination.setdefault(str(int(number)), set())
                group.update(str(ref) for ref in refs)

    indexed = {}
    for old_key, entry in indexed_series.items():
        key = normalized_key(entry.get("title", "")) or normalized_key(old_key) or old_key
        for season, episodes in entry.get("episodes", {}).items():
            position = (key, str(int(season)))
            indexed.setdefault(position, set()).update(
                int(number) for number in episodes if str(number).isdigit()
            )

    numbering_gaps = []
    for (key, season), nums in indexed.items():
        if not nums:
            continue
        missing = sorted(set(range(min(nums), max(nums) + 1)) - nums)
        if missing:
            numbering_gaps.append({
                "series": key, "season": season, "missing_between_known": missing[:40],
                "truncated": len(missing) > 40,
            })

    source_gaps = []
    not_indexed = []
    for key, seasons in source_by_canonical.items():
        for season, numbers in seasons.items():
            nums = sorted(int(n) for n in numbers)
            if not nums:
                continue
            gaps = sorted(set(range(nums[0], nums[-1] + 1)) - set(nums))
            if gaps:
                source_gaps.append({
                    "series": key, "season": season,
                    "not_observed_between_known": gaps[:40],
                    "truncated": len(gaps) > 40,
                })
            for number in nums:
                if number not in indexed.get((key, season), set()):
                    not_indexed.append({
                        "series": key, "season": season, "episode": number,
                        "source_instances": len(numbers[str(number)]),
                    })

    scans = catalogue.get("scans", {})
    reasons = {}
    for reason in (eligibility_reasons or {}).values():
        reasons[reason] = reasons.get(reason, 0) + 1
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "scanned_episode_candidates": len(observed),
        "source_title_variants": len(source_inventory),
        "canonical_titles": len(source_by_canonical),
        "source_title_variants_collapsed": len(source_inventory) - len(source_by_canonical),
        "source_episode_numbers_observed": sum(
            len(numbers) for seasons in source_by_canonical.values()
            for numbers in seasons.values()),
        "not_yet_indexed": not_indexed[:100],
        "not_yet_indexed_total": len(not_indexed),
        "numbering_gaps": numbering_gaps[:100],
        "numbering_gap_seasons": len(numbering_gaps),
        "source_numbering_gaps": source_gaps[:100],
        "source_numbering_gap_seasons": len(source_gaps),
        "unnumbered_videos_skipped": ignored_unnumbered,
        "eligibility_rejections": reasons,
        "source_scan_complete": bool(scans) and all(
            scan.get("complete") for scan in scans.values()),
        "note": "Titres normalisés pour le diagnostic uniquement ; trous et épisodes en attente ne prouvent pas une copie autorisée ou disponible.",
    }
    catalogue["audit"] = report
    if source_gaps or numbering_gaps:
        LOG.warning("%s : source_gaps=%s, index_gaps=%s, historique_complet=%s",
                    category, len(source_gaps), len(numbering_gaps),
                    report["source_scan_complete"])
    LOG.info("%s : variantes titres=%s, séries canoniques=%s, épisodes uniques=%s, non indexés=%s",
             category, len(source_inventory), len(source_by_canonical),
             report["source_episode_numbers_observed"], len(not_indexed))
    return report
