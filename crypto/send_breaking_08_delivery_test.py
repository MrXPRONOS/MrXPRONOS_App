"""Vérification de livraison d'une PHOTO Telegram #08, sans fausse actualité."""
from __future__ import annotations
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont
from scripts.telegram_test_guard import validate_test_channel

TEST_CHANNEL = "@predict_mrxp"
IMAGE_PATH = Path("crypto/generated/test/breaking_08_delivery_test.png")


def create_diagnostic_image() -> Path:
    IMAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1080, 1350), "#071526")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((64, 180, 1016, 1150), radius=38,
                           fill="#10273f", outline="#41617f", width=3)
    try:
        bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        big = ImageFont.truetype(bold, 69)
        medium = ImageFont.truetype(bold, 38)
        normal = ImageFont.truetype(regular, 30)
    except OSError:
        big = medium = normal = ImageFont.load_default()
    gold, white, soft = "#e9c58e", "#f5f8fc", "#b4cadc"
    draw.text((75, 61), "MR XPRONOS", fill=gold, font=medium)
    draw.text((80, 262), "ACTU CRYPTO #08", fill=soft, font=medium)
    draw.text((80, 391), "TEST TELEGRAM", fill=white, font=big)
    draw.text((80, 494), "PHOTO + LEGENDE", fill=gold, font=medium)
    draw.line((80, 577, 980, 577), fill="#436484", width=3)
    for i, line in enumerate((
        "Verification technique de livraison",
        "Image generee automatiquement",
        "Aucune actualite reelle dans ce test",
        "Destination : @predict_mrxp",
    )):
        draw.text((90, 660 + i * 95), line, fill=soft, font=normal)
    date = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    draw.text((85, 1080), date, fill=gold, font=normal)
    draw.text((85, 1224), "DEMONSTRATION - NON PUBLIABLE", fill=white, font=normal)
    image.save(IMAGE_PATH, "PNG")
    return IMAGE_PATH


def send_delivery_test(token: str, requester=requests.post) -> int:
    token = (token or "").strip()
    dest = validate_test_channel(TEST_CHANNEL, token)
    image_path = create_diagnostic_image()
    caption = (
        "🧪 TEST TECHNIQUE — MR XPRONOS ACTU CRYPTO #08\n\n"
        "✅ Vérification de la livraison Telegram avec PHOTO et légende.\n"
        "⚠️ IMAGE DE TEST : aucune actualité ni conseil financier.\n"
        "📍 Canal de test : @predict_mrxp"
    )
    with image_path.open("rb") as photo:
        try:
            response = requester(
                "https://api.telegram.org/bot" + token + "/sendPhoto",
                data={"chat_id": dest["chat_id"], "caption": caption,
                      "disable_notification": True},
                files={"photo": (image_path.name, photo, "image/png")},
                timeout=(10, 90),
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError(
                "Livraison Telegram incertaine : ne pas relancer automatiquement"
            ) from None
    if not isinstance(data, dict) or data.get("ok") is not True:
        raise RuntimeError("Telegram a refuse la photo")
    result = data.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
        raise RuntimeError("Identifiant du message introuvable")
    chat = result.get("chat")
    if not isinstance(chat, dict) or chat.get("id") != dest["chat_id"]:
        raise RuntimeError("Destinataire Telegram inattendu")
    if not isinstance(result.get("photo"), list) or not result["photo"]:
        raise RuntimeError("Telegram n'a pas confirme de piece jointe photo")
    print("BREAKING_08_DELIVERY_PHOTO_CONFIRMED",
          "chat=@" + dest["username"],
          "message_id=" + str(result["message_id"]),
          "photo_variants=" + str(len(result["photo"])))
    return result["message_id"]


if __name__ == "__main__":
    send_delivery_test(os.environ.get("FOOTBALL_NEWS_BOT_TOKEN", ""))
