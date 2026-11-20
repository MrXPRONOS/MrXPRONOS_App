"""Selection policy for a complete Anime season and standalone movie quota.

Unlike TV-series eligibility, each Anime season is considered independently.
Historical observations still prevent treating a partial season as complete.
"""
from __future__ import annotations

from .short_series import normalized_key, short_complete_groups


def complete_anime_seasons(groups, catalogue, maximum=25, diagnostics=None):
    """Yield (series_key, ordered_season_rows), maximum one whole season per item."""
    if diagnostics is not None:
        diagnostics.clear()
    observations = catalogue.get("source_observed", {}) or {}
    stored = catalogue.get("series", {}) or {}
    eligible = []
    for key, rows in groups.items():
        canonical = normalized_key(key)
        for season in sorted({int(row["season"]) for row in rows}):
            season_str = str(season)
            observed_numbers = set()
            stored_episodes = {}
            for earlier_key, season_map in observations.items():
                if normalized_key(earlier_key) == canonical:
                    observed_numbers.update(int(x) for x in
                                            season_map.get(season_str, []))
            for earlier_key, entry in stored.items():
                if (normalized_key(earlier_key) == canonical or
                        normalized_key(entry.get("title", "")) == canonical):
                    stored_episodes.update(
                        entry.get("episodes", {}).get(season_str, {}))
            scoped = {
                "source_observed": {
                    key: {season_str: sorted(observed_numbers)}
                },
                "series": {
                    key: {"episodes": {season_str: stored_episodes}}
                },
            }
            reasons = {}
            candidates = short_complete_groups(
                {key: [row for row in rows if int(row["season"]) == season]},
                scoped, maximum=maximum, diagnostics=reasons,
                require_completion_evidence=True,
            )
            if candidates:
                eligible.extend(candidates)
            elif diagnostics is not None:
                diagnostics[f"{key}:S{season:02d}"] = reasons.get(
                    key, "saison_non_admissible")
    return eligible



def progressive_anime_seasons(groups, catalogue, maximum=25, diagnostics=None):
    """Select a contiguous, verifiable chunk of an ongoing season.

    This does NOT assert that a season is complete. Numbered source episodes
    are required, gaps are never skipped, and existing receipts are retained.
    The caller must preflight actual source media and artwork before upload.
    """
    if diagnostics is not None:
        diagnostics.clear()
    result = []
    stored = catalogue.get("series", {}) or {}
    for key, rows in groups.items():
        canonical = normalized_key(key)
        existing = next((
            entry for old_key, entry in stored.items()
            if normalized_key(old_key) == canonical
            or normalized_key(entry.get("title", "")) == canonical
        ), {})
        by_season = {}
        for row in sorted(rows, key=lambda row: row["timestamp"], reverse=True):
            season = int(row["season"])
            number = int(row["episode"])
            if not (1 <= season <= 50 and 1 <= number <= 999):
                continue
            if row.get("poster") is None:
                continue
            by_season.setdefault(season, {}).setdefault(number, row)
        for season in sorted(by_season):
            entries = by_season[season]
            receipts = existing.get("episodes", {}).get(str(season), {})
            # Start at episode one. Never publish episode 12 while 1..11
            # are absent from both the catalogue and the scanned source.
            ordered = []
            for number in range(1, 1000):
                if number in entries:
                    ordered.append(entries[number])
                elif str(number) not in receipts:
                    break
                if len(ordered) >= maximum:
                    break
            if not ordered:
                if diagnostics is not None:
                    diagnostics[f"{key}:S{season:02d}"] = "debut_ou_suite_indisponible"
                continue
            if all(str(row["episode"]) in receipts for row in ordered):
                continue
            result.append((key, ordered))
    return result

def select_anime_season(eligible, catalogue):
    """Select one new or unfinished season; keep earlier season receipts intact."""
    if catalogue.get("active_batch"):
        return None  # Active batch is recovered by its exact source IDs.
    stored = catalogue.get("series", {}) or {}
    for key, rows in eligible:
        from .anime_catalog import series_title, slug
        existing = stored.get(key)
        if existing is None:
            existing = next((
                value for value in stored.values()
                if series_title(str(value.get("title", "")))
                and slug(series_title(str(value.get("title", "")))) == key
            ), {})
        season = str(rows[0]["season"])
        episode_receipts = existing.get("episodes", {}).get(season, {})
        if (not existing.get("public_id")
                or not existing.get("season_indices", {}).get(season)
                or any(str(row["episode"]) not in episode_receipts
                       for row in rows)):
            return (key, rows)
    return None


def anime_movie_slots(limit: int, *, finished_series: bool, active_batch: bool) -> int:
    """Two films alone, or one film alongside a complete Anime season."""
    if active_batch:
        return 0
    return max(0, min(2, int(limit)) - int(bool(finished_series)))
