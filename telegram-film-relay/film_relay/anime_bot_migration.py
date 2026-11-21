"""Non-destructive import of legacy CinéX Anime receipts to private Bot API state.

This code never sends Telegram messages or overwrites existing Bot V2
receipts. Historic indices were often authored by a personal session and
cannot safely be edited by a bot; preserve their IDs as READ-ONLY history.
"""
from __future__ import annotations

from copy import deepcopy

from .anime_identity import consolidate_catalog, identity
from .episode_identity import canonical_title


def migrate_legacy_catalogue(state: dict, source: dict):
    original = deepcopy(state)
    target = deepcopy(state)
    stored = target.setdefault("series", {})
    canonical, report = consolidate_catalog(source)
    result = {"imported_series": 0, "imported_private_episodes": 0,
              "imported_public_pairs": 0, "legacy_unverified_episodes": 0,
              "collisions": [], "requires_review": []}
    if canonical.get("active_batch"):
        raise RuntimeError(
            "Legacy Anime has unfinished active batch: migration stopped.")
    unsafe = set()
    for entry in report["skipped_collisions"]:
        unsafe.update(entry.get("keys", []))
        result["requires_review"].append("legacy_identity_collision")
    for old_key, entry in canonical.get("series", {}).items():
        if old_key in unsafe:
            continue
        new_key = identity(old_key, entry)
        if not new_key:
            result["requires_review"].append("unknown_legacy_title")
            continue
        if new_key in stored and stored[new_key].get("episodes"):
            # Never overwrite an existing Bot V2 series on import.
            result["collisions"].append(new_key)
            continue
        mapped = {
            "title": str(entry.get("title") or old_key),
            "episodes": {},
            "public_episode_posts": {},
            "season_public_ids": deepcopy(
                entry.get("season_public_ids", {})),
            "legacy_public_id": entry.get("public_id"),
            "legacy_public_ids": deepcopy(entry.get("legacy_public_ids", [])),
            "legacy_main_index_id": entry.get("main_index_id"),
            "legacy_season_index_ids": deepcopy(
                entry.get("season_indices", {})),
            "legacy_unverified_episode_keys": [],
            "season_index_ids": {}, "index_pages": {},
            "migrated_from_legacy": True,
        }
        # An older public card is preserved. It may be bot-authored, but a
        # different bot's edit rights must be verified at integration.
        if entry.get("public_id"):
            mapped["public_id"] = int(entry["public_id"])
        for season, eps in entry.get("episodes", {}).items():
            dest = mapped["episodes"].setdefault(str(season), {})
            for ep, receipt in eps.items():
                private_msg = receipt.get("message_id")
                if not private_msg:
                    result["requires_review"].append("missing_private_receipt")
                    continue
                dest[str(ep)] = {
                    "message_id": int(private_msg),
                    "source_key": "legacy",
                    "file_unique_id": "",
                    "legacy": True,
                }
                result["imported_private_episodes"] += 1
        for marker, pair in entry.get("public_episode_posts", {}).items():
            if not (isinstance(pair, dict) and pair.get("poster")
                    and pair.get("video")):
                result["requires_review"].append("invalid_legacy_pair")
                continue
            mapped["public_episode_posts"][marker] = {
                "poster": int(pair["poster"]), "video": int(pair["video"]),
                "private_video": int(pair.get("private_video") or 0),
                "legacy": True,
            }
            result["imported_public_pairs"] += 1
        for season, eps in mapped["episodes"].items():
            for ep in eps:
                marker = f"S{int(season):02d}E{int(ep):02d}"
                if marker not in mapped["public_episode_posts"]:
                    mapped["legacy_unverified_episode_keys"].append(marker)
                    result["legacy_unverified_episodes"] += 1
        stored[new_key] = mapped
        result["imported_series"] += 1
    if result["collisions"]:
        # No partial migration when an existing V2 series could be overwritten.
        return original, result
    return target, result
