#!/usr/bin/env python3
"""Album Telegram TEST: image 1 = vraie découpe 2 matchs, image 2 = coupon complet.

Contrôle strict du canal @predict_mrxp, jamais de publication production.
"""
import json
import os
from pathlib import Path

import requests
from PIL import Image
from telegram_test_guard import validate_test_channel


def check_photo(file: Path):
    if not file.is_file() or file.stat().st_size < 1000:
        raise SystemExit("Image Telegram absente ou invalide: " + str(file))
    with Image.open(file) as im:
        width, height = im.size
        if im.format != "PNG" or width != 1080 or width + height > 10000:
            raise SystemExit("Dimensions de photo non supportées: " + str(im.size))
        if max(width, height) / min(width, height) > 20:
            raise SystemExit("Format de photo Telegram invalide")
        return width, height


def main():
    token = (os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    chat = (os.getenv("TELEGRAM_TEST_CHAT_ID") or "").strip()
    full = Path(os.getenv("ACCUMULATOR_OUTPUT", "telegram_out/accumulator_reference.png"))
    preview = Path(os.getenv("ACCUMULATOR_PREVIEW", "telegram_out/accumulator_preview.png"))
    width_preview, height_preview = check_photo(preview)
    width_full, height_full = check_photo(full)
    if height_preview >= height_full:
        raise SystemExit("L'aperçu doit être plus court que le coupon complet")
    verified = validate_test_channel(chat, token)
    report_path = Path(os.getenv("ACCUMULATOR_DATA_REPORT", "telegram_out/accumulator_data_report.json"))
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
    count = int(report["included"]) if report else 11
    mode_label = "TEST DONNÉES RÉELLES DU JOUR" if report else "TEST MAQUETTE"
    media = [
        {
            "type": "photo",
            "media": "attach://preview",
            "caption": f"🧪 MR XPRONOS — {mode_label}\n1/2 : aperçu du coupon (deux premiers matchs)\n2/2 : coupon complet ({count} matchs)\nSimulation visuelle, pas un pari accepté."
        },
        {"type": "photo", "media": "attach://full"},
    ]
    # Une seule requête pour un unique album de deux images, dans l'ordre.
    with preview.open("rb") as a, full.open("rb") as b:
        response = requests.post(
            "https://api.telegram.org/bot" + token + "/sendMediaGroup",
            data={"chat_id": verified["chat_id"], "media": json.dumps(media, ensure_ascii=False)},
            files={
                "preview": ("mrxpronos-combine-apercu.png", a, "image/png"),
                "full": ("mrxpronos-combine-complet.png", b, "image/png"),
            },
            timeout=(10, 120),
        )
    response.raise_for_status()
    payload = response.json()
    messages = payload.get("result") or []
    if payload.get("ok") is not True or len(messages) != 2:
        raise RuntimeError("L'album Telegram de deux photos n'est pas confirmé")
    ids = [message["message_id"] for message in messages]
    print(
        "ACCUMULATOR_ALBUM_SENT",
        json.dumps({
            "chat": verified["username"],
            "message_ids": ids,
            "preview_size": [width_preview, height_preview],
            "full_size": [width_full, height_full],
            "media_type": "photo",
        }, ensure_ascii=False),
    )


if __name__ == "__main__":
    main()
