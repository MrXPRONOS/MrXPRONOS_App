"""CinéX: bounded 24-hour retention for videos in verified PUBLIC relay channels.

The original poster, category libraries, central private stock and backups are
NEVER deleted. ONLY newly auto-published public videos with the V4 caption
receipt are eligible. Manual/legacy public videos are excluded, even if old.
This is a retention tool for content the operator is authorized to distribute,
NOT a way to avoid copyright claims or platform moderation.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import logging
import os

from .public_video_archive import is_video_message, video_document_id
from .ten_video_rotation import category_targets
from .runner import resolve_peer
from .cinex_v4_policy import has_automatic_ttl, canonical_public_handle

# Fichiers Cloud is reserved for a future publishing lot, not active here.
EXPECTED_PUBLIC_RELAYS = {
    "films": "@cinexfilms_vf",
    "series": "@seriesvf_cinex",
    "desir": "@cinexdesirfr",
    "comedie": "@cinexcomediefr",
    "anime": "@cinexanimefr",
    "action": "@filmsaction2026vf",
}


def validate_retention_targets(configured) -> None:
    """Never report a partial scan as successful production cleanup."""
    if len(configured) != len(EXPECTED_PUBLIC_RELAYS):
        raise RuntimeError("Retention 24h partielle : six couples publics/prives requis")
    seen = set()
    for category, handle, private_id in configured:
        if category in seen:
            raise RuntimeError("Retention 24h : categorie dupliquee")
        seen.add(category)
        if EXPECTED_PUBLIC_RELAYS.get(category) != canonical_public_handle(handle):
            raise RuntimeError("Retention 24h : canal public hors perimetre")
        if not str(private_id).startswith("-100"):
            raise RuntimeError("Retention 24h : videotheque privee non verifiee")
    if seen != set(EXPECTED_PUBLIC_RELAYS):
        raise RuntimeError("Retention 24h : categories manquantes")


LOG = logging.getLogger("cinex.public_video_retention")
LIFETIME = timedelta(hours=24)
MAX_HISTORY = 4000
MAX_PER_CHANNEL = 100
PAUSE_SECONDS = 6


def due_for_removal(message, now: datetime, lifetime: timedelta = LIFETIME) -> bool:
    """Use the actual Telegram timestamp. Fail closed on missing/naive dates."""
    if not is_video_message(message) or not has_automatic_ttl(message):
        return False
    # A film/video-retention policy must not silently erase GIFs, trailers,
    # warnings, promotional clips or unrelated football publications.
    from .public_video_archive import video_title
    caption = str(video_title(message) or "").casefold()
    filename = str(getattr(getattr(message, "file", None), "name", "") or "").casefold()
    if any(token in caption or token in filename for token in (
        "animation gif", "animation.gif", "daily_pronos", "pronostics mr xpronos",
        "bande-annonce", "bande annonce", "trailer", "teaser",
        "publicité", "publicite", "advertisement",
    )):
        return False
    published = getattr(message, "date", None)
    if (not isinstance(published, datetime) or published.tzinfo is None
            or now.tzinfo is None):
        return False
    return now.astimezone(timezone.utc) - published.astimezone(timezone.utc) >= lifetime


def select_due(messages: list, now: datetime, *, lifetime: timedelta = LIFETIME):
    """Oldest tagged automated video first; manual/legacy posts are protected."""
    rows = [m for m in messages if due_for_removal(m, now, lifetime)]
    return sorted(rows, key=lambda m: (m.date, int(m.id)))


async def process_public(client, *, category: str, public, private_id: int,
                         apply: bool, now: datetime, max_deleted: int = MAX_PER_CHANNEL,
                         history: int = MAX_HISTORY):
    from telethon import utils
    public_id = utils.get_peer_id(public)
    handle = str(getattr(public, "username", "") or "").lstrip("@").casefold()
    if not getattr(public, "broadcast", False) or not handle:
        raise RuntimeError("La retention refuse les groupes et canaux prives.")
    if str(int(private_id)) == str(public_id):
        raise RuntimeError("La destination est une videotheque privee, refus.")
    items = [m async for m in client.iter_messages(public, limit=history)]
    expired = select_due(items, now)
    report = {
        "category": category, "public": "@" + handle,
        "scanned_messages": len(items),
        "expired_videos": len(expired),
        "deleted": 0, "not_deleted": len(expired), "errors": 0,
        "history_truncated": len(items) == history,
        "mode": "apply" if apply else "preview",
    }
    if not apply:
        return report
    # Verify production deletion rights even when zero videos are expired.
    # Otherwise a successful empty run could conceal missing admin rights.
    if report["history_truncated"]:
        raise RuntimeError("Historique Telegram tronqué : rétention incomplète")
    identity = await client.get_me()
    rights = await client.get_permissions(public, identity)
    if not (getattr(rights, "is_creator", False) or (
        getattr(rights, "is_admin", False)
        and getattr(rights, "delete_messages", False))):
        raise RuntimeError("Suppression interdite : droits Telegram non confirmes.")
    if not expired:
        LOG.info("%s : aucun média public marqué arrivé à échéance ; droits vérifiés", category)
        return report
    for video in expired[:max_deleted]:
        actual = await client.get_messages(public, ids=int(video.id))
        if not actual or not is_video_message(actual):
            continue
        if (video_document_id(actual) != video_document_id(video)
                or not due_for_removal(actual, datetime.now(timezone.utc))):
            report["errors"] += 1
            LOG.warning("%s: identite ou date video changee; refuse", category)
            continue
        await client.delete_messages(public, [int(video.id)], revoke=True)
        after = await client.get_messages(public, ids=int(video.id))
        if after and is_video_message(after):
            raise RuntimeError("Suppression Telegram non confirmee")
        report["deleted"] += 1
        report["not_deleted"] -= 1
        await asyncio.sleep(PAUSE_SECONDS)
    LOG.info("PUBLIC_RETENTION_RESULT %s", report)
    return report


async def execute(*, apply: bool = False, max_deleted: int = MAX_PER_CHANNEL,
                  history: int = MAX_HISTORY):
    from telethon import TelegramClient, utils
    from telethon.sessions import StringSession
    if not 1 <= max_deleted <= MAX_PER_CHANNEL:
        raise ValueError("Limite de suppression: 1 a 100 par canal")
    if apply and not all(os.getenv(flag, "").lower() == "true" for flag in (
        "CINEX_ARCHIVE_ENABLED", "CINEX_ARCHIVE_DELETE_APPROVED",
        "CINEX_RIGHTS_VERIFIED", "CINEX_PUBLIC_RETENTION_24H_ENABLED"
    )):
        raise RuntimeError("Retenue 24h non autorisee par les quatre controles")
    credentials = (os.getenv("TG_API_ID"), os.getenv("TG_API_HASH"),
                   os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
                   or os.getenv("TG_STREAM_SESSION"))
    if not all(credentials):
        raise RuntimeError("Session Telegram indisponible")
    configured = category_targets()
    if not configured:
        raise RuntimeError("Aucun couple canal public/videotheque verifie")
    if apply:
        validate_retention_targets(configured)
    # A previously configured channel must STILL belong to the secure admin
    # inventory; never delete when a channel was transferred or removed.
    if apply:
        from .rotation_coverage import fetch_secure_cinema_targets, public_handle
        secure_targets = fetch_secure_cinema_targets()
        verified_public = {
            public_handle(row["public_username"])
            for row in secure_targets if row.get("is_private") is False
        }
        if any(public_handle(username) not in verified_public
               for _, username, _ in configured):
            raise RuntimeError("Canal public non confirme dans l'inventaire securise")
    client = TelegramClient(StringSession(credentials[2]), int(credentials[0]),
                            credentials[1], request_retries=1,
                            flood_sleep_threshold=0)
    await client.connect()
    reports = []
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram non autorisee")
        seen = set()
        for category, username, private_id in configured:
            try:
                public = await resolve_peer(client, username)
                public_id = utils.get_peer_id(public)
                if public_id in seen:
                    raise RuntimeError("Canal public configure deux fois")
                seen.add(public_id)
                if str(getattr(public, "username", "") or "").lower() != username.lstrip("@").lower():
                    raise RuntimeError("Identite du canal public non conforme")
                result = await process_public(
                    client, category=category, public=public, private_id=private_id,
                    apply=apply, now=datetime.now(timezone.utc),
                    max_deleted=max_deleted, history=history,
                )
                reports.append(result)
            except Exception as exc:
                if type(exc).__name__ in ("FloodWaitError", "PeerFloodError"):
                    raise
                LOG.error("Retention %s: %s", category, type(exc).__name__)
                reports.append({"category": category, "errors": 1})
    finally:
        await client.disconnect()
    totals = {key: sum(int(r.get(key, 0)) for r in reports)
              for key in ("expired_videos", "deleted", "not_deleted", "errors")}
    LOG.info("PUBLIC_RETENTION_SUMMARY %s", {"mode": "apply" if apply else "preview",
                                             "totals": totals, "categories": reports})
    summary_file = os.getenv("GITHUB_STEP_SUMMARY", "").strip()
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as fp:
            fp.write("\n### CinéX : rétention de 24 heures, vidéos publiques seulement\n")
            fp.write("| Catégorie | Expirées | Supprimées | Restantes | Erreurs |\n")
            fp.write("|---|---:|---:|---:|---:|\n")
            for row in reports:
                fp.write("| {category} | {expired_videos} | {deleted} | {not_deleted} | {errors} |\n".format(
                    **{key: row.get(key, 0) for key in (
                        "category", "expired_videos", "deleted", "not_deleted", "errors")}))
            fp.write("\nAucune photo ni vidéothèque privée n'est supprimée. "
                     "La suppression ne garantit pas l'absence de signalements.\n")
    if totals["errors"]:
        raise RuntimeError("Retention partielle : verification requise")
    return reports


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--max-deleted", type=int, default=MAX_PER_CHANNEL)
    parser.add_argument("--history", type=int, default=MAX_HISTORY)
    args = parser.parse_args()
    if not 1 <= args.max_deleted <= MAX_PER_CHANNEL or not 100 <= args.history <= 10000:
        parser.error("Limites de nettoyage invalides")
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(execute(apply=args.apply, max_deleted=args.max_deleted,
                        history=args.history))


if __name__ == "__main__":
    main()
