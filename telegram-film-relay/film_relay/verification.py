"""Strict, conservative structural verification of Telegram poster + movie pairs.

Neither this heuristic nor the public visibility of a source establishes media rights.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Sequence

from .matching import Pair, match_pairs
from .text import clean_caption, first_title


@dataclass(frozen=True)
class Screening:
    pairs: tuple[Pair, ...]
    rejected: int
    reasons: tuple[str, ...]


def _duration(message: Any) -> int:
    return int(getattr(getattr(message, "file", None), "duration", 0) or 0)


def _size(message: Any) -> int:
    doc = getattr(message, "document", None)
    return int(getattr(getattr(message, "file", None), "size", None) or getattr(doc, "size", 0) or 0)


def normalized_title(text: str) -> str:
    title = first_title(text).lower()
    title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", title).strip()


def screen_pairs(
    messages: Sequence[Any], *, min_minutes: int = 40,
    min_megabytes: int = 150, max_gap: int = 2,
    max_age_minutes: int = 60, min_caption_chars: int = 25,
) -> Screening:
    """Require long, substantial video file + meaningful caption + tight pairing.

    Rejects items with missing metadata instead of guessing. Distinct titles
    are checked separately at the channel-level (not per message).
    """
    accepted: list[Pair] = []
    reasons: list[str] = []
    candidates = match_pairs(messages, max_gap=max_gap, max_age_minutes=max_age_minutes)
    for pair in candidates:
        if getattr(pair.poster, "noforwards", False) or getattr(pair.movie, "noforwards", False):
            reasons.append("message_protege")
            continue
        description = clean_caption(getattr(pair.poster, "raw_text", "") or "", getattr(pair.poster, "entities", None))
        title = normalized_title(description)
        if len(description) < min_caption_chars or len(title) < 7:
            reasons.append("description_insuffisante")
            continue
        if _duration(pair.movie) < min_minutes * 60:
            reasons.append("duree_courte_ou_inconnue")
            continue
        if _size(pair.movie) < min_megabytes * 1_000_000:
            reasons.append("fichier_petit_ou_taille_inconnue")
            continue
        accepted.append(pair)
    return Screening(tuple(accepted), len(reasons), tuple(reasons))


def channel_format_verified(screening: Screening, *, min_pairs: int = 2) -> bool:
    titles = {
        normalized_title(clean_caption(p.poster.raw_text or "", getattr(p.poster, "entities", None)))
        for p in screening.pairs
    }
    return len(screening.pairs) >= min_pairs and len(titles) >= min_pairs
