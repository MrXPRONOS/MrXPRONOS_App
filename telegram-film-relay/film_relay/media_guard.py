"""Reject non-photo Telegram previews before copying source media.

A Telegram MessageMediaWebPage is a link preview, never an image upload.
Keep this guard independent of the Telegram network for deterministic tests.
"""
from __future__ import annotations


def valid_photo_message(message) -> bool:
    """Accept only a genuine, unprotected Telegram photo with usable media."""
    if message is None or getattr(message, "noforwards", False):
        return False
    if getattr(message, "photo", None) is None:
        return False
    media = getattr(message, "media", None)
    if media is None:
        return False
    # Telethon MessageMediaPhoto has a .photo field; MessageMediaWebPage does not.
    return getattr(media, "photo", None) is not None


def require_photo(message) -> object:
    """Return valid photo media or raise before any Telegram send."""
    if not valid_photo_message(message):
        raise ValueError("Affiche invalide : photo Telegram réelle requise (aperçu Web interdit).")
    return message.media
