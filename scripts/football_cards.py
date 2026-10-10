"""Cartes d'actualité football Mr XPRONOS.

Rendu Pillow 1080 x 1080, sans logos d'équipes présumés ni photos tierces.
Usage:
    python scripts/football_cards.py --demo --out-dir /tmp/xpronos-cards
Les vrais chiffres et rencontres proviennent de BSD V2 via football_channel.py.
"""
from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

W = H = 1080
NAVY = "#071521"
NAVY_2 = "#0D2534"
PANEL = "#132D3F"
GOLD = "#F3C969"
WHITE = "#F7F9FC"
GREY = "#A8B8C2"
SUBTLE = "#587180"

FONT_BOLD = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)
FONT_REGULAR = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


def font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    for candidate in (FONT_BOLD if bold else FONT_REGULAR):
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def fit(draw: ImageDraw.ImageDraw, value: Any, max_width: int, *,
        size: int = 32, min_size: int = 19, bold: bool = True) -> tuple[str, ImageFont.ImageFont]:
    """Conserver les noms complets lorsqu'ils tiennent; tronquer sinon."""
    title = clean(value)
    for n in range(size, min_size - 1, -1):
        current = font(n, bold=bold)
        if draw.textbbox((0, 0), title, font=current)[2] <= max_width:
            return title, current
    current = font(min_size, bold=bold)
    while len(title) > 2 and draw.textbbox((0, 0), title + "…", font=current)[2] > max_width:
        title = title[:-1]
    return title.rstrip() + ("…" if title != clean(value) else ""), current


def txt(draw: ImageDraw.ImageDraw, value: Any, x: int, y: int, *,
        size: int = 28, bold: bool = False, color: str = WHITE, anchor: str = "lt",
        max_width: int | None = None, min_size: int = 18) -> None:
    if max_width:
        content, face = fit(draw, value, max_width, size=size, min_size=min_size, bold=bold)
    else:
        content, face = clean(value), font(size, bold=bold)
    draw.text((x, y), content, font=face, fill=color, anchor=anchor)


def base(section: str, kicker: str, day: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(image)
    draw.polygon([(645, 0), (1080, 0), (1080, 400), (990, 530)], fill=NAVY_2)
    draw.polygon([(0, 900), (0, 1080), (390, 1080)], fill=NAVY_2)
    for offset in range(3):
        x = 920 + 25 * offset
        draw.line([(x, 0), (x + 230, 460)], fill="#173343", width=2)
    # Wordmark éditorial (sans usurper un fichier de logo)
    draw.rounded_rectangle((54, 54, 130, 130), radius=18, fill=GOLD)
    txt(draw, "X", 92, 92, size=51, bold=True, color=NAVY, anchor="mm")
    txt(draw, "MR", 151, 60, size=25, bold=True, color=GOLD)
    txt(draw, "XPRONOS", 151, 86, size=35, bold=True, color=WHITE)
    draw.line((54, 160, 1026, 160), fill="#345060", width=2)
    draw.rounded_rectangle((54, 189, 318, 231), radius=17, fill="#1F4151")
    txt(draw, kicker.upper(), 186, 210, size=20, bold=True, color=GOLD, anchor="mm",
        max_width=244)
    txt(draw, section.upper(), 54, 254, size=58, bold=True, max_width=967, min_size=38)
    txt(draw, day, 1026, 1030, size=23, color=GREY, anchor="rt", max_width=340)
    draw.line((54, 1004, 1026, 1004), fill="#345060", width=2)
    txt(draw, "MR XPRONOS  /  FOOTBALL", 54, 1028, size=22, bold=True, color=GOLD)
    return image, draw


def panel(draw: ImageDraw.ImageDraw, bounds: tuple[int, int, int, int], *,
          fill: str = PANEL, accent: bool = False) -> None:
    draw.rounded_rectangle(bounds, radius=24, fill=fill, outline="#294657", width=2)
    if accent:
        draw.rounded_rectangle((bounds[0], bounds[1]+8, bounds[0]+6, bounds[3]-8),
                               radius=3, fill=GOLD)


def programme_card(payload: dict[str, Any]) -> Image.Image:
    # Les 7 variantes sont isolées dans programme_styles pour conserver
    # ce fichier compatible avec les autres rubriques.
    from programme_styles import render_programme
    return render_programme(payload)


def result_card(payload: dict[str, Any]) -> Image.Image:
    home, away = clean(payload.get("home")), clean(payload.get("away"))
    scores = payload.get("scores")
    if not home or not away or not isinstance(scores, (tuple, list)) or len(scores) != 2:
        raise ValueError("Résultat incomplet")
    h, a = int(scores[0]), int(scores[1])
    if min(h, a) < 0:
        raise ValueError("Score négatif")
    image, d = base("RESULTAT FINAL", "COUP DE SIFFLET FINAL", clean(payload.get("day", "")))
    txt(d, payload.get("league") or "FOOTBALL", 540, 368, size=30, bold=True,
        color=GREY, anchor="mt", max_width=900)
    panel(d, (54, 428, 1026, 824), accent=True)
    txt(d, home, 270, 503, size=39, bold=True, anchor="mt", max_width=375, min_size=25)
    txt(d, away, 815, 503, size=39, bold=True, anchor="mt", max_width=375, min_size=25)
    txt(d, str(h), 397, 651, size=145, bold=True, anchor="mm", color=GOLD)
    txt(d, ":", 540, 641, size=112, bold=True, anchor="mm", color=GREY)
    txt(d, str(a), 683, 651, size=145, bold=True, anchor="mm", color=GOLD)
    if h == a:
        headline = "MATCH NUL"
    else:
        headline = "VICTOIRE  •  " + (home if h > a else away)
    txt(d, headline, 540, 882, size=29, bold=True, anchor="mt",
        color=GOLD, max_width=870)
    txt(d, "SCORE CONFIRME PAR BSD V2", 540, 942, size=21, bold=True,
        anchor="mt", color=GREY)
    return image


def statistic_card(payload: dict[str, Any]) -> Image.Image:
    home, away = clean(payload.get("home")), clean(payload.get("away"))
    scores = payload.get("scores")
    if not home or not away or not isinstance(scores, (tuple, list)) or len(scores) != 2:
        raise ValueError("Statistique incomplète")
    h, a = int(scores[0]), int(scores[1])
    if min(h, a) < 0:
        raise ValueError("Score négatif")
    image, d = base("LE CHIFFRE DU JOUR", "STATISTIQUE BSD", clean(payload.get("day", "")))
    panel(d, (54, 374, 1026, 867), accent=True)
    txt(d, "B U T S", 540, 425, size=28, bold=True, color=GREY, anchor="mt")
    txt(d, str(h + a), 540, 591, size=195, bold=True, color=GOLD, anchor="mm")
    d.line((355, 727, 725, 727), fill="#527184", width=2)
    txt(d, home, 284, 767, size=31, bold=True, color=WHITE, anchor="mt",
        max_width=383, min_size=22)
    txt(d, str(h) + " - " + str(a), 540, 766, size=37, bold=True, color=GOLD, anchor="mt")
    txt(d, away, 799, 767, size=31, bold=True, color=WHITE, anchor="mt",
        max_width=383, min_size=22)
    txt(d, payload.get("league") or "FOOTBALL", 540, 914, size=27, color=GREY,
        anchor="mt", max_width=860)
    txt(d, "UNE RENCONTRE D'HIER, PARMI LES MATCHS RECUPERES",
        540, 961, size=19, color=GREY, anchor="mt", max_width=968)
    return image


def render_card(category: str, payload: dict[str, Any], output: str | Path) -> Path:
    factories = {
        "programme": programme_card,
        "resultat": result_card,
        "statistique": statistic_card,
    }
    if category not in factories:
        raise ValueError("Rubrique sans modèle graphique: " + str(category))
    image = factories[category](payload)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=True)
    return destination


