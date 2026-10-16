"""CinéX Telegram rich captions and URL buttons for a BOT-authored public photo.

The personal user session can read allowed source posts and send private media,
but only a bot session may attach an inline keyboard to a public post.
"""
from __future__ import annotations

import io
import re
from html import escape

from .text import first_title

META = re.compile(
    r"^(?P<label>Titre(?: original)?|Genre|Durée|Année|Sortie|Réalisateur|"
    r"Acteurs?|Casting|Langue|Synopsis|Résumé)\s*:\s*(?P<value>.*)$",
    re.IGNORECASE,
)


def rich_caption(description: str, *, private: bool = False) -> str:
    """Safe, readable HTML caption, bounded by Telegram's 1024 visible chars."""
    original = (description or "").strip()[:820]
    if not original:
        original = "Film"
    title = first_title(original).strip()
    lines = original.splitlines()
    # Preserve all metadata, but avoid repeating an identical first title line.
    tail = lines[1:] if lines else []
    pieces = [f"<b>🎬 {escape(title)}</b>"]
    if tail:
        pieces.append("")
    for line in tail:
        stripped = line.strip()
        if not stripped:
            if pieces and pieces[-1] != "":
                pieces.append("")
            continue
        match = META.match(stripped)
        if match:
            label, value = match.group("label"), match.group("value")
            if label.casefold() in ("synopsis", "résumé"):
                pieces.append(f"<b>{escape(label)} :</b> <i>{escape(value)}</i>")
            else:
                pieces.append(f"<b>{escape(label)} :</b> {escape(value)}")
        else:
            pieces.append(escape(stripped))
    while pieces and not pieces[-1]:
        pieces.pop()
    if not private:
        pieces.extend(["", "<i>👇 Accède au film avec le bouton ci-dessous.</i>"])
    return "\n".join(pieces)


def rich_video_title(description: str) -> str:
    return f"<b>🎞️ {escape(first_title(description))}</b>"


def url_button_rows(movie_url: str, invitation_url: str = "") -> list[list[tuple[str, str]]]:
    """Describe actual clickable buttons independently of the Telegram library."""
    if not movie_url.startswith("https://t.me/c/"):
        raise ValueError("Le lien vidéo privé doit être un lien t.me/c validé.")
    rows = [[("🎬 REGARDER LE FILM", movie_url)]]
    if invitation_url and invitation_url.startswith("https://t.me/"):
        rows.append([("🔐 REJOINDRE LA VIDÉOTHÈQUE", invitation_url)])
    return rows


async def send_public_poster_with_buttons(
    user_client, bot_client, public_peer, poster_message,
    description: str, private_movie_link: str, invite_link: str = "",
):
    """Bot sends a NEW photo with a caption and embedded URL keyboard.

    No fallback to a raw URL. On bot errors caller retains the staged private
    video so a later workflow can finish the public post without duplicates.
    """
    from telethon import Button

    contents = await user_client.download_media(poster_message.media, file=bytes)
    if not contents:
        raise RuntimeError("Affiche inaccessible : photo non téléchargée ; aucune publication publique.")
    photo = io.BytesIO(contents)
    photo.name = "cinex_affiche.jpg"
    rows = url_button_rows(private_movie_link, invite_link)
    keyboard = [[Button.url(label, url) for label, url in row] for row in rows]
    return await bot_client.send_file(
        public_peer, photo, caption=rich_caption(description),
        parse_mode="html", buttons=keyboard, force_document=False
    )
