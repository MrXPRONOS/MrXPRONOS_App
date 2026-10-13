#!/usr/bin/env python3
"""Real one-card programme recovery for the dedicated Telegram test channel.

No production history, quotas, or Supabase state are read or updated.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from football_channel import BSDClient, BSDAPIError, Sender, TZ, programme


def main() -> None:
    if os.getenv("FOOTBALL_REQUIRE_COMMENTS") != "0":
        raise RuntimeError("Le rattrapage ne doit pas exiger de groupe de discussion")
    now = datetime.now(timezone.utc)
    today = now.astimezone(TZ).date()
    api = BSDClient(max_requests=18, max_retries=1)

    post = None
    for day in (today, today + timedelta(days=1)):
        page = api.list_events(day, day, max_pages=8, ttl=0)
        if not page.complete:
            raise BSDAPIError("Journée BSD incomplète : " + day.isoformat())
        post = programme(page.events, day, as_of=now)
        if post is not None:
            if day != today:
                post.text = post.text.replace("MATCHS DU JOUR", "MATCHS DE DEMAIN")
            break

    if post is None:
        raise RuntimeError("Aucun programme authentique disponible pour le test")

    post.text = "<b>🧪 TEST DE RATTRAPAGE — PROGRAMME SEUL</b>\n\n" + post.text
    message_id = Sender(dry_run=False).send(post)
    if not isinstance(message_id, int):
        raise RuntimeError("Telegram n'a pas confirmé le message_id du programme")
    print("TELEGRAM_TEST_PROGRAMME_OK message_id", message_id)


if __name__ == "__main__":
    main()
