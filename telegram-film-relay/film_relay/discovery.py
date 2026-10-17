"""Read-only public Telegram channel discovery. Never joins, forwards or downloads media.

Finds broadcast channels by public keyword search and checks for a nearby photo
caption + long-video *pattern*. This is not proof of a film's identity, or a license.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .verification import screen_pairs, channel_format_verified
from .text import clean_caption, first_title

LOG = logging.getLogger("telegram_film_discovery")
USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$")


def normalize_username(value: str) -> str | None:
    """Accept @username or the root of a public t.me/channel link only."""
    value = str(value or "").strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/", "https://telegram.me/"):
        if value.lower().startswith(prefix):
            value = value[len(prefix):].split("?", 1)[0].strip("/")
            break
    value = value.lstrip("@")
    if "/" in value or not USERNAME_RE.fullmatch(value):
        return None
    return value


def is_public_broadcast(entity: Any) -> bool:
    return bool(getattr(entity, "broadcast", False) and not getattr(entity, "noforwards", False)
                and normalize_username(getattr(entity, "username", "")))


def evaluate_messages(messages: list[Any], cfg: dict | None = None) -> dict:
    """Strict structural checks only; never interpret these as rights verification."""
    cfg = cfg or {}
    screening = screen_pairs(
        messages, min_minutes=int(cfg.get("min_video_minutes", 40)),
        min_megabytes=int(cfg.get("min_video_megabytes", 150)),
        max_gap=int(cfg.get("max_pair_message_gap", 2)),
        max_age_minutes=int(cfg.get("max_pair_age_minutes", 60)),
        min_caption_chars=int(cfg.get("min_caption_chars", 25)),
    )
    pairs_needed = max(2, int(cfg.get("min_verified_pairs", 2)))
    verified = channel_format_verified(screening, min_pairs=pairs_needed)
    return {
        "matching_pairs": len(screening.pairs),
        "sample_post_ids": [int(pair.poster.id) for pair in screening.pairs[:3]],
        "format": "photo_texte_puis_video" if verified else "non_verifie",
        "format_verified": verified,
        "strict_filters": {"min_verified_pairs": pairs_needed,
                           "min_video_minutes": int(cfg.get("min_video_minutes", 40)),
                           "min_video_megabytes": int(cfg.get("min_video_megabytes", 150))},
        "rejected_pairs": screening.rejected,
    }


def load_config(path: str) -> dict:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    cfg["search_queries"] = [str(x).strip() for x in cfg.get("search_queries", []) if str(x).strip()][:8]
    cfg["seed_channels"] = [x for x in cfg.get("seed_channels", []) if normalize_username(x)][:50]
    cfg["max_channels_per_run"] = min(30, max(1, int(cfg.get("max_channels_per_run", 16))))
    cfg["sample_messages"] = min(150, max(10, int(cfg.get("sample_messages", 80))))
    cfg["results_per_query"] = min(20, max(1, int(cfg.get("results_per_query", 10))))
    cfg["request_pause_seconds"] = max(2.0, float(cfg.get("request_pause_seconds", 3.0)))
    cfg["min_verified_pairs"] = max(2, min(5, int(cfg.get("min_verified_pairs", 2))))
    cfg["min_video_minutes"] = max(30, int(cfg.get("min_video_minutes", 40)))
    cfg["min_video_megabytes"] = max(100, int(cfg.get("min_video_megabytes", 150)))
    cfg["max_pair_message_gap"] = min(3, max(1, int(cfg.get("max_pair_message_gap", 2))))
    cfg["max_pair_age_minutes"] = min(90, max(10, int(cfg.get("max_pair_age_minutes", 60))))
    cfg["min_caption_chars"] = max(20, int(cfg.get("min_caption_chars", 25)))
    if not cfg["search_queries"] and not cfg["seed_channels"]:
        raise ValueError("Ajoutez search_queries ou seed_channels dans discovery.json.")
    return cfg


def candidate_window(candidates: list[Any], cap: int, offset: int) -> list[Any]:
    """Rotate across search results between runs rather than reread the same channels."""
    if not candidates:
        return []
    start = max(0, offset) % len(candidates)
    count = min(max(1, cap), len(candidates))
    return [candidates[(start + i) % len(candidates)] for i in range(count)]


def load_previous(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {x["username"].lower(): x for x in data.get("channels", []) if x.get("username")}


async def discover(client, cfg: dict, start_offset: int = 0) -> tuple[list[dict], dict]:
    """Global channel search + read-only sampling; no join/subscribe action."""
    from telethon.tl.functions.contacts import SearchRequest
    from telethon.errors import FloodWaitError

    candidates = {}
    statistics = {"queries": 0, "found": 0, "checked": 0, "not_readable": 0,
                  "attempted": 0, "next_candidate_offset": 0, "rate_limited": False, "protected": 0, "strict_rejected": 0}

    for keyword in cfg["search_queries"]:
        try:
            response = await client(SearchRequest(q=keyword, limit=cfg["results_per_query"]))
            statistics["queries"] += 1
            for ent in response.chats:
                if is_public_broadcast(ent):
                    candidates[ent.username.lower()] = ent
            await asyncio.sleep(cfg["request_pause_seconds"])
        except FloodWaitError as exc:
            LOG.warning("Limite Telegram (%ss). Arrêt de la recherche sans forcer les requêtes.", exc.seconds)
            statistics["rate_limited"] = True
            break
        except Exception as exc:
            LOG.warning("Recherche %r indisponible : %s", keyword, exc)

    # Manually supplied channel URLs can be checked without membership.
    if not statistics["rate_limited"]:
        for item in cfg["seed_channels"]:
            username = normalize_username(item)
            if username.lower() in candidates:
                continue
            try:
                ent = await client.get_entity("@" + username)
                if is_public_broadcast(ent):
                    candidates[ent.username.lower()] = ent
                await asyncio.sleep(cfg["request_pause_seconds"])
            except FloodWaitError as exc:
                statistics["rate_limited"] = True
                LOG.warning("Limite Telegram (%ss). Arrêt des vérifications.", exc.seconds)
                break
            except Exception as exc:
                LOG.info("Lien public non accessible %s : %s", username, exc)

    statistics["found"] = len(candidates)
    results = []
    if not statistics["rate_limited"]:
        for ent in candidate_window(list(candidates.values()), cfg["max_channels_per_run"], start_offset):
            statistics["attempted"] += 1
            try:
                # Public channel content protection is a hard exclusion.
                # Resolve current entity because a search result may be stale.
                current = await client.get_entity("@" + ent.username)
                if getattr(current, "noforwards", False):
                    statistics["protected"] += 1
                    LOG.info("Canal protégé @%s : refusé", ent.username)
                    continue
                # Explicitly read ONLY; does not call JoinChannelRequest.
                messages = [m async for m in client.iter_messages(ent, limit=cfg["sample_messages"])]
                statistics["checked"] += 1
                assessment = evaluate_messages(messages, cfg)
                if not assessment["format_verified"]:
                    statistics["strict_rejected"] += 1
                if assessment["format_verified"]:
                    results.append({
                        "username": ent.username,
                        "title": getattr(ent, "title", ent.username),
                        "url": "https://t.me/" + ent.username,
                        "sampled_messages": len(messages),
                        **assessment,
                        "redistribution_rights": "non_verifies",
                        "joined_by_tool": False,
                        "source_status": "pending_rights",
                        "transfer_restricted": False,
                    })
                await asyncio.sleep(cfg["request_pause_seconds"])
            except FloodWaitError as exc:
                statistics["rate_limited"] = True
                LOG.warning("Limite Telegram (%ss). Arrêt des lectures.", exc.seconds)
                break
            except Exception as exc:
                statistics["not_readable"] += 1
                LOG.info("Lecture publique indisponible @%s : %s", ent.username, exc)
    if candidates:
        statistics["next_candidate_offset"] = (start_offset + statistics["attempted"]) % len(candidates)
    return results, statistics


def notification_text(channel: dict) -> str:
    """Compose a short Saved Messages notice without presumed redistribution rights."""
    from html import escape
    title = escape(str(channel.get("title") or channel["username"])[:120])
    username = normalize_username(channel.get("username", "")) or ""
    if not username:
        raise ValueError("Nom de canal Telegram invalide.")
    count = max(0, int(channel.get("matching_pairs", 0)))
    return (
        "🎬 <b>Canal de films repéré</b>\n"
        f"📺 <b>{title}</b>\n"
        f"🔗 https://t.me/{username}\n"
        f"🎞️ {count} couples affiche/vidéo détectés dans l'échantillon\n"
        "🔎 Proposition uniquement — non ajoutée aux sources du relais.\n"
        "⚠️ Droits de redistribution non vérifiés."
    )


async def notify_saved_messages(client, channels: list[dict], previously_notified: set[str]
                                ) -> tuple[list[str], int]:
    """Send each unnotified result to the user's own Telegram Saved Messages."""
    notified = []
    failed = 0
    for channel in channels:
        username = normalize_username(channel.get("username", ""))
        if not username or username.casefold() in previously_notified:
            continue
        try:
            await client.send_message("me", notification_text(channel), parse_mode="html",
                                      link_preview=False)
        except Exception as exc:
            failed += 1
            LOG.warning("Notification Messages enregistrés impossible @%s : %s",
                        username, type(exc).__name__)
            continue
        notified.append(username.casefold())
        previously_notified.add(username.casefold())
    return notified, failed


