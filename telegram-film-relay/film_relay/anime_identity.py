"""Conservative, lossless consolidation of fragmented Anime series receipts.

This module never calls Telegram, never deletes public posts, and skips any
ambiguous episode/source collision. Original entries remain archived in the
catalogue for audit and manual rollback; live URLs/IDs remain untouched.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy

from .episode_identity import canonical_title, series_title

_RESERVED = {"anime", "serie", "episode", "film", "vf", "vostfr", "mangas"}


def identity(key: str, entry: dict) -> str:
    """Canonical name ONLY when explicit title evidence survives cleaning."""
    raw = str(entry.get("title") or "")
    title = series_title(raw) or series_title(key.replace("-", " "))
    value = canonical_title(title)
    return value if len(value) >= 5 and value not in _RESERVED else ""


def resolve_series_key(catalogue: dict, candidate: str) -> str:
    aliases = catalogue.get("series_aliases") or {}
    seen = set()
    current = str(candidate)
    while current in aliases and current not in seen:
        seen.add(current)
        current = aliases[current]
    return current


def _conflicts(target: dict, incoming: dict) -> list:
    issues = []
    for season, episodes in incoming.get("episodes", {}).items():
        existing = target.get("episodes", {}).get(str(season), {})
        for number, receipt in episodes.items():
            prior = existing.get(str(number))
            if prior is not None and prior != receipt:
                issues.append(f"episode:S{season}E{number}")
    for key in ("source_items", "public_episode_posts", "episode_poster_ids"):
        for item, receipt in incoming.get(key, {}).items():
            prior = target.get(key, {}).get(item)
            if prior is not None and prior != receipt:
                issues.append(f"{key}:{item}")
    return issues


def consolidate_catalog(catalogue: dict):
    """Return (copy, report). Existing Telegram IDs never change.

    The key with the earliest public card wins, retaining its deterministic
    marker, private index and public post. Other published cards are recorded,
    *not deleted*. Collision groups are quarantined as entire groups.
    """
    result = deepcopy(catalogue)
    series = result.setdefault("series", {})
    aliases = result.setdefault("series_aliases", {})
    backups = result.setdefault("legacy_series_records", {})
    groups = defaultdict(list)
    for key, entry in series.items():
        name = identity(key, entry)
        if name:
            groups[name].append(key)
    report = {"merged_groups": [], "skipped_collisions": [],
              "skipped_active": [], "consolidated_entries": 0}
    active_key = str((result.get("active_batch") or {}).get("key") or "")
    for name, keys in sorted(groups.items()):
        if len(keys) < 2:
            continue
        if active_key and (active_key in keys
                           or resolve_series_key(result, active_key) in keys):
            report["skipped_active"].append(name)
            continue
        keys.sort(key=lambda key: (
            int(series[key].get("public_id") or 10**15),
            -sum(len(e) for e in series[key].get("episodes", {}).values()),
            key,
        ))
        primary = keys[0]
        merged = deepcopy(series[primary])
        conflicts = []
        for old_key in keys[1:]:
            conflicts.extend(_conflicts(merged, series[old_key]))
            if conflicts:
                break
            for season, episodes in series[old_key].get("episodes", {}).items():
                merged.setdefault("episodes", {}).setdefault(str(season), {}).update(
                    deepcopy(episodes))
            for field in ("source_items", "public_episode_posts", "episode_poster_ids"):
                merged.setdefault(field, {}).update(
                    deepcopy(series[old_key].get(field, {})))
        if conflicts:
            report["skipped_collisions"].append(
                {"canonical": name, "keys": keys, "conflicts": sorted(set(conflicts))})
            continue
        old_posts = merged.setdefault("legacy_public_ids", [])
        old_indices = merged.setdefault("legacy_index_ids", [])
        for old_key in keys:
            entry = series[old_key]
            if old_key not in backups:
                backups[old_key] = deepcopy(entry)
            if old_key != primary:
                if entry.get("public_id") and entry["public_id"] != merged.get("public_id"):
                    old_posts.append(int(entry["public_id"]))
                for i in [entry.get("main_index_id"),
                          *entry.get("season_indices", {}).values()]:
                    if i and i != merged.get("main_index_id") and i not in (
                            merged.get("season_indices", {}).values()):
                        old_indices.append(int(i))
                for field in ("private_poster_id", "main_index_id", "public_id"):
                    if not merged.get(field) and entry.get(field):
                        merged[field] = entry[field]
                for field in ("season_indices", "season_public_ids", "season_status"):
                    for season, value in entry.get(field, {}).items():
                        merged.setdefault(field, {}).setdefault(str(season), value)
                del series[old_key]
                aliases[old_key] = primary
        merged["legacy_public_ids"] = sorted(set(map(int, old_posts)))
        merged["legacy_index_ids"] = sorted(set(map(int, old_indices)))
        merged["index_repair_pending"] = True
        merged["title"] = series_title(str(merged.get("title") or "")) or merged.get("title")
        series[primary] = merged
        aliases[name] = primary
        for old_key in keys:
            aliases[old_key] = primary
        # Avoid redirecting the primary key to itself in a cyclic chain.
        if primary in aliases and aliases[primary] == primary:
            del aliases[primary]
        report["consolidated_entries"] += len(keys) - 1
        report["merged_groups"].append(
            {"canonical": name, "primary": primary,
             "merged_keys": keys, "episode_count": sum(
                 len(episodes) for episodes in merged.get("episodes", {}).values())})
    return result, report
