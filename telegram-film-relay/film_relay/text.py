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
