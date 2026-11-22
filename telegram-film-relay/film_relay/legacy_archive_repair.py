"""Repair safely recognizable legacy CinéX media across configured channels.

Default is read-only. In apply mode, create/verify a PRIVATE poster+video and
EDIT the EXISTING PUBLIC photo in place to point to that saved video. Never
repost the public photo. If Telegram denies edits, leave the old public video
untouched. Rotation alone may delete after verifying the original photo.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import logging
import os

from .bot_http import BotHTTPClient, url_button
from .original_poster_edit import edit_original_cover, preflight_original_editability
from .unified_download import UnifiedLibrary
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


def public_buttons(url: str, public, poster, *, category: str,
                   extra_text: str = "", download_url: str | None = None):
    from types import SimpleNamespace
    from .rescue_channels import add_rescue_button_row
    name = "📺 REGARDER L'ÉPISODE" if category in ("anime", "series") else "🎬 VOIR LE FILM"
    result = [[url_button(name, url, style="success")]]
    if download_url:
        from .radar_download_registry import is_bot_download_url
        if not is_bot_download_url(download_url):
            raise ValueError("Téléchargement CinéRadar invalide.")
        result.append([url_button("⬇️ TÉLÉCHARGER LA VIDÉO", download_url, style="success")])
    youtube = youtube_url_for(poster) or youtube_url_for(
        SimpleNamespace(raw_text=extra_text, buttons=None))
    if youtube:
        result.append([url_button("▶️ YouTube", youtube, style="primary")])
    result = add_rescue_button_row(result, public)
    result.append([url_button("📁 Rejoindre le dossier", film_folder_url(), style="primary")])
    return result


def public_poster_verified(message, video, category, url: str, public,
                           *, reference=None, download_url=None):
    rescue = rescue_link_for(public)
    return bool(
        getattr(message, "photo", None)
        and compatible(reference or video_identity(video, category),
                       poster_identity(message, category)) >= 0.95
        and rescue
        and all(has_verified_button(message, link)
                for link in (url, rescue, film_folder_url())
                + ((download_url,) if download_url else ()))
    )


def original_public_poster_verified(message, source_poster, video, category,
                                   url, public, *, all_messages=(),
                                   reference=None, download_url=None,
                                   extra_text=""):
    """Verify the exact original post, not a newly published copy."""
    from .legacy_neighbor_matching import find_neighbor_pair
    if not message or not getattr(message, "photo", None):
        return False
    if message.id != source_poster.id:
        return False
    if getattr(message.photo, "id", None) != getattr(source_poster.photo, "id", None):
        return False
    before = str(getattr(source_poster, "raw_text", "") or "")
    after = str(getattr(message, "raw_text", "") or "")
    if not after.startswith(before):
        return False
    if extra_text.strip() and extra_text.strip() not in after:
        return False
    nearby = find_neighbor_pair(video, all_messages, category) if all_messages else None
    association = (compatible(reference or video_identity(video, category),
                              poster_identity(message, category)) >= 0.95
                   or bool(nearby and nearby.poster.id == source_poster.id))
    rescue = rescue_link_for(public)
    return bool(association and rescue and all(
        has_verified_button(message, link)
        for link in (url, rescue, film_folder_url())
        + ((download_url,) if download_url else ())
    ))


def shared_legacy_cover(video, poster, old, posters, category, messages) -> bool:
    """True when one legacy cover ambiguously describes two older videos.

    This read-only preflight MUST run before copying an image, uploading video,
    or registering a download token; false positives fail closed for review.
    """
    for other in old:
        if other.id == video.id:
            continue
        candidate = find_legacy_poster(other, posters, category)
        if candidate is None:
            adjacent = find_neighbor_pair(other, messages, category)
            candidate = adjacent.poster if adjacent else None
        if candidate and candidate.id == poster.id:
            return True
    return False


def existing_download_button(post) -> bool:
    """A private t.me/c link is a WATCH link, not a CineRadar download."""
    from .radar_download_registry import is_bot_download_url
    for row in getattr(post, "buttons", None) or ():
        for button in row:
            url = getattr(button, "url", None) or getattr(
                getattr(button, "button", None), "url", None)
            if is_bot_download_url(url):
                return True
    return False


def fully_linked_legacy_poster(poster, private_id, private_video_id, rescue_url, folder_url, *, extra_text="") -> bool:
    """Existing fully verified posters must not consume the new-edit budget."""
    target = private_message_link(private_id, private_video_id)
    return bool(
        getattr(poster, "photo", None)
        and movie_button_target(poster, private_id) == private_video_id
        and all(has_verified_button(poster, url) for url in
                (target, rescue_url, folder_url))
        and existing_download_button(poster)
        and (not extra_text.strip() or extra_text.strip() in
             str(getattr(poster, "raw_text", "") or ""))
    )


def bot_can_edit_original(permission) -> bool:
    """Bot must hold channel edit rights before copying archived media."""
    return bool(getattr(permission, "is_creator", False) or (
        getattr(permission, "is_admin", False)
        and getattr(permission, "post_messages", False)
        and getattr(permission, "edit_messages", False)
    ))


def verified_owner_pair(video, poster, category: str) -> bool:
    """Owner-selected IDs do not replace evidence of the same actual movie.

    Matching title or explicit episode/part is mandatory. One photo may not
    secretly stand for several different films; shared covers remain blocked
    by shared_legacy_cover in the caller.
    """
    if not video or not poster or not getattr(poster, "photo", None):
        return False
    if not is_video_message(video) or getattr(video, "noforwards", False):
        return False
    if getattr(poster, "noforwards", False):
        return False
    if not 0 < int(video.id) - int(poster.id) <= MAX_HISTORY:
        return False
    return compatible(video_identity(video, category),
                      poster_identity(poster, category)) >= 0.95


async def repair_channel(client, bot, category: str, public, private,
                         *, apply: bool, max_repaired: int = 2,
                         history: int = MAX_HISTORY, unified=None,
                         manual_pair: tuple[int, int] | None = None):
    from telethon import utils
    public_id, private_id = utils.get_peer_id(public), utils.get_peer_id(private)
    if public_id == private_id or not str(private_id).startswith("-100"):
        raise RuntimeError("L'archive doit rester un canal privé distinct")
    messages = [m async for m in client.iter_messages(public, limit=history)]
    recent, old = split_recent_and_old(messages, category)
    posters = [m for m in messages if getattr(m, "photo", None)]
    if manual_pair:
        manual_video_id, manual_poster_id = manual_pair
        chosen_video = next((m for m in old if int(m.id) == manual_video_id), None)
        chosen_poster = next((m for m in posters if int(m.id) == manual_poster_id), None)
        if not chosen_video or not chosen_poster:
            raise RuntimeError("Paire manuelle introuvable ou vidéo protégée par la rotation des dix dernières.")
        if not verified_owner_pair(chosen_video, chosen_poster, category):
            raise RuntimeError("Paire manuelle non vérifiable par titre, identité ou distance.")
    report = {
        "category": category, "public": public_id, "private": private_id,
        "protected": len(recent), "older": len(old), "recognized": 0,
        "private_existing": 0, "private_created": 0, "public_linked": 0,
        "public_already_linked": 0,
        "public_edited": 0, "public_edit_failed": 0,
        "unmatched": 0, "adjacent_recognized": 0, "ambiguous": 0, "skipped": 0,
        "private_pair_unverified": 0, "preflight_failed": 0,
        "preflight_budget_exhausted": 0, "errors": 0,
        "mode": "apply" if apply else "simulation",
    }
    if len(recent) < 10 and not manual_pair:
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
            if destination == public and not bot_can_edit_original(perm):
                # Telegram may refuse an edit even with this right, but without
                # it a copy-first repair is known to produce orphan archives.
                raise RuntimeError(
                    f"{category}: bot sans droit edit_messages; aucune archive copiée")
    private_messages = ([m async for m in client.iter_messages(private, limit=history)]
                        if apply else [])
    edit_probes = 0
    probe_budget = min(25, max(4, max_repaired * 5))
    for video in reversed(old):
        if manual_pair and int(video.id) != manual_pair[0]:
            continue
        if report["public_edited"] >= max_repaired:
            break
        if apply and edit_probes >= probe_budget:
            report["preflight_budget_exhausted"] = 1
            LOG.warning("%s : budget de vérifications atteint ; prochain passage requis", category)
            break
        identity = video_identity(video, category)
        poster = chosen_poster if manual_pair else find_legacy_poster(video, posters, category)
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
        # A shared historic poster cannot be bound to multiple videos.
        # Reject it BEFORE any private upload or bot download registration.
        # The previous placement of this check occurred after creating media
        # and caused orphaned duplicate private copies on each repair run.
        if shared_legacy_cover(video, poster, old, posters, category, messages):
            report["ambiguous"] += 1
            LOG.warning("%s : affiche #%s associée à plusieurs vidéos; "
                        "aucun nouvel archivage ni modification sans appariement manuel",
                        category, poster.id)
            continue
        report["recognized"] += 1
        if not apply:
            LOG.info("[SIMULATION] %s old video #%s -> poster #%s (%s)",
                     category, video.id, poster.id, identity)
            continue
        # Avoid exhausting the edit budget and Telegram bot quota on a post
        # that ALREADY has a verified photo/video pair and every required link.
        # Verify the exact private document before trusting the old buttons.
        existing_pair = find_verified_private_pair(
            private_messages, video, category, rescue_url=rescue, reference=identity)
        if existing_pair and fully_linked_legacy_poster(
                poster, private_id, existing_pair[0].id, rescue,
                film_folder_url(), extra_text=extra):
            report["private_existing"] += 1
            report["public_already_linked"] += 1
            report["public_linked"] += 1
            continue
        # A rights check alone is insufficient: Telegram may reject editing
        # old messages authored by another bot. Probe with unchanged markup
        # before uploading any private photo/video or registering a token.
        edit_probes += 1
        try:
            await preflight_original_editability(client, bot, public, poster)
        except Exception as exc:
            if type(exc).__name__ in ("FloodWaitError", "PeerFloodError"):
                raise
            report["preflight_failed"] += 1
            LOG.warning("%s : affiche historique non éditable, aucune nouvelle copie", category)
            continue
        try:
            pair = find_verified_private_pair(private_messages, video, category,
                                              rescue_url=rescue, reference=identity)
            if pair:
                private_video_id = pair[0].id
                report["private_existing"] += 1
            else:
                # A copy of this exact document with an unverified/missing
                # poster is not a new item to resend. Quarantine for manual
                # association, instead of multiplying the same private video.
                document = video_document_id(video)
                if any(is_video_message(item) and video_document_id(item) == document
                       for item in private_messages):
                    report["private_pair_unverified"] += 1
                    LOG.warning("%s : archive privée non vérifiable pour vidéo #%s ; "
                                "aucune copie supplémentaire", category, video.id)
                    continue
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
                if not any(int(m.id) == int(verified_photo.id) for m in private_messages):
                    private_messages.append(verified_photo)
                private_messages.append(verified_video)
                report["private_created"] += 1
            target = private_message_link(private_id, private_video_id)
            descriptive_caption = cover_caption(
                poster, video, category, identity=identity, extra_text=extra)
            download_url = (await unified.store(
                video, category=category, title=descriptive_caption,
                public=public, poster=poster, description=descriptive_caption,
            )) if unified is not None else None
            # NEVER create a new photo in the public channel. The historical
            # photo's ID, location, description and links must be preserved.
            required = (target, rescue, film_folder_url()) + (
                (download_url,) if download_url else ())
            if all(has_verified_button(poster, link) for link in required) and (
                not extra.strip() or extra.strip() in (poster.raw_text or "")):
                report["public_linked"] += 1
                report["public_already_linked"] += 1
                continue
            verified_public = await edit_original_cover(
                client, bot, public, poster, video,
                buttons=public_buttons(
                    target, public, poster, category=category,
                    extra_text=extra, download_url=download_url),
                private_video_url=target,
                extra_text=extra,
            )
            if not original_public_poster_verified(
                    verified_public, poster, video, category, target, public,
                    all_messages=messages, reference=identity,
                    download_url=download_url, extra_text=extra):
                raise RuntimeError(
                    "L'affiche originale ou ses boutons n'ont pas été vérifiés")
            posters = [verified_public if item.id == poster.id else item for item in posters]
            messages = [verified_public if item.id == poster.id else item for item in messages]
            report["public_linked"] += 1
            report["public_edited"] += 1
            LOG.info("%s : vidéo #%s archivée privée #%s ; fiche originale #%s modifiée",
                     category, video.id, private_video_id, poster.id)
            await asyncio.sleep(30)
        except Exception as exc:
            if type(exc).__name__ in ("FloodWaitError", "PeerFloodError"):
                raise
            report["errors"] += 1
            report["public_edit_failed"] += 1
            LOG.exception("%s : ancienne fiche non modifiée pour vidéo #%s, "
                          "vidéo publique conservée pour réparation", category, video.id)
    LOG.info("BILAN RATTRAPAGE %s", report)
    return report


def legacy_repair_completion(reports):
    """Never label a successful GitHub run as a completed historical migration.

    The remaining public posts can be unsafe, uneditable or unidentifiable.
    A partial classification is useful even when zero API exceptions occur.
    """
    totals = {
        name: sum(int(row.get(name, 0) or 0) for row in reports)
        for name in ("older", "public_linked", "public_edited",
                     "public_already_linked", "private_created",
                     "unmatched", "ambiguous", "private_pair_unverified",
                     "preflight_failed", "errors", "preflight_budget_exhausted")
    }
    # Conservative coverage only: repair stops at max_repaired, so we cannot
    # assert these items are all broken; they were not verified in this pass.
    totals["unresolved"] = max(0, totals["older"] - totals["public_linked"])
    totals["complete"] = (totals["unresolved"] == 0
                           and totals["errors"] == 0
                           and totals["preflight_budget_exhausted"] == 0)
    return totals


async def execute(*, apply=False, max_repaired=2, history=MAX_HISTORY,
                  manual_category=None, manual_video_id=None, manual_poster_id=None):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from .runner import resolve_peer
    manual_values=(manual_category, manual_video_id, manual_poster_id)
    if any(value is not None for value in manual_values) and not all(
            value is not None for value in manual_values):
        raise RuntimeError("La catégorie, la vidéo et l'affiche doivent toutes être précisées.")
    if manual_category is not None:
        if manual_category not in ("films","series","anime","action","comedie","desir"):
            raise RuntimeError("Catégorie manuelle inconnue.")
        if (not isinstance(manual_video_id,int) or not isinstance(manual_poster_id,int)
                or manual_video_id<1 or manual_poster_id<1):
            raise RuntimeError("Identifiants Telegram manuels invalides.")
        max_repaired=1
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
        unified = UnifiedLibrary(client) if apply else None
        selected=[t for t in category_targets() if manual_category is None or t[0]==manual_category]
        if manual_category is not None and len(selected)!=1:
            raise RuntimeError("Canal sélectionné absent de la configuration.")
        for category, public_username, private_id in selected:
            try:
                public = await resolve_peer(client, public_username)
                private = await resolve_peer(client, str(private_id))
                reports.append(await repair_channel(
                    client, bot, category, public, private, apply=apply,
                    max_repaired=max_repaired, history=history,
                    unified=unified, manual_pair=(
                        (manual_video_id,manual_poster_id)
                        if manual_category is not None else None),
                ))
            except Exception as exc:
                if type(exc).__name__ in ("FloodWaitError", "PeerFloodError"):
                    raise
                LOG.exception("%s: réparation interrompue sans suppression", category)
                reports.append({"category": category, "errors": 1})
    finally:
        await client.disconnect()
    LOG.info("RÉSULTAT GLOBAL RATTRAPAGE %s", reports)
    completion = legacy_repair_completion(reports)
    LOG.info("CINEX_REPAIR_VERIFICATION %s", {
        "complete": completion["complete"], "unresolved": completion["unresolved"],
        "edited": completion["public_edited"], "errors": completion["errors"]})
    summary_path = os.getenv("GITHUB_STEP_SUMMARY", "").strip()
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("\n### CinéX — Rattrapage sûr des anciennes vidéos\n")
            summary.write("| Canal | Anciennes | Fiches originales liées | Nouvelles copies privées | Sans paire fiable | Affiches ambiguës | Édition refusée | Copies incertaines | Erreurs |\n")
            summary.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
            for row in reports:
                summary.write("| {category} | {older} | {public_linked} | {private_created} | {unmatched} | {ambiguous} | {preflight_failed} | {private_pair_unverified} | {errors} |\n".format(
                    **{k: row.get(k, 0) for k in (
                        "category", "older", "public_linked", "private_created",
                        "unmatched", "ambiguous", "preflight_failed",
                        "private_pair_unverified", "errors")}))
            summary.write(
                "\n**Vérification : " + ("COMPLÈTE" if completion["complete"] else "PARTIELLE") +
                "** — anciennes fiches non validées pendant ce passage : " + str(completion["unresolved"]) +
                ", éditions originales confirmées : " + str(completion["public_edited"]) +
                ". Les affiches ambiguës ou interdites par Telegram ne sont pas modifiées.\n"
            )
    if manual_category is not None and any(
            row.get("errors",0)>0 or row.get("recognized",0)!=1 or
            (apply and row.get("public_linked",0)!=1)
            for row in reports):
        raise RuntimeError("Paire manuelle non vérifiée : aucune autre vidéo ne doit être traitée.")
    if any(row.get("errors", 0) for row in reports):
        raise RuntimeError("Réparation partielle : examiner les journaux avant une relance")
    return reports


def main():
    parser = argparse.ArgumentParser(description="CineX : réparer l'archivage ancien")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--max-repaired", type=int, default=2)
    parser.add_argument("--history", type=int, default=MAX_HISTORY)
    parser.add_argument("--manual-category", choices=("films","series","anime","action","comedie","desir"))
    parser.add_argument("--manual-video-id", type=int)
    parser.add_argument("--manual-poster-id", type=int)
    args = parser.parse_args()
    if not 1 <= args.max_repaired <= 10:
        parser.error("--max-repaired doit être compris entre 1 et 10")
    if not 100 <= args.history <= 20000:
        parser.error("--history doit être compris entre 100 et 20000")
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(execute(apply=args.apply,
                        max_repaired=args.max_repaired, history=args.history,
                        manual_category=args.manual_category,
                        manual_video_id=args.manual_video_id,
                        manual_poster_id=args.manual_poster_id))


if __name__ == "__main__":
    main()
