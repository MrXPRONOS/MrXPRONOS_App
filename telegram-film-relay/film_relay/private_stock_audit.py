"""Read-only audit of CineX private stocks: cover, description, file names.

Never sends, edits, joins, forwards, copies, downloads, or deletes media.
Only reads already configured destination channels.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from pathlib import PurePath

from .public_video_archive import is_video_message
from .ten_video_rotation import category_targets

_VIDEO_EXT = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}
_GENERIC = re.compile(
    r"(?i)^(?:video|vid|movie|film|fichier|document|file|telegram|"
    r"whatsapp|upload|unknown|untitled|titre non identifie|"
    r"new film|video cinex)(?:[\W_]*\d+)?$"
)
_TIMESTAMPS = re.compile(r"^(?:20\d{6}[\W_]*\d{6,}|\d{10,18}|[0-9a-f]{20,})$", re.I)
_MARKER = re.compile(r"(?i)#(?:CXSTOCK_|CXSERIES_|CINEX_VIDEO_|CXS)[A-Za-z0-9_]*")


def source_filename(message) -> str:
    name = getattr(getattr(message, "file", None), "name", None)
    if name:
        return str(name)
    for attr in getattr(getattr(message, "document", None), "attributes", []) or []:
        if type(attr).__name__ == "DocumentAttributeFilename":
            return str(getattr(attr, "file_name", "") or "")
    return ""


def filename_descriptive(name: str) -> bool:
    if not name or len(name) > 250:
        return False
    path = PurePath(name)
    if path.suffix.lower() not in _VIDEO_EXT:
        return False
    stem = re.sub(r"[\W_]+", " ", path.stem, flags=re.U).strip().lower()
    return bool(len(stem) >= 4 and not _GENERIC.fullmatch(stem)
                and not _TIMESTAMPS.fullmatch(stem)
                and re.search(r"[^\W\d_]{3}", stem, flags=re.U))


def description_descriptive(message) -> bool:
    text = str(getattr(message, "raw_text", "") or "")
    text = _MARKER.sub("", text)
    text = re.sub(r"(?i)(?:https?://\S+|#[a-z_0-9]{3,})", "", text)
    clean = re.sub(r"\s+", " ", text).strip()
    # A name plus episode number is a valid *title*, but not a description.
    return bool(len(clean) >= 35 and len(clean.split()) >= 7)


def audit_messages(messages, *, stock: str, limit: int) -> dict:
    """Audit metadata without guessing ownership or pairing by title."""
    rows = sorted(messages, key=lambda x: int(x.id))
    photos = []
    totals = {
        "stock": stock, "messages_scanned": len(rows),
        "scan_limit_reached": len(rows) >= limit, "videos": 0,
        "prior_photo_3": 0, "prior_photo_80": 0,
        "photo_description_3": 0, "photo_description_80": 0,
        "file_named": 0, "filename_missing_or_generic": 0,
        "videos_with_caption": 0, "video_without_photo_80": 0,
        "photo_without_description_80": 0, "samples": [],
    }
    for item in rows:
        if getattr(item, "photo", None):
            photos.append(item)
            continue
        if not is_video_message(item):
            continue
        totals["videos"] += 1
        nearby = [photo for photo in photos if 0 < item.id - photo.id <= 80]
        cover = nearby[-1] if nearby else None
        if cover is not None:
            totals["prior_photo_80"] += 1
            if description_descriptive(cover):
                totals["photo_description_80"] += 1
            else:
                totals["photo_without_description_80"] += 1
            if item.id - cover.id <= 3:
                totals["prior_photo_3"] += 1
                if description_descriptive(cover):
                    totals["photo_description_3"] += 1
        else:
            totals["video_without_photo_80"] += 1
        filename_ok = filename_descriptive(source_filename(item))
        totals["file_named" if filename_ok else "filename_missing_or_generic"] += 1
        if str(getattr(item, "raw_text", "") or "").strip():
            totals["videos_with_caption"] += 1
        if (len(totals["samples"]) < 12
                and (cover is None or not filename_ok
                     or not description_descriptive(cover))):
            reasons = []
            if cover is None:
                reasons.append("no_prior_photo_80")
            elif not description_descriptive(cover):
                reasons.append("short_or_absent_cover_description")
            if not filename_ok:
                reasons.append("filename_not_descriptive")
            totals["samples"].append({"video_message_id": int(item.id),
                                      "reason": reasons})
    totals["all_verified"] = bool(
        totals["videos"] and totals["prior_photo_80"] == totals["videos"]
        and totals["photo_description_80"] == totals["videos"]
        and totals["file_named"] == totals["videos"]
        and not totals["scan_limit_reached"]
    )
    return totals


async def execute(*, history=4000):
    from telethon import TelegramClient, utils
    from telethon.sessions import StringSession
    from .runner import resolve_peer
    from .unified_download import configured_private_id

    credentials = (
        os.getenv("TG_API_ID"),
        os.getenv("TG_API_HASH"),
        os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
        or os.getenv("TG_STREAM_SESSION"),
    )
    if not all(credentials):
        raise RuntimeError("Telegram session credentials missing")
    target_list = [(name, int(private)) for name, _, private in category_targets()]
    try:
        central = configured_private_id()
        if central:
            target_list.append(("central_cineradar", int(central)))
    except Exception as exc:
        print("AUDIT_TARGET_ERROR " + json.dumps(
            {"stock": "central_cineradar", "error_type": type(exc).__name__}))
    reports = []
    client = TelegramClient(StringSession(credentials[2]),
                            int(credentials[0]), credentials[1],
                            request_retries=1, flood_sleep_threshold=0)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram session unauthorized")
        seen = {}
        for name, private_id in target_list:
            try:
                if private_id in seen:
                    print("AUDIT_DUPLICATE " + json.dumps(
                        {"stock": name, "same_as": seen[private_id]}))
                    continue
                seen[private_id] = name
                private = await resolve_peer(client, str(private_id))
                if utils.get_peer_id(private) != private_id:
                    raise RuntimeError("Unexpected private chat identity")
                if not getattr(private, "broadcast", False) or getattr(private, "username", None):
                    raise RuntimeError("Private destination not a private broadcast channel")
                messages = [m async for m in client.iter_messages(private, limit=history)]
                row = audit_messages(messages, stock=name, limit=history)
                reports.append(row)
                print("AUDIT_STOCK " + json.dumps(row, ensure_ascii=False))
                await asyncio.sleep(2)
            except Exception as exc:
                if type(exc).__name__ in ("FloodWaitError", "PeerFloodError"):
                    raise
                row = {"stock": name, "error_type": type(exc).__name__}
                reports.append(row)
                print("AUDIT_STOCK_ERROR " + json.dumps(row))
    finally:
        await client.disconnect()
    summary = os.getenv("GITHUB_STEP_SUMMARY", "")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("\n### Audit lecture seule — affiches, descriptions et fichiers privés\n")
            f.write("| Stock | Vidéos vues | Photo <=3 | Photo <=80 | Description photo <=80 | Fichiers nommés | Scan complet | Erreur |\n")
            f.write("|---|---:|---:|---:|---:|---:|---|---|\n")
            for row in reports:
                f.write(
                    f"| {row['stock']} | {row.get('videos', '—')} | "
                    f"{row.get('prior_photo_3', '—')} | {row.get('prior_photo_80', '—')} | "
                    f"{row.get('photo_description_80', '—')} | "
                    f"{row.get('file_named', '—')} | "
                    f"{'Non' if row.get('scan_limit_reached') else 'Oui'} | "
                    f"{row.get('error_type', '—')} |\n"
                )
            f.write("\nLes photos proches sont des indices de structure, pas une preuve d'identité du film. Un fichier nommé désigne un nom présent et non générique, pas une vérification sémantique du titre. Aucun média modifié.\n")
    return reports


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", type=int, default=4000)
    args = parser.parse_args()
    if not 100 <= args.history <= 20000:
        parser.error("--history doit être entre 100 et 20000")
    asyncio.run(execute(history=args.history))


if __name__ == "__main__":
    main()
