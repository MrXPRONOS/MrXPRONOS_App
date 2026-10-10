"""Rendu des cartes Mr XPRONOS à partir des templates PNG déposés dans assets/images.

Les templates contiennent le branding/statique. Ce module masque uniquement les
zones variables avant d'y injecter les vraies données BSD/RSS.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "images"
W = H = 1080

TEMPLATES = {
    "programme": "template_programme_matchs_du_jour.png",
    "avant_match": "template_avant_match.png",
    "resultat": "template_resultat_final.png",
    "statistique": "template_stat_du_jour.png",
    "flash": "template_flash_foot.png",
    "sondage": "template_sondage.png",
}

WHITE = "#F7F9FC"
GREY = "#A8B8C2"
GOLD = "#F1C55A"
NAVY = "#061522"
PANEL = "#071B2B"
PANEL_2 = "#0B2335"

FONT_BOLD = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)
FONT_REG = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for path in (FONT_BOLD if bold else FONT_REG):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fit(draw: ImageDraw.ImageDraw, value: Any, max_width: int, size: int,
        min_size: int = 14, bold: bool = True):
    value = clean(value)
    for current in range(size, min_size - 1, -1):
        face = font(current, bold)
        if draw.textbbox((0, 0), value, font=face)[2] <= max_width:
            return value, face
    face = font(min_size, bold)
    short = value
    while len(short) > 2 and draw.textbbox((0, 0), short + "…", font=face)[2] > max_width:
        short = short[:-1]
    return short.rstrip() + ("…" if short != value else ""), face


def text(draw: ImageDraw.ImageDraw, value: Any, xy: tuple[int, int], *,
         size: int = 26, bold: bool = False, fill: str = WHITE,
         anchor: str = "mm", width: int | None = None, min_size: int = 14) -> None:
    if width:
        value, face = fit(draw, value, width, size, min_size, bold)
    else:
        value, face = clean(value), font(size, bold)
    draw.text(xy, value, font=face, fill=fill, anchor=anchor)


def template(category: str) -> Image.Image:
    filename = TEMPLATES.get(category)
    if not filename:
        raise ValueError("Template inconnu: " + category)
    path = ASSETS / filename
    if not path.is_file():
        raise FileNotFoundError(
            f"Template absent: {path}. Déposer {filename} dans assets/images/."
        )
    image = Image.open(path).convert("RGB")
    if image.size != (W, H):
        image = ImageOps.fit(image, (W, H), method=Image.Resampling.LANCZOS)
    return image


def blank(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], *,
          radius: int = 18, fill: str = PANEL, outline: str | None = None,
          outline_width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill,
                           outline=outline, width=outline_width)


def logo(url: str, max_px: int) -> Image.Image:
    # Reuse the shared network/cache behavior already used by the programme engine.
    from programme_styles import load_logo
    result = load_logo(clean(url), max_px)
    if result is None:
        raise ValueError("Logo introuvable: " + clean(url)[:80])
    return result


def paste_logo(image: Image.Image, url: str, center: tuple[int, int], max_px: int) -> None:
    badge = logo(url, max_px)
    image.paste(
        badge,
        (center[0] - badge.width // 2, center[1] - badge.height // 2),
        badge,
    )


def remote_photo(url: str, size: tuple[int, int]) -> Image.Image | None:
    if not clean(url).startswith(("https://", "http://")):
        return None
    try:
        response = requests.get(
            clean(url), timeout=(6, 18),
            headers={"User-Agent": "Mozilla/5.0 MrXPRONOS-template/1.0"},
        )
        response.raise_for_status()
        if len(response.content) > 7_000_000:
            return None
        source = Image.open(io.BytesIO(response.content)).convert("RGB")
        return ImageOps.fit(source, size, Image.Resampling.LANCZOS, centering=(0.5, 0.44))
    except Exception:
        return None


def render_programme(payload: dict[str, Any]) -> Image.Image:
    rows = list(payload.get("matches") or [])[:5]
    if not rows:
        raise ValueError("Programme sans matchs")

    image = template("programme")
    d = ImageDraw.Draw(image)

    # Date variable.
    blank(d, (350, 244, 730, 304), radius=27, fill="#071A29")
    text(d, payload.get("day", ""), (540, 274), size=24, bold=True, width=310)

    centers = [382, 488, 594, 700, 806]
    for y, item in zip(centers, rows):
        home_logo = clean(item.get("home_logo"))
        away_logo = clean(item.get("away_logo"))
        if not home_logo or not away_logo:
            raise ValueError("Programme: les deux logos sont obligatoires")

        # Nettoyer uniquement les données d'exemple présentes dans le template.
        blank(d, (78, y-34, 155, y+34), radius=16, fill="#081B2B")
        blank(d, (160, y-28, 445, y+28), radius=12, fill="#081B2B")
        blank(d, (478, y-24, 602, y+18), radius=10, fill="#E7B84A")
        blank(d, (635, y-28, 920, y+28), radius=12, fill="#081B2B")
        blank(d, (925, y-34, 1002, y+34), radius=16, fill="#081B2B")

        paste_logo(image, home_logo, (116, y), 62)
        paste_logo(image, away_logo, (964, y), 62)
        text(d, item.get("home", ""), (300, y), size=24, bold=True, width=270, min_size=15)
        text(d, item.get("away", ""), (780, y), size=24, bold=True, width=270, min_size=15)
        text(d, item.get("time", ""), (540, y-4), size=20, bold=True, fill=NAVY, width=105)
        text(d, "VS", (540, y+27), size=18, bold=True, fill=GOLD)

    return image


def render_prematch(payload: dict[str, Any]) -> Image.Image:
    image = template("avant_match")
    d = ImageDraw.Draw(image)

    home, away = clean(payload.get("home")), clean(payload.get("away"))
    if not home or not away:
        raise ValueError("Avant-match incomplet")

    # Logos + noms.
    blank(d, (115, 350, 315, 565), radius=28, fill="#071A29")
    blank(d, (765, 350, 965, 565), radius=28, fill="#071A29")
    paste_logo(image, payload.get("home_logo", ""), (215, 440), 118)
    paste_logo(image, payload.get("away_logo", ""), (865, 440), 118)
    text(d, home, (245, 572), size=28, bold=True, width=330, min_size=17)
    text(d, away, (835, 572), size=28, bold=True, width=330, min_size=17)

    # Heure.
    blank(d, (455, 398, 625, 482), radius=20, fill="#E7B84A")
    text(d, payload.get("time", ""), (540, 440), size=31, bold=True, fill=NAVY, width=145)

    # Forme.
    home_form = clean(payload.get("home_form"))
    away_form = clean(payload.get("away_form"))
    blank(d, (125, 620, 955, 750), radius=25, fill="#081E30", outline="#6A5121")
    if home_form or away_form:
        text(d, "FORME RÉCENTE", (540, 646), size=18, bold=True, fill=GREY)
        if home_form:
            text(d, home, (175, 684), size=16, bold=True, anchor="lm", width=300)
            text(d, home_form, (175, 718), size=17, bold=True, fill=GOLD,
                 anchor="lm", width=330, min_size=13)
        if away_form:
            text(d, away, (575, 684), size=16, bold=True, anchor="lm", width=300)
            text(d, away_form, (575, 718), size=17, bold=True, fill=GOLD,
                 anchor="lm", width=330, min_size=13)

    blank(d, (430, 835, 650, 885), radius=16, fill="#071A29")
    text(d, payload.get("day", ""), (540, 860), size=18, fill=GREY)
    return image


def render_result(payload: dict[str, Any]) -> Image.Image:
    image = template("resultat")
    d = ImageDraw.Draw(image)
    home, away = clean(payload.get("home")), clean(payload.get("away"))
    scores = payload.get("scores")
    if not home or not away or not isinstance(scores, (list, tuple)) or len(scores) != 2:
        raise ValueError("Résultat incomplet")
    hs, aw = int(scores[0]), int(scores[1])

    blank(d, (135, 360, 355, 610), radius=30, fill="#071A29")
    blank(d, (725, 360, 945, 610), radius=30, fill="#071A29")
    paste_logo(image, payload.get("home_logo", ""), (245, 465), 128)
    paste_logo(image, payload.get("away_logo", ""), (835, 465), 128)
    text(d, home, (245, 590), size=29, bold=True, width=310, min_size=18)
    text(d, away, (835, 590), size=29, bold=True, width=310, min_size=18)

    blank(d, (410, 420, 670, 590), radius=28, fill="#E7B84A")
    text(d, f"{hs}  –  {aw}", (540, 505), size=68, bold=True, fill=NAVY)

    winner = "MATCH NUL" if hs == aw else "VICTOIRE • " + (home if hs > aw else away)
    blank(d, (230, 660, 850, 735), radius=22, fill="#081E30")
    text(d, winner, (540, 698), size=28, bold=True, fill=GOLD, width=560, min_size=18)

    blank(d, (430, 875, 650, 925), radius=16, fill="#071A29")
    text(d, payload.get("day", ""), (540, 900), size=18, fill=GREY)
    return image


def render_stat(payload: dict[str, Any]) -> Image.Image:
    image = template("statistique")
    d = ImageDraw.Draw(image)
    home, away = clean(payload.get("home")), clean(payload.get("away"))
    scores = payload.get("scores")
    if not home or not away or not isinstance(scores, (list, tuple)) or len(scores) != 2:
        raise ValueError("Statistique incomplète")
    hs, aw = int(scores[0]), int(scores[1])

    # Chiffre/stat principal.
    blank(d, (405, 355, 675, 505), radius=28, fill="#E7B84A")
    text(d, str(hs + aw), (540, 418), size=92, bold=True, fill=NAVY)
    blank(d, (435, 500, 645, 545), radius=14, fill="#071A29")
    text(d, "BUTS", (540, 522), size=22, bold=True, fill=GOLD)

    # Match.
    blank(d, (115, 565, 965, 735), radius=28, fill="#081E30", outline="#6A5121")
    paste_logo(image, payload.get("home_logo", ""), (175, 650), 82)
    paste_logo(image, payload.get("away_logo", ""), (905, 650), 82)
    text(d, home, (340, 648), size=27, bold=True, width=245, min_size=17)
    text(d, away, (740, 648), size=27, bold=True, width=245, min_size=17)
    blank(d, (470, 603, 610, 690), radius=18, fill="#E7B84A")
    text(d, f"{hs} - {aw}", (540, 646), size=34, bold=True, fill=NAVY)

    blank(d, (300, 755, 780, 800), radius=12, fill="#071A29")
    text(d, (payload.get("league") or "Football").upper(), (540, 777),
         size=21, bold=True, width=430)

    blank(d, (430, 895, 650, 940), radius=14, fill="#071A29")
    text(d, payload.get("day", ""), (540, 917), size=18, fill=GREY)
    return image


def render_flash(payload: dict[str, Any]) -> Image.Image:
    image = template("flash")
    d = ImageDraw.Draw(image)

    # Photo d'article.
    photo = remote_photo(payload.get("image_url", ""), (900, 470))
    blank(d, (90, 225, 990, 695), radius=28, fill="#081A29")
    if photo is not None:
        mask = Image.new("L", (900, 470), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle((0, 0, 899, 469), radius=28, fill=255)
        image.paste(photo, (90, 225), mask)
        overlay = Image.new("RGBA", (900, 470), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        for y in range(470):
            alpha = int(15 + 175 * (y / 469) ** 1.7)
            od.line((0, y, 900, y), fill=(2, 10, 20, alpha))
        image.paste(overlay, (90, 225), overlay)

    # Titre/article + métadonnées.
    blank(d, (105, 545, 975, 685), radius=18, fill="#071725")
    title = clean(payload.get("title"))
    words = title.split()
    lines, current = [], ""
    for word in words:
        trial = (current + " " + word).strip()
        if len(trial) > 48 and current:
            lines.append(current)
            current = word
        else:
            current = trial
        if len(lines) >= 2:
            break
    if current and len(lines) < 2:
        lines.append(current)
    yy = 577
    for line in lines[:2]:
        text(d, line, (125, yy), size=29, bold=True, anchor="la", width=820, min_size=20)
        yy += 42

    text(d, "SOURCE • " + clean(payload.get("source", "Foot Mercato")).upper(),
         (125, 660), size=17, bold=True, fill=GOLD, anchor="la", width=430)
    text(d, payload.get("day", ""), (950, 660), size=16, fill=GREY, anchor="ra", width=190)

    # Résumé nettoyé.
    blank(d, (115, 800, 965, 930), radius=26, fill="#081E30")
    summary = clean(payload.get("summary"))
    text(d, summary, (540, 842), size=18, fill=WHITE, width=760, min_size=14)
    return image


def render_poll(payload: dict[str, Any]) -> Image.Image:
    image = template("sondage")
    d = ImageDraw.Draw(image)
    question = clean(payload.get("question"))
    options = list(payload.get("options") or [])[:3]

    blank(d, (120, 300, 960, 500), radius=30, fill="#081E30", outline="#6A5121")
    text(d, question, (540, 400), size=30, bold=True, width=740, min_size=19)

    ys = [610, 720, 830]
    for idx, y in enumerate(ys):
        blank(d, (155, y-42, 925, y+42), radius=26, fill="#081E30", outline="#6A5121")
        if idx < len(options):
            text(d, options[idx], (540, y), size=24, bold=True, width=650, min_size=16)

    blank(d, (430, 895, 650, 940), radius=14, fill="#071A29")
    text(d, payload.get("day", ""), (540, 917), size=18, fill=GREY)
    return image


RENDERERS = {
    "programme": render_programme,
    "avant_match": render_prematch,
    "resultat": render_result,
    "statistique": render_stat,
    "flash": render_flash,
    "sondage": render_poll,
}


def render(category: str, payload: dict[str, Any]) -> Image.Image:
    renderer = RENDERERS.get(category)
    if renderer is None:
        raise ValueError("Rubrique sans template: " + category)
    return renderer(payload)
