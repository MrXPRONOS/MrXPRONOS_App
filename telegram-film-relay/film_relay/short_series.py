"""Conservative, per-title eligibility for complete short TV/anime series."""
from __future__ import annotations
import re
import unicodedata

END_OF_SERIES = re.compile(
    r"(?i)\b(?:s[eé]rie compl[eè]te|saison compl[eè]te|int[eé]grale|"
    r"fin de (?:la )?s[eé]rie|fin de saison|termin[eé]e)\b"
)
DECLARED_TOTAL = re.compile(r"(?i)\b(\d{1,3})\s*(?:[eé]pisodes|eps)\b")
DONE_COUNTER = re.compile(r"\b(\d{1,3})\s*/\s*\1\b")


def normalized_key(value):
    raw = str(value or "").lower().strip()
    raw = re.sub(r"(?i)^@[a-z0-9_]{5,32}\s+(?:vf|fv)?\s*", "", raw)
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    raw = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    raw = re.sub(r"^(?:mangas-fv|animes-canal)-", "", raw)
    return re.sub(r"-(?:episode|ep)0*\d{1,3}$", "", raw)


def short_complete_groups(groups, catalogue, maximum=12):
    """No truncation: reject long or incomplete series BEFORE uploading anything.

    Historical source observations and prior private receipts count toward the
    TOTAL number of episodes, including multiple seasons. A 1..12 run is
    sufficient to establish an entire 12-episode season; for a smaller series
    its authentic source caption must announce a complete run or its total.
    """
    result = []
    inventory = catalogue.get("source_observed", {}) or {}
    stored = catalogue.get("series", {}) or {}
    for key, rows in groups.items():
        canonical = normalized_key(key)
        unique = {}
        for row in sorted(rows, key=lambda r: r["timestamp"], reverse=True):
            unique.setdefault((int(row["season"]), int(row["episode"])), row)
        available = set(unique)
        found = set(available)
        for old_key, seasons in inventory.items():
            if normalized_key(old_key) != canonical:
                continue
            for season, numbers in seasons.items():
                found.update((int(season), int(n)) for n in numbers)
        for old_key, entry in stored.items():
            if normalized_key(old_key) != canonical and normalized_key(entry.get("title", "")) != canonical:
                continue
            for season, numbers in entry.get("episodes", {}).items():
                found.update((int(season), int(n)) for n in numbers)
        if not found or len(found) > maximum or any(n > maximum for _, n in found):
            continue
        if any(
            {no for sn, no in found if sn == season}
            != set(range(1, max(no for sn, no in found if sn == season) + 1))
            for season in {sn for sn, _ in found}
        ):
            continue
        # The full series must be available this run (or already stored).
        already_stored = {
            (int(season), int(n))
            for old_key, entry in stored.items()
            if normalized_key(old_key) == canonical
            or normalized_key(entry.get("title", "")) == canonical
            for season, numbers in entry.get("episodes", {}).items()
            for n in numbers
        }
        if not found.issubset(available | already_stored):
            continue
        context = " ".join(
            str(getattr(row.get("poster"), "raw_text", "") or "") + " " +
            str(getattr(row.get("video"), "raw_text", "") or "")
            for row in rows
        )
        totals = [int(x) for x in DECLARED_TOTAL.findall(context)]
        totals += [int(x) for x in DONE_COUNTER.findall(context)]
        if totals and (max(totals) > maximum or len(found) not in totals):
            continue
        sequential_twelve = (len(found) == maximum and
                             len({season for season, _ in found}) == 1)
        if not (sequential_twelve or END_OF_SERIES.search(context) or totals):
            continue
        ordered = sorted(unique.values(), key=lambda r: (r["season"], r["episode"]))
        # A real series illustration is required; do not substitute a text card.
        if not any(row.get("poster") is not None for row in ordered):
            continue
        result.append((key, ordered))
    return result