async def execute() -> int:
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    credentials = (os.getenv("TG_API_ID"), os.getenv("TG_API_HASH"), (os.getenv("TG_SESSION_STRING") or os.getenv("TG_STRING_SESSION") or os.getenv("TG_STREAM_SESSION")))
    if not all(credentials):
        raise RuntimeError("Secrets requis : TG_API_ID, TG_API_HASH, TG_SESSION_STRING (ou TG_STRING_SESSION).")
    cfg = load_config(os.getenv("DISCOVERY_CONFIG", "config/discovery.json"))
    path = Path(os.getenv("DISCOVERY_REPORT", "state/discovered_channels.json"))
    previous = load_previous(path)
    existing_report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    offset = int(existing_report.get("statistics", {}).get("next_candidate_offset", 0))
    # Do not automatically sleep for long Telegram flood waits on CI runners.
    client = TelegramClient(StringSession(credentials[2]), int(credentials[0]), credentials[1],
                            request_retries=1, connection_retries=2, flood_sleep_threshold=0)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram non autorisée ou expirée.")
        results, stats = await discover(client, cfg, start_offset=offset)
        sent_before = {
            name.casefold() for name, channel in previous.items()
            if channel.get("notified_saved_messages_at")
        }
        notified, notification_failures = await notify_saved_messages(client, results, sent_before)
    finally:
        await client.disconnect()

    timestamp = datetime.now(timezone.utc).isoformat()
    for channel in results:
        key = channel["username"].lower()
        channel["first_detected"] = previous.get(key, {}).get("first_detected", timestamp)
        channel["last_detected"] = timestamp
        previous[key] = channel

    # Discovery NEVER edits auto_sources.json or any relay configuration.
    # Keep notification receipts only in the discovery report to avoid duplicates.
    for username in notified:
        previous[username]["notified_saved_messages_at"] = timestamp
    stats["notified_saved_messages"] = len(notified)
    stats["notification_failures"] = notification_failures

    report = {
        "last_scan": timestamp,
        "notice": "Liens publics à examiner manuellement. Aucun canal rejoint ; aucun droit de diffusion présumé.",
        "statistics": stats,
        "channels": sorted(previous.values(), key=lambda x: (-x.get("matching_pairs", 0), x.get("username", "").lower()))[:300],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    LOG.info("Canaux analysés=%s | correspondant au format=%s | liens conservés=%s",
             stats["checked"], len(results), len(report["channels"]))
    return 0 if not stats["rate_limited"] and not notification_failures else 2


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s | %(levelname)s | %(message)s")
    try:
        status = asyncio.run(execute())
    except Exception:
        LOG.exception("Échec découverte")
        status = 1
    raise SystemExit(status)


if __name__ == "__main__":
    main()
