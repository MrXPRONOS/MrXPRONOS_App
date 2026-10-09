"""Canonical public image endpoints for the BSD football API.

BSD image proxy needs no API key and accepts *numeric BSD entity IDs*:
  https://sports.bzzoiro.com/img/team/{id}/?bg=transparent
  https://sports.bzzoiro.com/img/league/{id}/?bg=transparent

Invalid or missing IDs must never produce guessed or unrelated artwork.
"""
from __future__ import annotations

from urllib.parse import urlsplit

BASE="https://sports.bzzoiro.com/img"
IMAGE_TYPES=frozenset(("team","league"))

def valid_id(value):
    """Positive canonical BSD numeric ID; refuse bool, null, float, path chars."""
    if isinstance(value,bool) or value is None:
        return None
    if isinstance(value,int):
        return value if value>0 else None
    if isinstance(value,str):
        s=value.strip()
        if s.isascii() and s.isdecimal() and int(s)>0:
            return int(s)
    return None

def bsd_logo_url(kind,entity_id,*,transparent=True):
    if kind not in IMAGE_TYPES:
        raise ValueError("Unsupported BSD image type")
    entity=valid_id(entity_id)
    if entity is None:
        return ""
    suffix="?bg=transparent" if transparent else ""
    return f"{BASE}/{kind}/{entity}/{suffix}"

def image_fields(fixture):
    """Verified IDs -> URL strings; no network needed for deterministic URLs."""
    if not isinstance(fixture,dict):
        return {"home_logo":"","away_logo":"","league_logo":""}
    return {
        "home_logo":bsd_logo_url("team",fixture.get("home_team_id")),
        "away_logo":bsd_logo_url("team",fixture.get("away_team_id")),
        "league_logo":bsd_logo_url("league",fixture.get("league_id")),
    }
