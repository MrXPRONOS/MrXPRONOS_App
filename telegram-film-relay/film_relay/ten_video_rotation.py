"""CinéX unified video rotation: retain ten recent media videos per main channel.

Unlike the historical backfill, this routine NEVER copies media or edits
posters. New relays must have already posted poster+buttons then video to both
the private library and the public channel. Dry run is the default.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re

from .publication import film_folder_url
from .cinex_v4_policy import has_automatic_ttl
from .public_video_archive import (
    has_verified_button, is_video_message, is_primary_film_video,
    video_document_id, video_title, title_similarity, poster_heading,
)
from .rescue_channels import rescue_link_for
from .text import private_message_link

LOG = logging.getLogger("cinex.ten_video_rotation")
KEEP = 10
VIDEO_LINK = re.compile(r"^https://t\.me/c/(\d+)/(\d+)(?:\?.*)?$")
MANUAL_TITLES = ("john wick",)


def is_rotatable_video(message, category: str) -> bool:
    """Avoid animations, promotional videos and manual John Wick inventory."""
    if not is_video_message(message):
        return False
    title = video_title(message).casefold()
    filename = str(getattr(getattr(message, "file", None), "name", "") or "").casefold()
    if ("animation gif" in title or "animation.gif" in filename
            or "pronostics mr xpronos" in title or "daily_pronos" in filename):
        return False
    if category == "films":
        return is_primary_film_video(message)
    # Other channels contain both movies and series episodes; retain the ten
    # newest actual video messages, not only title-matched movie pairs.
    if any(name in title for name in MANUAL_TITLES):
        return False
    return True


def split_recent_and_old(messages, category: str, count: int = KEEP):
    videos = sorted((m for m in messages if is_rotatable_video(m, category)),
                    key=lambda msg: int(msg.id), reverse=True)
    return videos[:count], videos[count:]


def pinned_archive_order(old, messages, category: str):
    """Pinned film covers first; preserve the retention boundary and exact pairing.

    A pin is scheduling evidence only, never proof that a video belongs to a
    cover. Use the same title/neighbor matchers as the repair routine. Shared
    covers are inventoried, not authorized for copying/deleting by this helper.
    All parts of a pinned cover that can be matched are considered together.
    """
    from .legacy_media_identity import find_legacy_poster, video_identity, multipart_identity
    from .legacy_neighbor_matching import find_neighbor_pair

    posters = [m for m in messages if getattr(m, "photo", None)]
    pins = {int(m.id) for m in posters if getattr(m, "pinned", False)}
    pinned_groups = {}
    pinned_parts = {}
    for video in old:
        poster = find_legacy_poster(video, posters, category)
        if poster is None:
            adjacent = find_neighbor_pair(video, messages, category)
            poster = adjacent.poster if adjacent else None
        if poster is not None and int(poster.id) in pins:
            pinned_groups[int(video.id)] = int(poster.id)
            part = multipart_identity(video, poster, category)
            if part:
                pinned_parts[int(video.id)] = part.part

    def sort_key(video):
        vid = int(video.id)
        if vid in pinned_groups:
            return (0, pinned_groups[vid], pinned_parts.get(vid, 0), vid)
        if getattr(video, "pinned", False):
            return (0, vid, 0, vid)
        return (1, vid, 0, vid)

    ordered = sorted(old, key=sort_key)
    counts = {}
    for video in ordered:
        cover_id = pinned_groups.get(int(video.id))
        if cover_id is None:
            continue
        ident = video_identity(video, category)
        counts.setdefault(cover_id, []).append(
            pinned_parts.get(int(video.id), ident.part if ident.kind == "film_part" else None))
    for cover_id, parts in sorted(counts.items()):
        numbered = sorted(p for p in parts if p is not None)
        LOG.info("Affiche épinglée #%s : %s vidéo(s) ancienne(s), parties explicites=%s",
                 cover_id, len(parts), numbered)
        if len(parts) > 1:
            LOG.warning("Affiche épinglée #%s partagée : ne pas déduire de liens "
                        "multiples ni de parties manquantes sans preuve", cover_id)
    return ordered


def movie_button_targets(poster, private_id: int) -> set[int]:
    """All explicit links to the configured library, no other channel."""
    expected_prefix = str(abs(int(private_id)))[3:] if str(private_id).startswith("-100") else None
    if not expected_prefix:
        return set()
    candidates = set()
    for row in getattr(poster, "buttons", None) or ():
        for button in row:
            url = getattr(button, "url", None) or getattr(
                getattr(button, "button", None), "url", None)
            match = VIDEO_LINK.fullmatch(str(url or ""))
            if match and match.group(1) == expected_prefix:
                candidates.add(int(match.group(2)))
    return candidates


def movie_button_target(poster, private_id: int) -> int | None:
    candidates = movie_button_targets(poster, private_id)
    return next(iter(candidates)) if len(candidates) == 1 else None


def category_targets(env: dict | None = None):
    """Allow only explicitly configured known destination pairs."""
    env = os.environ if env is None else env
    categories = (
        ("films", "@CineXFilms_vf", env.get("TG_PRIVATE_CHANNEL")),
        ("series", env.get("SERIES_PUBLIC_CHANNEL"), env.get("SERIES_PRIVATE_CHANNEL")),
        ("desir", env.get("DESIR_PUBLIC_CHANNEL") or "@CineXDesirfr",
         env.get("DESIR_PRIVATE_CHANNEL")),
        ("comedie", env.get("COMEDIE_PUBLIC_CHANNEL"), env.get("COMEDIE_PRIVATE_CHANNEL")),
        ("anime", env.get("ANIME_PUBLIC_CHANNEL") or "@CineXAnimeFR",
         env.get("ANIME_PRIVATE_CHANNEL")),
        ("action", env.get("ACTION_PUBLIC_CHANNEL") or "@filmsaction2026vf",
         env.get("ACTION_PRIVATE_CHANNEL")),
    )
    selected = []
    for category, public, private in categories:
        if not public or not private:
            LOG.warning("%s : canal principal ou vidéothèque non configuré, ignoré", category)
            continue
        if not re.fullmatch(r"-100\d{5,}", str(private)):
            raise RuntimeError(f"{category}: l'ID vidéothèque doit commencer par -100")
        if not re.fullmatch(r"@[A-Za-z0-9_]{5,32}", str(public)):
            raise RuntimeError(f"{category}: canal principal doit être un @username")
        selected.append((category, str(public), int(private)))
    return selected


def unmatched_candidate(video, messages, category: str) -> bool:
    """Only old movie-like media lacking *both* title- and sequence-pairing.

    Never purge a recognizable but not-yet-archived movie. Such a video
    requires archive repair first, rather than an irreversible purge.
    """
    from .legacy_media_identity import find_legacy_poster
    from .legacy_neighbor_matching import find_neighbor_pair
    if not is_rotatable_video(video, category):
        return False
    raw = (video_title(video) + " " +
           str(getattr(getattr(video, "file", None), "name", "") or "")).casefold()
    if any(marker in raw for marker in (
        "bande annonce", "bande-annonce", "trailer", "teaser",
        "promo", "publicité", "publicite", "clip", "advert",
        "daily pronos", "animation gif",
    )):
        return False
    posters = [m for m in messages if getattr(m, "photo", None)]
    return (find_legacy_poster(video, posters, category) is None
            and find_neighbor_pair(video, messages, category) is None)


async def verify_existing_pair(client, public, private, private_id, video, posters,
                               category: str = "films", messages=None):
    """Allow later repair covers while requiring exact source-document identity.

    A repair poster may have been created AFTER the legacy video. A nearby
    cover alone is NEVER sufficient for deletion; the private Telegram media,
    its preceding private cover and the public URL buttons must all agree.
    """
    from .legacy_media_identity import (
        compatible, poster_identity, video_identity, find_legacy_poster, multipart_identity,
    )
    from .legacy_neighbor_matching import find_neighbor_pair
    ident = video_identity(video, category)
    nearby = find_neighbor_pair(video, messages, category) if messages is not None else None
    if not ident.safe and nearby:
        ident = nearby.identity
    if not ident.safe:
        return None
    # An old bot-created duplicate cover published AFTER the old video may
    # contain valid links, but it must not authorize deletion while the
    # ORIGINAL photo remains unchanged. Only an original preceding the video
    # can permit rotation after its buttons have been verified.
    source_photo = None
    if messages is not None:
        originals = [m for m in posters if m.id < video.id]
        source_photo = (find_legacy_poster(video, originals, category) or
                        (nearby.poster if nearby else None))
        if not source_photo:
            return None
    rescue_url = rescue_link_for(public)
    if not rescue_url:
        raise RuntimeError("Invitation Secours manquante pour ce canal")
    folder_url = film_folder_url()
    matched = []
    for poster in posters:
        if not getattr(poster, "photo", None):
            continue
        if source_photo is not None and poster.id != source_photo.id:
            continue
        part = multipart_identity(video, poster, category)
        identity_matches = bool(part) or compatible(ident, poster_identity(poster, category)) >= 0.95
        adjacency_matches = bool(nearby and nearby.poster.id == poster.id)
        if not (identity_matches or adjacency_matches):
            continue
        targets = movie_button_targets(poster, private_id)
        if not part and len(targets) != 1:
            continue
        if not targets or len(targets) > 10:
            continue
        matches = 0
        for private_video_id in sorted(targets):
            url = private_message_link(private_id, private_video_id)
            if not all(has_verified_button(poster, link)
                       for link in (url, rescue_url, folder_url)):
                continue
            private_video = await client.get_messages(private, ids=private_video_id)
            if (not is_video_message(private_video)
                    or video_document_id(private_video) != video_document_id(video)):
                continue
            prior_ids = list(range(max(1, private_video_id - 8), private_video_id))
            private_posters = await client.get_messages(private, ids=prior_ids)
            for private_poster in private_posters or []:
                proof = poster_identity(private_poster, category)
                if (getattr(private_poster, "photo", None)
                        and (getattr(private_poster, "raw_text", "") or "").strip()
                        and compatible(part or ident, proof) >= 0.95
                        and (not part or proof.part == part.part)
                        and has_verified_button(private_poster, rescue_url)
                        and has_verified_button(private_poster, folder_url)):
                    matches += 1
                    break
        if matches == 1:
            matched.append(poster)
    # Any ambiguity stops deletion: one verified public cover per media.
    return matched[0] if len(matched) == 1 else None

async def rotate_channel(client, category: str, public, private,
                         *, apply: bool, max_deleted: int = 10, history: int = 4000,
                         purge_unmatched: bool = False):
    from telethon import utils
    public_id, private_id = utils.get_peer_id(public), utils.get_peer_id(private)
    if public_id == private_id:
        raise RuntimeError("Même canal public et privé : rotation interdite")
    messages = [m async for m in client.iter_messages(public, limit=history)]
    recent, old = split_recent_and_old(messages, category)
    report = {"category": category, "videos": len(recent) + len(old),
              "protected": len(recent), "older": len(old), "deleted": 0,
              "unverified": 0, "purged_unmatched": 0,
              "unmatched_candidates": 0}
    if len(recent) < KEEP:
        LOG.info("%s : moins de dix vidéos, aucune suppression", category)
        return report
    me = await client.get_me()
    permissions = await client.get_permissions(public, me)
    if apply and not (getattr(permissions, "is_creator", False) or
                      (getattr(permissions, "is_admin", False)
                       and getattr(permissions, "delete_messages", False))):
        raise RuntimeError(f"{category}: absence de droits de suppression")
    # Oldest first. Unknown candidates are reported in simulation; only
    # explicitly requested destructive runs can remove them.
    posters = [m for m in messages if getattr(m, "photo", None)]
    report["unmatched_candidates"] = sum(
        unmatched_candidate(v, messages, category) for v in old
    )
    for video in pinned_archive_order(old, messages, category):
        if report["deleted"] >= max_deleted:
            break
        # V4 videos are exclusively managed by the scheduled 24h retention.
        # The historical ten-video rotation must NEVER remove them early.
        if has_automatic_ttl(video):
            LOG.info("%s : video CineX V4 #%s reservee au TTL 24 h", category, video.id)
            continue
        if not apply:
            LOG.info("[SIMULATION] %s : ancienne vidéo #%s", category, video.id)
            continue
        # A known verified archive ALWAYS takes precedence over an unknown
        # classification, even when its repaired cover was published later.
        public_poster = await verify_existing_pair(
            client, public, private, private_id, video, posters, category,
            messages=messages)
        unknown = (not public_poster and purge_unmatched
                   and unmatched_candidate(video, messages, category))
        if not public_poster and not unknown:
            report["unverified"] += 1
            LOG.warning("%s : ancienne vidéo #%s gardée (archive absente ou non vérifiée)",
                        category, video.id)
            continue
        # Newly added movies may have moved the 10-film boundary. Re-evaluate
        # against live Telegram immediately before every destructive call.
        latest = []
        async for current in client.iter_messages(public, limit=1000):
            if is_rotatable_video(current, category):
                latest.append(current)
            if len(latest) >= KEEP:
                break
        if len(latest) < KEEP or video.id in {m.id for m in latest}:
            report["unverified"] += 1
            LOG.warning("%s : frontière des dix dernières vidéos non sûre", category)
            continue
        actual = await client.get_messages(public, ids=video.id)
        if not actual or video_document_id(actual) != video_document_id(video):
            report["unverified"] += 1
            continue
        if public_poster:
            fresh = await client.get_messages(public, ids=public_poster.id)
            from .original_poster_edit import public_keyboard_signature
            if (not fresh or not getattr(fresh, "photo", None)
                    or getattr(fresh.photo, "id", None) != getattr(public_poster.photo, "id", None)
                    or (getattr(public_poster, "pinned", False) and not getattr(fresh, "pinned", False))
                    or public_keyboard_signature(fresh) != public_keyboard_signature(public_poster)):
                report["unverified"] += 1
                continue
        await client.delete_messages(public, [video.id], revoke=True)
        after = await client.get_messages(public, ids=video.id)
        if after and is_video_message(after):
            raise RuntimeError(f"{category}: la suppression #{video.id} n'est pas confirmée")
        report["deleted"] += 1
        if unknown:
            report["purged_unmatched"] += 1
            LOG.warning("%s : vidéo NON IDENTIFIÉE #%s supprimée du public "
                        "(aucune copie privée ; action explicitement demandée)",
                        category, video.id)
        else:
            LOG.info("%s : ancienne vidéo #%s supprimée ; fiche #%s conservée",
                     category, video.id, public_poster.id)
        await asyncio.sleep(36)
    LOG.info("BILAN %s", report)
    return report


async def execute(*, apply: bool = False, max_deleted: int = 10,
                  purge_unmatched: bool = False):
    from telethon import TelegramClient, utils
    from telethon.sessions import StringSession
    from .runner import resolve_peer
    if purge_unmatched and not apply:
        LOG.info("Simulation : candidats non reconnus seulement ; aucune suppression")
    if (apply and purge_unmatched
            and os.getenv("CINEX_MANUAL_PURGE_REQUEST", "").lower() != "true"):
        raise RuntimeError(
            "Purge inconnus interdite hors workflow manuel explicitement confirmé")
    if apply and not all(os.getenv(v, "").lower() == "true" for v in
                         ("CINEX_ARCHIVE_ENABLED", "CINEX_ARCHIVE_DELETE_APPROVED",
                          "CINEX_RIGHTS_VERIFIED")):
        raise RuntimeError("Les trois confirmations d'archivage sont requises")
    targets = category_targets()
    credentials = (os.getenv("TG_API_ID"), os.getenv("TG_API_HASH"),
                   os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
                   or os.getenv("TG_STREAM_SESSION"))
    if not all(credentials):
        raise RuntimeError("Session Telegram manquante")
    client = TelegramClient(StringSession(credentials[2]), int(credentials[0]),
                            credentials[1], request_retries=1, flood_sleep_threshold=0)
    await client.connect()
    reports = []
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram non autorisée")
        seen_public = set()
        for category, public_name, private_id in targets:
            try:
                public = await resolve_peer(client, public_name)
                private = await resolve_peer(client, str(private_id))
                if utils.get_peer_id(public) in seen_public:
                    raise RuntimeError("Canal principal dupliqué dans deux catégories")
                seen_public.add(utils.get_peer_id(public))
                reports.append(await rotate_channel(
                    client, category, public, private, apply=apply,
                    max_deleted=max_deleted, purge_unmatched=purge_unmatched))
            except Exception:
                LOG.exception("Rotation %s interrompue, autres catégories conservées", category)
                reports.append({"category": category, "error": True})
    finally:
        await client.disconnect()
    LOG.info("RÉSULTAT GLOBAL %s", reports)
    summary_path = os.getenv("GITHUB_STEP_SUMMARY", "").strip()
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("\n### CinéX — Rotation et nettoyage des anciennes vidéos\n")
            summary.write("| Canal | Anciennes | Supprimées | Inconnues supprimées | "
                          "Inconnues détectées | Non vérifiées |\n")
            summary.write("|---|---:|---:|---:|---:|---:|\n")
            for row in reports:
                summary.write("| {category} | {older} | {deleted} | {purged_unmatched} | "
                              "{unmatched_candidates} | {unverified} |\n".format(
                    **{key: row.get(key, 0) for key in (
                        "category", "older", "deleted", "purged_unmatched",
                        "unmatched_candidates", "unverified")}))
    if any(report.get("error") for report in reports):
        raise RuntimeError("Une ou plusieurs catégories nécessitent une correction")
    return reports


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--max-deleted", type=int, default=10)
    parser.add_argument("--purge-unmatched", action="store_true",
                        help="Supprimer aussi les anciens médias non reconnus ; uniquement manuel")
    options = parser.parse_args()
    if not 1 <= options.max_deleted <= 10:
        parser.error("Limite par canal : de 1 à 10")
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(execute(apply=options.apply, max_deleted=options.max_deleted,
                        purge_unmatched=options.purge_unmatched))


if __name__ == "__main__":
    main()
