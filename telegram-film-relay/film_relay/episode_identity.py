"""Shared, conservative episode/title identity for TV and anime catalogues.

No episode number is inferred. Conflicting explicit titles are quarantined
instead of being attributed to the most recently seen artwork.
"""
from __future__ import annotations
import re
import unicodedata
from pathlib import Path

from .text import first_title

EPISODE = re.compile(
    r"(?i)(?<![a-z0-9])(?:s(?:aison|eason)?[ ._-]*0*(\d{1,2})[ ._-]*"
    r"[eé](?:p(?:isode)?)?[ ._-]*0*(\d{1,3})|"
    r"(\d{1,2})[ ._-]*x[ ._-]*0*(\d{1,3})|"
    r"[eé](?:p(?:isode)?)?[ ._-]*0*(\d{1,3}))(?!\d)"
)
SEASON_HEADER = re.compile(
    r"(?i)(?<![a-z0-9])s(?:aison|eason)?[ ._-]*0*(\d{1,2})(?!\d)"
)
SOURCE_SIGNATURE = re.compile(r"(?i)^@[a-z0-9_]{5,32}\s+(?:vf|fv|vostfr)?\s*")
EP_LABEL = re.compile(r"(?i)\b(?:[eé](?:p(?:isode)?)?[ ._-]*0*\d{1,3}|"
                      r"s\d{1,2}[ ._-]*e\d{1,3}|\d{1,2}x\d{1,3})\b")
SEASON_LABEL = re.compile(r"(?i)\b(?:saison|season)[ ._-]*0*\d{1,2}\b|"
                          r"(?<![a-z0-9])s0*\d{1,2}(?![a-z0-9])")
TOTAL_LABEL = re.compile(r"(?i)\b\d{1,3}\s*(?:[eé]pisodes?|eps)\b|"
                         r"\b(?:s[eé]rie|saison)\s+compl[eè]te\b|\bint[eé]grale\b")
TECH_LABEL = re.compile(
    r"(?i)\b(?:vf|vostfr|french|hd|720p|1080p|480p|360p|2160p|"
    r"web[ ._-]?dl|web[ ._-]?rip|mp4|mkv|convertie?|non[ ._-]?convertie?|"
    r"dub|fin|complet)\b"
)
GENERIC = {"anime", "dessin anime", "serie", "série", "film", "video",
           "episode", "épisode", "vf", "vostfr", "fichier", "new", "nouveau"}


def episode_numbers(text: str):
    m = EPISODE.search(text or "")
    if not m:
        return None
    season = int(m.group(1) or m.group(3) or 1)
    episode = int(m.group(2) or m.group(4) or m.group(5))
    if not (1 <= season <= 50 and 1 <= episode <= 999):
        return None
    return season, episode


def series_title(text: str):
    text = str(text or "").strip()
    if not text:
        return ""
    value = first_title(text)
    value = SOURCE_SIGNATURE.sub("", value).split("@", 1)[0]
    value = re.sub(r"(?i)\bs(?:aison|eason)?[ ._-]*0*\d{1,2}[ .:_-]+compl[eè]te\b",
                   " ", value)
    value = EPISODE.sub(" ", value)
    value = SEASON_LABEL.sub(" ", value)
    value = TOTAL_LABEL.sub(" ", value)
    value = re.sub(r"(?i)\b(?:fin de (?:la )?s[eé]rie|fin de saison)\b", " ", value)
    value = TECH_LABEL.sub(" ", value)
    value = re.sub(r"(?i)\b(?:titre|title)\s*:", " ", value)
    value = re.sub(r"(?i)\.(?:mkv|mp4|avi|mov)\b", " ", value)
    value = re.sub(r"[|_\[\](){},:.#]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" -.!?🎬🎞📺🌸")
    if not value or value.casefold() in GENERIC or len(value) < 3:
        return ""
    return value[:90]


def canonical_title(value: str) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "").lower())
    clean = raw.encode("ascii", "ignore").decode()
    clean = re.sub(r"[^a-z0-9]+", "-", clean).strip("-")
    # Remove only declared Telegram source signatures and release metadata.
    clean = re.sub(
        r"^(?:(?:mangas-fv|animes-canal|animeisekaic|animeuniverselvfvostfr|"
        r"animes-vf-vosfr)-)+", "", clean)
    while True:
        previous = clean
        clean = re.sub(
            r"-(?:ep(?:isode)?0*\d{1,3}|e0*\d{1,3}|"
            r"s0*\d{1,2}(?:-e0*\d{1,3})?|"
            r"(?:\d{1,2})x0*\d{1,3}|"
            r"360p|480p|720p|1080p|2160p|mkv|mp4|"
            r"convertie|converti|non-convertie|non-converti|fin)$", "", clean)
        if clean == previous:
            break
    return clean


def consistent_title(poster_text: str, video_caption: str, filename: str) -> str:
    """Return one explicitly compatible title; blank means quarantine."""
    from_caption = series_title(video_caption)
    from_filename = series_title(Path(str(filename or "")).stem)
    from_poster = series_title(poster_text)
    a = canonical_title(from_caption) if from_caption else ""
    b = canonical_title(from_filename) if from_filename else ""
    c = canonical_title(from_poster) if from_poster else ""
    if a and b and a != b:
        return ""
    chosen = from_caption or from_filename
    if chosen and c and canonical_title(chosen) != c:
        return ""
    return chosen or from_poster
