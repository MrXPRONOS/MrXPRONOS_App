"""Clean captions from promotional links, keeping the film's description."""
from __future__ import annotations

import re
from typing import Any

URL_RE = re.compile(r"(?i)(?:https?://|www\.|t\.me/|telegram\.me/|bit\.ly/|tinyurl\.com/)\S+")
HANDLE_RE = re.compile(r"(?<!\w)@[a-zA-Z0-9_]{5,32}\b")
PROMO_RE = re.compile(r"(?i)\b(abonnez[- ]vous|rejoignez notre|notre canal|cliquez ici|subscribe|join our channel|publicit[eé])\b")
WHITESPACE = re.compile(r"\n{3,}")


def _remove_hidden_urls(text: str, entities: Any) -> str:
    """Remove clickable hidden links based on Telegram UTF-16 offsets."""
    if not entities:
        return text
    encoded = text.encode("utf-16-le")
    ranges = []
    for item in entities:
        kind = type(item).__name__
        if kind in ("MessageEntityTextUrl", "MessageEntityUrl", "MessageEntityMention"):
            start = int(getattr(item, "offset", 0)) * 2
            end = start + int(getattr(item, "length", 0)) * 2
            ranges.append((start, end))
    for start, end in sorted(ranges, reverse=True):
        encoded = encoded[:start] + encoded[end:]
    return encoded.decode("utf-16-le", errors="replace")


def clean_caption(text: str, entities: Any = None) -> str:
    text = _remove_hidden_urls(text or "", entities)
    text = URL_RE.sub("", text)
    text = HANDLE_RE.sub("", text)
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        line = line.strip(" -•\t")
        if not line or PROMO_RE.search(line):
            continue
        cleaned_lines.append(line)
    return WHITESPACE.sub("\n\n", "\n".join(cleaned_lines)).strip()


def first_title(text: str) -> str:
    lines = [re.sub(r"^[🎬🎞🍿📽\s:]+", "", x).strip() for x in text.splitlines() if x.strip()]
    return (lines[0] if lines else "Film")[:130]


def caption_with_link(description: str, message_link: str, invite_link: str = "") -> str:
    footer = f"🎬 Voir le film : {message_link}"
    if invite_link:
        footer += f"\n🔐 Rejoindre le canal privé : {invite_link}"
    # Telegram captions have a limit. Reserve room for the full footer.
    cap = max(0, 1024 - len(footer) - 2)
    truncated = description[:cap]
    if len(description) > cap and cap > 1:
        truncated = truncated[:-1].rstrip() + "…"
    return f"{truncated}\n\n{footer}" if truncated else footer


def private_message_link(private_peer_id: int, post_id: int) -> str:
    """Telethon PeerChannel ids are represented with a -100 prefix."""
    s = str(private_peer_id)
    if not s.startswith("-100") or len(s) <= 4:
        raise ValueError("Destination privée : ID de canal Telegram invalide (-100...).")
    return f"https://t.me/c/{s[4:]}/{int(post_id)}"


def private_poster_caption(description: str) -> str:
    """Description sous l'affiche privée, sans aucun lien ajouté."""
    description = (description or "").strip()
    if len(description) <= 1024:
        return description
    return description[:1023].rstrip() + "…"


def private_video_caption(description: str) -> str:
    """Titre seul sous la vidéo; aucun lien et aucune référence technique."""
    return f"🎬 {first_title(description)}"[:1024]


# Titles are presentation only: these helpers never authorize a poster/video
# association or a protected source. Call them after the existing media guards.
_TITLE_FIELD = re.compile(r"(?i)^titre(?:\s+du\s+film|\s+original)?\s*:\s*(.+)$")
_METADATA_FIELD = re.compile(
    r"(?i)^(?:genres?|catégorie|durée|année|date|sortie|réalisateur|acteurs?|"
    r"casting|langue|synopsis|résumé|description|qualité|format|source|"
    r"épisodes?|saison|pays|production|note|téléchargement)\s*[:=]"
)
_GENERIC_TITLE = re.compile(
    r"(?i)^(?:#?\s*(?:films?|movies?|vidéos?|videos?|fichiers?|uploads?|"
    r"documents?|cinéx|cinex|nouveau film|titre non identifié|"
    r"film cinéx(?: désir)?|vidéo cinéx))(?:[\s._-]*\d+)?$"
)


def _title_candidate(value: str) -> str:
    value = re.sub(r"^[\W_]+", "", str(value or "").strip())
    value = re.sub(r"\s+", " ", value).strip(" -:•")
    if (not value or _GENERIC_TITLE.fullmatch(value)
            or _METADATA_FIELD.match(value)
            or value.isdecimal()
            or re.fullmatch(r"(?i)(?:[a-f0-9]{12,}|S\d+E\d+)", value)):
        return ""
    from .title_guard import GENERIC_UPLOAD, tokens
    if GENERIC_UPLOAD.fullmatch(value):
        return ""
    if not tokens(value) and not re.fullmatch(r"[A-Za-zÀ-ÿ]{1,2}", value):
        return ""
    return value[:130]


def descriptive_title(text: str) -> str:
    """Prefer an explicit Titre field over the first meaningful heading."""
    lines = clean_caption(str(text or "")).splitlines()
    for line in lines:
        normalized = re.sub(r"^[\W_]+", "", line).strip()
        match = _TITLE_FIELD.match(normalized)
        if match:
            title = _title_candidate(match.group(1))
            if title:
                return title
    for line in lines[:6]:
        if line.lstrip().startswith("#"):
            continue
        normalized = re.sub(r"^[\W_]+", "", line).strip()
        if _METADATA_FIELD.match(normalized):
            # The lines following metadata may be a multiline synopsis.
            break
        if _TITLE_FIELD.match(normalized):
            continue
        # A prose paragraph is not a reliable movie title.
        if len(normalized) > 130 or len(normalized.split()) > 16:
            continue
        title = _title_candidate(normalized)
        if title:
            return title
    return ""


def resolved_media_title(poster=None, video=None, *, preferred="", description="") -> str:
    """Use supplied metadata or real file names, never invent a title."""
    from .title_guard import filename_title, RELEASE_MARKER, tokens
    from .matching import filename_of
    for value in (preferred, description, getattr(poster, "raw_text", ""),
                  getattr(video, "raw_text", "")):
        title = descriptive_title(value)
        if title:
            return title
    # Preserve the source filename's capitalization where Telegram exposes it.
    name = (getattr(getattr(video, "file", None), "name", None)
            or filename_of(video))
    if name:
        candidate = filename_title(str(name))
        for marker in RELEASE_MARKER.finditer(candidate):
            prefix = candidate[:marker.start()].strip(" -")
            if tokens(prefix):
                candidate = prefix
                break
        title = _title_candidate(candidate)
        if title:
            return title
    return "Titre non identifié"


def description_with_title(title: str, *descriptions: str) -> str:
    """A real title first, followed by distinct, source-provided details."""
    result = [title or "Titre non identifié"]
    seen = {result[0].casefold()}
    for description in descriptions:
        for line in clean_caption(str(description or "")).splitlines():
            line = line.strip()
            normalized = re.sub(r"^[\W_]+", "", line).strip()
            match = _TITLE_FIELD.match(normalized)
            if match and match.group(1).strip().casefold() == result[0].casefold():
                continue
            if (not line or _GENERIC_TITLE.fullmatch(normalized)
                    or line.startswith("#CXSTOCK_")
                    or line.startswith("#CINEX_VIDEO_")
                    or normalized.casefold() in seen):
                continue
            seen.add(normalized.casefold())
            result.append(line)
    return "\n".join(result)
