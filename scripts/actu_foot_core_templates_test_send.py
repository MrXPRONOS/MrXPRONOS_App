#!/usr/bin/env python3
"""Preview the four dedicated premium Actu Foot templates in Telegram TEST only."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import programme_styles
import template_cards as tc
from telegram_rich import post_photo
from telegram_test_guard import validate_test_channel


def fake_logo(url: str, maximum: int = 160):
    """Deterministic transparent test crest, never uses network."""
    home = "home" in str(url).lower() or "a-logo" in str(url).lower()
    im = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    outline = (241, 197, 90, 255) if home else (230, 238, 248, 255)
    fill = (9, 54, 98, 255) if home else (27, 69, 112, 255)
    d.ellipse((15, 15, 225, 225), fill=fill, outline=outline, width=12)
    try:
        ft = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 82)
    except OSError:
        ft = ImageFont.load_default()
    d.text((120, 120), "A" if home else "B", font=ft, fill=outline, anchor="mm")
    im.thumbnail((maximum, maximum), Image.Resampling.LANCZOS)
    return im


PAYLOADS = (
    (
        "programme",
        "MATCHS DU JOUR",
        {
            "day": "14/10/2026",
            "matches": [
                {"home": "Atlético Madrid", "away": "Manchester United", "time": "19H00", "home_logo": "https://test/a-logo-1", "away_logo": "https://test/b-logo-1"},
                {"home": "Viking FK", "away": "FC Bayern München", "time": "19H00", "home_logo": "https://test/a-logo-2", "away_logo": "https://test/b-logo-2"},
                {"home": "Arsenal", "away": "Lille", "time": "19H00", "home_logo": "https://test/a-logo-3", "away_logo": "https://test/b-logo-3"},
                {"home": "Galatasaray", "away": "FC Barcelona", "time": "19H00", "home_logo": "https://test/a-logo-4", "away_logo": "https://test/b-logo-4"},
                {"home": "RB Leipzig", "away": "PSV Eindhoven", "time": "19H00", "home_logo": "https://test/a-logo-5", "away_logo": "https://test/b-logo-5"},
            ],
        },
    ),
    (
        "avant_match",
        "AVANT-MATCH",
        {
            "day": "14/10/2026",
            "home": "Manchester City",
            "away": "Paris Saint-Germain",
            "time": "19H00",
            "home_logo": "https://test/a-logo",
            "away_logo": "https://test/b-logo",
            "home_form": "V • V • V • V • V | 15/15 pts",
            "away_form": "V • V • V • V • D | 12/15 pts",
        },
    ),
    (
        "resultat",
        "RÉSULTAT FINAL",
        {
            "day": "13/10/2026",
            "home": "Red Bull Bragantino",
            "away": "Cruzeiro",
            "scores": (4, 2),
            "source": "BSD V2",
            "home_logo": "https://test/a-logo",
            "away_logo": "https://test/b-logo",
        },
    ),
    (
        "composition",
        "COMPOSITIONS OFFICIELLES",
        {
            "home": "St. Louis CITY SC",
            "away": "LA Galaxy",
            "competition": "Football",
            "time": "23H00",
            "source": "ESPN",
            "home_logo": "https://test/a-logo",
            "away_logo": "https://test/b-logo",
            "home_players": [
                "Roman Bürki", "Timo Baumgartl", "Dante Polvara", "Lukas MacNaughton",
                "Christopher Durkin", "Daniel Edelman", "Tomas Totland", "Conrad Wallem",
                "Rafael Navarro", "Alexandru Matan", "Carlo Holse",
            ],
            "away_players": [
                "JT Marcinkowski", "Justin Haak", "Jakob Glesnes", "Julián Aude",
                "Harbor Miller", "Sergi Roberto", "Erik Thommy", "Pablo Ruiz",
                "Kyogo Furuhashi", "Robert Taylor", "Troy Elgersma",
            ],
        },
    ),
)


def main() -> int:
    token = os.getenv("FOOTBALL_NEWS_BOT_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_TEST_CHAT_ID", "").strip()
    if not token or not chat:
        raise RuntimeError("TEST REFUSED: token/canal Telegram test manquant")

    guard = validate_test_channel(chat, token)
    if guard.get("username") != "predict_mrxp":
        raise RuntimeError("TEST REFUSED: destination autre que @predict_mrxp")

    # All logos are local test drawings: no third-party logo/network dependency.
    programme_styles.load_logo = fake_logo
    session = requests.Session()
    sent: dict[str, int] = {}

    with tempfile.TemporaryDirectory(prefix="actu-foot-core-premium-") as tmp:
        tmpdir = Path(tmp)
        for index, (category, label, payload) in enumerate(PAYLOADS, 1):
            graphic = tc.render(category, payload)
            expected = (1374, 1145) if category == "composition" else (1080, 1080)
            if graphic.size != expected:
                raise RuntimeError(f"{category}: dimensions {graphic.size}, attendu {expected}")
            path = tmpdir / f"{index:02d}-{category}.png"
            graphic.save(path, "PNG", optimize=True)

            caption = (
                "<b>🧪 TEST VISUEL • ACTU FOOT PREMIUM</b>\n"
                f"<b>{index:02d}/04 — {label}</b>\n\n"
                "<i>Données de démonstration • Canal test uniquement.</i>"
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
            sent[category] = message_id
            print("ACTU_FOOT_CORE_TEST_SENT", category, message_id, flush=True)

    if len(sent) != 4:
        raise RuntimeError("Les 4 previews n'ont pas été envoyées")
    print("ACTU_FOOT_CORE_TEST_REPORT", json.dumps(sent, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
