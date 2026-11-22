"""Safely mirror *already archived* CineX videos into one central private channel.

No deletes, no public edits. Read-only by default; in apply mode at most two
videos per original category library per pass. Deduplicate by Telegram document
ID and validate every new private receipt.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os

from .public_video_archive import is_video_message, video_document_id, video_title, matching_poster
from .ten_video_rotation import category_targets
from .unified_download import UnifiedLibrary

LOG = logging.getLogger("cinex.unified_backfill")


def archive_cover_for_video(video, source_messages):
    """Never reconstruct an archive from a video without a matching REAL poster."""
    return matching_poster(video, source_messages, max_gap=8)


async def execute(*, apply=False, per_channel=2, history=4000):
    from telethon import TelegramClient, utils
    from telethon.sessions import StringSession
    from .runner import resolve_peer

    if not 1 <= per_channel <= 10 or not 100 <= history <= 20000:
        raise ValueError("Passage limité à 1-10 vidéos par bibliothèque et 100-20000 messages.")
    creds = (os.getenv("TG_API_ID"), os.getenv("TG_API_HASH"),
             os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
             or os.getenv("TG_STREAM_SESSION"))
    if not all(creds):
        raise RuntimeError("Session Telegram manquante.")
    client = TelegramClient(StringSession(creds[2]), int(creds[0]), creds[1],
                            request_retries=1, flood_sleep_threshold=0)
    await client.connect()
    results = []
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram non autorisée.")
        central = UnifiedLibrary(client, history=history)
        if central.target_id is None:
            raise RuntimeError("Renseigner CINEX_UNIFIED_PRIVATE_CHANNEL avant tout rattrapage.")
        await central.prepare()
        if apply and os.getenv("CINEX_RIGHTS_VERIFIED", "").lower() != "true":
            raise RuntimeError("Copie centrale réelle interdite sans CINEX_RIGHTS_VERIFIED=true.")
        public_ids = set()
        for category, public_name, original_id in category_targets():
            report = {"category": category, "existing_private_videos": 0,
                      "already_in_central": 0, "candidates": 0, "created": 0,
                      "skipped": 0, "missing_poster": 0,
                      "legacy_cover_unverified": 0, "errors": 0}
            try:
                public = await resolve_peer(client, public_name)
                pid = utils.get_peer_id(public)
                if pid in public_ids:
                    raise RuntimeError("Doublon de canal public dans les catégories.")
                public_ids.add(pid)
                await central.prepare(public=public)
                if central.target_id == original_id:
                    report["skipped"] = 1
                    results.append(report)
                    continue
                source = await resolve_peer(client, str(original_id))
                if utils.get_peer_id(source) != original_id:
                    raise RuntimeError("Bibliothèque historique : ID incorrect.")
                source_messages = [m async for m in client.iter_messages(source, limit=history)]
                archive = [m for m in source_messages if is_video_message(m)]
                report["existing_private_videos"] = len(archive)
                for video in reversed(archive):
                    document = video_document_id(video)
                    if not document:
                        report["skipped"] += 1
                        continue
                    if int(document) in central.index:
                        report["already_in_central"] += 1
                        if not central.verified_cover_for(document):
                            report["legacy_cover_unverified"] += 1
                        continue
                    report["candidates"] += 1
                    poster = archive_cover_for_video(video, source_messages)
                    if not poster:
                        report["missing_poster"] += 1
                        LOG.warning("%s : vidéo ancienne #%s sans affiche fiable; "
                                    "stock central non modifié", category, video.id)
                        continue
                    if not apply or report["created"] >= per_channel:
                        continue
                    try:
                        url = await central.store(video, category=category,
                                                  title=video_title(video), public=public,
                                                  poster=poster,
                                                  description=str(getattr(poster, "raw_text", "") or video_title(video)))
                        if not url:
                            raise RuntimeError("La copie centrale n'a pas retourné de lien.")
                        report["created"] += 1
                        await asyncio.sleep(36)
                    except Exception as exc:
                        if type(exc).__name__ in ("FloodWaitError", "PeerFloodError"):
                            raise
                        report["errors"] += 1
                        LOG.exception("%s : vidéo historique #%s non copiée", category, video.id)
                results.append(report)
            except Exception as exc:
                if type(exc).__name__ in ("FloodWaitError", "PeerFloodError"):
                    raise
                LOG.exception("%s : catégorie historique non migrée", category)
                report["errors"] += 1
                results.append(report)
    finally:
        await client.disconnect()
    LOG.info("BILAN CENTRAL %s", results)
    summary_path = os.getenv("GITHUB_STEP_SUMMARY", "").strip()
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("\n### CinéX — Rattrapage vidéothèque centrale\n")
            f.write("| Canal | Anciennes vidéos | Déjà présentes | Couvre non vérifiée | Sans affiche source | Copiées | Erreurs |\n")
            f.write("|---|---:|---:|---:|---:|---:|---:|\n")
            for r in results:
                f.write("| {category} | {existing_private_videos} | {already_in_central} | "
                        "{legacy_cover_unverified} | {missing_poster} | {created} | {errors} |\n".format(**r))
    if any(r["errors"] for r in results):
        raise RuntimeError("Rattrapage central partiel : lire les diagnostics.")
    return results


def main():
    parser = argparse.ArgumentParser(description="CinéX : réunir les anciennes vidéos privées")
    parser.add_argument("--apply", action="store_true", help="Autoriser la copie privée")
    parser.add_argument("--per-channel", type=int, default=2)
    parser.add_argument("--history", type=int, default=4000)
    opts = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(execute(apply=opts.apply, per_channel=opts.per_channel,
                        history=opts.history))


if __name__ == "__main__":
    main()
