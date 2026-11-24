"""Pure, conservative decision engine for owner-posted Telegram fallback media.

No network calls. A fallback is not a bypass for Telegram FloodWait/PeerFlood.
The caller must supply durable receipts from BOTH personal and bot transports.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Mapping, Sequence

# Existing ordinary CineX relays cap these categories at 2 posts/cycle.
# Series/anime count is per series batch; episode counts remain governed by
# their existing V4 season publisher, not this generic selector.
CYCLE_CAPS = {
    "films": 2, "desir": 2, "comedie": 2, "action": 2,
    "series": 2, "animes": 2,
    "formation_general": 1, "formation_business": 1,
    "formation_finance": 1, "formation_digitale": 1,
    "formation_mindset": 1,
}
_CATEGORY = frozenset(CYCLE_CAPS)
_TAGS = re.compile(r"(?i)\b(?:vf|vostfr|french|hd|1080p|720p|2160p|mkv|mp4|x264|x265|bluray|webrip)\b")
_WORD = re.compile(r"[a-z0-9]+")
_EPISODE = re.compile(r"(?i)\bS(\d{1,2})[ ._-]*E(\d{1,3})\b")
_YEAR = re.compile(r"(?<!\d)(?:19\d{2}|20\d{2})(?!\d)")
_VALID_ID = re.compile(r"^-100\d{5,}$")


@dataclass(frozen=True)
class Candidate:
    category: str
    stock_chat_id: str
    poster_message_id: int
    video_message_id: int
    title: str
    file_unique_id: str = ""
    year: str = ""
    season: int | None = None
    episode: int | None = None
    rights_confirmed: bool = False

    def __post_init__(self):
        if self.category not in _CATEGORY:
            raise ValueError("Unrecognized publishing category")
        if not _VALID_ID.fullmatch(self.stock_chat_id):
            raise ValueError("A real private -100... chat ID is required")
        if self.poster_message_id < 1 or self.video_message_id < 1:
            raise ValueError("Poster and video must be actual Telegram messages")
        if self.poster_message_id == self.video_message_id:
            raise ValueError("Poster and video cannot be the same Telegram message")


def normalized_title(title: str) -> str:
    value = unicodedata.normalize("NFKD", str(title or "").casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = _TAGS.sub(" ", value)
    value = _YEAR.sub(" ", value)
    value = _EPISODE.sub(" ", value)
    return " ".join(_WORD.findall(value))


def semantic_identity(item: Candidate) -> str | None:
    title = normalized_title(item.title)
    if len(title) < 5 or title in {"film", "anime", "serie", "episode", "formation"}:
        return None
    if item.category in {"series", "animes"}:
        if not item.season or not item.episode:
            return None
        return f"{item.category}:episode:{title}:S{item.season:02d}E{item.episode:03d}"
    if item.category.startswith("formation_"):
        # A course title alone cannot safely identify a multi-file course.
        return None
    years = set(_YEAR.findall(item.title))
    if item.year:
        years.add(str(item.year))
    if len(years) > 1:
        return None
    if not years:
        # Do not erase remakes by title alone when there is no year.
        return None
    return f"{item.category}:title:{title}:year:{next(iter(years))}"


def media_identity(item: Candidate) -> str | None:
    value = str(item.file_unique_id or "").strip()
    return f"file:{value}" if value and len(value) >= 8 else None


def may_activate_fallback(*, personal_status: str, bot_ready: bool,
                          stock_ready: bool, rights_attested: bool,
                          durable_receipts: bool, owner_enabled: bool) -> bool:
    """Fail closed unless the personal session is demonstrably unavailable.

    Do NOT circumvent FloodWait, rights restrictions or uncertain writes.
    """
    return bool(
        owner_enabled and rights_attested and bot_ready and stock_ready
        and durable_receipts and personal_status in {"session_missing", "session_revoked"}
    )


def choose_candidates(candidates: Sequence[Candidate], *,
                      published_media: set[str] | None = None,
                      published_semantic: set[str] | None = None,
                      already_used: Mapping[str, int] | None = None):
    """Deduplicate cross-mode receipts, quarantine collisions, preserve quotas.

    All published_media / published_semantic must come from a DURABLE shared
    registry, not a checkout-local cache. No send is performed here.
    """
    known_media = set(published_media or ())
    known_semantic = set(published_semantic or ())
    used = dict(already_used or {})
    if any(key not in _CATEGORY or not isinstance(value, int) or value < 0
           for key, value in used.items()):
        raise ValueError("Invalid existing per-cycle quota")
    review = []
    duplicates = []
    seen_source = set()
    identities: dict[str, list[Candidate]] = defaultdict(list)
    media_labels: dict[str, set[str]] = defaultdict(set)
    # Preflight the full queue BEFORE selecting. Never publish first candidate
    # if a later copy declares a conflicting identity for the same file.
    for item in candidates:
        source_key = (item.stock_chat_id, item.video_message_id)
        if source_key in seen_source:
            duplicates.append((item, "same_source_message"))
            continue
        seen_source.add(source_key)
        if not item.rights_confirmed:
            review.append((item, "missing_rights"))
            continue
        semantic = semantic_identity(item)
        media = media_identity(item)
        if not (semantic or media):
            review.append((item, "insufficient_identity"))
            continue
        identities[semantic or media].append(item)
        if media:
            media_labels[media].add(semantic or media)
    collision_files = {key for key, labels in media_labels.items() if len(labels) > 1}
    for media in collision_files:
        for group in identities.values():
            for item in group:
                if media_identity(item) == media:
                    review.append((item, "same_video_conflicting_title"))
    blocked_sources = {(item.stock_chat_id, item.video_message_id) for item, _ in review}
    selected = []
    selected_media = set()
    selected_semantic = set()
    for group in identities.values():
        # Two DIFFERENT videos claiming the same film/year/episode: review.
        variants = {media_identity(item) for item in group if media_identity(item)}
        if len(variants) > 1:
            for item in group:
                review.append((item, "multiple_video_versions"))
                blocked_sources.add((item.stock_chat_id, item.video_message_id))
            continue
        for item in group:
            source_key = (item.stock_chat_id, item.video_message_id)
            if source_key in blocked_sources:
                continue
            media = media_identity(item)
            semantic = semantic_identity(item)
            if ((media and media in known_media) or
                (semantic and semantic in known_semantic) or
                (media and media in selected_media) or
                (semantic and semantic in selected_semantic)):
                duplicates.append((item, "already_delivered"))
                continue
            if used.get(item.category, 0) >= CYCLE_CAPS[item.category]:
                review.append((item, "cycle_cap"))
                continue
            selected.append(item)
            used[item.category] = used.get(item.category, 0) + 1
            if media:
                selected_media.add(media)
            if semantic:
                selected_semantic.add(semantic)
    return {"selected": selected, "review": review, "duplicates": duplicates,
            "used": used}
