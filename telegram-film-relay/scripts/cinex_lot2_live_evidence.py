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
from pathlib import Path

from film_relay.public_video_archive import is_video_message
from film_relay.cinex_v4_policy import has_automatic_ttl
from film_relay.publication import (
    film_folder_url, video_labels, verify_complete_public_video_keyboard,
)
from film_relay.radar_download_registry import is_bot_download_url, RadarRegistry
from film_relay.ten_video_rotation import category_targets
from film_relay.public_video_retention import validate_retention_targets
from film_relay.runner import resolve_peer

LOG = logging.getLogger("cinex.lot2.live")


def button_pairs(message):
    rows = getattr(message, "buttons", None) or ()
    result = []
    for row in rows:
        result.append([
            (str(getattr(getattr(button, "button", button), "text", "") or ""),
             str(getattr(getattr(button, "button", button), "url", "") or ""))
            for button in row
        ])
    return result


def is_private_fiche(message, public_handle):
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
        and (is_bot_download_url(last_url)
             or last_url.startswith("https://t.me/c/"))  # Season index
    )


def validate_public_sample(message, public, category=None):
    rows = button_pairs(message)
    if len(rows) != 4 or any(len(row) != 1 for row in rows):
        return False
    first_label, private_link = rows[0][0]
    if category is not None and first_label not in {
        video_labels(category, episode=False)[0],
        video_labels(category, episode=True)[0],
    }:
        return False
    _, download_url = rows[1][0]
    return verify_complete_public_video_keyboard(
        message, public, private_link, download_url,
        watch_label=first_label
    )


def check_receipt(download_url):
    """Read-only D1 proof: a deep-link token resolves to an actual published item."""
    if not is_bot_download_url(download_url):
        return False
    token = download_url.split("?start=d_", 1)[-1]
    rows = RadarRegistry()._query(
        "SELECT status FROM cine_classic_links WHERE token=? LIMIT 1",
        [token]
    ).get("results") or []
    return len(rows) == 1 and rows[0].get("status") == "published"


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
                        "verified" if validate_public_sample(video, public, category) else "invalid"
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
                            "verified" if check_receipt(dl) else "not_verified"
                        )
                    else:
                        result["errors"] += 1
                posters = [
                    m async for m in client.iter_messages(private, limit=limit)
                    if getattr(m, "photo", None) and len(button_pairs(m)) == 3
                ]
                if posters:
                    result["private_three_buttons"] = (
                        "verified" if any(
                            is_private_fiche(poster, public_handle)
                            for poster in posters[:12]
                        ) else "invalid"
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
        any(value == "pending_no_sample" for value in (
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
    summary = os.getenv("GITHUB_STEP_SUMMARY", "").strip()
    if summary:
        with Path(summary).open("a", encoding="utf-8") as f:
            f.write("\n### CinéX Lot 2 — échantillons de publications réelles\n")
            f.write("| Catégorie | Vidéo publique 4 boutons | Affiche privée 3 boutons | Lien D1 | Erreurs |\n")
            f.write("|---|---|---|---|---:|\n")
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
    args = parser.parse_args()
    if not 100 <= args.limit <= 4000:
        parser.error("invalid_message_scan_limit")
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(inspect(limit=args.limit))


if __name__ == "__main__":
    main()
