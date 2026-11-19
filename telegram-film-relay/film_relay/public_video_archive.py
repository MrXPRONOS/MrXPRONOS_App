"""Ciné X Films VF: conserver les 10 vidéos publiques les plus récentes.

Lecture de l'historique via la session propriétaire Telethon. Les anciennes
vidéos ne sont supprimées qu'après vérification du média privé et du bouton
sur l'affiche du même film. Mode simulation par défaut.

Utiliser uniquement avec des contenus dont la redistribution est autorisée.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import PurePath

from .bot_http import BotHTTPClient, TelegramBotHTTPError, url_button
from .publication import film_folder_url, rich_caption, rich_video_title
from .text import first_title, private_message_link, clean_caption

LOG = logging.getLogger("cinex.public_video_archive")
EXPECTED_PUBLIC = "@CineXFilms_vf"
MAX_HISTORY = 4000
KEEP_COUNT = 10
# Legacy posts can have many intervening messages between a movie poster
# and its video. Long-distance matches require significantly stronger titles.
MAX_POSTER_DISTANCE = 1200
USER_RESERVED_TITLES = ("john wick",)


def video_document_id(message) -> int | None:
    document = getattr(message, "document", None)
    return getattr(document, "id", None)


def is_video_message(message) -> bool:
    """Inclut vidéos natives et fichiers vidéo MKV/MP4 envoyés en document."""
    if not message or not video_document_id(message):
        return False
    if getattr(message, "video", None) is not None:
        return True
    document = message.document
    for attribute in getattr(document, "attributes", ()) or ():
        if type(attribute).__name__ == "DocumentAttributeVideo":
            return True
        if type(attribute).__name__ == "DocumentAttributeFilename":
            name = (getattr(attribute, "file_name", "") or "").lower()
            if name.endswith((".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v")):
                return True
    filename = getattr(getattr(message, "file", None), "name", "") or ""
    return filename.lower().endswith((".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"))


def normalize_title(text: str) -> str:
    """Évite d'associer deux films uniquement parce qu'ils sont voisins."""
    title = first_title(text or "")
    title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    title = re.sub(r"(?i)\b(?:voir|regarder|film|complet|vf|vostfr|french|hd|ultra|uhd|4k|2160p|1080p|720p|mkv|mp4|avi|mov|webm|m4v)\b", " ", title)
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def poster_heading(message) -> str:
    """Find an actual movie heading, skipping legacy '#Film' and hashtags.

    Several imported posters contain '#Film' on line one and the actual movie
    title on line two, so first_title(raw_text) is not enough.
    """
    lines = (getattr(message, "raw_text", "") or "").splitlines()
    for line in lines[:7]:
        line = re.sub(r"^[🎬🎞🍿📽\s:]+", "", line).strip()
        if not line or re.fullmatch(r"(?i)#?films?", line):
            continue
        if re.match(r"(?i)^(synopsis|résumé|genre|date|année|langue|durée)\s*:", line):
            continue
        heading = re.sub(r"(?i)^titre\s*:\s*", "", line).strip()
        if heading:
            return heading[:130]
    return ""


def video_title(message) -> str:
    text = (getattr(message, "raw_text", "") or "").strip()
    if text:
        return text
    name = (getattr(getattr(message, "file", None), "name", "") or "").strip()
    return PurePath(name).stem.replace(".", " ").replace("_", " ") if name else ""


def title_similarity(first: str, second: str) -> float:
    a, b = normalize_title(first), normalize_title(second)
    # Four-character exact movie names (e.g. Hope) are legitimate. Short
    # names must match an entire token, never an arbitrary string fragment.
    if min(len(a), len(b)) < 4:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.94
    return SequenceMatcher(None, a, b).ratio()


def last_ten_video_ids(messages, limit: int = KEEP_COUNT) -> set[int]:
    videos = sorted((m for m in messages if is_video_message(m)),
                    key=lambda m: m.id, reverse=True)
    return {m.id for m in videos[:limit]}


def matching_poster(
    video, messages, *, claimed: set[int] | None = None,
    max_gap: int = MAX_POSTER_DISTANCE,
):
    """Match a preceding poster by movie title, never simply by adjacency.

    Long-distance associations need an almost identical title. If two
    plausible posters are too close in rank, preserve the video for review.
    """
    claimed = claimed or set()
    title = video_title(video)
    ranked = []
    for item in messages:
        if not item or not getattr(item, "photo", None) or item.id in claimed:
            continue
        distance = video.id - item.id
        if distance <= 0 or distance > max_gap:
            continue
        score = title_similarity(title, poster_heading(item))
        threshold = 0.80 if distance <= 12 else (0.91 if distance <= 100 else 0.96)
        if score >= threshold:
            ranked.append((score, distance, item))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    if not ranked:
        return None
    if len(ranked) > 1:
        best, second = ranked[:2]
        if (best[0] - second[0] < 0.06
                and abs(best[1] - second[1]) < 25
                and not (
                    best[0] >= 0.99 and best[1] <= 12
                    and (second[0] < 0.99 or second[1] > 12
                         or (best[1] <= 2 and second[1] >= best[1] + 2))
                )):
            return None
        if best[0] - second[0] < 0.04 and best[1] == second[1]:
            return None
    return ranked[0][2]


def is_user_reserved_film(video, poster) -> bool:
    """The owner will handle the remaining John Wick films manually."""
    title = normalize_title(video_title(video))
    poster_title = normalize_title(poster_heading(poster))
    return any(name in title or name in poster_title for name in USER_RESERVED_TITLES)


def has_verified_button(message, link: str) -> bool:
    for row in getattr(message, "buttons", None) or ():
        for button in row:
            url = getattr(button, "url", None) or getattr(getattr(button, "button", None), "url", None)
            if url == link:
                return True
    return False


def archive_buttons(link: str, public_peer=None):
    from .rescue_channels import add_rescue_button_row
    buttons = add_rescue_button_row([
        [url_button("🎬 VOIR LE FILM", link, style="success")],
    ], public_peer)
    buttons.append([url_button("📁 Rejoindre le dossier", film_folder_url(), style="danger")])
    return buttons


def verified_film_video_pairs(messages):
    """Only title-matched poster+video pairs count towards the ten-film rotation.

    Unrelated videos, orphan videos and promotions never consume a movie slot.
    Unmatched videos are retained (fail closed), not silently deleted.
    """
    videos = sorted((m for m in messages if is_video_message(m)),
                    key=lambda m: m.id, reverse=True)
    matches = []
    claimed = set()
    for video in videos:
        # TV episodes are handled by the separate series catalogue.
        if re.search(r"(?i)\\bS\d{1,2}\s*E[P]?\s*\d{1,3}\\b", video_title(video)):
            continue
        poster = matching_poster(video, messages, claimed=claimed)
        if poster is not None:
            matches.append((video, poster))
            claimed.add(poster.id)
    return matches


async def existing_private_media(client, private, limit: int = MAX_HISTORY) -> dict[int, int]:
    by_document = {}
    async for message in client.iter_messages(private, limit=limit):
        docid = video_document_id(message)
        if docid and is_video_message(message):
            by_document.setdefault(docid, message.id)
    return by_document



async def private_video_has_poster(client, private, video_id: int,
                                   expected_document_id: int) -> bool:
    """Reuse a private movie only when its own descriptive poster is before it."""
    current = await client.get_messages(private, ids=video_id)
    if not is_video_message(current) or video_document_id(current) != expected_document_id:
        return False
    previous_ids = list(range(max(1, video_id - 8), video_id))
    previous = await client.get_messages(private, ids=previous_ids)
    matching = matching_poster(current, previous or [], max_gap=8)
    return bool(matching and (getattr(matching, "raw_text", "") or "").strip())


async def ensure_private_poster_then_video(
    client, private, poster, video, private_docs: dict[int, int],
) -> int:
    """Ensure the archive points to a verified PHOTO then VIDEO sequence.

    If an old private video exists without a preceding poster, re-publish a
    complete pair instead of linking to that incomplete entry. Reuse a
    previously completed pair on retries, preventing duplicate archive posts.
    """
    document_id = video_document_id(video)
    existing_id = private_docs.get(document_id)
    if existing_id and await private_video_has_poster(
        client, private, existing_id, document_id
    ):
        return existing_id
    if getattr(poster, "noforwards", False) or getattr(video, "noforwards", False):
        raise RuntimeError("Affiche ou vidéo protégée : aucune copie autorisée")

    description = clean_caption(getattr(poster, "raw_text", "") or "")
    if not description or not getattr(poster, "photo", None):
        raise RuntimeError("Affiche ou description absente : conservation de la vidéo publique")

    # Recovery from an interrupted cycle that sent the private poster but not
    # yet the video. All Telegram-owner workflows share a single Actions lock.
    last_private = [m async for m in client.iter_messages(private, limit=1)]
    pending = last_private[0] if last_private else None
    if not (pending and getattr(pending, "photo", None)
            and title_similarity(getattr(pending, "raw_text", "") or "", description) >= 0.95):
        pending = await client.send_file(
            private, poster.media, caption=rich_caption(description, private=True),
            parse_mode="html",
        )
    photo_check = await client.get_messages(private, ids=int(pending.id))
    if not photo_check or not getattr(photo_check, "photo", None) or not (
        getattr(photo_check, "raw_text", "") or ""
    ).strip():
        raise RuntimeError("Affiche privée non confirmée ; vidéo publique conservée")

    await asyncio.sleep(12)
    posted = await client.send_file(
        private, video.media, caption=rich_video_title(video_title(video)), parse_mode="html",
    )
    confirmed = await client.get_messages(private, ids=int(posted.id))
    if not is_video_message(confirmed) or video_document_id(confirmed) != document_id:
        raise RuntimeError("Vidéo privée non confirmée ou document différent")
    if not (0 < int(confirmed.id) - int(photo_check.id) <= 3):
        raise RuntimeError("Affiche et vidéo privées non consécutives")
    if not await private_video_has_poster(client, private, int(confirmed.id), document_id):
        raise RuntimeError("L'affiche de la vidéothèque n'a pas pu être associée à la vidéo")
    private_docs[document_id] = int(confirmed.id)
    return int(confirmed.id)


async def replace_uneditable_public_poster(
    client, bot, public, original_poster, movie_url: str, rescue_url: str | None,
) -> int:
    """Create an equivalent bot-owned photo only when the old one cannot be edited.

    Reuse an already verified replacement after a partially interrupted run.
    Never remove the old photo or movie here: that happens only after the
    replacement and the private movie are both verified.
    """
    import re
    title = poster_heading(original_poster)
    if not title:
        raise RuntimeError("Affiche publique sans titre fiable : aucun remplacement")
    folder = film_folder_url()
    async for existing in client.iter_messages(public, limit=500):
        if (getattr(existing, "photo", None)
                and existing.id != original_poster.id
                and has_verified_button(existing, movie_url)
                and has_verified_button(existing, folder)
                and (not rescue_url or has_verified_button(existing, rescue_url))
                and title_similarity(poster_heading(existing), title) >= 0.95):
            LOG.info("Fiche de remplacement existante #%s : réutilisation", existing.id)
            return int(existing.id)
    raw = clean_caption(getattr(original_poster, "raw_text", "") or "")
    lines = raw.splitlines()
    if lines and re.fullmatch(r"(?i)#?films?", lines[0].strip()):
        lines = lines[1:]
    description = "\n".join(lines).strip()
    if not description or not getattr(original_poster, "photo", None):
        raise RuntimeError("Affiche sans description ou média : remplacement refusé")
    image = await client.download_media(original_poster.media, file=bytes)
    if not image:
        raise RuntimeError("Impossible de lire l'affiche : vidéo publique conservée")
    created = await bot.send_file(
        public, image,
        caption=rich_caption(description), parse_mode="html",
        buttons=archive_buttons(movie_url, public),
    )
    check = await client.get_messages(public, ids=int(created.id))
    if (not check or not getattr(check, "photo", None)
            or not (getattr(check, "raw_text", "") or "").strip()
            or not has_verified_button(check, movie_url)
            or not has_verified_button(check, folder)
            or (rescue_url and not has_verified_button(check, rescue_url))):
        raise RuntimeError("Nouvelle fiche publique non vérifiée ; ancienne vidéo conservée")
    LOG.info("Nouvelle fiche modifiable #%s créée pour remplacer #%s",
             created.id, original_poster.id)
    return int(created.id)


async def execute(*, apply: bool = False, limit: int = MAX_HISTORY, max_archived: int | None = None) -> dict:
    from telethon import TelegramClient, utils
    from telethon.errors import FloodWaitError, PeerFloodError
    from telethon.sessions import StringSession

    api_id = os.environ.get("TG_API_ID", "").strip()
    api_hash = os.environ.get("TG_API_HASH", "").strip()
    session = (os.environ.get("TG_STRING_SESSION")
               or os.environ.get("TG_SESSION_STRING")
               or os.environ.get("TG_STREAM_SESSION") or "").strip()
    private_name = os.environ.get("TG_PRIVATE_CHANNEL", "").strip()
    public_name = os.environ.get("TG_PUBLIC_CHANNEL", EXPECTED_PUBLIC).strip()
    bot_token = (os.environ.get("CINEX_BOT_TOKEN") or "").strip()

    if not (api_id and api_hash and session and private_name):
        raise RuntimeError("TG_API_ID, TG_API_HASH, session et TG_PRIVATE_CHANNEL requis")
    if public_name.lower() != EXPECTED_PUBLIC.lower():
        raise RuntimeError("Sécurité: cette rotation est réservée à @CineXFilms_vf")
    if apply and not bot_token:
        raise RuntimeError("CINEX_BOT_TOKEN requis avant toute modification")
    if apply and os.environ.get("TG_RIGHTS_ATTESTED", "").lower() != "true":
        raise RuntimeError("TG_RIGHTS_ATTESTED=true requis pour archiver des films")

    report = {"mode": "APPLY" if apply else "DRY_RUN", "videos": 0,
              "kept": 0, "eligible": 0, "archived": 0, "skipped": 0, "errors": 0}
    client = TelegramClient(StringSession(session), int(api_id), api_hash,
                            request_retries=1, flood_sleep_threshold=0)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram personnelle non autorisée")
        public = await client.get_entity(public_name)
        private = await client.get_entity(int(private_name) if private_name.lstrip("-").isdigit() else private_name)
        public_id, private_id = utils.get_peer_id(public), utils.get_peer_id(private)
        if getattr(public, "username", "").lower() != "cinexfilms_vf":
            raise RuntimeError("Identité du canal principal différente de Ciné X Films VF")
        if private_id == public_id or not str(private_id).startswith("-100"):
            raise RuntimeError("La vidéothèque doit être un canal Telegram privé distinct")

        messages = [m async for m in client.iter_messages(public, limit=limit)]
        videos = sorted([m for m in messages if is_video_message(m)],
                        key=lambda m: m.id, reverse=True)
        film_pairs = verified_film_video_pairs(messages)
        protected = {video.id for video, _poster in film_pairs[:KEEP_COUNT]}
        to_archive = [(video, poster) for video, poster in film_pairs[KEEP_COUNT:]
                      if not is_user_reserved_film(video, poster)]
        reserved = sum(is_user_reserved_film(v, p) for v, p in film_pairs[KEEP_COUNT:])
        unmatched = len(videos) - len(film_pairs)
        report.update({
            "videos": len(videos), "kept": len(protected),
            "eligible": len(to_archive), "unmatched": unmatched, "reserved": reserved,
        })
        LOG.info(
            "Canal=%s vidéothèque=%s vidéos=%d films_associes=%d "
            "conservés=%d candidats=%d non_associes=%d John_Wick_reserves=%d",
            public_id, private_id, len(videos), len(film_pairs),
            len(protected), len(to_archive), unmatched, reserved,
        )
        paired_ids = {v.id for v, _ in film_pairs}
        for item in videos:
            if item.id not in paired_ids and item.id not in {v.id for v in videos[:KEEP_COUNT]}:
                LOG.warning("Vidéo ancienne non associable #%s : %s ; laissée intacte",
                            item.id, normalize_title(video_title(item))[:80])
        if len(messages) == limit:
            LOG.warning("Historique tronqué à %d messages : vidéos plus anciennes non examinées", limit)

        private_docs = await existing_private_media(client, private) if apply else {}
        bot = BotHTTPClient(bot_token, client) if apply else None
        bot_can_delete = False
        if bot:
            identity = await bot.get_me()
            permissions = await bot.get_permissions(public, identity)
            if not (permissions.is_creator or getattr(permissions, "is_admin", False)):
                raise RuntimeError("Le bot CinéX doit être administrateur pour modifier les affiches")
            bot_can_delete = bool(permissions.is_creator or getattr(
                permissions, "delete_messages", False))
            if not bot_can_delete:
                LOG.warning(
                    "Le bot ne peut pas supprimer ; le compte propriétaire prendra "
                    "le relais après vérification de la vidéothèque et des boutons")
            me = await client.get_me()
            owner_rights = await client.get_permissions(public, me)
            if not (getattr(owner_rights, "is_creator", False) or
                    getattr(owner_rights, "is_admin", False) and
                    getattr(owner_rights, "delete_messages", False)):
                raise RuntimeError("Le compte principal ne possède pas les droits de suppression")

        # Rattrapage du plus ANCIEN au plus récent ; les John Wick restants
        # sont gérés manuellement par le propriétaire.
        for video, poster in reversed(to_archive):
            if max_archived is not None and report["archived"] >= max_archived:
                LOG.info("Limite de test atteinte : %d vidéo(s) archivées", max_archived)
                break
            LOG.info("VIDEO #%s -> AFFICHE #%s (%s)",
                     video.id, poster.id, normalize_title(video_title(video))[:90])
            if not apply:
                continue
            try:
                if getattr(video, "noforwards", False):
                    raise RuntimeError("Vidéo protégée contre la redistribution")
                # Private archive must contain the FILM POSTER FIRST,
                # followed by its VIDEO. Reuse existing verified pairs only.
                document_id = video_document_id(video)
                destination_id = await ensure_private_poster_then_video(
                    client, private, poster, video, private_docs,
                )
                proof = await client.get_messages(private, ids=destination_id)
                if not proof or video_document_id(proof) != document_id:
                    raise RuntimeError("Paire privée non vérifiée : vidéo publique conservée")
                url = private_message_link(private_id, destination_id)
                from .rescue_channels import read_state, rescue_link_for
                rescue_state = read_state().get("channels", {}).get("@cinexfilms_vf")
                rescue_url = rescue_link_for(public) if rescue_state else None
                if rescue_state and not rescue_url:
                    raise RuntimeError("Lien Secours indisponible : affiche et vidéo conservées")
                replacement_id = None
                try:
                    await bot.edit_reply_markup(
                        public, poster.id, buttons=archive_buttons(url, public))
                except TelegramBotHTTPError as exc:
                    if "message can't be edited" not in str(exc).casefold():
                        raise
                    LOG.warning(
                        "Affiche #%s non modifiable par le bot ; création d'une "
                        "fiche équivalente avec liens vérifiables", poster.id)
                    replacement_id = await replace_uneditable_public_poster(
                        client, bot, public, poster, url, rescue_url)
                refreshed = await client.get_messages(
                    public, ids=replacement_id or poster.id)
                if not refreshed or not has_verified_button(refreshed, url):
                    raise RuntimeError("Le bouton Voir le film n'a pas été vérifié")
                if not has_verified_button(refreshed, film_folder_url()):
                    raise RuntimeError("Le bouton Dossier n'a pas été vérifié")
                if rescue_url and not has_verified_button(refreshed, rescue_url):
                    raise RuntimeError("Le bouton Secours n'a pas été vérifié")

                # Dernière vérification, pour ne pas effacer une vidéo qui
                # serait devenue parmi les dix dernières pendant le cycle.
                # Even when hundreds of poster messages separate videos, find
                # ALL ten newest videos before deleting any candidate.
                newest_messages = []
                video_count = 0
                # Scan enough history for matching *film posters*, not just
                # ten arbitrary video posts. Always keep the 12-message window
                # behind the last candidate for poster verification.
                last_candidate_id = None
                async for latest in client.iter_messages(public, limit=20000):
                    newest_messages.append(latest)
                    if is_video_message(latest):
                        video_count += 1
                        if video_count == KEEP_COUNT + 30:
                            last_candidate_id = latest.id
                    if last_candidate_id is not None and latest.id < last_candidate_id - 12:
                        break
                recent_pairs = verified_film_video_pairs(newest_messages)
                recent_ids = {m.id for m, _ in recent_pairs[:KEEP_COUNT]}
                if len(recent_ids) < KEEP_COUNT:
                    raise RuntimeError("Impossible de confirmer dix films récents : suppression suspendue")
                if video.id in recent_ids:
                    LOG.warning("Vidéo #%s désormais récente : suppression annulée", video.id)
                    report["skipped"] += 1
                    continue
                original = await client.get_messages(public, ids=video.id)
                if not original or video_document_id(original) != document_id:
                    raise RuntimeError("La vidéo publique a changé ou disparu")
                # Permission Bot API missing? Use the Telegram owner session,
                # whose actual delete permission was checked above. Never
                # bypass the verified poster, private copy or latest-ten guards.
                if not bot_can_delete:
                    await client.delete_messages(public, [video.id], revoke=True)
                    LOG.info("Vidéo #%s retirée par le compte administrateur", video.id)
                else:
                    try:
                        await bot.delete_message(public, video.id)
                        LOG.info("Vidéo #%s supprimée par le bot", video.id)
                    except TelegramBotHTTPError as exc:
                        reason = str(exc).casefold()
                        known_limitation = any(s in reason for s in (
                            "message can't be deleted", "message to delete not found",
                            "not enough rights", "not enough permission",
                            "message is too old", "forbidden", "have no rights",
                        ))
                        if not known_limitation:
                            raise
                        LOG.warning("Bot limité sur #%s ; passage au propriétaire : %s",
                                    video.id, str(exc)[:120])
                        await asyncio.sleep(30)
                        await client.delete_messages(public, [video.id], revoke=True)
                after = await client.get_messages(public, ids=video.id)
                if after and is_video_message(after):
                    raise RuntimeError("Suppression non confirmée par Telegram")
                report["archived"] += 1
                if replacement_id:
                    await client.delete_messages(public, [poster.id], revoke=True)
                    old_poster = await client.get_messages(public, ids=poster.id)
                    if old_poster and getattr(old_poster, "photo", None):
                        report["errors"] += 1
                        LOG.error("Ancienne affiche #%s encore visible, remplacement #%s confirmé",
                                  poster.id, replacement_id)
                    else:
                        LOG.info("Affiche historique #%s retirée ; nouvelle fiche #%s conservée",
                                 poster.id, replacement_id)
                LOG.info("ARCHIVÉ #%s vers vidéothèque #%s ; affiche #%s",
                         video.id, destination_id, replacement_id or poster.id)
                await asyncio.sleep(30)  # 2x+ marge prudente entre suppressions
            except (FloodWaitError, PeerFloodError):
                raise
            except Exception as exc:
                report["errors"] += 1
                LOG.exception("Vidéo #%s non supprimée : %s", video.id, exc)

        LOG.info("BILAN %s", report)
        output = os.getenv("GITHUB_STEP_SUMMARY", "")
        if output:
            with open(output, "a", encoding="utf-8") as f:
                f.write(
                    "\n### Ciné X : rotation des vidéos publiques\n"
                    f"- Mode : {report['mode']}\n"
                    f"- Vidéos visibles analysées : {report['videos']}\n"
                    f"- Dix dernières préservées : {report['kept']}\n"
                    f"- Anciennes vidéos candidates : {report['eligible']}\n"
                    f"- Vidéos archivées et supprimées du public : {report['archived']}\n"
                    f"- Vidéos conservées faute de correspondance : {report['skipped']}\n"
                    f"- Films réservés (John Wick) : {report['reserved']}\n"
                    f"- Vidéos sans affiche fiable, laissées intactes : {report['unmatched']}\n"
                    f"- Erreurs : {report['errors']}\n"
                )
        return report
    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Conserver les 10 dernières vidéos Ciné X")
    parser.add_argument("--apply", action="store_true",
                        help="Modifier les affiches et supprimer les anciens médias vérifiés")
    parser.add_argument("--limit", type=int, default=MAX_HISTORY)
    parser.add_argument("--max-archived", type=int, default=None,
                        help="Limiter les suppressions réellement confirmées, utile pour les tests")
    args = parser.parse_args()
    if args.max_archived is not None and not 1 <= args.max_archived <= 100:
        parser.error("--max-archived doit être compris entre 1 et 100")
    if args.limit < 20 or args.limit > 20000:
        parser.error("--limit doit être compris entre 20 et 20000")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    report = asyncio.run(execute(apply=args.apply, limit=args.limit, max_archived=args.max_archived))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
