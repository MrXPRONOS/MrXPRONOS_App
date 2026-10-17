"""CinéX Telegram rich captions and URL buttons for a BOT-authored public photo.

The personal user session can read allowed source posts and send private media,
but only a bot session may attach an inline keyboard to a public post.
"""
from __future__ import annotations

import io
import os
import re
from html import escape

from .text import first_title

# User's Telegram shared-chat folder: replaces the old private-library button.
DEFAULT_FILM_FOLDER_URL = "https://t.me/addlist/ZmW4vfwcrMAwNzJk"
FILM_FOLDER_BUTTON_TEXT = "🔥 PLUS DE FILMS ? REJOINS LA TEAM !"


def film_folder_url() -> str:
    url = (os.getenv("CINEX_FILM_FOLDER_URL") or DEFAULT_FILM_FOLDER_URL).strip()
    if not url.startswith("https://t.me/addlist/"):
        raise ValueError("Le lien du dossier films doit être un lien Telegram t.me/addlist.")
    return url


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
        pieces.extend([
            "",
            "<i>👇 Regarde ce film, puis rejoins notre team pour découvrir encore plus de films !</i>",
            f'🎞️ <a href="{escape(film_folder_url(), quote=True)}">DÉCOUVRE ENCORE PLUS DE FILMS 🎬</a>',
        ])
    return "\n".join(pieces)


def rich_video_title(description: str) -> str:
    return f"<b>🎞️ {escape(first_title(description))}</b>"


def url_button_rows(movie_url: str, invitation_url: str = "") -> list[list[tuple[str, str]]]:
    """Two movie buttons: film in green; Telegram movie folder in red.

    The old invitation URL is intentionally ignored: the second button is
    always the shared Telegram films folder, across Classic and Désir.
    """
    if not movie_url.startswith("https://t.me/c/"):
        raise ValueError("Le lien vidéo privé doit être un lien t.me/c validé.")
    return [
        [("🎬 REGARDER LE FILM", movie_url)],
        [(FILM_FOLDER_BUTTON_TEXT, film_folder_url())],
    ]


async def send_public_poster_with_buttons(
    user_client, bot_client, public_peer, poster_message,
    description: str, private_movie_link: str, invite_link: str = "",
):
    """Bot sends a NEW photo with a caption and embedded URL keyboard.

    No fallback to a raw URL. On bot errors caller retains the staged private
    video so a later workflow can finish the public post without duplicates.
    """
    from .bot_http import url_button

    contents = await user_client.download_media(poster_message.media, file=bytes)
    if not contents:
        raise RuntimeError("Affiche inaccessible : photo non téléchargée ; aucune publication publique.")
    photo = io.BytesIO(contents)
    photo.name = "cinex_affiche.jpg"
    rows = url_button_rows(private_movie_link, invite_link)
    keyboard = [
        [url_button(label, url, style="success" if index == 0 else "danger")
         for label, url in row]
        for index, row in enumerate(rows)
    ]
    return await bot_client.send_file(
        public_peer, photo, caption=rich_caption(description),
        parse_mode="html", buttons=keyboard, force_document=False
    )
