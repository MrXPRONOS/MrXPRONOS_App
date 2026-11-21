"""Conservative publishing cadence hints extracted from channel posts.

A GIF, sticker, photo or text mentioning weekly releases is a hint associated
with the current explicit anime context, never proof of media identity.
"""
from __future__ import annotations

import re


_FORTNIGHT = re.compile(
    r"(?i)\b(?:bi[ -]?hebdomadaire|toutes? les deux semaines|"
    r"tous les (?:14|quinze) jours|every (?:two|2) weeks|fortnightly)\b"
)
_WEEKLY = re.compile(
    r"(?i)\b(?:hebdomadaire|chaque semaine|toutes? les semaines|"
    r"tous les (?:7|sept) jours|weekly|every week)\b"
)


def cadence_hint(text: str) -> str:
    """Only unambiguous explicit announcements, not time inference."""
    raw = str(text or "")
    if _FORTNIGHT.search(raw):
        return "fortnightly"
    if _WEEKLY.search(raw):
        return "weekly"
    return "unknown"


def cadence_from_message(message) -> str:
    parts = [getattr(message, "raw_text", "") or ""]
    parts.append(getattr(getattr(message, "file", None), "name", "") or "")
    return cadence_hint(" ".join(str(value) for value in parts))
