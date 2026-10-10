"""Cartes d'actualité football Mr XPRONOS.

Rendu Pillow 1080 x 1080, sans logos d'équipes présumés ni photos tierces.
Usage:
    python scripts/football_cards.py --demo --out-dir /tmp/xpronos-cards
Les vrais chiffres et rencontres proviennent de BSD V2 via football_channel.py.
"""
from __future__ import annotations

import argparse
import io
import re
from datetime import date
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

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


def remote_image(url: str, size: tuple[int, int]) -> Image.Image | None:
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        return None
    try:
        response = requests.get(
            url, timeout=(6, 15),
            headers={"User-Agent": "Mozilla/5.0 MrXPRONOS-card/1.0"},
        )
        response.raise_for_status()
        if len(response.content) > 6_000_000:
            return None
        source = Image.open(io.BytesIO(response.content)).convert("RGB")
        return ImageOps.fit(
            source, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.45)
        )
    except Exception:
        return None


def paste_required_logo(image: Image.Image, url: str, center: tuple[int, int],
                        max_px: int = 130) -> None:
    from programme_styles import load_logo
    logo = load_logo(url, max_px)
    if logo is None:
        raise ValueError("Logo d'équipe introuvable au rendu")
    image.paste(
        logo,
        (center[0] - logo.width // 2, center[1] - logo.height // 2),
        logo,
    )


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
    home_logo = clean(payload.get("home_logo"))
    away_logo = clean(payload.get("away_logo"))
    if not home_logo or not away_logo:
        raise ValueError("Résultat sans deux logos")

    from programme_styles import (
        background as premium_background,
        gradient_text,
        gradient_round_rect,
        gradient_outline_round_rect,
    )

    image, d = premium_background(6)

    txt(d, "♛", 540, 35, size=28, bold=True, color=GOLD, anchor="ma")
    txt(d, "MR", 495, 62, size=29, bold=True, color=WHITE, anchor="ra")
    gradient_text(image, "XPRONOS", (505, 62), size=29, anchor="la")
    d.line((315, 75, 410, 75), fill="#D99D2B", width=2)
    d.line((670, 75, 765, 75), fill="#D99D2B", width=2)

    txt(d, "RÉSULTAT", 530, 120, size=64, bold=True, color=WHITE, anchor="ra")
    gradient_text(image, "FINAL", (550, 120), size=64, anchor="la")
    txt(d, (payload.get("league") or "FOOTBALL").upper(), 540, 207,
        size=22, bold=True, color=GREY, anchor="ma", max_width=800)

    d.rounded_rectangle((62, 285, 1018, 825), radius=34, fill="#061827")
    gradient_outline_round_rect(image, (62, 285, 1018, 825), 34, width=3, glow=True)

    paste_required_logo(image, home_logo, (245, 470), 150)
    paste_required_logo(image, away_logo, (835, 470), 150)

    txt(d, home, 245, 585, size=32, bold=True, anchor="ma",
        max_width=300, min_size=20)
    txt(d, away, 835, 585, size=32, bold=True, anchor="ma",
        max_width=300, min_size=20)

    gradient_round_rect(image, (410, 420, 670, 590), 28)
    txt(d, str(h) + "  –  " + str(a), 540, 505, size=72, bold=True,
        color="#061521", anchor="mm")

    if h == a:
        headline = "MATCH NUL"
    else:
        headline = "VICTOIRE • " + (home if h > a else away)
    txt(d, headline, 540, 700, size=32, bold=True, color=GOLD, anchor="ma",
        max_width=820, min_size=21)
    txt(d, "SCORE CONFIRMÉ PAR BSD V2", 540, 757, size=19,
        color=GREY, anchor="ma")

    d.line((280, 900, 430, 900), fill="#D99D2B", width=2)
    d.line((650, 900, 800, 900), fill="#D99D2B", width=2)
    txt(d, clean(payload.get("day", "")), 540, 900, size=19, color=GREY, anchor="mm")

    d.rounded_rectangle((190, 952, 890, 1032), radius=35, fill="#071927")
    gradient_outline_round_rect(image, (190, 952, 890, 1032), 35, width=2, glow=True)
    txt(d, "VOTRE RÉACTION DANS LES COMMENTAIRES", 540, 992,
        size=20, bold=True, anchor="mm", max_width=620, min_size=16)
    return image

def statistic_card(payload: dict[str, Any]) -> Image.Image:
    home, away = clean(payload.get("home")), clean(payload.get("away"))
    scores = payload.get("scores")
    if not home or not away or not isinstance(scores, (tuple, list)) or len(scores) != 2:
        raise ValueError("Statistique incomplète")
    h, a = int(scores[0]), int(scores[1])
    if min(h, a) < 0:
        raise ValueError("Score négatif")

    from programme_styles import (
        background as premium_background,
        gradient_text,
        gradient_round_rect,
        gradient_outline_round_rect,
        team_visual,
    )

    image, d = premium_background(6)

    # Header brand
    txt(d, "♛", 540, 35, size=28, bold=True, color=GOLD, anchor="ma")
    txt(d, "MR", 495, 62, size=29, bold=True, color=WHITE, anchor="ra")
    gradient_text(image, "XPRONOS", (505, 62), size=29, anchor="la")
    d.line((315, 75, 410, 75), fill="#D99D2B", width=2)
    d.line((670, 75, 765, 75), fill="#D99D2B", width=2)

    txt(d, "LA STAT", 530, 118, size=65, bold=True, color=WHITE, anchor="ra")
    gradient_text(image, "DU JOUR", (550, 118), size=65, anchor="la")
    txt(d, "LE FAIT MARQUANT D’HIER", 540, 202, size=21, bold=True, color=GREY, anchor="ma")

    # Main content frame
    d.rounded_rectangle((62, 272, 1018, 876), radius=34, fill="#061827")
    gradient_outline_round_rect(image, (62, 272, 1018, 876), 34, width=3, glow=True)

    # Number no longer dominates everything: concise gold badge
    txt(d, "STATISTIQUE MARQUANTE", 540, 324, size=22, bold=True, color=GREY, anchor="ma")
    gradient_round_rect(image, (405, 355, 675, 493), 28)
    txt(d, str(h + a), 540, 424, size=104, bold=True, color="#071521", anchor="mm")
    txt(d, "BUTS", 540, 514, size=25, bold=True, color="#F5D576", anchor="ma")

    # Score becomes the real focus
    d.rounded_rectangle((112, 566, 968, 731), radius=28, fill="#081D2E")
    gradient_outline_round_rect(image, (112, 566, 968, 731), 28, width=2, glow=False)

    home_logo = clean(payload.get("home_logo", ""))
    away_logo = clean(payload.get("away_logo", ""))
    if not home_logo or not away_logo:
        raise ValueError("Statistique sans deux logos")
    paste_required_logo(image, home_logo, (175, 649), 115)
    paste_required_logo(image, away_logo, (905, 649), 115)

    txt(d, home, 340, 647, size=31, bold=True, color=WHITE, anchor="mm",
        max_width=250, min_size=19)
    txt(d, away, 740, 647, size=31, bold=True, color=WHITE, anchor="mm",
        max_width=250, min_size=19)

    gradient_round_rect(image, (465, 600, 615, 690), 18)
    txt(d, str(h) + " - " + str(a), 540, 645, size=38, bold=True,
        color="#061521", anchor="mm")

    league_name = payload.get("league") or "Football"
    txt(d, league_name.upper(), 540, 772, size=24, bold=True, color=WHITE,
        anchor="ma", max_width=760, min_size=17)
    txt(d, "SÉLECTIONNÉE PARMI LES MATCHS BSD D’HIER",
        540, 820, size=17, color=GREY, anchor="ma", max_width=860, min_size=14)

    # Footer
    d.line((270, 920, 430, 920), fill="#D99D2B", width=2)
    d.line((650, 920, 810, 920), fill="#D99D2B", width=2)
    txt(d, clean(payload.get("day", "")), 540, 920, size=19, color=GREY, anchor="mm")

    d.rounded_rectangle((165, 960, 915, 1035), radius=34, fill="#071927")
    gradient_outline_round_rect(image, (165, 960, 915, 1035), 34, width=2, glow=True)
    txt(d, "💬 QUEL AUTRE MATCH VOUS A MARQUÉ ?", 540, 998,
        size=21, bold=True, color=WHITE, anchor="mm", max_width=680, min_size=16)
    return image



def prematch_card(payload: dict[str, Any]) -> Image.Image:
    from programme_styles import (
        background as premium_background,
        gradient_text,
        gradient_round_rect,
        gradient_outline_round_rect,
        team_visual,
    )

    home = clean(payload.get("home"))
    away = clean(payload.get("away"))
    if not home or not away:
        raise ValueError("Avant-match incomplet")

    image, d = premium_background(6)

    txt(d, "♛", 540, 35, size=28, bold=True, color=GOLD, anchor="ma")
    txt(d, "MR", 495, 62, size=29, bold=True, color=WHITE, anchor="ra")
    gradient_text(image, "XPRONOS", (505, 62), size=29, anchor="la")

    txt(d, "AVANT", 530, 120, size=64, bold=True, color=WHITE, anchor="ra")
    gradient_text(image, "MATCH", (550, 120), size=64, anchor="la")
    txt(d, (payload.get("league") or "FOOTBALL").upper(), 540, 205,
        size=21, bold=True, color=GREY, anchor="ma", max_width=820)

    d.rounded_rectangle((65, 285, 1015, 790), radius=34, fill="#061827")
    gradient_outline_round_rect(image, (65, 285, 1015, 790), 34, width=3, glow=True)

    home_item = {"home": home, "home_logo": payload.get("home_logo", "")}
    away_item = {"away": away, "away_logo": payload.get("away_logo", "")}
    team_visual(image, d, 190, 455, home_item, "home", scale=1.15, circle=True)
    team_visual(image, d, 890, 455, away_item, "away", scale=1.15, circle=True)

    txt(d, home, 260, 570, size=31, bold=True, anchor="ma",
        max_width=330, min_size=19)
    txt(d, away, 820, 570, size=31, bold=True, anchor="ma",
        max_width=330, min_size=19)

    gradient_round_rect(image, (455, 398, 625, 480), 18)
    txt(d, payload.get("time", "--h--"), 540, 439, size=33, bold=True,
        color="#061521", anchor="mm")
    txt(d, "COUP D’ENVOI • HEURE DU TOGO", 540, 520, size=17,
        bold=True, color=GOLD, anchor="ma")

    d.rounded_rectangle((125, 625, 955, 735), radius=25,
                        fill="#0A2234", outline="#5C4A24", width=2)
    txt(d, "FORME RÉCENTE", 540, 650, size=18, bold=True, color=GREY, anchor="ma")
    txt(d, home + " : " + clean(payload.get("home_form", "")),
        155, 690, size=18, color=WHITE, anchor="lm", max_width=365, min_size=14)
    txt(d, away + " : " + clean(payload.get("away_form", "")),
        560, 690, size=18, color=WHITE, anchor="lm", max_width=365, min_size=14)

    txt(d, clean(payload.get("day", "")), 540, 860, size=19,
        color=GREY, anchor="mm")

    d.rounded_rectangle((175, 930, 905, 1015), radius=36, fill="#071927")
    gradient_outline_round_rect(image, (175, 930, 905, 1015), 36, width=2, glow=True)
    txt(d, "QUEL SCÉNARIO IMAGINEZ-VOUS ?", 540, 972,
        size=22, bold=True, anchor="mm", max_width=650, min_size=17)
    return image


def flash_card(payload: dict[str, Any]) -> Image.Image:
    from programme_styles import (
        background as premium_background,
        gradient_text,
        gradient_outline_round_rect,
    )

    image, d = premium_background(6)
    photo = remote_image(clean(payload.get("image_url", "")), (940, 520))

    txt(d, "♛", 540, 34, size=27, bold=True, color=GOLD, anchor="ma")
    txt(d, "MR", 495, 61, size=28, bold=True, color=WHITE, anchor="ra")
    gradient_text(image, "XPRONOS", (505, 61), size=28, anchor="la")

    txt(d, "FLASH", 530, 116, size=62, bold=True, color=WHITE, anchor="ra")
    gradient_text(image, "FOOT", (550, 116), size=62, anchor="la")

    frame = (70, 230, 1010, 750)
    d.rounded_rectangle(frame, radius=34, fill="#071A29")
    gradient_outline_round_rect(image, frame, 34, width=3, glow=True)

    if photo:
        mask = Image.new("L", (940, 520), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle((0, 0, 939, 519), radius=30, fill=255)
        image.paste(photo, (70, 230), mask)

        overlay = Image.new("RGBA", (940, 520), (4, 15, 28, 0))
        od = ImageDraw.Draw(overlay)
        for y in range(520):
            alpha = int(18 + 185 * (y / 519) ** 1.7)
            od.line((0, y, 940, y), fill=(2, 10, 20, alpha))
        image.paste(overlay, (70, 230), overlay)

    title = clean(payload.get("title", "Actualité football"))
    words = title.split()
    lines = []
    current = ""
    for word in words:
        trial = (current + " " + word).strip()
        if len(trial) > 46 and current:
            lines.append(current)
            current = word
        else:
            current = trial
        if len(lines) >= 2:
            break
    if current and len(lines) < 2:
        lines.append(current)

    y = 590
    for line in lines[:2]:
        txt(d, line, 110, y, size=31, bold=True, color=WHITE,
            anchor="la", max_width=860, min_size=22)
        y += 45

    txt(d, "SOURCE • " + clean(payload.get("source", "Foot Mercato")).upper(),
        110, 705, size=18, bold=True, color=GOLD, anchor="la")
    txt(d, clean(payload.get("day", "")), 970, 705,
        size=17, color=GREY, anchor="ra")

    d.rounded_rectangle((110, 815, 970, 940), radius=28, fill="#081D2E")
    summary = clean(payload.get("summary", ""))
    txt(d, summary, 540, 850, size=19, color=WHITE, anchor="ma",
        max_width=790, min_size=15)
    txt(d, "LIRE L’ARTICLE COMPLET VIA LE BOUTON TELEGRAM", 540, 907,
        size=16, bold=True, color=GREY, anchor="ma")
    txt(d, "MR XPRONOS • L’ACTUALITÉ DU FOOTBALL", 540, 1010,
        size=18, bold=True, color=GOLD, anchor="mm")
    return image

def render_card(category: str, payload: dict[str, Any], output: str | Path) -> Path:
    factories = {
        "programme": programme_card,
        "resultat": result_card,
        "statistique": statistic_card,
        "avant_match": prematch_card,
        "flash": flash_card,
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
        ("resultat", {"day": day, "league": "Premier League", "home": "Leeds United",
                      "away": "Sunderland", "scores": [2, 1],
                      "home_logo": "https://r2.thesportsdb.com/images/media/team/badge/jcgrml1756649030.png",
                      "away_logo": "https://r2.thesportsdb.com/images/media/team/badge/tprtus1448813498.png"}),
        ("statistique", {"day": day, "league": "Premier League", "home": "Leeds United",
                         "away": "Sunderland", "scores": [3, 2],
                         "home_logo": "https://r2.thesportsdb.com/images/media/team/badge/jcgrml1756649030.png",
                         "away_logo": "https://r2.thesportsdb.com/images/media/team/badge/tprtus1448813498.png"}),
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
