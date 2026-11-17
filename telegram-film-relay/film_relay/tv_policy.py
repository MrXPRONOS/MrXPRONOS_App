"""Select complete TV seasons independently, not by lifetime series length."""
from .short_series import normalized_key, short_complete_groups


def complete_tv_seasons(groups, catalogue, maximum=12, diagnostics=None):
    """Each 1..maximum season must be complete; total show may exceed maximum."""
    if diagnostics is not None:
        diagnostics.clear()
    observations = catalogue.get("source_observed", {}) or {}
    stored = catalogue.get("series", {}) or {}
    result = []
    for key, rows in groups.items():
        canonical = normalized_key(key)
        for season in sorted({int(row["season"]) for row in rows}):
            season_label = str(season)
            observed_numbers = set()
            prior_receipts = {}
            for old_key, seasons in observations.items():
                if normalized_key(old_key) == canonical:
                    observed_numbers.update(int(n) for n in
                                            seasons.get(season_label, {}))
            for old_key, entry in stored.items():
                if (normalized_key(old_key) == canonical or
                        normalized_key(entry.get("title", "")) == canonical):
                    prior_receipts.update(entry.get("episodes", {}).get(season_label, {}))
            subset = {
                "source_observed": {key: {season_label: sorted(observed_numbers)}},
                "series": {key: {"episodes": {season_label: prior_receipts}}},
            }
            reasons = {}
            matched = short_complete_groups(
                {key: [r for r in rows if int(r["season"]) == season]},
                subset, maximum=maximum, diagnostics=reasons,
                require_completion_evidence=True,
            )
            if matched:
                result.extend(matched)
            elif diagnostics is not None:
                diagnostics[f"{key}:S{season:02d}"] = reasons.get(
                    key, "saison_non_admissible")
    return result
