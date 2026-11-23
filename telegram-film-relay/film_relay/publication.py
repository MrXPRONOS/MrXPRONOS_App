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


def url_button_rows(movie_url: str, invitation_url: str = "", *, public_peer=None,
                    download_url: str | None = None, watch_label: str = "🎬 VOIR LE FILM") -> list[list[tuple[str, str]]]:
    """Historic optional rows; new public media use complete_public_video_rows.

    Order: watch in category library, CineRadar download, channel Secours,
    shared channel folder. The legacy invitation_url argument is ignored.
    """
    if not movie_url.startswith("https://t.me/c/"):
        raise ValueError("Le lien vidéo privé doit être un lien t.me/c validé.")
    from .rescue_channels import add_rescue_tuple_row
    buttons = [[(watch_label, movie_url)]]
    if download_url:
        # This points to a verified copy in the owner's central private
        # Telegram library. Never label an unverified/external URL as a download.
        from .radar_download_registry import is_bot_download_url
        if not is_bot_download_url(download_url):
            raise ValueError("Téléchargement : véritable lien du bot CinéRadar requis.")
        buttons.append([("⬇️ TÉLÉCHARGER LA VIDÉO", download_url)])
    rows = add_rescue_tuple_row(buttons, public_peer)
    rows.append([(FILM_FOLDER_BUTTON_TEXT, film_folder_url())])
    return rows

def complete_public_video_rows(movie_url: str, download_url: str, *, public_peer,
                               watch_label: str = "🎬 VOIR LE FILM"):
    """Fail closed unless all four public media buttons are independently valid."""
    if not download_url:
        raise RuntimeError("Téléchargement CineRadar absent : fiche publique non publiée.")
    from .rescue_channels import rescue_link_for
    from .radar_download_registry import is_bot_download_url
    rescue = rescue_link_for(public_peer)
    if not rescue:
        raise RuntimeError("Canal Secours dédié introuvable : fiche publique non publiée.")
    rows = url_button_rows(movie_url, public_peer=public_peer,
                           download_url=download_url, watch_label=watch_label)
    links = [url for row in rows for _, url in row]
    required = (movie_url, download_url, rescue, film_folder_url())
    if (not is_bot_download_url(download_url) or len(rows) != 4
            or any(len(row) != 1 for row in rows)
            or tuple(links) != required or len(set(links)) != 4):
        raise RuntimeError("Fiche CinéX : les quatre boutons ne sont pas conformes.")
    return rows


def verify_complete_public_video_poster(poster, public_peer,
                                        private_video_link: str, download_url: str):
    """Re-read the public post and verify all four exact destinations."""
    from .public_video_archive import has_verified_button
    try:
        complete_public_video_rows(private_video_link, download_url,
                                   public_peer=public_peer)
        from .rescue_channels import rescue_link_for
        expected = (private_video_link, download_url,
                    rescue_link_for(public_peer), film_folder_url())
    except (ValueError, RuntimeError, TypeError):
        return False
    if not poster or not getattr(poster, "photo", None):
        return False
    rows = getattr(poster, "buttons", None) or ()
    links = [getattr(getattr(button, "button", button), "url", None)
             for row in rows for button in row]
    return bool(len(rows) == 4 and all(len(row) == 1 for row in rows)
                and tuple(links) == expected
                and all(has_verified_button(poster, link) for link in expected))




def verify_complete_public_video_keyboard(message, public_peer,
                                          private_video_link: str, download_url: str,
                                          *, watch_label: str = "🎬 VOIR LE FILM") -> bool:
    """Verify the exact four URL buttons on the VIDEO itself, not just its poster."""
    try:
        expected_rows = complete_public_video_rows(
            private_video_link, download_url, public_peer=public_peer,
            watch_label=watch_label,
        )
    except (ValueError, RuntimeError, TypeError):
        return False
    buttons = getattr(message, "buttons", None) or ()
    if len(buttons) != 4 or any(len(row) != 1 for row in buttons):
        return False
    actual = [
        (str(getattr(getattr(btn, "button", btn), "text", "") or ""),
         str(getattr(getattr(btn, "button", btn), "url", "") or ""))
        for row in buttons for btn in row
    ]
    expected = [(label, url) for row in expected_rows for label, url in row]
    return actual == expected


