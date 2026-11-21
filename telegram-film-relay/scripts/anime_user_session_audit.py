"""CinéX Anime user-session Telegram audit: strictly READ ONLY.

The owner is authorized to forward content from friends' source channels. No
bot administrator access to sources is required. Do NOT use getUpdates, edit
permissions, send, forward, copy, download media or modify Telegram messages.

Report aggregate diagnostics only. No source handles, Telegram IDs, message
captions, bot tokens, session strings or deep links in logs/artifacts.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient, utils
from telethon.errors import FloodWaitError, PeerFloodError
from telethon.sessions import StringSession

from film_relay.anime_catalog import read_catalog
from film_relay.category_runner import category_config
from film_relay.public_video_archive import is_video_message, video_document_id
from film_relay.runner import resolve_peer


def _flatten(catalogue: dict):
    private = defaultdict(set)
    public_pairs = defaultdict(list)
    markers = []
    unreceipted = 0
    for series_key, series in (catalogue.get("series") or {}).items():
        published = series.get("public_episode_posts") or {}
        for season, episodes in (series.get("episodes") or {}).items():
            for number, receipt in episodes.items():
                marker = f"S{int(season):02d}E{int(number):02d}"
                if receipt.get("message_id"):
                    private[int(receipt["message_id"])].add((series_key, marker))
                if marker not in published:
                    unreceipted += 1
        for marker, pair in published.items():
            if pair.get("poster") and pair.get("video"):
                public_pairs[int(pair["video"])].append(
                    (series_key, marker, int(pair["poster"]),
                     int(pair.get("private_video") or
                         (series.get("episodes") or {}).get(
                             str(int(marker.split("E")[0][1:])), {}).get(
                                 str(int(marker.split("E")[1])), {}
                             ).get("message_id") or 0)))
            else:
                markers.append("incomplete_public_receipt")
    return private, public_pairs, unreceipted, markers


def summarize_receipt_messages(catalogue, private_messages, public_messages):
    """Pure analysis of exact-ID Telegram receipts; no media parsing guesses."""
    private_index, public_index, historic, bad_receipts = _flatten(catalogue)
    errors = Counter(bad_receipts)
    private_docs = {}
    for mid, identities in private_index.items():
        msg = private_messages.get(mid)
        if not msg or not is_video_message(msg):
            errors["private_missing_or_not_video"] += 1
            continue
        doc = video_document_id(msg)
        if not doc:
            errors["private_document_missing"] += 1
            continue
        private_docs[mid] = doc
        if len(identities) != 1:
            errors["private_video_reused_across_episodes"] += 1
    docs_to_episodes = defaultdict(set)
    for mid, identities in private_index.items():
        if mid in private_docs:
            for identity in identities:
                docs_to_episodes[private_docs[mid]].add(identity)
    errors["private_document_used_for_different_episodes"] = sum(
        len(v) > 1 for v in docs_to_episodes.values())
    verified_pairs = 0
    for video_id, refs in public_index.items():
        if len(refs) > 1:
            errors["public_video_id_reused"] += 1
        video = public_messages.get(video_id)
        if not video or not is_video_message(video):
            errors["public_video_missing"] += len(refs)
            continue
        for series, marker, poster_id, private_id in refs:
            poster = public_messages.get(poster_id)
            if not poster or not getattr(poster, "photo", None):
                errors["public_poster_missing"] += 1
                continue
            if private_id and (private_id not in private_docs or
                               video_document_id(video) != private_docs[private_id]):
                errors["public_media_mismatch"] += 1
                continue
            if not private_id:
                errors["public_pair_without_private_reference"] += 1
                continue
            verified_pairs += 1
    return {
        "catalogue_series": len(catalogue.get("series") or {}),
        "private_receipts": len(private_index),
        "public_pairs": sum(map(len, public_index.values())),
        "verified_public_pairs": verified_pairs,
        "legacy_episodes_without_new_public_receipt": historic,
        "issues": {key: value for key, value in sorted(errors.items()) if value},
        "checked_private_ids": len(private_messages),
        "checked_public_ids": len(public_messages),
    }


def _mark_duplicates(recent_public):
    from film_relay.publication import catalog_public_marker
    posters = Counter()
    for msg in recent_public:
        if not getattr(msg, "photo", None):
            continue
        caption = str(getattr(msg, "raw_text", "") or "")
        for token in caption.split():
            if token.startswith("#CXPAIR_") and len(token) == len("#CXPAIR_") + 18:
                posters[token] += 1
    return sum(v - 1 for v in posters.values() if v > 1)


async def _batch_fetch(client, peer, message_ids, *, max_ids=300):
    ids = sorted(set(int(n) for n in message_ids if int(n) > 0))
    if len(ids) > max_ids:
        raise RuntimeError("Too many receipt IDs for a bounded read-only audit.")
    result = {}
    for i in range(0, len(ids), 75):
        batch = ids[i:i+75]
        response = await client.get_messages(peer, ids=batch)
        # Telethon returns lists for list inputs, including missing messages.
        for requested, actual in zip(batch, response):
            result[requested] = actual
        await asyncio.sleep(1.0)
    return result


async def read_only_audit():
    cfg = category_config("anime")
    session = (os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
               or os.getenv("TG_STREAM_SESSION") or "").strip()
    api_id = os.getenv("TG_API_ID", "").strip()
    api_hash = os.getenv("TG_API_HASH", "").strip()
    if not (api_id.isdigit() and api_hash and session):
        raise RuntimeError("Missing existing Telegram user-session credentials.")
    source_count = len(cfg["sources"])
    catalogue = read_catalog()
    private, public, _, _ = _flatten(catalogue)
    if len(private) > 300 or len(public) > 300:
        raise RuntimeError("Refusing unbounded public/private receipt request.")
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "session_type": "user_authorized",
        "read_only": True,
        "telegram_mutations": 0,
        "configured_anime_source_count": source_count,
        "source_accessible_count": 0,
        "source_protected_count": 0,
        "source_inaccessible_count": 0,
        "unified_stock_confirmed": False,
        "public_recent_duplicate_pair_markers": 0,
        "source_sample_videos": 0,
    }
    client = TelegramClient(
        StringSession(session), int(api_id), api_hash, receive_updates=False,
        request_retries=0, connection_retries=2, flood_sleep_threshold=0,
    )
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram personal session no longer authorized.")
        private_peer = await resolve_peer(client, cfg["private"])
        public_peer = await resolve_peer(client, cfg["public"])
        if (utils.get_peer_id(private_peer) != int(cfg["private"])
                or private_peer == public_peer):
            raise RuntimeError("Wrong private/public Telegram destinations.")
        me = await client.get_me()
        permissions = await client.get_permissions(private_peer, me)
        if not (getattr(permissions, "is_creator", False) or
                (getattr(permissions, "is_admin", False)
                 and getattr(permissions, "post_messages", False))):
            raise RuntimeError("User account cannot publish to Anime library.")
        from film_relay.unified_download import configured_private_id
        central_id = configured_private_id()
        if central_id is not None:
            central_peer = await resolve_peer(client, str(central_id))
            if (utils.get_peer_id(central_peer) != central_id or
                    getattr(central_peer, "username", None)):
                raise RuntimeError("CineRadar private stock differs from owner-approved ID.")
            report["unified_stock_confirmed"] = True
        for name in cfg["sources"]:
            try:
                peer = await resolve_peer(client, name)
                if (str(getattr(peer, "username", "")).casefold()
                        != str(name).lstrip("@").casefold()):
                    raise RuntimeError("Source identity mismatch")
                if getattr(peer, "noforwards", False):
                    report["source_protected_count"] += 1
                    continue
                messages = [msg async for msg in client.iter_messages(peer, limit=3)]
                report["source_accessible_count"] += 1
                report["source_sample_videos"] += sum(
                    is_video_message(msg) for msg in messages)
            except (FloodWaitError, PeerFloodError):
                raise
            except Exception:
                report["source_inaccessible_count"] += 1
            await asyncio.sleep(2.0)
        private_messages = await _batch_fetch(client, private_peer, private.keys())
        public_ids = set(public.keys())
        for refs in public.values():
            public_ids.update(poster_id for _, _, poster_id, _ in refs)
        public_messages = await _batch_fetch(client, public_peer, public_ids)
        report["receipts"] = summarize_receipt_messages(
            catalogue, private_messages, public_messages)
        recent = [x async for x in client.iter_messages(public_peer, limit=300)]
        report["public_recent_duplicate_pair_markers"] = _mark_duplicates(recent)
        report["status"] = (
            "attention_required"
            if (report["source_inaccessible_count"]
                or report["source_protected_count"]
                or report["receipts"]["issues"]
                or report["public_recent_duplicate_pair_markers"])
            else "verified_sample"
        )
    finally:
        await client.disconnect()
    return report


def main():
    try:
        report = asyncio.run(read_only_audit())
        Path("state").mkdir(parents=True, exist_ok=True)
        Path("state/anime_user_session_audit.json").write_text(
            json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print("CINEX_ANIME_USER_SESSION_AUDIT " +
              json.dumps(report, sort_keys=True, ensure_ascii=False))
        return 0
    except (FloodWaitError, PeerFloodError) as exc:
        print("CINEX_ANIME_USER_SESSION_AUDIT cooldown_required " +
              type(exc).__name__, file=sys.stderr)
        return 3
    except Exception as exc:
        # No exception body: Telethon may include private peer names or IDs.
        print("CINEX_ANIME_USER_SESSION_AUDIT failed " +
              type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
