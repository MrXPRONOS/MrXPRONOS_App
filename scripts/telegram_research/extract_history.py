#!/usr/bin/env python3
"""Extraction ponctuelle de l'historique d'un canal Telegram public via Telethon.

Aucun workflow n'est associé à ce script. Il ne s'exécute que lorsqu'on le lance
explicitement. Secrets attendus: TG_API_ID, TG_API_HASH, TG_SESSION_STRING.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc


def normalize_channel(value: str) -> str:
    value = re.sub(r"^https?://(?:www\.)?(?:t\.me|telegram\.me)/(?:s/)?", "", value.strip(), flags=re.I)
    value = value.strip("/").lstrip("@").split("/")[0].split("?")[0]
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", value):
        raise ValueError("Canal public invalide")
    return value


async def collect(channel: str, since: datetime, until: datetime) -> tuple[list[dict], int]:
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    api_id = os.getenv("TG_API_ID", "").strip()
    api_hash = os.getenv("TG_API_HASH", "").strip()
    session_string = os.getenv("TG_SESSION_STRING", "").strip()
    if not (api_id.isdigit() and api_hash and session_string):
        raise RuntimeError("Secrets requis: TG_API_ID, TG_API_HASH, TG_SESSION_STRING")

    rows: list[dict] = []
    scanned = 0
    async with TelegramClient(StringSession(session_string), int(api_id), api_hash) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram non autorisée ou révoquée")
        entity = await client.get_entity(channel)
        async for msg in client.iter_messages(entity, limit=None, wait_time=1):
            scanned += 1
            if not msg.date:
                continue
            stamp = msg.date.astimezone(UTC)
            if stamp < since:
                break
            if stamp > until:
                continue
            reactions = {}
            for item in getattr(getattr(msg, "reactions", None), "results", None) or []:
                reaction = getattr(item, "reaction", None)
                label = getattr(reaction, "emoticon", None)
                if not label:
                    label = "custom:" + str(getattr(reaction, "document_id", "unknown"))
                reactions[label] = int(getattr(item, "count", 0) or 0)
            rows.append({
                "id": int(msg.id),
                "date_utc": stamp.isoformat(),
                "text": msg.raw_text or "",
                "url": f"https://t.me/{channel}/{msg.id}",
                "views": getattr(msg, "views", None),
                "forwards": getattr(msg, "forwards", None),
                "reactions": reactions,
                "media_type": type(msg.media).__name__ if msg.media else None,
                "grouped_id": str(msg.grouped_id) if getattr(msg, "grouped_id", None) else None,
            })
    return sorted(rows, key=lambda row: (row["date_utc"], row["id"])), scanned


def safe_csv(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def export(channel: str, hours: int, rows: list[dict], scanned: int, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "channel": channel,
        "window_hours": hours,
        "scanned": scanned,
        "count": len(rows),
        "messages": rows,
    }
    (out / f"{channel}_{stamp}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = ["id", "date_utc", "text", "url", "views", "forwards", "reactions", "media_type", "grouped_id"]
    with (out / f"{channel}_{stamp}.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            item = dict(row)
            item["reactions"] = json.dumps(item["reactions"], ensure_ascii=False)
            writer.writerow({key: safe_csv(item.get(key)) for key in fields})
    with (out / f"{channel}_{stamp}.txt").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(f"\n{'='*60}\n{row['date_utc']} | {row['url']}\n{'='*60}\n{row['text']}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True, help="@canal ou URL https://t.me/canal")
    parser.add_argument("--hours", type=int, default=72, help="Fenêtre glissante, 1 à 336 heures")
    parser.add_argument("--out", default="telegram_exports")
    args = parser.parse_args()
    if not 1 <= args.hours <= 336:
        parser.error("--hours doit être compris entre 1 et 336")
    channel = normalize_channel(args.channel)
    until = datetime.now(UTC)
    since = until - timedelta(hours=args.hours)
    rows, scanned = asyncio.run(collect(channel, since, until))
    export(channel, args.hours, rows, scanned, Path(args.out))
    print(f"TELEGRAM_EXPORT_OK channel=@{channel} count={len(rows)} scanned={scanned}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"TELEGRAM_EXPORT_ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
