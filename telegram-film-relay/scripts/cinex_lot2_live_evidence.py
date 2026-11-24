"""Read-only CineX V4 Lot 2 acceptance of real public/private Telegram messages.

Only inspect the six configured official category pairs. Never send, edit,
delete, forward or register a media item. No private URLs/IDs or tokens logged.
An absent new V4 sample is PENDING, not a verified success and not a defect.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
from pathlib import Path

from film_relay.public_video_archive import is_video_message, video_document_id
from film_relay.cinex_v4_policy import has_automatic_ttl
from film_relay.publication import (
    film_folder_url, video_labels, verify_complete_public_video_keyboard,
    read_url_button_rows,
)
from film_relay.radar_download_registry import is_bot_download_url, RadarRegistry
from film_relay.ten_video_rotation import category_targets
from film_relay.public_video_retention import validate_retention_targets
from film_relay.runner import resolve_peer
from film_relay.unified_download import configured_private_id

LOG = logging.getLogger("cinex.lot2.live")
# A message URL is only trusted for the exact owner-registered category library.
INTERNAL_LINK = re.compile(r"^https://t\.me/c/([0-9]{6,})/([1-9][0-9]*)$")
EPISODE_CODE = re.compile(r"\bS[0-9]{2,3}E[0-9]{2,3}\b", re.IGNORECASE)
DOWNLOAD_LINK = re.compile(
    r"https://t\.me/CineRadarFr_Bot\?start=d_[A-Za-z0-9_-]{24}"
)


def private_message_id(url: str, private_id: int) -> int | None:
    match = INTERNAL_LINK.fullmatch(str(url or ""))
    if not match or not str(private_id).startswith("-100"):
        return None
    if match.group(1) != str(private_id)[4:]:
        return None
    return int(match.group(2))


def button_pairs(message):
    return read_url_button_rows(message)

def is_private_fiche(message, public_handle, private_id=None):
    if not getattr(message, "photo", None):
        return False
    rows = button_pairs(message)
    if len(rows) != 3 or any(len(row) != 1 for row in rows):
        return False
    (first_label, first_url), (second_label, second_url), (last_label, last_url) = (
        row[0] for row in rows
    )
    return bool(
        "rejoindre le canal" in first_label.casefold()
        and first_url.casefold() == "https://t.me/" + public_handle.lstrip("@").casefold()
        and "rejoindre le dossier" in second_label.casefold()
        and second_url == film_folder_url()
        and "télécharger" in last_label.casefold()
        and (
            is_bot_download_url(last_url)
            or (private_id is not None
                and private_message_id(last_url, private_id) is not None)
        )  # Only the exact category library can host a season index
    )


def validate_public_sample(message, public, category=None, private_id=None):
    """Recognize both V4 contracts: one-film CineRadar link or season batch index.

    No shortcut accepts an arbitrary t.me/c URL as the archive/delivery target.
    """
    rows = button_pairs(message)
    if len(rows) != 4 or any(len(row) != 1 for row in rows):
        return False
    first_label, private_link = rows[0][0]
    if category is not None and first_label not in {
        video_labels(category, episode=False)[0],
        video_labels(category, episode=True)[0],
    }:
        return False
    if private_id is not None and private_message_id(private_link, private_id) is None:
        return False
    _, download_url = rows[1][0]
    if is_bot_download_url(download_url):
        return verify_complete_public_video_keyboard(
            message, public, private_link, download_url,
            watch_label=first_label
        )
    if category not in ("series", "anime") or private_id is None:
        return False
    if private_message_id(download_url, private_id) is None:
        return False
    try:
        from film_relay.season_batches_v4 import batch_public_rows
        expected = batch_public_rows(
            public, private_link, download_url, kind=category)
    except (ValueError, RuntimeError, TypeError):
        return False
    return rows == expected


async def check_receipt(client, video, download_url):
    """Validate the exact approved stock channel and real Telegram document."""
    from telethon import utils
    if not is_bot_download_url(download_url):
        return False
    expected_doc = video_document_id(video)
    if not expected_doc:
        return False
    approved_id = configured_private_id()
    if approved_id is None:
        return False
    token = download_url.split("?start=d_", 1)[-1]
    rows = RadarRegistry()._query(
        "SELECT l.source_chat_id,l.source_message_id FROM cine_classic_links AS l "
        "JOIN cine_private_stock_config AS s "
        "ON s.singleton=1 AND l.source_chat_id=s.stock_chat_id "
        "WHERE l.token=? AND l.status='published' AND s.ready=1 "
        "AND s.radar_bot_id>0 LIMIT 1",
        [token]
    ).get("results") or []
    if (len(rows) != 1 or str(rows[0].get("source_chat_id")) != str(approved_id)
            or int(rows[0].get("source_message_id") or 0) <= 0):
        return False
    stock = await resolve_peer(client, str(approved_id))
    if (utils.get_peer_id(stock) != approved_id
            or not getattr(stock, "broadcast", False)
            or getattr(stock, "username", None)):
        return False
    mid = int(rows[0]["source_message_id"])
    stored = await client.get_messages(stock, ids=mid)
    return bool(is_video_message(stored) and int(getattr(stored, "id", 0)) == mid
                and video_document_id(stored) == expected_doc)


async def check_download_target(client, private, private_id: int,
                                video, download_url: str) -> bool:
    """Follow the index of the exact episode, never confuse index with a receipt."""
    if is_bot_download_url(download_url):
        return await check_receipt(client, video, download_url)
    index_id = private_message_id(download_url, private_id)
    if not index_id:
        return False
    marker = EPISODE_CODE.search(str(getattr(video, "raw_text", "") or ""))
    if not marker:
        return False
    index = await client.get_messages(private, ids=index_id)
    if not index:
        return False
    code = marker.group().upper()
    matching_lines = [line for line in str(getattr(index, "raw_text", "") or "").splitlines()
                      if re.search(r"(?<![A-Z0-9])" + re.escape(code)
                                   + r"(?![A-Z0-9])", line.upper())]
    if len(matching_lines) != 1:
        return False
    links = DOWNLOAD_LINK.findall(matching_lines[0])
    if len(links) != 1:
        return False
    return await check_receipt(client, video, links[0])


async def matching_private_fiche(client, private, private_id: int,
                                 public_handle: str, public_video, *,
                                 max_older: int = 120) -> bool:
    """Prove the SAME Telegram item has a real three-button private photo.

    For season batches the watch link points straight at the private cover.
    For single films it points at the private video: require matching document
    identity and find the nearest preceding cover with the identical D1 link.
    Never accept an unrelated old three-button poster as proof of a new video.
    """
    rows = button_pairs(public_video)
    if len(rows) != 4:
        return False
    watch = rows[0][0][1]
    download = rows[1][0][1]
    watch_id = private_message_id(watch, private_id)
    if not watch_id:
        return False
    target = await client.get_messages(private, ids=watch_id)
    if target is None:
        return False
    if private_message_id(download, private_id) is not None:
        return (is_private_fiche(target, public_handle, private_id)
                and button_pairs(target)[2][0][1] == download)
    if not is_bot_download_url(download):
        return False
    if (not is_video_message(target)
        or not video_document_id(target)
        or video_document_id(target) != video_document_id(public_video)):
        return False
    async for candidate in client.iter_messages(
            private, limit=max_older, max_id=watch_id):
        if (is_private_fiche(candidate, public_handle, private_id)
            and button_pairs(candidate)[2][0][1] == download):
            return True
    return False


async def inspect(*, limit=600):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    credentials = (
        os.getenv("TG_API_ID", ""), os.getenv("TG_API_HASH", ""),
        (os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
         or os.getenv("TG_STREAM_SESSION") or ""),
    )
    if not all(credentials):
        raise RuntimeError("missing_owner_session")
    pairs = category_targets()
    validate_retention_targets(pairs)
    client = TelegramClient(StringSession(credentials[2]), int(credentials[0]),
                            credentials[1], flood_sleep_threshold=0, request_retries=1)
    await client.connect()
    results = []
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("unauthorized_owner_session")
        for category, public_handle, private_id in pairs:
            result = {
                "category": category, "latest_public_v4": "pending_no_sample",
                "private_three_buttons": "pending_no_sample",
                "public_photo_four_buttons": "pending_no_sample",
                "central_receipt": "pending_no_sample",
                "errors": 0,
            }
            try:
                public = await resolve_peer(client, public_handle)
                private = await resolve_peer(client, str(private_id))
                public_messages = [
                    m async for m in client.iter_messages(public, limit=limit)
                ]
                videos = [
                    m for m in public_messages
                    if is_video_message(m) and has_automatic_ttl(m)
                ]
                if videos:
                    video = videos[0]
                    result["latest_public_v4"] = (
                        "verified" if validate_public_sample(video, public, category, private_id) else "invalid"
                    )
                    # Match a real preceding public photo with the SAME
                    # exact buttons as the public V4 video. Season episodes
                    # may share a single batch cover.
                    candidates = [
                        m for m in public_messages
                        if getattr(m, "photo", None)
                        and int(m.id) < int(video.id)
                        and button_pairs(m) == button_pairs(video)
                    ]
                    result["public_photo_four_buttons"] = (
                        "verified" if candidates else "pending_no_matching_poster"
                    )
                    if result["latest_public_v4"] == "verified":
                        dl = button_pairs(video)[1][0][1]
                        result["central_receipt"] = (
                            "verified" if await check_download_target(
                                client, private, private_id, video, dl
                            ) else "not_verified"
                        )
                        if result["central_receipt"] != "verified":
                            result["errors"] += 1
                    else:
                        result["errors"] += 1
                if videos and result["latest_public_v4"] == "verified":
                    result["private_three_buttons"] = (
                        "verified" if await matching_private_fiche(
                            client, private, private_id, public_handle, video
                        ) else "not_verified"
                    )
                    if result["private_three_buttons"] != "verified":
                        result["errors"] += 1
            except Exception as exc:
                # The exception text may contain a private Telegram URL.
                result["errors"] += 1
                LOG.error("%s: read-only inspection failed: %s", category,
                          type(exc).__name__)
            LOG.info("LOT2_LIVE %s public=%s private=%s d1=%s errors=%s",
                     category, result["latest_public_v4"],
                     result["private_three_buttons"],
                     result["central_receipt"], result["errors"])
            results.append(result)
    finally:
        await client.disconnect()
    pending = sum(
        any(value.startswith("pending_") for value in (
            row["latest_public_v4"], row["private_three_buttons"],
            row["public_photo_four_buttons"], row["central_receipt"]))
        for row in results
    )
    failed = sum(row["errors"] for row in results)
    verified = sum(
        row["latest_public_v4"] == "verified"
        and row["private_three_buttons"] == "verified"
        and row["public_photo_four_buttons"] == "verified"
        and row["central_receipt"] == "verified"
        for row in results
    )
    LOG.info("LOT2_LIVE_SUMMARY completed_categories=%d/6 pending_categories=%d errors=%d",
             verified, pending, failed)
    if pending and not failed:
        print(f"::warning::CINEX_LOT2_PRODUCTION_PENDING: {pending}/6 categories "
              "do not yet have complete V4 evidence. CI success only proves "
              "the read-only audit executed, NOT that publication is validated.")
    summary = os.getenv("GITHUB_STEP_SUMMARY", "").strip()
    if summary:
        with Path(summary).open("a", encoding="utf-8") as f:
            f.write("\n### CinéX Lot 2 — échantillons de publications réelles\n")
            f.write("| Catégorie | Vidéo publique 4 boutons | Affiche publique 4 boutons | Affiche privée 3 boutons | Lien D1 | Erreurs |\n")
            f.write("|---|---|---|---|---|---:|\n")
            for row in results:
                f.write(f"| {row['category']} | {row['latest_public_v4']} | "
                        f"{row['public_photo_four_buttons']} | "
                        f"{row['private_three_buttons']} | {row['central_receipt']} | "
                        f"{row['errors']} |\n")
            f.write("\nAbsence d'échantillon = en attente, jamais succès. "
                    "Aucune publication, modification ou suppression effectuée.\n")
    if failed:
        raise RuntimeError("lot2_live_buttons_invalid_or_unavailable")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=600)
    parser.add_argument("--require-complete", action="store_true",
                        help="Recevoir le lot seulement après preuve réelle sur 6/6 catégories")
    args = parser.parse_args()
    if not 100 <= args.limit <= 4000:
        parser.error("invalid_message_scan_limit")
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    results = asyncio.run(inspect(limit=args.limit))
    if args.require_complete:
        required = {"films", "series", "desir", "comedie", "anime", "action"}
        verified = {row["category"] for row in results
                    if all(row.get(key) == "verified" for key in (
                        "latest_public_v4", "public_photo_four_buttons",
                        "private_three_buttons", "central_receipt"))
                    and row.get("errors") == 0}
        if verified != required:
            raise SystemExit("LOT2_NOT_ACCEPTED: " +
                             ", ".join(sorted(required - verified)))


if __name__ == "__main__":
    main()
