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
FILM_FOLDER_BUTTON_TEXT = "📁 Rejoindre le dossier"


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


def url_button_rows(movie_url: str, invitation_url: str = "", *, public_peer=None) -> list[list[tuple[str, str]]]:
    """Two movie buttons: film in green; Telegram movie folder in red.

    The old invitation URL is intentionally ignored: the second button is
    always the shared Telegram films folder, across Classic and Désir.
    """
    if not movie_url.startswith("https://t.me/c/"):
        raise ValueError("Le lien vidéo privé doit être un lien t.me/c validé.")
    from .rescue_channels import add_rescue_tuple_row
    rows = add_rescue_tuple_row([
        [("🎬 REGARDER LE FILM", movie_url)],
    ], public_peer)
    rows.append([(FILM_FOLDER_BUTTON_TEXT, film_folder_url())])
    return rows


async def send_public_poster_with_buttons(
    user_client, bot_client, public_peer, poster_message,
    description: str, private_movie_link: str, invite_link: str = "",
):
    """Bot sends a NEW photo with a caption and embedded URL keyboard.

    No fallback to a raw URL. On bot errors caller retains the staged private
    video so a later workflow can finish the public post without duplicates.
    """
    contents = await user_client.download_media(poster_message.media, file=bytes)
    if not contents:
        raise RuntimeError("Affiche inaccessible : photo non téléchargée ; aucune publication publique.")
    photo = io.BytesIO(contents)
    photo.name = "cinex_affiche.jpg"
    # A missing Secours link is a publication blocker, never omit a required
    # button silently. The link is loaded transiently from the safe runtime.
    library_button_rows(public_peer)
    rows = url_button_rows(private_movie_link, invite_link, public_peer=public_peer)
    keyboard = make_button_keyboard(rows)
    return await bot_client.send_file(
        public_peer, photo, caption=rich_caption(description),
        parse_mode="html", buttons=keyboard, force_document=False
    )


def library_button_rows(public_peer):
    """Exactly two buttons on a library poster: Secours and the shared folder.

    Resolve the invitation from the verified runtime ledger; never hardcode or
    persist an invitation in a repository.
    """
    from .rescue_channels import BUTTON_TEXT, rescue_link_for
    rescue_url = rescue_link_for(public_peer)
    if not rescue_url:
        raise RuntimeError(
            "Lien du canal Secours absent ou non vérifié : publication "
            "de la fiche privée suspendue."
        )
    return [[(BUTTON_TEXT, rescue_url)],
            [(FILM_FOLDER_BUTTON_TEXT, film_folder_url())]]


def make_button_keyboard(rows):
    from .bot_http import url_button
    return [
        [url_button(
            label, url, style=(
                "success" if ("télécharger" in label.casefold() or
                              "regarder" in label.casefold() or
                              "voir le film" in label.casefold()) else
                "danger" if "secours" in label.casefold() else "primary"
            ),
        ) for label, url in row]
        for row in rows
    ]


async def verify_library_bot(bot_client, private_peer):
    """Bot API inline keyboards require publishing rights on the private channel."""
    me = await bot_client.get_me()
    try:
        perms = await bot_client.get_permissions(private_peer, me)
    except Exception as exc:
        raise RuntimeError(
            "Le bot CineX doit être ajouté comme administrateur de la "
            "vidéothèque (autorisation Publier des messages)."
        ) from exc
    if not (getattr(perms, "is_creator", False) or
            (getattr(perms, "is_admin", False) and
             getattr(perms, "post_messages", False))):
        raise RuntimeError(
            "Bot CineX sans droit de publication dans la vidéothèque."
        )


async def send_library_poster_with_buttons(
    user_client, bot_client, private_peer, public_peer,
    poster_message, description: str,
):
    """Send the real original image + synopsis + Secours/Folder keyboard."""
    import io
    rows = library_button_rows(public_peer)
    photo = await user_client.download_media(poster_message.media, file=bytes)
    if not photo:
        raise RuntimeError("Affiche privée absente : aucune vidéo ne sera envoyée.")
    stream = io.BytesIO(photo)
    stream.name = "cinex_videotheque.jpg"
    return await bot_client.send_file(
        private_peer, stream, caption=rich_caption(description, private=True),
        parse_mode="html", buttons=make_button_keyboard(rows),
        force_document=False,
    )


