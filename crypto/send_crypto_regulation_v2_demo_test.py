"""#10: send a clearly fictional visual to the approved Telegram test channel.

There is deliberately NO method to send real regulatory announcements:
human legal review and explicit approval must be added in a separate process.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import requests
from scripts.telegram_test_guard import validate_test_channel

PHOTO = Path("crypto/generated/test/regulation_v2_demo.png")
DATA = Path("crypto/generated/test/regulation_v2_demo.json")
CHANNEL = "@predict_mrxp"


def main(requester=requests.post) -> int:
    if not PHOTO.is_file() or PHOTO.stat().st_size < 10_000 or not DATA.is_file():
        raise RuntimeError("Missing vetted #10 demo image or JSON")
    if PHOTO.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("Preview image is not PNG")
    d = json.loads(DATA.read_text(encoding="utf-8"))
    if (d.get("publication") != 10 or d.get("status") != "demo"
            or d.get("is_demo") is not True or d.get("approval_required") is not True
            or d.get("legal_status_confirmed") is not False):
        raise RuntimeError("Refuse unexpected legal-news payload for demo")
    token = (os.environ.get("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    dest = validate_test_channel(CHANNEL, token)
    caption = (
        "🧪 MR XPRONOS — ACTU CRYPTO #10\n"
        "⚖️ Réglementation crypto mondiale\n\n"
        "⚠️ MAQUETTE FICTIVE — NON PUBLIABLE.\n"
        "Ceci est uniquement un test d'image premium et de livraison Telegram.\n"
        "Aucune loi réelle, date d'application ou conclusion juridique n'est annoncée.\n\n"
        "Canal de test : @predict_mrxp"
    )
    with PHOTO.open("rb") as file:
        try:
            response = requester(
                "https://api.telegram.org/bot" + token + "/sendPhoto",
                data={"chat_id": dest["chat_id"], "caption": caption,
                      "disable_notification": True},
                files={"photo": (PHOTO.name, file, "image/png")},
                timeout=(10, 90))
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError("Telegram result uncertain; do not retry automatically") from None
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Telegram rejected demo image")
    message = result.get("result")
    if (not isinstance(message, dict) or not isinstance(message.get("message_id"), int)
            or not isinstance(message.get("chat"), dict)
            or message["chat"].get("id") != dest["chat_id"]
            or not isinstance(message.get("photo"), list) or not message["photo"]):
        raise RuntimeError("Telegram did not confirm attached photo on approved channel")
    print("REG10_TELEGRAM_PREMIUM_DEMO_PHOTO_CONFIRMED",
          "chat=@" + dest["username"], "message_id=" + str(message["message_id"]),
          "photo_variants=" + str(len(message["photo"])))
    return message["message_id"]


if __name__ == "__main__":
    main()
