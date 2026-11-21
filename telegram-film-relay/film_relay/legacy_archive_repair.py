"""Repair safely recognizable legacy CinéX media across configured channels.

Default is read-only. In apply mode, create/verify PRIVATE poster+video and a
PUBLIC bot-owned poster pointing to that exact saved video. This module NEVER
deletes any Telegram message. Rotation remains a separate verified operation.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import logging
import os

from .bot_http import BotHTTPClient, url_button
from .legacy_neighbor_matching import find_neighbor_pair, identity_for_pair
from .legacy_media_identity import (
    compatible, find_legacy_poster, poster_identity, video_identity, youtube_url_for,
)
from .public_video_archive import (
    is_video_message, has_verified_button, video_document_id, video_title,
)
from .publication import film_folder_url, library_button_rows, make_button_keyboard, rich_caption
from .rescue_channels import rescue_link_for
from .text import clean_caption, private_message_link
from .ten_video_rotation import category_targets, split_recent_and_old, movie_button_target

LOG = logging.getLogger("cinex.legacy_archive_repair")
MAX_HISTORY = 4000


def cover_caption(poster, video, category: str, *, identity=None, extra_text: str = "") -> str:
    """Preserve original description, inserting episode/part identity above it."""
    ident = identity or identity_for_pair(video, poster, category, extra_text)
    raw = clean_caption(getattr(poster, "raw_text", "") or "").strip()
    if extra_text.strip():
        raw = (raw + "\n" + clean_caption(extra_text)).strip()
    if ident.kind == "unknown":
        symbol = "📺" if category in ("anime", "series") else "🎬"
        prefix = f"{symbol} {ident.title}"
    elif ident.kind == "episode":
        prefix = f"📺 {ident.title} — S{ident.season:02d}E{ident.episode:02d}"
    elif ident.kind == "film_part":
        prefix = f"🎬 {ident.title} — Partie {ident.part}"
    elif ident.kind == "season_pack":
        prefix = f"📺 {ident.title} — Saison {ident.season} intégrale"
    else:
        prefix = f"🎬 {ident.title}"
    # Source caption may have a generic title; the explicit media identity
    # first is what keeps multiple parts and episodes distinct.
    return (prefix + "\n" + raw)[:790]


def find_verified_public_link(posts, video, category: str, private_id: int,
                              private_video_id: int, rescue_url: str, *, reference=None):
    target = private_message_link(private_id, private_video_id)
    found = []
    for post in posts:
        if not getattr(post, "photo", None):
            continue
        if movie_button_target(post, private_id) != private_video_id:
            continue
        if compatible(reference or video_identity(video, category),
                      poster_identity(post, category)) < 0.95:
            continue
        if all(has_verified_button(post, link)
               for link in (target, rescue_url, film_folder_url())):
            found.append(post)
    return found[0] if len(found) == 1 else None


def find_verified_private_pair(private_messages, video, category: str, *, rescue_url=None, reference=None):
    """Prefer exact Telegram document ID, never a same-title substitute."""
    expected = video_document_id(video)
    if not expected:
        return None
    paired = []
    photos = [m for m in private_messages if getattr(m, "photo", None)]
    for item in private_messages:
        if not is_video_message(item) or video_document_id(item) != expected:
            continue
        for photo in photos:
            if not (0 < item.id - photo.id <= 3):
                continue
            if (compatible(reference or video_identity(video, category),
                           poster_identity(photo, category)) >= 0.95
                    and (not rescue_url or all(has_verified_button(photo, link)
                       for link in (rescue_url, film_folder_url())))): 
                paired.append((item, photo))
    return paired[0] if len(paired) == 1 else None


def public_buttons(url: str, public, poster, *, category: str):
    from .rescue_channels import add_rescue_button_row
    name = "📺 REGARDER L'ÉPISODE" if category in ("anime", "series") else "🎬 VOIR LE FILM"
    result = [[url_button(name, url, style="success")]]
    youtube = youtube_url_for(poster)
    if youtube:
        result.append([url_button("▶️ YouTube", youtube, style="primary")])
    result = add_rescue_button_row(result, public)
    result.append([url_button("📁 Rejoindre le dossier", film_folder_url(), style="primary")])
    return result


def public_poster_verified(message, video, category, url: str, public, *, reference=None):
    rescue = rescue_link_for(public)
    return bool(
        getattr(message, "photo", None)
        and compatible(reference or video_identity(video, category),
                       poster_identity(message, category)) >= 0.95
        and rescue
        and all(has_verified_button(message, link)
                for link in (url, rescue, film_folder_url()))
    )


async def repair_channel(client, bot, category: str, public, private,
                         *, apply: bool, max_repaired: int = 2,
                         history: int = MAX_HISTORY):
    from telethon import utils
    public_id, private_id = utils.get_peer_id(public), utils.get_peer_id(private)
    if public_id == private_id or not str(private_id).startswith("-100"):
        raise RuntimeError("L'archive doit rester un canal privé distinct")
    messages = [m async for m in client.iter_messages(public, limit=history)]
    recent, old = split_recent_and_old(messages, category)
    posters = [m for m in messages if getattr(m, "photo", None)]
    report = {
        "category": category, "public": public_id, "private": private_id,
        "protected": len(recent), "older": len(old), "recognized": 0,
        "private_existing": 0, "private_created": 0, "public_linked": 0,
        "unmatched": 0, "adjacent_recognized": 0, "ambiguous": 0, "skipped": 0, "errors": 0,
        "mode": "apply" if apply else "simulation",
    }
    if len(recent) < 10:
        return report
    rescue = rescue_link_for(public)
    if apply and not rescue:
        raise RuntimeError(f"{category}: invitation Secours non vérifiée")
    if apply:
        me = await client.get_me()
        for destination in (public, private):
            perm = await client.get_permissions(destination, me)
            if not (getattr(perm, "is_creator", False) or
                    (getattr(perm, "is_admin", False)
                     and getattr(perm, "post_messages", False))):
                raise RuntimeError(f"{category}: droits d'envoi insuffisants")
        bot_me = await bot.get_me()
        for destination in (public, private):
            perm = await bot.get_permissions(destination, bot_me)
            if not (getattr(perm, "is_creator", False) or
                    (getattr(perm, "is_admin", False)
                     and getattr(perm, "post_messages", False))):
                raise RuntimeError(f"{category}: droits de publication du bot insuffisants")
    private_messages = ([m async for m in client.iter_messages(private, limit=history)]
                        if apply else [])
    repaired = 0
    for video in reversed(old):
        if repaired >= max_repaired:
            break
        identity = video_identity(video, category)
        poster = find_legacy_poster(video, posters, category)
        neighbor = None
        if poster is None:
            neighbor = find_neighbor_pair(video, messages, category)
            if neighbor:
                poster = neighbor.poster
                identity = neighbor.identity
                report["adjacent_recognized"] += 1
        if poster is None or not identity.safe:
            report["unmatched"] += 1
            continue
        extra = neighbor.extra_text if neighbor else ""
        identity = identity_for_pair(video, poster, category, extra)
        if not identity.safe:
            report["unmatched"] += 1
            continue
        if getattr(video, "noforwards", False) or getattr(poster, "noforwards", False):
            report["skipped"] += 1
            continue
        report["recognized"] += 1
        if not apply:
            LOG.info("[SIMULATION] %s old video #%s -> poster #%s (%s)",
                     category, video.id, poster.id, identity)
            continue
        try:
            pair = find_verified_private_pair(private_messages, video, category,
                                              rescue_url=rescue, reference=identity)
            if pair:
                private_video_id = pair[0].id
                report["private_existing"] += 1
            else:
                caption = cover_caption(poster, video, category,
                                        identity=identity, extra_text=extra)
                raw = await client.download_media(poster.media, file=bytes)
                if not raw:
                    raise RuntimeError("Affiche inaccessible")
                # Resume an interrupted copy only when the very last private
                # message is a matching, button-verified photo. Any competing
                # message defeats the retry, preventing accidental mispairing.
                latest_private = sorted(private_messages, key=lambda m: m.id, reverse=True)
                pending = next((item for item in latest_private[:1]
                    if getattr(item, "photo", None)
                    and compatible(identity,
                                   poster_identity(item, category)) >= 0.95
                    and all(has_verified_button(item, link) for link in
                            (rescue, film_folder_url()))), None)
                if pending:
                    verified_photo = pending
                    LOG.info("%s : photo privée inachevée #%s reprise",
                             category, pending.id)
                else:
                    private_image = io.BytesIO(raw)
                    private_image.name = "cinex_archivage.jpg"
                    private_photo = await bot.send_file(
                        private, private_image,
                        caption=rich_caption(caption, private=True),
                        parse_mode="html",
                        buttons=make_button_keyboard(library_button_rows(public)),
                    )
                    verified_photo = await client.get_messages(private, ids=private_photo.id)
                    if verified_photo:
                        private_messages.append(verified_photo)
                if not getattr(verified_photo, "photo", None):
                    raise RuntimeError("Photo privée non vérifiée")
                await asyncio.sleep(12)
                private_video = await client.send_file(
                    private, video.media,
                    caption=caption.splitlines()[0],
                )
                verified_video = await client.get_messages(private, ids=private_video.id)
                if (not is_video_message(verified_video)
                        or video_document_id(verified_video) != video_document_id(video)
                        or not 0 < verified_video.id - verified_photo.id <= 3):
                    raise RuntimeError("Vidéo privée non vérifiée")
                private_video_id = verified_video.id
                private_messages.extend((verified_photo, verified_video))
                report["private_created"] += 1
            target = private_message_link(private_id, private_video_id)
            # Old poster may be uneditable and far from its media. A new,
            # bot-owned cover is created without removing the old one.
            existing_public = find_verified_public_link(
                posters, video, category, private_id, private_video_id, rescue,
                reference=identity)
            if existing_public:
                report["public_linked"] += 1
                repaired += 1
                continue
            public_image = io.BytesIO(await client.download_media(poster.media, file=bytes))
            public_image.name = "cinex_archivage.jpg"
            if not public_image.getbuffer().nbytes:
                raise RuntimeError("Affiche publique inaccessible")
            new_post = await bot.send_file(
                public, public_image,
                caption=rich_caption(cover_caption(
                    poster, video, category, identity=identity, extra_text=extra)),
                parse_mode="html",
                buttons=public_buttons(target, public, poster, category=category),
            )
            verified_public = await client.get_messages(public, ids=new_post.id)
            if not public_poster_verified(
                    verified_public, video, category, target, public,
                    reference=identity):
                raise RuntimeError("Boutons publics non vérifiés")
            posters.append(verified_public)
            report["public_linked"] += 1
            repaired += 1
            LOG.info("%s : archive vidéo #%s -> privé #%s, affiche publique #%s",
                     category, video.id, private_video_id, verified_public.id)
            await asyncio.sleep(30)
        except Exception as exc:
            if type(exc).__name__ in ("FloodWaitError", "PeerFloodError"):
                raise
            report["errors"] += 1
            LOG.exception("%s : ancien média #%s conservé pour réparation", category, video.id)
    LOG.info("BILAN RATTRAPAGE %s", report)
    return report


async def execute(*, apply=False, max_repaired=2, history=MAX_HISTORY):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from .runner import resolve_peer
    if apply and not all(os.getenv(k, "").lower() == "true" for k in (
        "CINEX_ARCHIVE_ENABLED", "CINEX_ARCHIVE_DELETE_APPROVED",
        "CINEX_RIGHTS_VERIFIED",
    )):
        raise RuntimeError("Trois confirmations administrateur requises")
    creds = (os.getenv("TG_API_ID"), os.getenv("TG_API_HASH"),
             os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
             or os.getenv("TG_STREAM_SESSION"))
    if not all(creds):
        raise RuntimeError("Session Telegram absente")
    bot_token = os.getenv("CINEX_BOT_TOKEN")
    if apply and not bot_token:
        raise RuntimeError("Bot de publication CineX absent")
    client = TelegramClient(StringSession(creds[2]), int(creds[0]), creds[1],
                            request_retries=1, flood_sleep_threshold=0)
    await client.connect()
    reports = []
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram expirée")
        bot = BotHTTPClient(bot_token, client) if apply else None
        for category, public_username, private_id in category_targets():
            try:
                public = await resolve_peer(client, public_username)
                private = await resolve_peer(client, str(private_id))
                reports.append(await repair_channel(
                    client, bot, category, public, private, apply=apply,
                    max_repaired=max_repaired, history=history,
                ))
            except Exception as exc:
                if type(exc).__name__ in ("FloodWaitError", "PeerFloodError"):
                    raise
                LOG.exception("%s: réparation interrompue sans suppression", category)
                reports.append({"category": category, "errors": 1})
    finally:
        await client.disconnect()
    LOG.info("RÉSULTAT GLOBAL RATTRAPAGE %s", reports)
    summary_path = os.getenv("GITHUB_STEP_SUMMARY", "").strip()
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("\n### CinéX — Rattrapage sûr des anciennes vidéos\n")
            summary.write("| Canal | Anciennes | Reconnues | Vidéos privées créées | Liens publics vérifiés | Sans affiche | Erreurs |\n")
            summary.write("|---|---:|---:|---:|---:|---:|---:|\n")
            for row in reports:
                summary.write("| {category} | {older} | {recognized} | {private_created} | {public_linked} | {unmatched} | {errors} |\n".format(
                    **{k: row.get(k, 0) for k in (
                        "category", "older", "recognized", "private_created",
                        "public_linked", "unmatched", "errors")}))
    if any(row.get("errors", 0) for row in reports):
        raise RuntimeError("Réparation partielle : examiner les journaux avant une relance")
    return reports


def main():
    parser = argparse.ArgumentParser(description="CineX : réparer l'archivage ancien")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--max-repaired", type=int, default=2)
    parser.add_argument("--history", type=int, default=MAX_HISTORY)
    args = parser.parse_args()
    if not 1 <= args.max_repaired <= 10:
        parser.error("--max-repaired doit être compris entre 1 et 10")
    if not 100 <= args.history <= 20000:
        parser.error("--history doit être compris entre 100 et 20000")
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(execute(apply=args.apply,
                        max_repaired=args.max_repaired, history=args.history))


if __name__ == "__main__":
    main()
