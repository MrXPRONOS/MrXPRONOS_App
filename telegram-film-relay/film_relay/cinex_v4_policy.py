"""Shared V4 policy for owner-managed CineX distribution.

Only the high-volume public relay channels receive an individual Secours.
Specialized single-work channels remain independent and must not be
auto-provisioned. This policy changes no existing Telegram channel.
"""
from __future__ import annotations

import re

# A machine-readable tag placed ONLY on newly published automatic VIDEO posts.
# It is absent from older owner/manual posts, posters and all private archives.
AUTO_VIDEO_TTL_TAG = "#CINEX_VIDEO_24H_V1"

# This is the announced high-volume network, not every film-related channel
# discovered in the owner's Telegram inventory.
MAIN_RELAY_HANDLES = frozenset({
    "@cinexfilms_vf",
    "@seriesvf_cinex",
    "@cinexdesirfr",
    "@cinexcomediefr",
    "@cinexanimefr",
    "@filmsaction2026vf",
    "@fichiers_cloud",  # planned horror and thriller relay; not yet published
})

# Do not create or modify backup channels for these dedicated catalogues.
DEDICATED_NO_SECOURS = frozenset({
    "@bleachvffr",
    "@fastandfuriousvffr",
    "@lecarnetdelapovf",
    "@lupin4saisonsvf",
})


def canonical_public_handle(value) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().casefold()
    if not value.startswith("@"):
        value = "@" + value
    return value if re.fullmatch(r"@[a-z0-9_]{5,32}", value) else None


def is_main_relay(value) -> bool:
    return canonical_public_handle(value) in MAIN_RELAY_HANDLES


def has_automatic_ttl(message) -> bool:
    """Never classify a message by age alone: owner/manual posts stay intact."""
    caption = str(getattr(message, "raw_text", "") or "")
    return AUTO_VIDEO_TTL_TAG in caption.split()


def caption_with_automatic_ttl(caption: str) -> str:
    """Idempotently tag exactly the new public video caption (not its cover)."""
    body = (caption or "").strip()
    if not body:
        raise ValueError("La vidéo CinéX doit avoir une description")
    return body if AUTO_VIDEO_TTL_TAG in body.split() else body + "\n" + AUTO_VIDEO_TTL_TAG
