"""Ciné Radar: cache channel profile avatars from publicly indexed Telegram channels.
Uses an existing authorized MTProto session; never joins a channel or copies posts/videos.
Photos are limited to small public channel avatars and stored under cinecanaux/assets/avatars.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
AVATAR_DIR = ROOT / "assets" / "avatars"
INDEX_FILE = ROOT / "assets" / "avatar_index.json"
PUBLIC_DIRECTORY = "https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/api/catalog"
USERNAME = re.compile(r"^[a-z][a-z0-9_]{4,31}$", re.I)
LINK = re.compile(r"^https://t\.me/([a-z][a-z0-9_]{4,31})/?$", re.I)


def username_from_link(link: str) -> str | None:
    match = LINK.fullmatch(str(link or "").strip())
    return match.group(1).lower() if match else None


def directory_usernames(fetch_json=None) -> list[str]:
    if fetch_json is None:
        def fetch_json(url: str):
            request = Request(url, headers={"User-Agent": "CineRadarAvatarIndexer/1.0", "Accept": "application/json"})
            with urlopen(request, timeout=20) as response:
                if response.status != 200:
                    raise RuntimeError(f"Catalog returned HTTP {response.status}")
                return json.load(io.TextIOWrapper(response, encoding="utf-8"))
    result = []
    seen = set()
    for offset in range(0, 4000, 80):
        catalog = fetch_json(f"{PUBLIC_DIRECTORY}?limit=80&offset={offset}")
        channels = catalog.get("channels", [])
        if not isinstance(channels, list):
            raise RuntimeError("Invalid public channel catalog")
        for channel in channels:
            handle = username_from_link(channel.get("link", ""))
            if handle and handle not in seen:
                seen.add(handle)
                result.append(handle)
        if not channels or offset + 80 >= int(catalog.get("total", len(channels))):
            break
    return result


async def collect_avatars(handles: list[str]) -> dict:
    from PIL import Image, ImageOps
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.types import Channel
    from telethon.errors import FloodWaitError

    api_id = os.environ.get("TG_API_ID", "").strip()
    api_hash = os.environ.get("TG_API_HASH", "").strip()
    session = os.environ.get("TG_STRING_SESSION", "").strip()
    if not api_id.isdigit() or not api_hash or not session:
        raise RuntimeError("Telegram API credentials are missing")

    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    try:
        previous = json.loads(INDEX_FILE.read_text(encoding="utf-8")).get("avatars", {})
    except (FileNotFoundError, ValueError, OSError):
        previous = {}
    index = {key: value for key, value in previous.items()
             if USERNAME.fullmatch(key) and (AVATAR_DIR / (key + ".jpg")).exists()}
    refreshed = 0
    missing = 0
    errors = 0
    stop = False

    async with TelegramClient(StringSession(session), int(api_id), api_hash) as client:
        with tempfile.TemporaryDirectory(prefix="cineradar-avatars-") as tmp:
            for handle in handles[:160]:
                if stop:
                    break
                try:
                    # Public channels only; do not join, read messages or transfer media.
                    entity = await client.get_entity("@" + handle)
                    if not isinstance(entity, Channel) or not bool(getattr(entity, "broadcast", False)):
                        missing += 1
                        continue
                    if not getattr(entity, "photo", None):
                        missing += 1
                        continue
                    canonical = str(getattr(entity, "username", "") or "").lower()
                    if canonical != handle:
                        missing += 1
                        continue
                    saved = await client.download_profile_photo(entity, file=str(Path(tmp) / handle))
                    if not saved:
                        missing += 1
                        continue
                    file = Path(saved)
                    if file.stat().st_size > 8_000_000:
                        errors += 1
                        continue
                    with Image.open(file) as original:
                        cover = ImageOps.fit(original.convert("RGB"), (256, 256), method=Image.Resampling.LANCZOS)
                        output = AVATAR_DIR / (handle + ".jpg")
                        cover.save(output, "JPEG", quality=84, optimize=True, progressive=True)
                    index[handle] = {"telegram_id": str(entity.id), "updated_at": datetime.now(timezone.utc).isoformat()}
                    refreshed += 1
                except FloodWaitError as exc:
                    print(f"Telegram rate limit reached; remaining channels deferred ({int(exc.seconds)}s)", flush=True)
                    stop = True
                except Exception as exc:
                    errors += 1
                    print(f"Avatar unavailable for {handle}: {type(exc).__name__}", flush=True)
                finally:
                    # Gentle pace, share the existing Telegram account with other project jobs.
                    await asyncio.sleep(1.5)

    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps({
        "version": 1, "updated_at": datetime.now(timezone.utc).isoformat(),
        "requested": len(handles), "refreshed": refreshed,
        "missing": missing, "errors": errors, "avatars": index
    }, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {"requested": len(handles), "refreshed": refreshed, "retained": len(index), "missing": missing, "errors": errors}


if __name__ == "__main__":
    handles = directory_usernames()
    if not handles:
        raise SystemExit("No public channels returned by Ciné Radar")
    results = asyncio.run(collect_avatars(handles))
    print("Avatar indexing:", json.dumps(results))
    if not results["retained"]:
        raise SystemExit("No real Telegram profile photos available; generic art remains in use")
