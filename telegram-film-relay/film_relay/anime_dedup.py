"""Lossless, conservative identity-aware deduplication of Anime source candidates.

Never decide an episode's identity from a Telegram source message ID alone:
distinct sources frequently publish the same SxxExx. Only candidates with
explicit compatible series titles and episode numbers are coalesced.
Historical receipts are not overwritten; ambiguous media remain observable.
"""
from __future__ import annotations

from collections import defaultdict

from .anime_identity import resolve_series_key
from .episode_identity import canonical_title, series_title


def canonical_series_key(catalogue: dict, row: dict) -> str:
    """Resolve aliases first, then safe historical series-title identities."""
    series = catalogue.get("series", {}) or {}
    key = resolve_series_key(catalogue, str(row["series"]))
    if key in series:
        return key
    title = canonical_title(series_title(row.get("title", "")))
    if not title:
        return key
    candidates = [
        old_key for old_key, entry in series.items()
        if canonical_title(series_title(entry.get("title", ""))) == title
    ]
    return candidates[0] if len(candidates) == 1 else key


def document_id(row: dict):
    video = row.get("video")
    value = getattr(getattr(video, "document", None), "id", None)
    return str(value) if value else None


def deduplicate_anime_candidates(rows: list, catalogue: dict):
    """Return one selected source candidate per anime/season/episode.

    Series variants are resolved conservatively using the persisted aliases.
    Prefer an original source already attached to a private receipt; otherwise
    prefer a valid poster and then the newest source. Different document IDs
    are reported, not silently treated as proof of different episodes.
    """
    existing = catalogue.get("series", {}) or {}
    groups = defaultdict(list)
    for row in rows:
        key = canonical_series_key(catalogue, row)
        groups[(key, int(row["season"]), int(row["episode"]))].append(row)
    # An identical Telegram document attached to different numbered episodes
    # is stronger evidence of bad source labeling than the filename/title.
    # Never choose one of those records for a NEW publication automatically.
    media_identities = defaultdict(set)
    for identity, variants in groups.items():
        for candidate in variants:
            file_id = document_id(candidate)
            if file_id:
                media_identities[file_id].add(identity)
    unsafe_cross_labels = {
        identity for identities in media_identities.values()
        if len(identities) > 1 for identity in identities
    }
    chosen = []
    report = {"candidate_rows": len(rows), "unique_episodes": len(groups),
              "source_duplicates": 0, "media_variants": 0,
              "cross_episode_media_conflicts": 0, "conflicts": []}
    for (key, season, episode), variants in sorted(groups.items()):
        if (key, season, episode) in unsafe_cross_labels:
            known_entry = existing.get(key, {})
            has_receipt = str(episode) in (
                known_entry.get("episodes", {}).get(str(season), {}))
            if not has_receipt:
                report["cross_episode_media_conflicts"] += 1
                report["conflicts"].append({
                    "series": key, "season": season, "episode": episode,
                    "reason": "identical_document_used_for_distinct_episodes",
                    "source_keys": sorted(str(row["source_key"]) for row in variants),
                })
                continue
        entry = existing.get(key, {})
        known = entry.get("source_items", {}) or {}
        # Never discard source evidence: keep alternate source keys for audit.
        videos = {document_id(r) for r in variants if document_id(r)}
        report["source_duplicates"] += max(0, len(variants) - 1)
        if len(videos) > 1:
            report["media_variants"] += 1
            report["conflicts"].append({
                "series": key, "season": season, "episode": episode,
                "reason": "different_telegram_media_for_same_episode",
                "source_keys": sorted(str(r["source_key"]) for r in variants),
            })
            if not any(str(row["source_key"]) in known for row in variants):
                # Ambiguous re-encodes or conflicting episode labels cannot
                # safely be resolved by recency alone.
                continue
        best = max(
            variants,
            key=lambda row: (
                str(row["source_key"]) in known,
                bool(getattr(row.get("poster"), "photo", None)),
                float(row.get("timestamp") or 0),
                str(row["source_key"]),
            ),
        )
        normalized = dict(best)
        normalized["series"] = key
        normalized["alternative_source_keys"] = sorted(
            str(row["source_key"]) for row in variants
            if str(row["source_key"]) != str(best["source_key"])
        )
        chosen.append(normalized)
    return chosen, report



def reconcile_known_source_duplicates(rows: list, catalogue: dict):
    """Receipt an alternate source ONLY if the same numbered private episode exists.

    This prevents archive cursors from being blocked indefinitely by source
    reposts. Conflicting historical source receipts are never overwritten.
    """
    newly_linked, collisions = 0, []
    series = catalogue.get("series", {}) or {}
    for row in rows:
        key = canonical_series_key(catalogue, row)
        entry = series.get(key)
        if not entry:
            continue
        private = entry.get("episodes", {}).get(
            str(row["season"]), {}).get(str(row["episode"]))
        if not private or not private.get("message_id"):
            continue
        actual_id = int(private["message_id"])
        receipts = entry.setdefault("source_items", {})
        for source_key in [row["source_key"], *row.get("alternative_source_keys", [])]:
            prior = receipts.get(str(source_key))
            if prior is not None and int(prior) != actual_id:
                collisions.append(str(source_key))
                continue
            if prior is None:
                receipts[str(source_key)] = actual_id
                newly_linked += 1
    return {"new_source_receipts": newly_linked, "conflicting_source_receipts": collisions}


def pending_ongoing_episodes(groups: dict, catalogue: dict, *, maximum: int = 4):
    """Select at most one new contiguous episode per distinct ongoing anime.

    This is a pure, dry-run selector. It does not replace full-season batches.
    If an earlier episode is unpublished, a later episode is held back.
    """
    from .anime_policy import progressive_anime_seasons

    if not 1 <= maximum <= 4:
        raise ValueError("Quota des nouveautés : de 1 à 4 animés distincts.")
    if catalogue.get("active_batch"):
        return []
    batches = progressive_anime_seasons(groups, catalogue, maximum=25)
    candidates = []
    for key, rows in batches:
        stored = catalogue.get("series", {}).get(key, {})
        existing = stored.get("episodes", {})
        receipts = stored.get("public_episode_posts", {})
        for row in rows:
            ep = int(row["episode"])
            season = int(row["season"])
            in_private = str(ep) in existing.get(str(season), {})
            in_public = f"S{season:02d}E{ep:02d}" in receipts
            if not in_private or not in_public:
                candidates.append((key, row))
                break
    # A deterministic, fair order: oldest available new episode first.
    candidates.sort(key=lambda item: (
        float(item[1].get("timestamp") or 0), item[0],
        int(item[1]["season"]), int(item[1]["episode"])))
    chosen = []
    used = set()
    for key, row in candidates:
        if key in used:
            continue
        chosen.append((key, [row]))
        used.add(key)
        if len(chosen) >= maximum:
            break
    return chosen
