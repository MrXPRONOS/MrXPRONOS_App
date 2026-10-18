"""Test #08 : envoie la véritable maquette Playwright, clairement marquée SIMULATION.

Ne récupère aucune news réelle et n'envoie rien ailleurs que @predict_mrxp.
Le PNG et son JSON DEMO sont construits par export_breaking_v2.py
et render_crypto_breaking_v2.mjs, les mêmes générateurs que pour les vraies news.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests
from PIL import Image

from scripts.telegram_test_guard import validate_test_channel

TEST_CHANNEL = "@predict_mrxp"
DATA = Path("crypto/generated/test/breaking_v2_demo.json")
IMAGE = Path("crypto/generated/test/breaking_v2_demo.png")


def check_demo() -> None:
    if not DATA.is_file() or not IMAGE.is_file() or IMAGE.stat().st_size < 10_000:
        raise RuntimeError("Maquette Playwright n°08 absente : aucun envoi")
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    if (not isinstance(payload, dict) or payload.get("publication") != 8
            or payload.get("status") != "demo" or payload.get("is_demo") is not True):
        raise RuntimeError("Test Telegram : JSON non explicitement fictif")
    with Image.open(IMAGE) as img:
        if img.format != "PNG" or img.size != (1080, 1350):
            raise RuntimeError("Affiche #08 : format ou dimensions invalides")
        img.verify()


def send_delivery_test(token: str, requester=requests.post) -> int:
    check_demo()
    token = (token or "").strip()
    dest = validate_test_channel(TEST_CHANNEL, token)
    caption = (
        "🧪 MR XPRONOS • ACTU CRYPTO #08\n"
        "APERÇU PREMIUM — SIMULATION\n\n"
        "Cette image utilise le même moteur graphique que les futures actualités "
        "réelles. Le titre et les événements sont FICTIFS : ce message est un "
        "test visuel, pas une actualité.\n\n"
        "📍 Canal de test : @predict_mrxp"
    )
    with IMAGE.open("rb") as image_file:
        try:
            response = requester(
                "https://api.telegram.org/bot" + token + "/sendPhoto",
                data={"chat_id": dest["chat_id"], "caption": caption,
                      "disable_notification": True},
                files={"photo": (IMAGE.name, image_file, "image/png")},
                timeout=(10, 90),
            )
            response.raise_for_status()
            response_data = response.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError(
                "Envoi Telegram incertain : ne pas relancer automatiquement"
            ) from None
    if not isinstance(response_data, dict) or response_data.get("ok") is not True:
        raise RuntimeError("Telegram a refusé l'aperçu #08")
    result = response_data.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
        raise RuntimeError("Réponse Telegram sans identifiant de message")
    chat = result.get("chat")
    if not isinstance(chat, dict) or chat.get("id") != dest["chat_id"]:
        raise RuntimeError("Destination Telegram inattendue")
    if not isinstance(result.get("photo"), list) or not result["photo"]:
        raise RuntimeError("Photo non confirmée par Telegram")
    print("BREAKING_08_PREMIUM_DEMO_PHOTO_CONFIRMED",
          "chat=@" + dest["username"],
          "message_id=" + str(result["message_id"]),
          "photo_variants=" + str(len(result["photo"])),
          "image=" + str(IMAGE))
    return result["message_id"]


if __name__ == "__main__":
    send_delivery_test(os.environ.get("FOOTBALL_NEWS_BOT_TOKEN", ""))