async def send_public_poster_with_buttons(
    user_client, bot_client, public_peer, poster_message,
    description: str, private_movie_link: str, invite_link: str = "",
    *, download_url: str | None = None, watch_label: str = "🎬 VOIR LE FILM",
):
    """Bot sends a NEW photo with a caption and embedded URL keyboard.

    No fallback to a raw URL. On bot errors caller retains the staged private
    video so a later workflow can finish the public post without duplicates.
    """
    rows = complete_public_video_rows(
        private_movie_link, download_url, public_peer=public_peer,
        watch_label=watch_label)
    contents = await user_client.download_media(poster_message.media, file=bytes)
    if not contents:
        raise RuntimeError("Affiche inaccessible : photo non téléchargée ; aucune publication publique.")
    photo = io.BytesIO(contents)
    photo.name = "cinex_affiche.jpg"
    # A missing Secours link is a publication blocker, never omit a required
    # button silently. The link is loaded transiently from the safe runtime.
    library_button_rows(public_peer)
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
                              "voir le film" in label.casefold() or
                              "voir l'épisode" in label.casefold()) else
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
    poster_id: int, private_video_link: str, *, download_url: str | None = None,
):
    """Verified poster-first public video; no standalone movie uploads.

    A video is never sent until Telegram confirms the public picture and its
    link to the actual private movie. Checks the document ID after sending.
    """
    from .public_video_archive import (
        has_verified_button, is_video_message, video_document_id,
    )
    poster = await user_client.get_messages(public_peer, ids=int(poster_id))
    if (not poster or not (getattr(poster, "raw_text", "") or "").strip()
            or not verify_complete_public_video_poster(
                poster, public_peer, private_video_link, download_url)):
        raise RuntimeError(
            "Fiche publique incomplète : ses quatre boutons doivent précéder la vidéo."
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


async def post_public_video_by_bot_copy(
    user_client, bot_client, public_peer, private_peer, private_video,
    poster_id: int, private_video_link: str, description: str,
    *, download_url: str | None = None,
    watch_label: str = "🎬 VOIR LE FILM",
):
    """Bot-only server-side video copy; source must be an accessible library.

    Read-only verification still uses the existing session until the entire
    scanner is migrated. Never fall back to a personal-session upload when
    a bot copy fails, as that could create a duplicate.
    """
    from .public_video_archive import (
        has_verified_button, is_video_message, video_document_id,
    )
    poster = await user_client.get_messages(public_peer, ids=int(poster_id))
    if not verify_complete_public_video_poster(
            poster, public_peer, private_video_link, download_url):
        raise RuntimeError("Fiche publique sans quatre boutons : copie bot suspendue.")
    newest = [m async for m in user_client.iter_messages(public_peer, limit=1)]
    if not newest or int(newest[0].id) != int(poster_id):
        raise RuntimeError("Affiche plus récente absente : copie bot suspendue.")
    keyboard = make_button_keyboard(complete_public_video_rows(
        private_video_link, download_url, public_peer=public_peer,
        watch_label=watch_label,
    ))
    copied = await bot_client.copy_message(
        public_peer, private_peer, int(private_video.id),
        caption=rich_video_title(description), parse_mode="html", buttons=keyboard,
    )
    verified = await user_client.get_messages(public_peer, ids=int(copied.id))
    if (not is_video_message(verified)
            or video_document_id(verified) != video_document_id(private_video)
            or not verify_complete_public_video_keyboard(
                verified, public_peer, private_video_link, download_url,
                watch_label=watch_label)):
        raise RuntimeError(
            "Copie publique non vérifiée ou quatre boutons absents ; "
            "aucune répétition automatique.")
    return copied


def catalog_public_marker(title: str, season: int, episode: int) -> str:
    """Stable marker across source-channel reposts and interrupted transfers."""
    import hashlib
    from .episode_identity import canonical_title
    canonical = canonical_title(title)
    if not canonical:
        raise ValueError("Série sans identité canonique : publication impossible.")
    identity = f"{canonical}:S{int(season):02d}E{int(episode):02d}"
    return "#CXPAIR_" + hashlib.sha256(identity.encode()).hexdigest()[:18]


async def _find_recent_episode_poster(client, public_peer, marker: str):
    """Recover a previously bot-authored photo even if its response was lost."""
    if not hasattr(client, "iter_messages"):
        return None
    async for msg in client.iter_messages(public_peer, limit=300):
        if (getattr(msg, "photo", None)
                and marker in (getattr(msg, "raw_text", "") or "")):
            return int(msg.id)
    return None


async def _recover_episode_public_video(client, public_peer, poster_id: int,
                                        expected_document_id):
    """Recover a video sent after the known poster without sending another."""
    from .public_video_archive import is_video_message, video_document_id
    if not hasattr(client, "iter_messages"):
        return None
    async for msg in client.iter_messages(public_peer, limit=300):
        if int(msg.id) <= int(poster_id):
            break
        if (is_video_message(msg)
                and video_document_id(msg) == expected_document_id):
            return int(msg.id)
    return None



async def _recover_legacy_episode_pair(client, public_peer, document_id,
                                       private_url: str, season: int, episode: int):
    """Conservatively match an old, unreceipted public photo+video.

    Historical posts predate CXPAIR markers. Require matching Telegram media
    AND explicit SxxExx in the video caption AND a neighboring authentic
    photo whose button links to the *exact* private episode. Otherwise never
    infer an old receipt.
    """
    from .public_video_archive import (
        has_verified_button, is_video_message, video_document_id,
    )
    if not hasattr(client, "iter_messages"):
        return None
    code = f"S{int(season):02d}E{int(episode):02d}".casefold()
    async for msg in client.iter_messages(public_peer, limit=400):
        if (not is_video_message(msg)
                or video_document_id(msg) != document_id
                or code not in (getattr(msg, "raw_text", "") or "").casefold()):
            continue
        # Original pipeline posts poster immediately before each episode.
        poster_id = int(msg.id) - 1
        poster = await client.get_messages(public_peer, ids=poster_id)
        if (getattr(poster, "photo", None)
                and has_verified_button(poster, private_url)):
            return {"poster": poster_id, "video": int(msg.id)}
    return None


async def publish_catalog_episode_pairs(
    user_client, bot_client, public_peer, private_peer, private_id: int,
    series: dict, items: list, catalogue: dict, save_catalog, pause: float,
):
    """Publish each public pair exactly once, with crash-safe staged receipts.

    All media checks use the already-saved PRIVATE episode as reference: a
    newer source repost may use a different document or encoding without
    invalidating a previously verified public episode.
    """
    import asyncio
    from .public_video_archive import is_video_message, video_document_id
    from .text import clean_caption, private_message_link

    receipts = series.setdefault("public_episode_posts", {})
    staged = series.setdefault("pending_public_episode_posts", {})
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
        private_video = await user_client.get_messages(private_peer, ids=video_id)
        reference_doc = video_document_id(private_video)
        if not is_video_message(private_video) or not reference_doc:
            raise RuntimeError(f"Série : reçu privé invalide pour {key}")
        existing = receipts.get(key)
        if existing:
            stored_poster = await user_client.get_messages(
                public_peer, ids=int(existing["poster"]))
            stored_video = await user_client.get_messages(
                public_peer, ids=int(existing["video"]))
            if (getattr(stored_poster, "photo", None)
                    and is_video_message(stored_video)
                    and video_document_id(stored_video) == reference_doc):
                staged.pop(key, None)
                continue
            raise RuntimeError(
                f"Série {key} : reçu public incohérent ; aucune republication automatique")

        recovered_legacy = await _recover_legacy_episode_pair(
            user_client, public_peer, reference_doc, video_url,
            int(season), int(episode))
        if recovered_legacy:
            receipts[key] = {
                **recovered_legacy, "private_video": video_id,
            }
            staged.pop(key, None)
            save_catalog(catalogue)
            continue

        title = str(series.get("title") or row.get("title") or "")
        marker = catalog_public_marker(title, int(season), int(episode))
        source_poster = row.get("poster") or fallback
        entry = staged.setdefault(key, {})
        if entry.get("poster"):
            poster = await user_client.get_messages(
                public_peer, ids=int(entry["poster"]))
            if (not getattr(poster, "photo", None)
                    or marker not in (getattr(poster, "raw_text", "") or "")):
                raise RuntimeError(
                    f"Série {key} : affiche en cours introuvable, reprise bloquée")
        else:
            # Also protects a timeout after Telegram accepted the photo but
            # before the client obtained its response and could save the ID.
            found = await _find_recent_episode_poster(
                user_client, public_peer, marker)
            if found:
                entry["poster"] = int(found)
                save_catalog(catalogue)
            else:
                if not source_poster or not getattr(source_poster, "photo", None):
                    staged.pop(key, None)
                    raise RuntimeError(f"Série : vraie affiche manquante pour {key}")
                source_description = clean_caption(
                    getattr(source_poster, "raw_text", "") or title,
                    getattr(source_poster, "entities", None),
                ) or title
                description = (
                    f"📺 {title} — S{int(season):02d}E{int(episode):02d}\n"
                    + marker + "\n\n" + source_description
                )
                public_poster = await send_public_poster_with_buttons(
                    user_client, bot_client, public_peer, source_poster,
                    description, video_url,
                    download_url=private_record.get("download_url"),
                    watch_label="📺 VOIR L'ÉPISODE",
                )
                entry["poster"] = int(public_poster.id)
                save_catalog(catalogue)
                await asyncio.sleep(pause)

        # A prior send may have succeeded even though the video response was
        # lost; check Telegram before any attempt to send again.
        found_video = await _recover_episode_public_video(
            user_client, public_peer, int(entry["poster"]), reference_doc)
        if found_video:
            entry["video"] = int(found_video)
            save_catalog(catalogue)
        if not entry.get("video"):
            if entry.get("video_send_uncertain"):
                raise RuntimeError(
                    f"Série {key} : transfert public incertain ; vérification "
                    "manuelle nécessaire avant une autre tentative")
            description = f"📺 {title} — S{int(season):02d}E{int(episode):02d}"
            try:
                # Send the VERIFIED private copy, never a mismatched source
                # repost whose document ID or encoding could have changed.
                if not hasattr(bot_client, "copy_message"):
                    raise RuntimeError("Le bot CineX doit pouvoir copier les vidéos avec boutons.")
                public_video = await post_public_video_by_bot_copy(
                    user_client, bot_client, public_peer, private_peer,
                    private_video, int(entry["poster"]), video_url, description,
                    download_url=private_record.get("download_url"),
                    watch_label="📺 VOIR L'ÉPISODE",
                )
            except Exception:
                entry["video_send_uncertain"] = True
                save_catalog(catalogue)
                raise
            entry["video"] = int(public_video.id)
            entry.pop("video_send_uncertain", None)
            save_catalog(catalogue)

        receipts[key] = {
            "poster": int(entry["poster"]), "video": int(entry["video"]),
            "private_video": video_id,
        }
        staged.pop(key, None)
        save_catalog(catalogue)
        await asyncio.sleep(pause)
