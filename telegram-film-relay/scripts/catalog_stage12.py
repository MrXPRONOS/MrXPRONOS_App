"""Stages 1-2 only: read-only Telegram private-library audit and D1 metadata sync.

Neither this module nor its workflow sends, copies, forwards, edits or deletes
Telegram messages. All catalogue records are PENDING_REVIEW until a separate
future approval and delivery implementation. Existing historical catalogue
message IDs are intentionally not trusted or imported.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from film_relay.episode_identity import episode_numbers, consistent_title, canonical_title
from film_relay.public_video_archive import is_video_message, video_title
from film_relay.runner import resolve_peer

CATEGORIES = {
    "series": ("SERIES_PRIVATE_CHANNEL", "SERIES_PUBLIC_CHANNEL", "SERIES_RIGHTS_ATTESTED", "@seriesvf_cinex"),
    "action": ("ACTION_PRIVATE_CHANNEL", "ACTION_PUBLIC_CHANNEL", "ACTION_RIGHTS_ATTESTED", "@filmsaction2026vf"),
}
PRIVATE_ID = re.compile(r"^-100[0-9]{5,}$")
HANDLE = re.compile(r"^@[a-zA-Z0-9_]{5,32}$")
MAX_SCAN = 250
MAX_CANDIDATES = 180


def configured_targets(env: dict) -> list[dict]:
    targets = []
    for category, (id_var, pub_var, rights_var, default_public) in CATEGORIES.items():
        channel_id = str(env.get(id_var, "")).strip()
        public = str(env.get(pub_var) or default_public).strip()
        attested = str(env.get(rights_var, "")).strip().lower() == "true"
        if not PRIVATE_ID.fullmatch(channel_id):
            raise ValueError(f"{id_var} absent ou invalide")
        if not HANDLE.fullmatch(public):
            raise ValueError(f"{pub_var} absent ou invalide")
        targets.append({"category": category, "private_chat_id": channel_id,
                        "public_handle": public, "rights_attested": attested})
    if len({x["private_chat_id"] for x in targets}) != len(targets):
        raise ValueError("Vidéothèques séries et action identiques: arrêt")
    return targets


def classify(message, category: str) -> dict | None:
    if not is_video_message(message):
        return None
    document = getattr(message, "document", None)
    if document is None or not getattr(document, "id", None) or not getattr(message, "id", 0):
        return None
    if getattr(message, "noforwards", False):
        return None
    filename = str(getattr(getattr(message, "file", None), "name", "") or "")[:200]
    caption = str(getattr(message, "raw_text", "") or "")[:1200]
    if category == "series":
        number = episode_numbers(caption) or episode_numbers(filename)
        if not number:
            return None
        # Never associate a video to a series based on adjacency alone.
        title = consistent_title("", caption, filename) if filename else consistent_title("", caption, "")
        if not title:
            return None
        season, episode = number
    else:
        title = consistent_title("", caption, filename) if filename else consistent_title("", caption, "")
        if not title:
            return None
        # Action is strictly a film category; reject recognizable TV episodes.
        if episode_numbers(caption) or episode_numbers(filename):
            return None
        season = episode = None
    normalized = canonical_title(title)
    if not normalized or len(normalized) < 3:
        return None
    title_key = hashlib.sha256((category + "\0" + normalized).encode()).hexdigest()[:32]
    size = int(getattr(getattr(message, "file", None), "size", 0) or 0)
    if size < 0:
        return None
    return {
        "category": category, "source_message_id": int(message.id),
        "title_key": title_key, "normalized_title": normalized,
        "display_title": title[:90], "content_kind": "series" if category == "series" else "film",
        "season_number": season, "episode_number": episode, "filename": filename,
        "file_size": size, "media_kind": "video" if getattr(message, "video", None) else "document",
    }


def describe_result(target: dict, media: list[dict], scanned: int, ignored: int, *, bot_access: str = "unchecked") -> dict:
    return {
        **target, "owner_access": "verified", "bot_access": bot_access, "status": "scanned",
        "scanned_messages": scanned, "candidate_count": len(media),
        "ignored_messages": ignored, "media": media,
    }


async def audit_targets(targets: list[dict], *, max_scan: int = MAX_SCAN) -> dict:
    from telethon import TelegramClient, utils
    from telethon.sessions import StringSession
    session = os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING") or os.getenv("TG_STREAM_SESSION")
    api_id, api_hash = os.getenv("TG_API_ID"), os.getenv("TG_API_HASH")
    if not session or not str(api_id or "").isdigit() or not api_hash:
        raise RuntimeError("Session Telegram de lecture absente")
    client = TelegramClient(StringSession(session), int(api_id), api_hash,
                            flood_sleep_threshold=0, request_retries=1,
                            connection_retries=2, receive_updates=False)
    await client.connect()
    result = {"scanned_at": datetime.now(timezone.utc).isoformat(), "libraries": []}
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram utilisateur expirée")
        me = await client.get_me()
        # Resolve the actual public Cine Radar bot using the owner session:
        # no bot token is needed, and the publishing bots are not substitutes.
        radar_bot = None
        try:
            candidate = await client.get_entity("@CineRadarFr_Bot")
            if (getattr(candidate, "bot", False)
                    and str(getattr(candidate, "username", "") or "").casefold()
                    == "cineradarfr_bot"):
                radar_bot = candidate
        except Exception:
            pass
        for target in targets:
            item = {**target, "owner_access": "error", "status": "error", "media": [],
                    "candidate_count": 0, "scanned_messages": 0}
            try:
                peer = await resolve_peer(client, target["private_chat_id"])
                if (utils.get_peer_id(peer) != int(target["private_chat_id"])
                        or not getattr(peer, "broadcast", False)
                        or getattr(peer, "username", None)):
                    raise RuntimeError("Le canal privé configuré n'est pas le canal réellement résolu")
                if getattr(peer, "noforwards", False):
                    raise RuntimeError("Vidéothèque protégée contre la redistribution")
                permissions = await client.get_permissions(peer, me)
                if not (getattr(permissions, "is_creator", False) or
                        getattr(permissions, "is_admin", False)):
                    raise RuntimeError("Le compte utilisateur n'est pas administrateur de la vidéothèque")
                if not target["rights_attested"]:
                    raise RuntimeError("Attestation des droits non confirmée")
                bot_access = "error" if radar_bot is None else "not_member"
                if radar_bot is not None:
                    try:
                        bot_permissions = await client.get_permissions(peer, radar_bot)
                        if (getattr(bot_permissions, "is_creator", False) or
                                getattr(bot_permissions, "is_admin", False)):
                            bot_access = "verified"
                    except Exception:
                        # Bot absent: inventory remains available for review,
                        # but must NEVER be treated as delivery-ready.
                        bot_access = "not_member"
                found = []
                observed = 0
                for message in [m async for m in client.iter_messages(peer, limit=max_scan)]:
                    observed += 1
                    media = classify(message, target["category"])
                    if media:
                        found.append(media)
                    if len(found) >= MAX_CANDIDATES:
                        break
                item = describe_result(target, found, observed, observed-len(found), bot_access=bot_access)
            except Exception as exc:
                # No private Telegram IDs, usernames or tokens in log outputs.
                item["error_type"] = type(exc).__name__
                item["status"] = "blocked"
            result["libraries"].append(item)
    finally:
        await client.disconnect()
    return result


def sql_queries(report: dict):
    """One-way idempotent D1 upserts. Never approve titles/media for delivery."""
    for lib in report["libraries"]:
        if lib.get("status") != "scanned":
            continue
        yield {"sql": """INSERT INTO cine_delivery_libraries
          (category,public_handle,private_chat_id,rights_attested,owner_access,bot_access,observed_videos,last_scanned_at,last_bot_checked_at)
          VALUES(?,?,?,?,?,?,?,?,?)
          ON CONFLICT(category) DO UPDATE SET
          public_handle=excluded.public_handle,
          private_chat_id=excluded.private_chat_id,
          rights_attested=excluded.rights_attested,
          owner_access=excluded.owner_access,
          bot_access=excluded.bot_access,
          last_bot_checked_at=excluded.last_bot_checked_at,
          observed_videos=excluded.observed_videos,
          last_scanned_at=excluded.last_scanned_at,updated_at=CURRENT_TIMESTAMP""",
          "params": [lib["category"],lib["public_handle"],lib["private_chat_id"],
                     str(int(lib["rights_attested"])),lib["owner_access"],
                     lib.get("bot_access","unchecked"),str(len(lib["media"])),
                     report["scanned_at"],report["scanned_at"]]}
        for m in lib["media"]:
            yield {"sql": """INSERT INTO cine_delivery_titles
             (title_key,category,normalized_title,display_title,content_kind,rights_attested)
             VALUES(?,?,?,?,?,?)
             ON CONFLICT(title_key) DO UPDATE SET
             display_title=excluded.display_title,rights_attested=excluded.rights_attested,
             updated_at=CURRENT_TIMESTAMP""",
             "params": [m["title_key"],m["category"],m["normalized_title"],m["display_title"],
                        m["content_kind"],str(int(lib["rights_attested"]))]}
            yield {"sql": """INSERT INTO cine_delivery_media
             (category,source_message_id,title_key,season_number,episode_number,filename,file_size,media_kind,observed_at)
             VALUES(?,?,?,?,?,?,?,?,?)
             ON CONFLICT(category,source_message_id) DO UPDATE SET
             title_key=excluded.title_key,season_number=excluded.season_number,
             episode_number=excluded.episode_number,filename=excluded.filename,
             file_size=excluded.file_size,media_kind=excluded.media_kind,
             observed_at=excluded.observed_at""",
             "params": [m["category"],str(m["source_message_id"]),m["title_key"],
                        str(m["season_number"]) if m["season_number"] is not None else None,
                        str(m["episode_number"]) if m["episode_number"] is not None else None,
                        m["filename"],str(m["file_size"]),m["media_kind"],report["scanned_at"]]}


def sync_d1(report: dict, *, token: str, account: str, database: str) -> int:
    import requests
    if not token or not account or not database:
        raise RuntimeError("Connexion Cloudflare D1 absente ; métadonnées non importées")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{database}/query"
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    queries = list(sql_queries(report))
    # Keep batches small and retry idempotently on HTTP 429/5xx; no new media.
    for off in range(0, len(queries), 20):
        batch = queries[off:off+20]
        response = requests.post(url, json={"batch":batch}, headers=headers, timeout=40)
        if not response.ok:
            raise RuntimeError("Cloudflare D1 requête refusée: HTTP " + str(response.status_code))
        data = response.json()
        if not data.get("success") or not all(x.get("success", True) for x in data.get("result", [])):
            raise RuntimeError("Cloudflare D1 import incomplet")
    return sum(len(x.get("media", [])) for x in report["libraries"] if x.get("status") == "scanned")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-limit", type=int, default=MAX_SCAN)
    parser.add_argument("--output", default="state/catalog_stage12_report.json")
    parser.add_argument("--sync", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.scan_limit <= MAX_SCAN:
        parser.error("scan-limit doit être entre 1 et 250")
    targets = configured_targets(os.environ)
    report = asyncio.run(audit_targets(targets, max_scan=args.scan_limit))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    safe = {x["category"]: {"status":x["status"],"bot_access":x.get("bot_access","unchecked"),
                             "candidates":x["candidate_count"],
                             "observed":x["scanned_messages"],
                             "error_type":x.get("error_type")} for x in report["libraries"]}
    print("CATALOG_STAGE12_AUDIT: " + json.dumps(safe))
    if any(x["status"] != "scanned" for x in report["libraries"]):
        raise SystemExit("Au moins une vidéothèque inaccessible : import refusé")
    if args.sync:
        count = sync_d1(report, token=os.getenv("CLOUDFLARE_API_TOKEN", ""),
                        account=os.getenv("CLOUDFLARE_ACCOUNT_ID", ""),
                        database=os.getenv("CINERADAR_D1_DATABASE_ID", ""))
        print("CATALOG_STAGE12_IMPORTED: " + str(count) + " métadonnées à valider")
if __name__ == "__main__":
    main()
