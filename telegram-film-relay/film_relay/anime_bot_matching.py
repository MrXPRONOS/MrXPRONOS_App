"""Pure title-aware matching of authorized Bot API source messages.

Explicit episode numbers are mandatory. One source poster may establish
context for following bare Episode_07 files; conflicting explicit titles,
unrelated posters and special releases are quarantined rather than guessed.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from .anime_cadence import cadence_hint
from .episode_identity import (
    canonical_title, episode_numbers, series_title, SEASON_HEADER,
)


_SPECIAL = re.compile(
    r"(?i)(?<![a-z0-9])(?:OVA|ONA|special|hors[ _-]?s[eé]rie|recap|compilation)(?![a-z0-9])")
_DECLARED_COUNT = re.compile(
    r"(?i)\b(?:compl[eè]te?|int[eé]grale)\b.{0,32}\b(\d{1,3})\s*"
    r"(?:[eé]pisodes?|eps)\b|\b(\d{1,3})\s*(?:[eé]pisodes?|eps)"
    r".{0,32}\b(?:compl[eè]te?|int[eé]grale)\b"
)


def _label(record):
    return " ".join((str(record.get("text") or ""),
                     str(record.get("filename") or ""))).strip()


def _named_title(record):
    from_caption = series_title(str(record.get("text") or ""))
    from_file = series_title(Path(str(record.get("filename") or "")).stem)
    x, y = canonical_title(from_caption), canonical_title(from_file)
    if x and y and x != y:
        return "", "conflicting_caption_and_filename"
    return from_caption or from_file, None


def _season(label, inherited=1):
    found = SEASON_HEADER.search(label or "")
    return int(found.group(1)) if found else inherited


def _complete_count(text):
    match = _DECLARED_COUNT.search(text or "")
    return int(match.group(1) or match.group(2)) if match else None


def associate_anime_messages(messages: dict):
    """Return (candidates, review, cadence_by_title, complete_season_evidence).

    Only messages already accepted by the source allowlist are considered.
    We preserve source-specific order and never inherit posters across feeds.
    Context must be within 40 source messages and must be unambiguous.
    """
    by_source = defaultdict(list)
    for key, record in messages.items():
        if record.get("status") in ("ignored", "revoked"):
            continue
        if str(key) != (str(record.get("source_id")) + ":" +
                        str(record.get("message_id"))):
            continue
        by_source[str(record["source_id"])].append((key, record))
    candidates, review, cadence, complete = [], [], {}, {}
    for source_id, rows in sorted(by_source.items()):
        rows.sort(key=lambda pair: int(pair[1]["message_id"]))
        active = None
        active_title = ""
        season = 1
        poster = None
        poster_index = -10000
        frequency = "unknown"
        active_gif = None
        for index, (source_key, record) in enumerate(rows):
            kind = record.get("kind")
            description = _label(record)
            title, problem = _named_title(record)
            if kind == "poster":
                poster = source_key
                poster_index = index
                active = canonical_title(title) if title and not problem else None
                active_title = title if active else ""
                season = _season(description)
                frequency = cadence_hint(description)
                active_gif = None
                if active and (count := _complete_count(description)):
                    complete[(active, season)] = max(
                        count, complete.get((active, season), 0))
                continue
            if kind in ("text", "animation"):
                detected = cadence_hint(description)
                if active and detected != "unknown":
                    frequency = detected
                    cadence[active] = detected
                    if kind == "animation":
                        active_gif = source_key
                if active and _complete_count(description):
                    complete[(active, _season(description, season))] = max(
                        _complete_count(description),
                        complete.get((active, _season(description, season)), 0))
                # Ordinary text between poster and episode ("bientôt",
                # release schedule, synopsis) must not hijack its identity.
                # Only an explicit title declaration changes series context.
                title_declaration = re.search(
                    r"(?i)^\s*(?:titre|title|anim[eé])\s*:\s*",
                    str(record.get("text") or ""))
                explicit = title if title_declaration and not problem else ""
                if explicit and canonical_title(explicit) != active:
                    # Named text announces a new show without verified art:
                    # quarantine its bare episodes until new cover arrives.
                    active = canonical_title(explicit)
                    active_title = explicit
                    poster = None
                    active_gif = None
                    season = _season(description)
                elif active:
                    season = _season(description, season)
                continue
            if kind != "video":
                continue
            if _SPECIAL.search(description):
                review.append({"source_key": source_key, "reason": "special_release"})
                continue
            numbered = episode_numbers(description)
            if numbered is None:
                review.append({"source_key": source_key, "reason": "missing_episode_number"})
                continue
            if problem:
                review.append({"source_key": source_key, "reason": problem})
                continue
            explicit_title = canonical_title(title) if title else ""
            if explicit_title and active and explicit_title != active:
                review.append({"source_key": source_key, "reason": "conflicting_poster_title"})
                continue
            identity = explicit_title or active
            if not identity or not poster or index - poster_index > 40:
                review.append({"source_key": source_key, "reason": "ambiguous_series_or_poster"})
                continue
            explicit_season = SEASON_HEADER.search(description)
            season_no = int(explicit_season.group(1)) if explicit_season else (
                numbered[0] if re.search(r"(?i)\b\d{1,2}x\d{1,3}\b",
                                        description) else season)
            number = numbered[1]
            if not (1 <= season_no <= 50 and 1 <= number <= 999):
                review.append({"source_key": source_key, "reason": "invalid_episode"})
                continue
            if not record.get("file_id"):
                review.append({"source_key": source_key, "reason": "missing_bot_file"})
                continue
            candidates.append({
                "source_key": source_key, "source_id": source_id,
                "message_id": int(record["message_id"]),
                "title": title or active_title or identity,
                "series": identity, "season": season_no, "episode": number,
                "poster_source_key": poster,
                "file_unique_id": record.get("file_unique_id") or "",
                "date": int(record.get("date") or 0),
                "cadence_hint": frequency,
                "cadence_source_key": active_gif,
                "status": record.get("status", "pending"),
            })
            if frequency != "unknown":
                cadence[identity] = frequency
    return candidates, review, cadence, complete


def consolidate_source_candidates(rows, *, reviewed_variants=None):
    """Produce one canonical episode; quarantine conflicting media variants."""
    reviewed_variants = reviewed_variants or {}
    grouped = defaultdict(list)
    media_labels = defaultdict(set)
    for row in rows:
        key = (row["series"], int(row["season"]), int(row["episode"]))
        grouped[key].append(row)
        if row.get("file_unique_id"):
            media_labels[row["file_unique_id"]].add(key)
    cross_label_conflicts = {
        key for identities in media_labels.values()
        if len(identities) > 1 for key in identities
    }
    selected, review = [], []
    for key, variants in sorted(grouped.items()):
        if key in cross_label_conflicts:
            review.append({
                "series": key[0], "season": key[1], "episode": key[2],
                "reason": "one_video_labeled_as_distinct_episodes",
                "source_keys": sorted(row["source_key"] for row in variants),
            })
            continue
        fingerprints = {row["file_unique_id"] for row in variants
                        if row.get("file_unique_id")}
        allowed = reviewed_variants.get(
            f"{key[0]}:S{key[1]:02d}E{key[2]:02d}")
        if len(fingerprints) > 1 and allowed not in fingerprints:
            review.append({
                "series": key[0], "season": key[1], "episode": key[2],
                "reason": "conflicting_source_media",
                "source_keys": sorted(row["source_key"] for row in variants),
            })
            continue
        viable = [r for r in variants if not allowed or
                  r.get("file_unique_id") == allowed]
        best = min(viable, key=lambda row: (
            int(row.get("date") or 0), row["source_key"]))
        selected.append({
            **best,
            "alternate_source_keys": sorted(
                r["source_key"] for r in variants
                if r["source_key"] != best["source_key"]),
        })
    return selected, review


def select_bot_anime_batches(candidates, state, complete_evidence,
                             *, weekly_limit=4, complete_batch_limit=50):
    """One *whole season* OR up to four distinct ongoing series in one tour.

    Every selected ongoing title contains ALL currently available consecutive
    new numbered episodes (not just its first one). Previously published
    episode receipts are not reposted. A missing/unverified predecessor stops
    progression. No long complete season is arbitrarily sliced.
    """
    if not 1 <= weekly_limit <= 4:
        raise ValueError("At most four different ongoing anime series per cycle.")
    if not 1 <= complete_batch_limit <= 50:
        raise ValueError("At most fifty episodes in one verified arrival.")
    grouped = defaultdict(dict)
    for row in candidates:
        grouped[(row["series"], int(row["season"]))][int(row["episode"])] = row
    series = state.get("series", {})
    priority = []
    blocked = set()
    for (key, season), numbered in grouped.items():
        count = int(complete_evidence.get((key, season), 0))
        if count < 1:
            continue
        if count > complete_batch_limit:
            blocked.add((key, season))
            continue
        entry = series.get(key, {})
        receipts = entry.get("public_episode_posts", {})
        unverified = set(entry.get("legacy_unverified_episode_keys", []))
        if any(n not in numbered and str(n) not in
               entry.get("episodes", {}).get(str(season), {})
               for n in range(1, count + 1)):
            continue
        if any(f"S{season:02d}E{n:02d}" in unverified
               for n in range(1, count + 1)):
            blocked.add((key, season))
            continue
        pending = [numbered[n] for n in range(1, count + 1)
                   if f"S{season:02d}E{n:02d}" not in receipts
                   and n in numbered]
        if pending:
            priority.append((key, season, pending))
    if priority:
        priority.sort(key=lambda group: (
            min(int(r.get("date") or 0) for r in group[2]),
            group[0], group[1]))
        key, season, rows = priority[0]
        return [(key, rows, True)]

    ongoing = []
    for (key, season), numbered in grouped.items():
        if (key, season) in blocked or not numbered:
            continue
        entry = series.get(key, {})
        published = entry.get("public_episode_posts", {})
        unverified = set(entry.get("legacy_unverified_episode_keys", []))
        pending = []
        for n in range(1, max(numbered) + 1):
            marker = f"S{season:02d}E{n:02d}"
            if marker in published:
                continue
            if marker in unverified or n not in numbered:
                break
            pending.append(numbered[n])
            if len(pending) > complete_batch_limit:
                pending = []  # never silently cut a published season in half
                break
        if pending:
            ongoing.append((key, season, pending))
    ongoing.sort(key=lambda group: (
        min(int(row.get("date") or 0) for row in group[2]),
        group[0], group[1]))
    chosen, used = [], set()
    for key, season, rows in ongoing:
        if key in used:
            continue
        chosen.append((key, rows, False))
        used.add(key)
        if len(chosen) >= weekly_limit:
            break
    return chosen
