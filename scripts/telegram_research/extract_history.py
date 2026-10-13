import argparse
import asyncio
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession

async def collect(channel, days):
    api_id = os.environ.get("TG_API_ID", "")
    api_hash = os.environ.get("TG_API_HASH", "")
    session = os.environ.get("TG_SESSION_STRING", "")
    if not (api_id.isdigit() and api_hash and session):
        raise RuntimeError("Missing TG_API_ID, TG_API_HASH or TG_SESSION_STRING")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    collected = []
    async with TelegramClient(StringSession(session), int(api_id), api_hash) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram session is not authorized")
        entity = await client.get_entity(channel)
        async for message in client.iter_messages(entity, limit=None, wait_time=1):
            if not message.date:
                continue
            moment = message.date.astimezone(timezone.utc)
            if moment < cutoff:
                break
            collected.append({
                "id": message.id,
                "date_utc": moment.isoformat(),
                "text": message.raw_text or "",
                "url": "https://t.me/" + channel + "/" + str(message.id),
                "views": message.views,
                "forwards": message.forwards,
                "media_type": type(message.media).__name__ if message.media else None
            })
            if len(collected) % 100 == 0:
                print("Collected", len(collected), flush=True)
    return list(reversed(collected))

def export(channel, days, messages, folder):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (channel + "_history.json")
    path.write_text(json.dumps({
        "channel": channel,
        "days": days,
        "count": len(messages),
        "messages": messages
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    with (folder / (channel + "_history.csv")).open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["id", "date_utc", "text", "url", "views", "forwards", "media_type"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in messages:
            copy = dict(row)
            if copy["text"].lstrip().startswith(("=", "+", "-", "@")):
                copy["text"] = "'" + copy["text"]
            writer.writerow(copy)
    print("Exported", len(messages), "messages to", str(folder), flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", default="ActuFootZoneFr")
    parser.add_argument("--days", type=int, default=3, choices=(1, 2, 3, 7))
    parser.add_argument("--out", default="telegram_exports")
    args = parser.parse_args()
    if not args.channel.replace("_", "").isalnum():
        parser.error("Expected a public channel username")
    messages = asyncio.run(collect(args.channel, args.days))
    export(args.channel, args.days, messages, Path(args.out))

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Telegram extraction failed:", str(error), file=sys.stderr)
        sys.exit(1)
