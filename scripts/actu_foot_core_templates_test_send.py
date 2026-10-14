#!/usr/bin/env python3
"""Preview the four dedicated premium Actu Foot templates in Telegram TEST only."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import requests
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import programme_styles
import template_cards as tc
from telegram_rich import post_photo
from telegram_test_guard import validate_test_channel


def fake_logo(url: str, maximum: int = 160):
    """Blason local de test, dimensionné comme un vrai logo transparent."""
    key = str(url).lower()
    if "stl" in key:
        label, home = "STL", True
    elif "galaxy" in key or "la-logo" in key:
        label, home = "LA", False
    else:
        home = "home" in key or "a-logo" in key
        label = "A" if home else "B"

    im = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    outline = (241, 197, 90, 255) if home else (230, 238, 248, 255)
    fill = (9, 54, 98, 255) if home else (27, 69, 112, 255)
    # Forme écusson : aucune seconde bague qui pourrait fausser le test
    # d'alignement dans le cercle natif du template.
    d.polygon(
        [(120, 16), (210, 46), (198, 156), (120, 224), (42, 156), (30, 46)],
        fill=fill,
        outline=outline,
    )
    d.line(
        [(120, 16), (210, 46), (198, 156), (120, 224), (42, 156), (30, 46), (120, 16)],
        fill=outline,
        width=10,
        joint="curve",
    )
    try:
        size = 58 if len(label) >= 3 else 72
        ft = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        ft = ImageFont.load_default()
    d.text((120, 119), label, font=ft, fill=outline, anchor="mm")
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
            "competition": "Major League Soccer",
            "time": "23H00",
            "source": "ESPN",
            "home_logo": "mock://stl-logo",
            "away_logo": "mock://la-galaxy-logo",
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



def validate_composition_render(graphic: Image.Image) -> None:
    """Vérifie que chaque donnée est présente et reste dans sa surface."""
    blank = tc.template("composition")
    diff = ImageChops.difference(blank, graphic).convert("L")

    data_boxes: dict[str, tuple[int, int, int, int]] = {
        "competition": tc.COMPOSITION_LAYOUT["competition"]["safe"],
        "time": tc.COMPOSITION_LAYOUT["time"]["safe"],
        "home_logo": tc.COMPOSITION_LAYOUT["home_logo"]["surface"],
        "away_logo": tc.COMPOSITION_LAYOUT["away_logo"]["surface"],
        "home_name": tc.COMPOSITION_LAYOUT["home_name"]["safe"],
        "away_name": tc.COMPOSITION_LAYOUT["away_name"]["safe"],
        "source": tc.COMPOSITION_LAYOUT["source"]["safe"],
        "comment": tc.COMPOSITION_LAYOUT["comment"]["safe"],
        "brand": tc.COMPOSITION_LAYOUT["brand"]["safe"],
    }

    for side in ("home", "away"):
        x1, x2 = tc.COMPOSITION_LAYOUT[f"{side}_rows"]["player_x"]
        for index, (top, bottom) in enumerate(tc.COMPOSITION_ROWS, 1):
            data_boxes[f"{side}_player_{index:02d}"] = (x1, top, x2, bottom)

    missing = [
        name
        for name, box in data_boxes.items()
        if diff.crop(box).getbbox() is None
    ]
    if missing:
        raise RuntimeError(
            "Composition TEST: zones sans donnée rendue: " + ", ".join(missing)
        )

    # Toute différence entre le template vierge et le rendu doit rester dans
    # les surfaces de données prévues.
    allowed = Image.new("L", graphic.size, 0)
    mask_draw = ImageDraw.Draw(allowed)
    for box in data_boxes.values():
        mask_draw.rectangle(box, fill=255)

    outside_mask = ImageChops.invert(allowed)
    outside = ImageChops.multiply(diff, outside_mask)
    outside_bbox = outside.getbbox()
    if outside_bbox is not None:
        # Tolérance de 2 px autour des surfaces à cause de l'antialiasing PIL.
        expanded = Image.new("L", graphic.size, 0)
        ed = ImageDraw.Draw(expanded)
        for x1, y1, x2, y2 in data_boxes.values():
            ed.rectangle(
                (max(0, x1 - 2), max(0, y1 - 2),
                 min(graphic.width, x2 + 2), min(graphic.height, y2 + 2)),
                fill=255,
            )
        outside = ImageChops.multiply(diff, ImageChops.invert(expanded))
        if outside.getbbox() is not None:
            raise RuntimeError(
                "Composition TEST: pixels dynamiques hors des surfaces prévues "
                + str(outside.getbbox())
            )

    print(
        "COMPOSITION_DATA_SLOTS_OK",
        json.dumps(
            {
                "slots": len(data_boxes),
                "rows": 22,
                "canvas": graphic.size,
                "layout": tc.COMPOSITION_LAYOUT,
            },
            ensure_ascii=False,
            default=list,
        ),
        flush=True,
    )

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--category",
        choices=[item[0] for item in PAYLOADS],
        default=None,
        help="Limiter l'envoi à un seul template (sinon les quatre).",
    )
    args = parser.parse_args()

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
    selected = [
        item for item in PAYLOADS
        if args.category is None or item[0] == args.category
    ]
    sent: dict[str, int] = {}

    with tempfile.TemporaryDirectory(prefix="actu-foot-core-premium-") as tmp:
        tmpdir = Path(tmp)
        for index, (category, label, payload) in enumerate(selected, 1):
            graphic = tc.render(category, payload)
            expected = (1374, 1145) if category == "composition" else (1080, 1080)
            if graphic.size != expected:
                raise RuntimeError(f"{category}: dimensions {graphic.size}, attendu {expected}")
            if category == "composition":
                validate_composition_render(graphic)
            path = tmpdir / f"{index:02d}-{category}.png"
            graphic.save(path, "PNG", optimize=True)

            caption = (
                "<b>🧪 TEST VISUEL • ACTU FOOT PREMIUM</b>\n"
                f"<b>{label}</b>\n\n"
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

    if len(sent) != len(selected):
        raise RuntimeError("Toutes les previews sélectionnées n'ont pas été envoyées")
    print("ACTU_FOOT_CORE_TEST_REPORT", json.dumps(sent, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
