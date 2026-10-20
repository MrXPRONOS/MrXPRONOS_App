#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Send a production prediction video to Telegram and record its exact batch.

The Supabase ledger rows are written only after Telegram accepts the video.
This makes the morning run exclude selections already used by the evening run
and gives the validation workflow an exact batch to settle later.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests

KIND = "shorts_video_coupon"
DAILY_GUARD_KIND = "shorts_video_daily_guard"


def headers(key: str):
    return {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "Prefer": "return=representation,resolution=ignore-duplicates",
    }


def record_batch(session, base, key, manifest):
    slot = str(manifest.get("slot") or "").strip()
    target = str(manifest.get("target") or "").strip()
    rows = []
    for match in manifest.get("matches") or []:
        ident = str(match.get("id") or "").strip()
        if not ident:
            continue
        rows.append({
            "kind": KIND,
            "ref_id": f"{slot}:{ident}",
            "ref_date": target,
            "validation_sent": False,
        })
    if not rows:
        raise RuntimeError("Manifest sans sélection à enregistrer")

    url = base.rstrip("/") + "/rest/v1/telegram_sent"
    for row in rows:
        response = session.post(
            url,
            params={"on_conflict": "kind,ref_id,ref_date"},
            headers=headers(key),
            json=row,
            timeout=30,
        )
        response.raise_for_status()
    print("SHORTS_BATCH_LEDGER_RECORDED", json.dumps({
        "slot": slot, "target": target, "count": len(rows)
    }, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()

    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    base = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or "").strip()
    if not all((token, chat, base, key)):
        raise RuntimeError("Secrets Telegram/Supabase manquants")

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
    guard = session.post(
        base.rstrip("/") + "/rest/v1/telegram_sent",
        params={"on_conflict": "kind,ref_id,ref_date"},
        headers=headers(key),
        json={"kind": DAILY_GUARD_KIND, "ref_id": "one_daily_video",
              "ref_date": published_day, "validation_sent": False},
        timeout=30,
    )
    guard.raise_for_status()
    claimed = guard.json()
    if not isinstance(claimed,list):
        raise RuntimeError("Registre d'unicité quotidienne invalide")
    if not claimed:
        print("SHORTS_DAILY_ALREADY_SENT",published_day)
        output=os.getenv("GITHUB_OUTPUT")
        if output:
            with open(output,"a",encoding="utf-8") as fh: fh.write("video_sent=false\\n".replace("\\\\n","\\n"))
        return 0
    label = "Sélection du jour"
    caption = (
        f"⚽ Pronostics Mr XPRONOS — {target}\n"
        f"{label} · {manifest.get('count')} sélection(s)\n"
        "18+ · Joue responsablement."
    )

    keyboard = {
        "inline_keyboard": [[
            {"text": "Plus de pronostics 🔥",
             "url": "https://mrxpronos.github.io/MrXPRONOS_App/pronos.html"}
        ]]
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

    record_batch(session, base, key, manifest)
    output=os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output,"a",encoding="utf-8") as fh: fh.write("video_sent=true\\n".replace("\\\\n","\\n"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
