"""Conservative release identity used ONLY for exact-title anti-duplicates.

Do not conflate remakes (different years), sequels or weak/generic titles.
The actual Telegram document ID remains the strongest identity for exact copies.
"""
from __future__ import annotations
from .text import first_title
from .title_guard import tokens, release_year, filename_title


def film_fingerprint(description: str, filename: str = "") -> str | None:
    title = first_title(description or "").strip()
    words = sorted(tokens(title))
    if not words or (len(words) == 1 and len(words[0]) < 5):
        return None
    # Keep year discrimination when supplied in either source. Two explicitly
    # contradictory years must not be auto-deduplicated on title alone.
    years = release_year(title) | release_year(filename)
    if len(years) > 1:
        return None
    # File-name evidence can be generic or absent, but MUST NOT contradict an
    # explicit descriptive title. A different film must not be silently dropped.
    file_tokens = tokens(filename_title(filename))
    if file_tokens and set(words) != file_tokens:
        return None
    return "classic:title:" + ",".join(words) + ":year:" + (next(iter(years)) if years else "unknown")
