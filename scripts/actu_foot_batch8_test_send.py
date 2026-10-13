#!/usr/bin/env python3
"""Send batch-8 Actu Foot visual previews to the protected Telegram test channel only."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import programme_styles
from actu_foot_event_templates import render_event
from telegram_rich import post_photo
from telegram_test_guard import validate_test_channel


BATCH8 = (
    ("score_live_one_logo", "SCORE LIVE — 1 LOGO"),
    ("score_live_no_logos", "SCORE LIVE — 0 LOGO"),
    ("score_live_no_minute", "SCORE LIVE — MINUTE ABSENTE"),
    ("but_full", "BUT — BUTEUR + PASSEUR"),
    ("but_scorer_only", "BUT — BUTEUR SEUL"),
)


def dummy_logo(url: str, maximum: int):
    im = Image.new("RGBA", (220, 220), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    color = (241, 193, 92, 255) if "home" in url else (220, 230, 240, 255)
    d.ellipse((10, 10, 210, 210), outline=color, width=10)
    try:
        ft = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 92)
    except OSError:
        ft = ImageFont.load_default()
    label = "A" if "home" in url else "B"
    d.text((110, 110), label, font=ft, fill=color, anchor="mm")
    im.thumbnail((maximum, maximum))
    return im


def payload_for(kind: str) -> dict:
    base = {
        "home": "ÉQUIPE A • TEST",
        "away": "ÉQUIPE B • TEST",
        "home_logo": "https://example.invalid/home",
        "away_logo": "https://example.invalid/away",
        "competition": "COMPÉTITION • SIMULATION",
        "score": "2-1",
        "minute": "67",
        "source": "DÉMONSTRATION — DONNÉES FICTIVES",
        "status": "LIVE • TEST",
        "info": "Aperçu technique du template. Aucune information sportive réelle.",
        "scorer": "BUTEUR TEST",
        "assist": "PASSEUR TEST",
    }
    if kind == "score_live_one_logo":
        base["away_logo"] = ""
    elif kind == "score_live_no_logos":
        base["home_logo"] = ""
        base["away_logo"] = ""
    elif kind == "score_live_no_minute":
        base["minute"] = ""
        base["time"] = ""
    elif kind == "but_scorer_only":
        base["assist"] = ""
        base["assister"] = ""
        base["passeur"] = ""
        base["assistant"] = ""
    return base


def main():
    token = os.environ.get("FOOTBALL_NEWS_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_TEST_CHAT_ID", "").strip()
    if not token or not chat:
        raise RuntimeError("TEST REFUSED: token ou canal de test manquant")

    guard = validate_test_channel(chat, token)
    if guard.get("username") != "predict_mrxp":
        raise RuntimeError("TEST REFUSED: canal Telegram inattendu")

    session = requests.Session()
    sent = {}

    with patch.object(programme_styles, "load_logo", side_effect=dummy_logo):
        with tempfile.TemporaryDirectory(prefix="actu-foot-batch8-") as tmp:
            for idx, (kind, label) in enumerate(BATCH8, 1):
                payload = payload_for(kind)
                image = render_event(kind, payload)
                if image.size != (1122, 1402):
                    raise RuntimeError(f"Format inattendu pour {kind}: {image.size}")

                path = Path(tmp) / f"{kind}.png"
                image.save(path, "PNG", optimize=True)

                caption = (
                    "<b>🧪 TEST VISUEL • ACTU FOOT</b>\n"
                    f"<b>{idx:02d}/{len(BATCH8)} — {label}</b>\n\n"
                    "<i>Données fictives • Canal de test uniquement • "
                    "Ne pas interpréter comme une actualité réelle.</i>"
                )
                message_id = post_photo(
                    session,
                    token,
                    chat,
                    path,
                    caption,
                    {"inline_keyboard": []},
                    timeout=90,
                    mime="image/png",
                )
                sent[kind] = message_id
                print("ACTU_FOOT_BATCH8_TEST_SENT", kind, message_id, flush=True)

    print("ACTU_FOOT_BATCH8_TEST_REPORT", json.dumps(sent, ensure_ascii=False), flush=True)
    if len(sent) != len(BATCH8):
        raise RuntimeError("Tous les aperçus du lot 8 n'ont pas été envoyés")


if __name__ == "__main__":
    main()
