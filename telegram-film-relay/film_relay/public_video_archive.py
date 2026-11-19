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
from .publication import film_folder_url
from .text import first_title, private_message_link

LOG = logging.getLogger("cinex.public_video_archive")
EXPECTED_PUBLIC = "@CineXFilms_vf"
MAX_HISTORY = 4000
KEEP_COUNT = 10


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
    title = re.sub(r"(?i)\b(?:voir|regarder|film|complet|vf|vostfr|french|hd|1080p|720p)\b", " ", title)
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def video_title(message) -> str:
    text = (getattr(message, "raw_text", "") or "").strip()
    if text:
        return text
    name = (getattr(getattr(message, "file", None), "name", "") or "").strip()
    return PurePath(name).stem.replace(".", " ").replace("_", " ") if name else ""


def title_similarity(first: str, second: str) -> float:
    a, b = normalize_title(first), normalize_title(second)
    if min(len(a), len(b)) < 5:
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


def matching_poster(video, messages, *, claimed: set[int] | None = None):
    """Seulement affiche antérieure, titre concordant et proximité prouvée.

    Les associations ambiguës ou sans titre sont ignorées, jamais devinées.
    """
    claimed = claimed or set()
    title = video_title(video)
    ranked = []
    for item in messages:
        if not getattr(item, "photo", None) or item.id in claimed:
            continue
        if item.id >= video.id or video.id - item.id > 12:
            continue
        score = title_similarity(title, getattr(item, "raw_text", "") or "")
        if score >= 0.80:
            ranked.append((score, item.id, item))
    ranked.sort(reverse=True, key=lambda x: (x[0], x[1]))
    if not ranked:
        return None
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.10:
        return None
    return ranked[0][2]


def has_verified_button(message, link: str) -> bool:
    for row in getattr(message, "buttons", None) or ():
        for button in row:
            url = getattr(button, "url", None) or getattr(getattr(button, "button", None), "url", None)
            if url == link:
                return True
    return False


def archive_buttons(link: str, public_peer=None):
    from .rescue_channels import add_rescue_button_row
    return add_rescue_button_row([
        [url_button("🎬 VOIR LE FILM", link, style="success")],
        [url_button("👥 REJOINDRE LA TEAM", film_folder_url(), style="danger")],
    ], public_peer)


async def existing_private_media(client, private, limit: int = MAX_HISTORY) -> dict[int, int]:
    by_document = {}
    async for message in client.iter_messages(private, limit=limit):
        docid = video_document_id(message)
        if docid and is_video_message(message):
            by_document.setdefault(docid, message.id)
    return by_document


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
        by_id = {m.id: m for m in messages}
        videos = sorted([m for m in messages if is_video_message(m)],
                        key=lambda m: m.id, reverse=True)
        protected = {m.id for m in videos[:KEEP_COUNT]}
        report["videos"] = len(videos)
        report["kept"] = len(protected)
        report["eligible"] = max(0, len(videos) - len(protected))
        LOG.info("Canal=%s vidéothèque=%s vidéos=%d conservées=%d candidates=%d",
                 public_id, private_id, len(videos), len(protected), report["eligible"])
        if len(messages) == limit:
            LOG.warning("Historique tronqué à %d messages : vidéos plus anciennes non examinées", limit)

        claimed_posters: set[int] = set()
        private_docs = await existing_private_media(client, private) if apply else {}
        bot = BotHTTPClient(bot_token, client) if apply else None
        if bot:
            identity = await bot.get_me()
            permissions = await bot.get_permissions(public, identity)
            if not (permissions.is_creator or permissions.is_admin):
                raise RuntimeError("Le bot CinéX n'est pas administrateur du canal public")

        # Itérer du plus récent des candidats au plus ancien; aucune
        # suppression si une preuve (affiche, média, lien) est absente.
        for video in videos[KEEP_COUNT:]:
            if max_archived is not None and report["archived"] >= max_archived:
                LOG.info("Limite de test atteinte : %d vidéo(s) archivées", max_archived)
                break
            poster = matching_poster(video, messages, claimed=claimed_posters)
            if poster is None:
                report["skipped"] += 1
                LOG.warning("VIDEO #%s : affiche non associable sans ambiguïté ; conservée", video.id)
                continue
            claimed_posters.add(poster.id)
            LOG.info("VIDEO #%s -> AFFICHE #%s (%s)",
                     video.id, poster.id, normalize_title(video_title(video))[:90])
            if not apply:
                continue
            try:
                if getattr(video, "noforwards", False):
                    raise RuntimeError("Vidéo protégée contre la redistribution")
                # Un même document existe souvent déjà en vidéothèque, car
                # le relais originel y envoie les films en premier.
                document_id = video_document_id(video)
                destination_id = private_docs.get(document_id)
                if destination_id:
                    archived = await client.get_messages(private, ids=destination_id)
                    if not archived or video_document_id(archived) != document_id:
                        destination_id = None
                if not destination_id:
                    copied = await client.send_file(
                        private, video.media, caption=(video_title(video) or "🎬 Film")[:1024]
                    )
                    destination_id = int(copied.id)
                proof = await client.get_messages(private, ids=destination_id)
                if not proof or not is_video_message(proof):
                    raise RuntimeError("Copie privée absente ou sans média vidéo")
                if document_id and video_document_id(proof) != document_id:
                    raise RuntimeError("Le document privé ne correspond pas à l'original")
                private_docs[document_id] = destination_id
                url = private_message_link(private_id, destination_id)
                await bot.edit_reply_markup(public, poster.id, buttons=archive_buttons(url, public))
                refreshed = await client.get_messages(public, ids=poster.id)
                if not refreshed or not has_verified_button(refreshed, url):
                    raise RuntimeError("Le bouton Voir le film n'a pas été vérifié")
                if not has_verified_button(refreshed, film_folder_url()):
                    raise RuntimeError("Le bouton Rejoindre la team n'a pas été vérifié")

                # Dernière vérification, pour ne pas effacer une vidéo qui
                # serait devenue parmi les dix dernières pendant le cycle.
                newest = [m async for m in client.iter_messages(public, limit=80)]
                recent_ids = last_ten_video_ids(newest)
                if video.id in recent_ids:
                    LOG.warning("Vidéo #%s désormais récente : suppression annulée", video.id)
                    report["skipped"] += 1
                    continue
                original = await client.get_messages(public, ids=video.id)
                if not original or video_document_id(original) != document_id:
                    raise RuntimeError("La vidéo publique a changé ou disparu")
                # Le bot s'occupe des messages récents, le propriétaire
                # reprend seulement si Telegram signale explicitement
                # une restriction d'âge ou de droit Bot API.
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
                        # Refus indéterminé, rate-limit ou erreur réseau :
                        # ne pas forcer une seconde suppression.
                        raise
                    LOG.warning("Bot limité sur #%s ; passage au compte propriétaire : %s",
                                video.id, str(exc)[:120])
                    await asyncio.sleep(30)  # pause prudente avant relais
                    await client.delete_messages(public, [video.id], revoke=True)
                after = await client.get_messages(public, ids=video.id)
                if after and is_video_message(after):
                    raise RuntimeError("Suppression non confirmée par Telegram")
                report["archived"] += 1
                LOG.info("ARCHIVÉ #%s vers vidéothèque #%s ; affiche #%s",
                         video.id, destination_id, poster.id)
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