def demo(out_dir: str | Path) -> list[Path]:
    dest = Path(out_dir)
    day = date(2026, 10, 10).strftime("%d/%m/%Y")
    examples = [
        ("programme", {"day": day, "matches": [
            {"home": "Arsenal", "away": "Chelsea", "time": "17h30"},
            {"home": "Real Madrid", "away": "FC Barcelona", "time": "20h00"},
            {"home": "Paris Saint-Germain", "away": "Olympique de Marseille", "time": "21h00"},
            {"home": "Bayern Munich", "away": "Borussia Dortmund", "time": "15h30"},
            {"home": "Inter Milan", "away": "AC Milan", "time": "19h45"},
        ]}),
        ("resultat", {"day": day, "league": "Premier League", "home": "Arsenal",
                      "away": "Chelsea", "scores": [2, 1]}),
        ("statistique", {"day": day, "league": "Ligue des Champions", "home": "Real Madrid",
                         "away": "Borussia Dortmund", "scores": [4, 3]}),
    ]
    return [render_card(kind, payload, dest / (kind + "-demo.png")) for kind, payload in examples]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--programme-styles", action="store_true",
                        help="Genere les sept variantes Matchs du jour")
    parser.add_argument("--out-dir", default="/tmp/mrxpronos-football-cards")
    args = parser.parse_args()
    if args.programme_styles:
        from programme_styles import render_programme
        dest = Path(args.out_dir)
        payload = {"day": "10/10/2026", "matches": [
            {"home": "Arsenal", "away": "Chelsea", "time": "17h30"},
            {"home": "Real Madrid", "away": "FC Barcelona", "time": "20h00"},
            {"home": "PSG", "away": "Marseille", "time": "21h00"},
            {"home": "Bayern Munich", "away": "Borussia Dortmund", "time": "15h30"},
            {"home": "Inter Milan", "away": "AC Milan", "time": "19h45"},
        ]}
        dest.mkdir(parents=True, exist_ok=True)
        for style in range(1,8):
            out = dest / ("programme-style-" + str(style) + ".png")
            render_programme(payload, style=style).save(out, "PNG", optimize=True)
            print("PREVIEW_STYLE", style, out)
    elif args.demo:
        for path in demo(args.out_dir):
            print("PREVIEW", path)
    else:
        parser.error("Utilisez --demo ou --programme-styles")
