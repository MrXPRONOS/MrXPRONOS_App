#!/usr/bin/env python3
"""One-time, source-confirmed Clásico recovery announcement before daily football."""
from datetime import datetime, timezone
from scripts.football_channel import (
    History, Publication, RemotePublicationLedger, Sender,
    deliver_with_outbox, post_label,
)

KEY = "resultat:recovery:2026-10-25:barcelona-real-madrid"
SOURCE = "https://www.laliga.com/en-ES/partidazos/el-clasico"


def main():
    now = datetime.now(timezone.utc)
    state = History()
    sender = Sender()
    ledger = RemotePublicationLedger(sender.session, enabled=True)
    if state.seen(KEY) or ledger.is_sent(KEY):
        print("CLASICO_RECOVERY_ALREADY_SENT")
        return
    message = post_label(
        "<b>🏁 EL CLÁSICO — RÉSULTAT FINAL</b>\n\n"
        "🇪🇸 LaLiga • Dimanche 25 octobre 2026\n\n"
        "<b>FC Barcelone 1–2 Real Madrid</b>\n\n"
        "⚽ Raphinha 61' (Barça)\n"
        "⚽ Kylian Mbappé 41', 87' (Real Madrid)\n\n"
        "Le Real Madrid remporte le Clásico grâce à un doublé de Mbappé.\n\n"
        "🔎 Source officielle : " + SOURCE
    )
    item = Publication("resultat", KEY, message)
    result = deliver_with_outbox(sender, ledger, item, now)
    if result.get("sent") or ledger.is_sent(KEY):
        state.mark(KEY, "resultat", now)
        state.save(now)
        print("CLASICO_RECOVERY_CONFIRMED")
    elif result.get("error"):
        raise SystemExit("CLASICO_RECOVERY_DELIVERY_FAILED")
    else:
        print("CLASICO_RECOVERY_NOT_CLAIMED")


if __name__ == "__main__":
    main()
