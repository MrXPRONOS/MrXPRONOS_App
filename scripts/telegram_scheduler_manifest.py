#!/usr/bin/env python3
"""Single-run Telegram manifest publisher. Default is OFFLINE preview."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from telegram_scheduler.manifest import load_manifest, queue_counts
from telegram_scheduler.core import TelegramScheduler


async def execute(horizon, posts):
    session = TelegramScheduler.from_env(hours=horizon)
    async with session as scheduler:
        await scheduler.preflight_queue(queue_counts(posts))
        completed = 0
        for post in posts:
            result = await scheduler.schedule(post["peer"], post["at"], post["key"],
                text=post["text"], file=post["file"], kind=post["kind"],
                parse_mode=post["parse_mode"])
            completed += 1
            print(json.dumps({"item": completed, "result": result["status"]}))
            if completed < len(posts):
                await asyncio.sleep(max(8, int(os.getenv("TG_SCHEDULER_PACE_SECONDS", "10"))))
        print(json.dumps({"verified_or_duplicate": completed, "total": len(posts)}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--execute", action="store_true", help="Use live personal session after explicit gate")
    args = parser.parse_args()
    horizon, posts = load_manifest(args.manifest)
    counts = queue_counts(posts)
    print(json.dumps({"mode": "execute" if args.execute else "preview",
                      "hours": horizon, "posts": len(posts),
                      "destinations": len(counts)}, sort_keys=True))
    if not args.execute:
        print("OFFLINE_ONLY; no Telegram API called")
        return 0
    if os.getenv("TG_SCHEDULER_ENABLED") != "1":
        raise SystemExit("TG_SCHEDULER_ENABLED is not 1")
    asyncio.run(execute(horizon, posts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
