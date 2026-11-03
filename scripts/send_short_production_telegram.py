#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Send a production prediction video to Telegram and record its exact batch.

The Cloudflare D1 ledger rows are written only after Telegram accepts the video.
This makes the morning run exclude selections already used by the evening run
and gives the validation workflow an exact batch to settle later.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests
from d1_publication_ledger import D1Ledger

KIND = "shorts_video_coupon"
DAILY_GUARD_KIND = "shorts_video_daily_guard"


def record_batch(ledger, manifest):
    slot = str(manifest.get("slot") or "").strip()
    target = str(manifest.get("target") or "").strip()
    ids = [str(m.get("id") or "").strip() for m in manifest.get("matches") or []]
    ids = [x for x in ids if x]
    if not ids:
        raise RuntimeError("Manifest sans sélection à enregistrer")
    for event_id in ids:
        ref = f"{slot}:{event_id}"
        if ledger.claim(KIND, ref, target):
            ledger.mark(KIND, ref, target)
    print("SHORTS_BATCH_LEDGER_RECORDED", json.dumps({
        "slot": slot, "target": target, "count": len(ids)
    }, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()

    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.getenv("TG_VIDEO_PRIMARY_CHANNEL") or "@mrxpronosfr").strip()
    if not all((token, chat)):
        raise RuntimeError("Secrets Telegram manquants")

    video = Path(args.video)
    manifest_path = Path(args.manifest)
    if not video.is_file() or video.stat().st_size < 1000:
        raise RuntimeError("Vidéo production absente ou invalide")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if int(manifest.get("count") or 0) < 1:
        raise RuntimeError("Manifest production vide")

    target = str(manifest.get("target") or "")
    slot = str(manifest.get("slot") or "")
    from datetime import datetime, timezone
    published_day = datetime.now(timezone.utc).date().isoformat()
    # Réservation atomique : une seule vidéo de pronostics PAR JOUR, même en
    # présence de relances manuelles ou cron-job.org. Jamais deux vagues.
    session = requests.Session()
    ledger = D1Ledger()
    if not ledger.claim(DAILY_GUARD_KIND, "one_daily_video", published_day):
        print("SHORTS_DAILY_ALREADY_SENT", published_day)
        output = os.getenv("GITHUB_OUTPUT")
        if output:
            with open(output, "a", encoding="utf-8") as fh: fh.write("video_sent=false\n")
        return 0
    label = "Sélection du jour"
    caption = (
        f"⚽ Pronostics Mr XPRONOS — {target}\n"
        f"{label} · {manifest.get('count')} sélection(s)\n"
        "18+ · Joue responsablement."
    )

    # Trois vrais boutons inline sur la vidéo d'origine; les copies des autres
    # canaux réutiliseront exactement le même clavier.
    keyboard = {
        "inline_keyboard": [
            [{"text": "🎯 Coupons du jour", "url": "https://t.me/mrxpronosfr"}],
            [{"text": "⚽ Actualités Foot", "url": "https://t.me/actufoot_mrxp"}],
            [{"text": "🎬 Films, animés et séries", "url": "https://t.me/addlist/ZmW4vfwcrMAwNzJk"}],
        ]
    }
    url = "https://api.telegram.org/bot" + token + "/sendVideo"
    with video.open("rb") as fh:
        response = session.post(
            url,
            data={
                "chat_id": chat,
                "caption": caption[:1024],
                "supports_streaming": "true",
                "reply_markup": json.dumps(keyboard, ensure_ascii=False),
            },
            files={"video": (video.name, fh, "video/mp4")},
            timeout=600,
        )
    response.raise_for_status()
    body = response.json()
    if body.get("ok") is not True:
        raise RuntimeError("Telegram a refusé la vidéo production")

    message = body.get("result") or {}
    print("SHORTS_PRODUCTION_TELEGRAM_SENT", json.dumps({
        "message_id": message.get("message_id"),
        "chat_id": (message.get("chat") or {}).get("id"),
        "slot": slot,
        "target": target,
        "count": manifest.get("count"),
    }, ensure_ascii=False))

    if not isinstance(message.get("message_id"), int):
        raise RuntimeError("Telegram n'a pas fourni l'ID du message principal")
    # Reçu nécessaire pour recopier la même vidéo sans devoir la générer.
    receipt = {
        "primary_chat": chat,
        "primary_message_id": message["message_id"],
        "primary_chat_id": (message.get("chat") or {}).get("id"),
        "primary_file_id": ((message.get("video") or {}).get("file_id")),
        "target": target,
        "slot": slot,
        "published_day": published_day,
        "keyboard": keyboard,
        "caption": caption,
    }
    receipt_file = Path("telegram_out/production_short/telegram_primary_receipt.json")
    receipt_file.parent.mkdir(parents=True, exist_ok=True)
    receipt_file.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")

    ledger.mark(DAILY_GUARD_KIND, "one_daily_video", published_day,
                message_id=message["message_id"])
    record_batch(ledger, manifest)
    output=os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output,"a",encoding="utf-8") as fh: fh.write("video_sent=true\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
