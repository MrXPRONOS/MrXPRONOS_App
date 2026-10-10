"""Renderer premium Mr XPRONOS basé sur les six templates PNG.

Règle principale:
- le template fournit déjà cadres, cercles, capsules, titres et décoration;
- le code ne redessine PAS ces éléments;
- le code injecte uniquement les données dynamiques dans des zones mesurées
  sur les templates normalisés en 1080x1080.

Toutes les coordonnées de ce module sont donc des coordonnées 1080x1080.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any, Iterable

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
GREY = "#B7C2CC"
GOLD = "#F1C55A"
NAVY = "#061522"
PANEL = "#081D2E"

FONT_BOLD = (
    "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Heavy.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)
FONT_REG = (
    "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Medium.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
)

# Zones mesurées sur les templates 1080x1080.
PROGRAMME_ROWS = (
    {"y": 371, "home_box": (189, 346, 431, 394), "away_box": (650, 346, 891, 394)},
    {"y": 487, "home_box": (189, 462, 431, 510), "away_box": (650, 462, 891, 510)},
    {"y": 602, "home_box": (189, 577, 431, 625), "away_box": (650, 577, 891, 625)},
    {"y": 717, "home_box": (189, 692, 431, 741), "away_box": (650, 692, 891, 741)},
    {"y": 833, "home_box": (189, 808, 431, 856), "away_box": (650, 808, 891, 856)},
)
PROGRAMME_HOME_LOGO_X = 140
PROGRAMME_AWAY_LOGO_X = 941
PROGRAMME_TIME_X = 540

PREMATCH_HOME_LOGO = (237, 431)
PREMATCH_AWAY_LOGO = (842, 431)
PREMATCH_HOME_NAME = (112, 521, 362, 564)
PREMATCH_AWAY_NAME = (719, 521, 969, 564)
PREMATCH_TIME_BOX = (455, 405, 625, 462)
PREMATCH_DATE_BOX = (482, 840, 689, 883)
PREMATCH_FORM_LEFT = ((227, 699), (282, 699), (336, 699), (391, 699), (445, 699))
PREMATCH_FORM_RIGHT = ((624, 699), (679, 699), (734, 699), (789, 699), (843, 699))

RESULT_HOME_LOGO = (216, 487)
RESULT_AWAY_LOGO = (862, 487)
RESULT_HOME_NAME = (99, 594, 336, 642)
RESULT_AWAY_NAME = (745, 594, 982, 642)
RESULT_SCORE_BOX = (394, 437, 687, 576)
RESULT_WINNER_BOX = (310, 663, 771, 711)
RESULT_DATE_BOX = (508, 831, 663, 874)

STAT_VALUE_BOX = (356, 405, 723, 574)
STAT_LABEL_BOX = (370, 577, 711, 613)
STAT_HOME_LOGO = (164, 691)
STAT_AWAY_LOGO = (915, 691)
STAT_HOME_NAME = (215, 667, 431, 715)
STAT_AWAY_NAME = (655, 667, 870, 715)
STAT_SCORE_BOX = (463, 658, 617, 724)
STAT_DATE_BOX = (508, 896, 655, 939)

FLASH_PHOTO_BOX = (79, 234, 1001, 606)  # 922 x 372
FLASH_TITLE_BOX = (125, 644, 792, 699)
FLASH_SOURCE_BOX = (125, 704, 603, 736)
FLASH_DATE_BOX = (736, 699, 818, 734)
FLASH_SUMMARY_BOX = (267, 797, 956, 868)
FLASH_CTA_BOX = (336, 932, 810, 980)

POLL_QUESTION_BOX = (129, 349, 952, 435)
POLL_OPTION_BOXES = (
    (293, 508, 861, 560),
    (293, 634, 861, 686),
    (293, 760, 861, 812),
)
POLL_ICON_CENTERS = ((155, 534), (155, 660), (155, 786))
POLL_DATE_BOX = (491, 868, 680, 909)


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for path in (FONT_BOLD if bold else FONT_REG):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _box_size(box: tuple[int, int, int, int]) -> tuple[int, int]:
    return box[2] - box[0], box[3] - box[1]


def _text_width(draw: ImageDraw.ImageDraw, value: str, face: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), value, font=face)
    return bbox[2] - bbox[0]


def _line_height(draw: ImageDraw.ImageDraw, face: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), "Ag", font=face)
    return max(1, bbox[3] - bbox[1])


def _truncate_chars(value: str, max_chars: int | None) -> str:
    value = clean(value)
    if not max_chars or len(value) <= max_chars:
        return value
    short = value[: max(1, max_chars - 1)].rstrip()
    if " " in short:
        candidate = short.rsplit(" ", 1)[0].rstrip()
        if len(candidate) >= max_chars // 2:
            short = candidate
    return short.rstrip(" ,.;:-") + "…"


def _ellipsize_pixels(
    draw: ImageDraw.ImageDraw,
    value: str,
    face: ImageFont.ImageFont,
    max_width: int,
) -> str:
    value = clean(value)
    if _text_width(draw, value, face) <= max_width:
        return value
    suffix = "…"
    short = value
    while len(short) > 1 and _text_width(draw, short.rstrip() + suffix, face) > max_width:
        short = short[:-1]
    if " " in short:
        word_cut = short.rsplit(" ", 1)[0].rstrip()
        if word_cut and _text_width(draw, word_cut + suffix, face) <= max_width:
            short = word_cut
    return short.rstrip(" ,.;:-") + suffix


def _preferred_size_by_chars(
    value: str,
    rules: Iterable[tuple[int, int]],
    fallback: int,
) -> int:
    length = len(clean(value))
    for max_chars, size in rules:
        if length <= max_chars:
            return size
    return fallback


def draw_single_line(
    draw: ImageDraw.ImageDraw,
    value: Any,
    box: tuple[int, int, int, int],
    *,
    preferred_size: int,
    min_size: int,
    bold: bool = True,
    fill: str = WHITE,
    max_chars: int | None = None,
    align: str = "center",
) -> tuple[str, int]:
    """Dessine une ligne strictement à l'intérieur de box.

    Le garde-fou caractères évite des chaînes absurdes, mais la décision finale
    est toujours prise en pixels avec textbbox().
    """
    value = _truncate_chars(clean(value), max_chars)
    max_width, max_height = _box_size(box)
    max_width = max(1, max_width - 8)
    max_height = max(1, max_height - 4)

    chosen_face = _font(min_size, bold)
    chosen_size = min_size
    for size in range(preferred_size, min_size - 1, -1):
        face = _font(size, bold)
        if _text_width(draw, value, face) <= max_width and _line_height(draw, face) <= max_height:
            chosen_face = face
            chosen_size = size
            break

    value = _ellipsize_pixels(draw, value, chosen_face, max_width)
    x1, y1, x2, y2 = box
    cy = (y1 + y2) // 2
    if align == "left":
        draw.text((x1 + 4, cy), value, font=chosen_face, fill=fill, anchor="lm")
    elif align == "right":
        draw.text((x2 - 4, cy), value, font=chosen_face, fill=fill, anchor="rm")
    else:
        draw.text(((x1 + x2) // 2, cy), value, font=chosen_face, fill=fill, anchor="mm")
    return value, chosen_size


def _wrap_pixels(
    draw: ImageDraw.ImageDraw,
    value: str,
    face: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = clean(value).split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = current + " " + word
        if _text_width(draw, trial, face) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def draw_multiline(
    draw: ImageDraw.ImageDraw,
    value: Any,
    box: tuple[int, int, int, int],
    *,
    preferred_size: int,
    min_size: int,
    max_lines: int,
    bold: bool = False,
    fill: str = WHITE,
    max_chars: int | None = None,
    align: str = "left",
    line_gap: int = 3,
) -> tuple[list[str], int]:
    value = _truncate_chars(clean(value), max_chars)
    box_width, box_height = _box_size(box)
    max_width = max(1, box_width - 8)
    max_height = max(1, box_height - 4)

    chosen_lines: list[str] = []
    chosen_face = _font(min_size, bold)
    chosen_size = min_size
    chosen_height = _line_height(draw, chosen_face)

    for size in range(preferred_size, min_size - 1, -1):
        face = _font(size, bold)
        lines = _wrap_pixels(draw, value, face, max_width)
        lh = _line_height(draw, face)
        total_h = len(lines) * lh + max(0, len(lines) - 1) * line_gap
        if len(lines) <= max_lines and total_h <= max_height:
            chosen_lines = lines
            chosen_face = face
            chosen_size = size
            chosen_height = lh
            break

    if not chosen_lines:
        chosen_face = _font(min_size, bold)
        chosen_size = min_size
        chosen_height = _line_height(draw, chosen_face)
        chosen_lines = _wrap_pixels(draw, value, chosen_face, max_width)
        if len(chosen_lines) > max_lines:
            chosen_lines = chosen_lines[:max_lines]
            remaining = " ".join(chosen_lines[-1:])
            chosen_lines[-1] = _ellipsize_pixels(draw, remaining + "…", chosen_face, max_width)
        elif chosen_lines:
            chosen_lines[-1] = _ellipsize_pixels(draw, chosen_lines[-1], chosen_face, max_width)

    x1, y1, x2, y2 = box
    total_h = len(chosen_lines) * chosen_height + max(0, len(chosen_lines) - 1) * line_gap
    y = y1 + max(0, (box_height - total_h) // 2) + chosen_height // 2

    for line in chosen_lines:
        if align == "center":
            draw.text(((x1 + x2) // 2, y), line, font=chosen_face, fill=fill, anchor="mm")
        elif align == "right":
            draw.text((x2 - 4, y), line, font=chosen_face, fill=fill, anchor="rm")
        else:
            draw.text((x1 + 4, y), line, font=chosen_face, fill=fill, anchor="lm")
        y += chosen_height + line_gap

    return chosen_lines, chosen_size


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


def _load_logo(url: str, max_px: int) -> Image.Image:
    from programme_styles import load_logo

    badge = load_logo(clean(url), max_px)
    if badge is None:
        raise ValueError("Logo introuvable: " + clean(url)[:80])
    # Sécurité supplémentaire: ne jamais déformer un logo.
    badge.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    return badge


def paste_logo(
    image: Image.Image,
    url: str,
    center: tuple[int, int],
    max_px: int,
) -> tuple[int, int]:
    badge = _load_logo(url, max_px)
    image.paste(
        badge,
        (center[0] - badge.width // 2, center[1] - badge.height // 2),
        badge,
    )
    return badge.size


def remote_photo(url: str, size: tuple[int, int]) -> Image.Image | None:
    if not clean(url).startswith(("https://", "http://")):
        return None
    try:
        response = requests.get(
            clean(url),
            timeout=(6, 18),
            headers={"User-Agent": "Mozilla/5.0 MrXPRONOS-template/2.0"},
        )
        response.raise_for_status()
        if len(response.content) > 7_000_000:
            return None
        source = Image.open(io.BytesIO(response.content)).convert("RGB")
        return ImageOps.fit(
            source,
            size,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.44),
        )
    except Exception:
        return None


def paste_rounded_photo(
    image: Image.Image,
    photo: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
) -> None:
    width, height = _box_size(box)
    if photo.size != (width, height):
        photo = ImageOps.fit(photo, (width, height), method=Image.Resampling.LANCZOS)
    mask = Image.new("L", (width, height), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=255)
    image.paste(photo, (box[0], box[1]), mask)


def _gold_capsule(
    image: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
) -> None:
    """Reconstruit uniquement l'intérieur gold d'une zone placeholder.

    Utilisé exclusivement sur le template Stat qui contient encore X et 0-0.
    """
    x1, y1, x2, y2 = box
    width, height = _box_size(box)
    grad = Image.new("RGB", (width, height))
    gd = ImageDraw.Draw(grad)
    stops = (
        (255, 244, 174),
        (248, 211, 91),
        (227, 169, 53),
        (255, 228, 122),
    )
    for y in range(height):
        t = y / max(1, height - 1)
        if t < 0.35:
            a, b, u = stops[0], stops[1], t / 0.35
        elif t < 0.72:
            a, b, u = stops[1], stops[2], (t - 0.35) / 0.37
        else:
            a, b, u = stops[2], stops[3], (t - 0.72) / 0.28
        color = tuple(int(a[i] * (1 - u) + b[i] * u) for i in range(3))
        gd.line((0, y, width, y), fill=color)
    mask = Image.new("L", (width, height), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=255)
    image.paste(grad, (x1, y1), mask)


def _local_dark_patch(
    image: Image.Image,
    box: tuple[int, int, int, int],
    *,
    radius: int = 5,
    fill: str = "#0A2032",
) -> None:
    # Petit masque local uniquement pour effacer un placeholder intégré au PNG.
    ImageDraw.Draw(image).rounded_rectangle(box, radius=radius, fill=fill)


def _team_name_size(value: str, context: str) -> tuple[int, int, int]:
    value = clean(value)
    if context == "programme":
        size = _preferred_size_by_chars(value, ((19, 24), (21, 22), (24, 20), (28, 18)), 17)
        return size, 17, 28
    if context == "prematch":
        size = _preferred_size_by_chars(value, ((17, 28), (20, 25), (23, 22), (28, 19)), 17)
        return size, 17, 28
    if context == "result":
        size = _preferred_size_by_chars(value, ((16, 29), (19, 26), (22, 22), (25, 18)), 18)
        return size, 18, 25
    if context == "stat":
        size = _preferred_size_by_chars(value, ((15, 27), (18, 23), (21, 20), (24, 17)), 17)
        return size, 17, 24
    return 24, 16, 30


def _parse_form(value: Any) -> tuple[list[str], str]:
    value = clean(value)
    if not value:
        return [], ""
    parts = [part.strip() for part in value.split("|", 1)]
    verdicts = re.findall(r"\b[VND]\b", parts[0].upper())[:5]
    points = parts[1].strip() if len(parts) > 1 else ""
    return verdicts, points


def _draw_form_side(
    image: Image.Image,
    value: Any,
    centers: tuple[tuple[int, int], ...],
    *,
    points_center: tuple[int, int],
) -> None:
    verdicts, points = _parse_form(value)
    if not verdicts:
        return

    draw = ImageDraw.Draw(image)
    colors = {"V": "#2FD66C", "N": "#D6DEE7", "D": "#F24D5D"}
    for index, center in enumerate(centers):
        verdict = verdicts[index] if index < len(verdicts) else ""
        if not verdict:
            continue
        radius = 22
        draw.ellipse(
            (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius),
            fill="#071A29",
            outline=colors.get(verdict, GREY),
            width=3,
        )
        draw.text(center, verdict, font=_font(16, True), fill=WHITE, anchor="mm")

    if points:
        draw_single_line(
            draw,
            points,
            (points_center[0] - 90, points_center[1] - 18,
             points_center[0] + 90, points_center[1] + 18),
            preferred_size=16,
            min_size=13,
            bold=True,
            fill=GOLD,
            max_chars=12,
        )


def render_programme(payload: dict[str, Any]) -> Image.Image:
    rows = list(payload.get("matches") or [])[:5]
    if not rows:
        raise ValueError("Programme sans matchs")

    image = template("programme")
    draw = ImageDraw.Draw(image)

    draw_single_line(
        draw,
        payload.get("day", ""),
        (465, 251, 680, 300),
        preferred_size=24,
        min_size=20,
        bold=True,
        max_chars=10,
    )

    for meta, item in zip(PROGRAMME_ROWS, rows):
        home_logo = clean(item.get("home_logo"))
        away_logo = clean(item.get("away_logo"))
        if not home_logo or not away_logo:
            raise ValueError("Programme: les deux logos sont obligatoires")

        paste_logo(image, home_logo, (PROGRAMME_HOME_LOGO_X, meta["y"]), 60)
        paste_logo(image, away_logo, (PROGRAMME_AWAY_LOGO_X, meta["y"]), 60)

        home = clean(item.get("home"))
        away = clean(item.get("away"))
        home_size, home_min, home_chars = _team_name_size(home, "programme")
        away_size, away_min, away_chars = _team_name_size(away, "programme")

        draw_single_line(
            draw, home, meta["home_box"],
            preferred_size=home_size, min_size=home_min,
            bold=True, max_chars=home_chars,
        )
        draw_single_line(
            draw, away, meta["away_box"],
            preferred_size=away_size, min_size=away_min,
            bold=True, max_chars=away_chars,
        )
        draw_single_line(
            draw,
            item.get("time", ""),
            (484, meta["y"] - 22, 596, meta["y"] + 18),
            preferred_size=21,
            min_size=18,
            bold=True,
            fill=NAVY,
            max_chars=5,
        )
        # Le VS est déjà imprimé dans le template: ne pas le redessiner.

    return image


def render_prematch(payload: dict[str, Any]) -> Image.Image:
    image = template("avant_match")
    draw = ImageDraw.Draw(image)

    home = clean(payload.get("home"))
    away = clean(payload.get("away"))
    if not home or not away:
        raise ValueError("Avant-match incomplet")

    paste_logo(image, payload.get("home_logo", ""), PREMATCH_HOME_LOGO, 105)
    paste_logo(image, payload.get("away_logo", ""), PREMATCH_AWAY_LOGO, 105)

    home_size, home_min, home_chars = _team_name_size(home, "prematch")
    away_size, away_min, away_chars = _team_name_size(away, "prematch")
    draw_single_line(
        draw, home, PREMATCH_HOME_NAME,
        preferred_size=home_size, min_size=home_min,
        bold=True, max_chars=home_chars,
    )
    draw_single_line(
        draw, away, PREMATCH_AWAY_NAME,
        preferred_size=away_size, min_size=away_min,
        bold=True, max_chars=away_chars,
    )

    draw_single_line(
        draw, payload.get("time", ""), PREMATCH_TIME_BOX,
        preferred_size=36, min_size=30, bold=True, fill=NAVY, max_chars=5,
    )

    _draw_form_side(
        image,
        payload.get("home_form", ""),
        PREMATCH_FORM_LEFT,
        points_center=(336, 749),
    )
    _draw_form_side(
        image,
        payload.get("away_form", ""),
        PREMATCH_FORM_RIGHT,
        points_center=(734, 749),
    )

    draw_single_line(
        draw,
        payload.get("day", ""),
        PREMATCH_DATE_BOX,
        preferred_size=18,
        min_size=16,
        bold=False,
        fill=GREY,
        max_chars=10,
    )
    return image


def render_result(payload: dict[str, Any]) -> Image.Image:
    image = template("resultat")
    draw = ImageDraw.Draw(image)

    home = clean(payload.get("home"))
    away = clean(payload.get("away"))
    scores = payload.get("scores")
    if not home or not away or not isinstance(scores, (list, tuple)) or len(scores) != 2:
        raise ValueError("Résultat incomplet")
    home_score, away_score = int(scores[0]), int(scores[1])

    paste_logo(image, payload.get("home_logo", ""), RESULT_HOME_LOGO, 125)
    paste_logo(image, payload.get("away_logo", ""), RESULT_AWAY_LOGO, 125)

    home_size, home_min, home_chars = _team_name_size(home, "result")
    away_size, away_min, away_chars = _team_name_size(away, "result")
    draw_single_line(
        draw, home, RESULT_HOME_NAME,
        preferred_size=home_size, min_size=home_min,
        bold=True, max_chars=home_chars,
    )
    draw_single_line(
        draw, away, RESULT_AWAY_NAME,
        preferred_size=away_size, min_size=away_min,
        bold=True, max_chars=away_chars,
    )

    draw_single_line(
        draw,
        f"{home_score} - {away_score}",
        RESULT_SCORE_BOX,
        preferred_size=68,
        min_size=52,
        bold=True,
        fill=NAVY,
        max_chars=7,
    )

    winner = "MATCH NUL"
    if home_score != away_score:
        winner = "VICTOIRE • " + (home if home_score > away_score else away)
    preferred_winner = _preferred_size_by_chars(
        winner, ((32, 28), (38, 24), (45, 20)), 18
    )
    draw_single_line(
        draw,
        winner,
        RESULT_WINNER_BOX,
        preferred_size=preferred_winner,
        min_size=18,
        bold=True,
        fill=GOLD,
        max_chars=45,
    )

    draw_single_line(
        draw,
        payload.get("day", ""),
        RESULT_DATE_BOX,
        preferred_size=18,
        min_size=16,
        bold=False,
        fill=GREY,
        max_chars=10,
    )
    return image


def _prepare_stat_placeholder_zones(image: Image.Image) -> None:
    """Efface uniquement les placeholders intégrés à ce template précis."""
    # X dans la grande capsule.
    _gold_capsule(image, (365, 414, 714, 565), radius=26)

    # BUTS / TIRS / PASSES.
    _local_dark_patch(image, (385, 578, 700, 614), radius=4, fill="#0A2032")

    # Boucliers d'exemple dans les deux cercles: préserver l'anneau gold.
    draw = ImageDraw.Draw(image)
    for cx, cy in (STAT_HOME_LOGO, STAT_AWAY_LOGO):
        draw.ellipse((cx - 31, cy - 31, cx + 31, cy + 31), fill="#0A2032")

    # ÉQUIPE A / ÉQUIPE B.
    _local_dark_patch(image, (220, 669, 432, 715), radius=4, fill="#0A2032")
    _local_dark_patch(image, (650, 669, 861, 715), radius=4, fill="#0A2032")

    # 0 - 0.
    _gold_capsule(image, (467, 662, 613, 720), radius=13)

    # DATE, sans toucher à l'icône calendrier.
    _local_dark_patch(image, (520, 901, 620, 941), radius=4, fill="#071A29")


def render_stat(payload: dict[str, Any]) -> Image.Image:
    image = template("statistique")
    _prepare_stat_placeholder_zones(image)
    draw = ImageDraw.Draw(image)

    home = clean(payload.get("home"))
    away = clean(payload.get("away"))
    scores = payload.get("scores")
    if not home or not away or not isinstance(scores, (list, tuple)) or len(scores) != 2:
        raise ValueError("Statistique incomplète")

    home_score, away_score = int(scores[0]), int(scores[1])
    stat_value = clean(payload.get("stat_value")) or str(home_score + away_score)
    stat_label = clean(payload.get("stat_label")) or "BUTS"

    stat_size = _preferred_size_by_chars(
        stat_value, ((2, 92), (3, 82), (4, 72)), 68
    )
    draw_single_line(
        draw,
        stat_value,
        STAT_VALUE_BOX,
        preferred_size=stat_size,
        min_size=60,
        bold=True,
        fill=NAVY,
        max_chars=4,
    )

    stat_label_size = _preferred_size_by_chars(
        stat_label, ((18, 22), (24, 19)), 17
    )
    draw_single_line(
        draw,
        stat_label.upper(),
        STAT_LABEL_BOX,
        preferred_size=stat_label_size,
        min_size=17,
        bold=True,
        fill=GOLD,
        max_chars=24,
    )

    paste_logo(image, payload.get("home_logo", ""), STAT_HOME_LOGO, 64)
    paste_logo(image, payload.get("away_logo", ""), STAT_AWAY_LOGO, 64)

    home_size, home_min, home_chars = _team_name_size(home, "stat")
    away_size, away_min, away_chars = _team_name_size(away, "stat")
    draw_single_line(
        draw, home, STAT_HOME_NAME,
        preferred_size=home_size, min_size=home_min,
        bold=True, max_chars=home_chars,
    )
    draw_single_line(
        draw, away, STAT_AWAY_NAME,
        preferred_size=away_size, min_size=away_min,
        bold=True, max_chars=away_chars,
    )

    draw_single_line(
        draw,
        f"{home_score} - {away_score}",
        STAT_SCORE_BOX,
        preferred_size=34,
        min_size=28,
        bold=True,
        fill=NAVY,
        max_chars=7,
    )

    # FOOTBALL est statique dans le PNG; ne pas redessiner la compétition.
    draw_single_line(
        draw,
        payload.get("day", ""),
        STAT_DATE_BOX,
        preferred_size=18,
        min_size=16,
        bold=False,
        fill=GREY,
        max_chars=10,
    )
    return image


def render_flash(payload: dict[str, Any]) -> Image.Image:
    image = template("flash")
    draw = ImageDraw.Draw(image)

    photo = remote_photo(payload.get("image_url", ""), _box_size(FLASH_PHOTO_BOX))
    if photo is not None:
        paste_rounded_photo(image, photo, FLASH_PHOTO_BOX, radius=27)

    title = clean(payload.get("title"))
    title_preferred = 30 if len(title) <= 43 else 26
    draw_multiline(
        draw,
        title,
        FLASH_TITLE_BOX,
        preferred_size=title_preferred,
        min_size=22,
        max_lines=2,
        bold=True,
        fill=WHITE,
        max_chars=100,
        align="left",
        line_gap=2,
    )

    source = "SOURCE • " + clean(payload.get("source") or "FOOT MERCATO").upper()
    draw_single_line(
        draw,
        source,
        FLASH_SOURCE_BOX,
        preferred_size=17,
        min_size=14,
        bold=True,
        fill=GOLD,
        max_chars=50,
        align="left",
    )

    draw_single_line(
        draw,
        payload.get("day", ""),
        FLASH_DATE_BOX,
        preferred_size=15,
        min_size=13,
        bold=False,
        fill=GREY,
        max_chars=10,
        align="center",
    )

    summary = clean(payload.get("summary"))
    draw_multiline(
        draw,
        summary,
        FLASH_SUMMARY_BOX,
        preferred_size=17,
        min_size=14,
        max_lines=3,
        bold=False,
        fill=WHITE,
        max_chars=180,
        align="left",
        line_gap=2,
    )

    draw_single_line(
        draw,
        "LIRE L’ARTICLE COMPLET",
        FLASH_CTA_BOX,
        preferred_size=20,
        min_size=17,
        bold=True,
        fill=WHITE,
        max_chars=26,
    )
    return image


def _clean_poll_option(value: Any) -> str:
    value = clean(value)
    value = re.sub(r"^[🏠🤝✈️🗳️🔥⚽\s]+", "", value)
    return clean(value)


def _clean_poll_question(value: Any) -> str:
    value = clean(value)
    # Le template contient déjà MR XPRONOS / LE DÉBAT DU JOUR.
    value = re.sub(r"^.*?LE DÉBAT DU JOUR\s*", "", value, flags=re.I)
    value = re.sub(r"^[-•:|\s]+", "", value)
    value = value.replace("🔥", "").replace("🗳️", "")
    return clean(value)


def render_poll(payload: dict[str, Any]) -> Image.Image:
    image = template("sondage")
    draw = ImageDraw.Draw(image)

    question = clean(payload.get("image_question")) or _clean_poll_question(payload.get("question"))
    options = [
        _clean_poll_option(value)
        for value in list(payload.get("image_options") or payload.get("options") or [])[:3]
    ]

    question_preferred = 30 if len(question) <= 52 else 26
    draw_multiline(
        draw,
        question,
        POLL_QUESTION_BOX,
        preferred_size=question_preferred,
        min_size=24,
        max_lines=2,
        bold=True,
        fill=WHITE,
        max_chars=100,
        align="center",
        line_gap=3,
    )

    home_logo = clean(payload.get("home_logo"))
    away_logo = clean(payload.get("away_logo"))

    for index, box in enumerate(POLL_OPTION_BOXES):
        if index >= len(options):
            continue
        option = options[index]
        preferred = 24 if len(option) <= 32 else 20
        draw_single_line(
            draw,
            option,
            box,
            preferred_size=preferred,
            min_size=17,
            bold=True,
            fill=WHITE,
            max_chars=45,
        )

        center = POLL_ICON_CENTERS[index]
        if index == 0 and home_logo:
            paste_logo(image, home_logo, center, 52)
        elif index == 2 and away_logo:
            paste_logo(image, away_logo, center, 52)
        elif index == 1 and option.casefold() == "match nul":
            draw.text(center, "=", font=_font(26, True), fill=GOLD, anchor="mm")
        else:
            draw.text(center, str(index + 1), font=_font(22, True), fill=WHITE, anchor="mm")

    draw_single_line(
        draw,
        payload.get("day", ""),
        POLL_DATE_BOX,
        preferred_size=18,
        min_size=16,
        bold=False,
        fill=GREY,
        max_chars=10,
    )
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
    image = renderer(payload)
    if image.size != (W, H):
        raise AssertionError("Le renderer doit toujours produire 1080x1080")
    return image
