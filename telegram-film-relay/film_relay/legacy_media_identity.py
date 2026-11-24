"""Conservative identity and poster matching for CinéX legacy public media.

Pure functions: no Telegram calls or side effects. A wrong association is
worse than an unmatched item; ambiguous titles remain in the public channel.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata
from pathlib import PurePath

from .episode_identity import episode_numbers
from .public_video_archive import poster_heading, video_title

PART = re.compile(
    r"(?i)(?<![a-z0-9])(?:partie|part|pt|cd|disc|disque|volume|vol)"
    r"[ ._:#-]*0*([1-9]\d?)(?!\d)"
    r"|(?<!\d)([1-9]\d?)\s*/\s*([2-9]\d?)(?!\d)"
)
PACK = re.compile(
    r"(?i)\b(?:saison|season|s)\s*0*(\d{1,2})\b.{0,30}"
    r"\b(?:complete|compl[eè]te|integrale|int[eé]grale)\b"
)
SEASON = re.compile(r"(?i)(?<!\w)(?:saison|season|s)[ ._-]*0*(\d{1,2})(?!\d)")
TECH = re.compile(
    r"(?i)\b(?:vf|vostfr|vost|french|francais|film|films|serie|series|"
    r"anime|animes|video|complet|complete|integrale|hd|fullhd|uhd|4k|"
    r"720p|1080p|2160p|480p|360p|mp4|mkv|avi|mov|webm|"
    r"webrip|webdl|bluray|brrip|x264|x265|h264|h265|hevc|multi)\b"
)
TAG = re.compile(r"(?i)^\s*#(?:film|serie|series|anime|action|comedie|desir)\s*$")
EXPLICIT_YOUTUBE = re.compile(
    r"https://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?[^\s<>\"']+|"
    r"shorts/[a-zA-Z0-9_-]{11}|embed/[a-zA-Z0-9_-]{11})|"
    r"youtu\.be/[a-zA-Z0-9_-]{11})(?:[^\s<>\"']*)?",
    flags=re.IGNORECASE,
)
YOUTUBE_ID = re.compile(r"^[a-zA-Z0-9_-]{11}$")


@dataclass(frozen=True)
class Identity:
    title: str
    kind: str
    season: int | None = None
    episode: int | None = None
    part: int | None = None
    year: int | None = None

    @property
    def safe(self) -> bool:
        return len(self.title) >= 3 and self.title not in {
            "film", "serie", "anime", "video", "episode", "partie"
        }


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", str(text or "")).encode(
        "ascii", "ignore"
    ).decode("ascii").lower()


def cleaned_title(text: str) -> str:
    lines = _ascii(text).splitlines()
    value = lines[0] if lines else ""
    value = re.sub(r"(?i)^(?:@[\w]{5,32}\s+)", "", value)
    value = re.sub(
        r"(?i)^(?:(?:mangas[ ._-]*fv|animes[ ._-]*canal|"
        r"animeisekaic|animeuniverselvfvostfr)[ ._-]+)+", "", value
    )
    value = PART.sub(" ", value)
    # Explicit episodes / season headers and release-years are metadata,
    # not title identity. Conflicting metadata is compared separately.
    value = re.sub(
        r"(?i)(?<![a-z0-9])(?:s(?:aison|eason)?[ ._-]*\d{1,2}"
        r"[ ._-]*e(?:p(?:isode)?)?[ ._-]*\d{1,3}|"
        r"\d{1,2}[ ._-]*x[ ._-]*\d{1,3}|"
        r"e(?:p(?:isode)?)?[ ._-]*\d{1,3})(?!\d)", " ", value
    )
    value = SEASON.sub(" ", value)
    value = re.sub(r"\b(?:19|20)\d{2}\b", " ", value)
    value = TECH.sub(" ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return " ".join(value.split())[:110]


def parse_identity(value: str, category: str) -> Identity:
    raw = str(value or "").strip()
    episode = episode_numbers(raw)
    part = PART.search(_ascii(raw))
    if part and part.group(3) and int(part.group(2)) > int(part.group(3)):
        return Identity("", "conflict")
    pack = PACK.search(_ascii(raw))
    season = SEASON.search(_ascii(raw))
    years = {int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", raw)}
    if len(years) > 1:
        return Identity("", "conflict")
    title = cleaned_title(raw)
    if episode:
        kind = "episode"
        return Identity(title, kind, episode[0], episode[1],
                        None, next(iter(years), None))
    if pack:
        return Identity(title, "season_pack", int(pack.group(1)),
                        None, None, next(iter(years), None))
    if part:
        return Identity(title, "film_part", None, None,
                        int(part.group(1) or part.group(2)),
                        next(iter(years), None))
    kind = "anime_film" if category == "anime" else "film"
    return Identity(title, kind, int(season.group(1)) if season else None,
                    None, None, next(iter(years), None))


def video_identity(message, category: str) -> Identity:
    caption = video_title(message)
    filename = str(getattr(getattr(message, "file", None), "name", "") or "")
    stem = PurePath(filename).stem.replace("_", " ").replace(".", " ")
    principal = parse_identity(caption, category)
    secondary = parse_identity(stem, category)
    if principal.kind == "conflict":
        return principal
    if not principal.safe and secondary.safe:
        return secondary
    if principal.safe and secondary.safe:
        # Explicitly contradictory PART or EPISODE numbers are unsafe. A
        # generic source filename without these markers is not evidence.
        if (principal.episode is not None and secondary.episode is not None
                and (principal.season, principal.episode) !=
                (secondary.season, secondary.episode)):
            return Identity("", "conflict")
        if (principal.part is not None and secondary.part is not None
                and principal.part != secondary.part):
            return Identity("", "conflict")
        if (principal.year is not None and secondary.year is not None
                and principal.year != secondary.year):
            return Identity("", "conflict")
        if (principal.part is None and secondary.part is not None
                and principal.episode is None and principal.title == secondary.title):
            return Identity(principal.title, "film_part", part=secondary.part,
                            year=principal.year or secondary.year)
    return principal


def poster_identity(message, category: str) -> Identity:
    original = getattr(message, "raw_text", "") or ""
    heading = poster_heading(message)
    if not heading or TAG.fullmatch(heading):
        candidates = [line.strip() for line in original.splitlines()
                      if line.strip() and not TAG.fullmatch(line)]
        heading = candidates[0] if candidates else ""
    return parse_identity(heading, category)


def compatible(video: Identity, poster: Identity) -> float:
    if not video.safe or not poster.safe:
        return 0.0
    if video.year and poster.year and video.year != poster.year:
        return 0.0
    if poster.episode is not None:
        if (video.season, video.episode) != (poster.season, poster.episode):
            return 0.0
    if poster.part is not None and video.part != poster.part:
        return 0.0
    if poster.season is not None and video.season is not None:
        if poster.season != video.season:
            return 0.0
    if poster.kind == "episode" and video.kind != "episode":
        return 0.0
    if video.kind == "episode" and poster.kind == "film_part":
        return 0.0
    if video.kind != "episode" and poster.kind == "season_pack":
        return 0.0
    a, b = video.title, poster.title
    if a == b:
        return 1.0
    ratio = SequenceMatcher(None, a, b).ratio()
    # A typo may be accepted with a very high similarity; "Taxi 2"
    # must never be conflated with "Taxi 3" or a different sequel.
    if re.search(r"\d", a) or re.search(r"\d", b):
        return 0.0
    return ratio if ratio >= 0.97 else 0.0


def find_legacy_poster(video, posters, category: str, *, max_gap: int = 1600):
    identity = video_identity(video, category)
    if not identity.safe:
        return None
    ranked = []
    for photo in posters:
        if not getattr(photo, "photo", None):
            continue
        gap = int(video.id) - int(photo.id)
        if not 0 < gap <= max_gap:
            continue
        other = poster_identity(photo, category)
        score = compatible(identity, other)
        threshold = 0.97 if gap > 12 else 0.95
        if score >= threshold and (
            getattr(photo, "raw_text", "") or ""
        ).strip():
            ranked.append((score, gap, photo))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    if not ranked:
        return None
    if len(ranked) > 1:
        best, next_best = ranked[:2]
        # Same-title duplicate near the media: impossible to establish
        # which photo belongs to this upload. Preserve without deletion.
        if (best[0] - next_best[0] < 0.02
                and abs(best[1] - next_best[1]) <= 2):
            return None
        # Distant matches should not jump over many duplicate covers.
        if best[1] > 12 and best[0] - next_best[0] < 0.02:
            return None
    return ranked[0][2]


def youtube_url_for(message) -> str | None:
    """Only an explicit real YouTube video URL; never invent a trailer."""
    from urllib.parse import parse_qs, urlparse
    links = re.findall(r"https://[^\s<>\"']+", getattr(message, "raw_text", "") or "")
    for row in getattr(message, "buttons", None) or ():
        for button in row:
            links.append(str(getattr(button, "url", None) or getattr(
                getattr(button, "button", None), "url", "") or ""))
    for link in links:
        link = link.rstrip(".,;!)]}")
        try:
            url = urlparse(link)
            if url.scheme != "https" or url.username or url.password or url.port:
                continue
            host = (url.hostname or "").lower()
            if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
                if url.path == "/watch":
                    key = (parse_qs(url.query).get("v") or [""])[0]
                elif url.path.startswith(("/shorts/", "/embed/")):
                    key = url.path.split("/")[2]
                else:
                    continue
            elif host == "youtu.be":
                key = url.path.strip("/").split("/")[0]
            else:
                continue
            if YOUTUBE_ID.fullmatch(key):
                return "https://www.youtube.com/watch?v=" + key
        except ValueError:
            continue
    return None
