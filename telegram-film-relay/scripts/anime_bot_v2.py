"""CinéX Anime V2 Bot API runner.

No Telethon user sessions. The production switches are intentionally OFF.
Configure a dedicated bot and an independently persisted PRIVATE state store.
Mode audit is offline; poll saves channel updates; publish sends only verified
source media with rights and old-relay cutover attestations.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from film_relay.anime_bot_queue import ingest_channel_updates
from film_relay.anime_bot_matching import (
    associate_anime_messages, consolidate_source_candidates,
    select_bot_anime_batches,
)
from film_relay.anime_bot_publisher import AnimeBotPublisher
from film_relay.anime_bot_state import BotStateStore, require_durable_store
from film_relay.anime_bot_transport import (
    AnimeBotTransport, verify_anime_bot_guard,
)


def _channels():
    raw = os.environ.get("ANIME_AUTHORIZED_SOURCE_IDS", "")
    values = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
    if not values or any(not value.startswith("-100") or
                         not value[1:].isdigit() for value in values):
        raise RuntimeError("ANIME_AUTHORIZED_SOURCE_IDS must list real -100... IDs")
    if len(values) != len(set(values)):
        raise RuntimeError("Repeated source channel IDs are forbidden.")
    private = os.environ.get("ANIME_PRIVATE_CHANNEL", "").strip()
    public = os.environ.get("ANIME_PUBLIC_CHANNEL_ID", "").strip()
    for ch in [private, public]:
        if not ch.startswith("-100") or not ch[1:].isdigit():
            raise RuntimeError("Both destination channels must use -100... IDs.")
    if private == public or private in values or public in values:
        raise RuntimeError("Source and destination Telegram IDs must be distinct.")
    return values, private, public


def prepare(state):
    found, review, cadences, complete = associate_anime_messages(
        state.get("messages", {}))
    unique, ambiguous = consolidate_source_candidates(
        found, reviewed_variants=state.get("approved_media_variants") or {})
    batches = select_bot_anime_batches(unique, state, complete)
    return batches, {"candidates": len(found), "eligible": len(unique),
                     "ambiguous": len(ambiguous), "unmatched": len(review),
                     "complete_announcements": len(complete),
                     "weekly_hints": sum(x == "weekly" for x in cadences.values()),
                     "selected_batches": len(batches),
                     "selected_episodes": sum(len(rows) for _, rows, _ in batches),
                     "source_review": review, "media_review": ambiguous}


async def run(mode: str, *, state_path: str, max_poll_batches=20):
    if mode == "audit":
        state = BotStateStore(state_path).load()
        selected, report = prepare(state)
        # Only aggregate data. Never expose channel IDs, message IDs or file IDs.
        return {k: v for k, v in report.items()
                if k not in ("source_review", "media_review")}

    token = verify_anime_bot_guard()
    sources, private, public = _channels()
    if not os.environ.get("CINEX_ANIME_EXPECTED_BOT_ID", "").isdigit():
        raise RuntimeError("Dedicated bot identity must be explicitly attested.")
    if mode == "publish" and os.environ.get(
            "CINEX_ANIME_LEGACY_RELAY_DISABLED", "").lower() != "true":
        raise RuntimeError("Legacy Anime relay must be disabled before bot cutover.")
    if mode == "publish" and os.environ.get(
            "CINEX_ANIME_CUTOVER_VERIFIED", "").lower() != "true":
        raise RuntimeError("Production cutover has not been verified.")

    store = require_durable_store(state_path)
    with store.exclusive():
        state = store.load()
        transport = AnimeBotTransport(token)
        identity = await transport.identity()
        if str(identity.id) != os.environ["CINEX_ANIME_EXPECTED_BOT_ID"]:
            raise RuntimeError("Bot token identity disagrees with attested bot.")
        await transport.assert_permissions(sources, private, public)
        if mode == "poll":
            await transport.assert_polling_available()
            totals = {"accepted": 0, "repeated": 0, "unauthorized": 0,
                      "skipped": 0, "edited": 0}
            for _ in range(max_poll_batches):
                updates = await transport.get_updates(
                    offset=int(state.get("last_update_id", -1)) + 1)
                if not updates:
                    break
                state, report = ingest_channel_updates(updates, state, sources)
                # Offset is acknowledged to Telegram on NEXT getUpdates call,
                # so persist this batch BEFORE making that call.
                store.save(state)
                for key in totals:
                    totals[key] += report.get(key, 0)
                if len(updates) < 100:
                    break
            return {"mode": "poll", "counts": totals,
                    "queued_messages": len(state.get("messages", {}))}
        if mode != "publish":
            raise ValueError("Unsupported mode.")
        batches, report = prepare(state)
        # Do not publish while any candidate is ambiguous and conflicts with
        # the same canonical key; ambiguous rows are explicitly excluded.
        publisher = AnimeBotPublisher(
            transport, store, state, private_id=private, public_id=public,
            folder_url=os.environ.get("CINEX_FILM_FOLDER_URL", ""),
            pause=float(os.environ.get("CINEX_BOT_PAUSE_SECONDS", "3")))
        updated = 0
        published_anime = []
        for key, rows, is_complete in batches:
            for row in rows:
                await publisher.publish_episode(row)
                updated += 1
            published_anime.append(key)
            if is_complete:
                # One complete season per cycle; next batch continues later.
                break
        state["last_cycle"] = {
            "published_episodes": updated,
            "published_anime_count": len(set(published_anime)),
            "mode": "complete" if batches and batches[0][2] else "ongoing",
        }
        store.save(state)
        return {"mode": "publish", "published": updated,
                "series": len(set(published_anime)),
                "pending_review": report["unmatched"] + report["ambiguous"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("audit", "poll", "publish"),
                        required=True)
    parser.add_argument("--state-path", default=os.environ.get(
        "CINEX_ANIME_BOT_STATE_PATH", "state/anime_bot_v2.json"))
    opts = parser.parse_args()
    try:
        report = asyncio.run(run(opts.mode, state_path=opts.state_path))
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    except Exception as exc:
        # Don't include token, private source IDs or potentially sensitive
        # Telegram error bodies in the public workflow logs.
        print("Anime Bot V2 stopped safely: " + type(exc).__name__,
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