async def post_public_video_after_poster(
    user_client, public_peer, movie_message, description: str,
    poster_id: int, private_video_link: str,
):
    """Verified poster-first public video; no standalone movie uploads.

    A video is never sent until Telegram confirms the public picture and its
    link to the actual private movie. Checks the document ID after sending.
    """
    from .public_video_archive import (
        has_verified_button, is_video_message, video_document_id,
    )
    poster = await user_client.get_messages(public_peer, ids=int(poster_id))
    if (not poster or not getattr(poster, "photo", None)
            or not (getattr(poster, "raw_text", "") or "").strip()
            or not has_verified_button(poster, private_video_link)):
        raise RuntimeError(
            "Fiche publique absente ou sans bouton vidéothèque : vidéo non publiée."
        )
    current = [m async for m in user_client.iter_messages(public_peer, limit=1)]
    if not current or int(current[0].id) != int(poster_id):
        raise RuntimeError(
            "La dernière publication n'est pas la fiche de ce film ; "
            "vidéo publique suspendue pour éviter un mauvais rattachement."
        )
    sent = await user_client.send_file(
        public_peer, movie_message.media,
        caption=rich_video_title(description), parse_mode="html",
    )
    verified = await user_client.get_messages(public_peer, ids=int(sent.id))
    expected_doc = video_document_id(movie_message)
    if (not is_video_message(verified)
            or not expected_doc
            or video_document_id(verified) != expected_doc):
        raise RuntimeError("La vidéo publique ne correspond pas au média source.")
    return sent


async def publish_catalog_episode_pairs(
    user_client, bot_client, public_peer, private_peer, private_id: int,
    series: dict, items: list, catalogue: dict, save_catalog, pause: float,
):
    """Publish a real cover+synopsis then video for every new TV/anime episode.

    The existing season-index cards stay intact. Per-episode Telegram receipts
    are saved after both public messages are verified, so interrupted runs can
    resume without reposting completed episodes.
    """
    import asyncio
    from .public_video_archive import is_video_message, video_document_id
    from .text import clean_caption, private_message_link
    receipts = series.setdefault("public_episode_posts", {})
    fallback = next((r.get("poster") for r in items
                     if r.get("poster") is not None), None)
    for row in sorted(items, key=lambda r: (r["season"], r["episode"])):
        season, episode = str(row["season"]), str(row["episode"])
        key = f"S{int(season):02d}E{int(episode):02d}"
        private_record = series.get("episodes", {}).get(season, {}).get(episode)
        if not private_record:
            raise RuntimeError(f"Série : vidéo privée absente pour {key}")
        video_id = int(private_record["message_id"])
        video_url = private_message_link(private_id, video_id)
        existing = receipts.get(key)
        if existing:
            stored_poster = await user_client.get_messages(
                public_peer, ids=int(existing["poster"]))
            stored_video = await user_client.get_messages(
                public_peer, ids=int(existing["video"]))
            if (getattr(stored_poster, "photo", None)
                    and is_video_message(stored_video)
                    and video_document_id(stored_video) == video_document_id(row["video"])):
                continue
            raise RuntimeError(
                f"Série {key} : reçu public incohérent ; reprise bloquée pour éviter un doublon")
        source_poster = row.get("poster") or fallback
        if not source_poster or not getattr(source_poster, "photo", None):
            raise RuntimeError(f"Série : vraie affiche manquante pour {key}")
        private_video = await user_client.get_messages(private_peer, ids=video_id)
        if (not is_video_message(private_video)
                or video_document_id(private_video) != video_document_id(row["video"])):
            raise RuntimeError(f"Série : vidéothèque non confirmée pour {key}")

        title = str(series.get("title") or row.get("title") or "Série")
        source_description = clean_caption(
            getattr(source_poster, "raw_text", "") or title,
            getattr(source_poster, "entities", None),
        ) or title
        # Include episode number in the poster heading so viewers and the
        # rotation can distinguish all episodes of one season.
        description = (
            f"📺 {title} — S{int(season):02d}E{int(episode):02d}\n\n"
            + source_description
        )
        public_poster = await send_public_poster_with_buttons(
            user_client, bot_client, public_peer, source_poster,
            description, video_url,
        )
        await asyncio.sleep(pause)
        public_video = await post_public_video_after_poster(
            user_client, public_peer, row["video"], description,
            int(public_poster.id), video_url,
        )
        receipts[key] = {
            "poster": int(public_poster.id), "video": int(public_video.id),
            "private_video": video_id,
        }
        save_catalog(catalogue)
        await asyncio.sleep(pause)
