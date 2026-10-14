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
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

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
    "composition": "template_compositions_officielles.webp",
}

TEMPLATE_SIZES = {
    # Les 3 cartes éditoriales historiques restent en 1080x1080.
    # Le nouveau template Compositions officielles conserve son format natif.
    "composition": (1374, 1145),
    **{name: (1080, 1350) for name in ("kickoff", "goal", "mi_temps", "score_update", "statistique_avancee", "community_vote", "quiz", "debat", "reaction", "suivi_interrompu")},
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
PROGRAMME_LOGO_Y_OFFSET = 7
PROGRAMME_TIME_Y_OFFSET = -6

PREMATCH_HOME_LOGO = (237, 431)
PREMATCH_AWAY_LOGO = (842, 431)
PREMATCH_HOME_NAME = (112, 521, 362, 564)
PREMATCH_AWAY_NAME = (719, 521, 969, 564)
PREMATCH_TIME_BOX = (455, 405, 625, 462)
PREMATCH_DATE_BOX = (465, 837, 686, 886)
PREMATCH_FORM_LEFT = ((227, 699), (282, 699), (336, 699), (391, 699), (445, 699))
PREMATCH_FORM_RIGHT = ((624, 699), (679, 699), (734, 699), (789, 699), (843, 699))

RESULT_HOME_LOGO = (216, 487)
RESULT_AWAY_LOGO = (862, 487)
RESULT_HOME_NAME = (99, 594, 336, 642)
RESULT_AWAY_NAME = (745, 594, 982, 642)
RESULT_SCORE_BOX = (394, 437, 687, 576)
RESULT_WINNER_BOX = (310, 663, 771, 711)
RESULT_SOURCE_BOX = (350, 716, 730, 760)
RESULT_SOURCE_ERASE = (350, 716, 730, 760)
RESULT_DATE_BOX = (486, 828, 652, 878)

STAT_VALUE_BOX = (356, 405, 723, 574)
STAT_LABEL_BOX = (370, 577, 711, 613)
STAT_HOME_LOGO = (164, 691)
STAT_AWAY_LOGO = (915, 691)
STAT_HOME_NAME = (215, 667, 431, 715)
STAT_AWAY_NAME = (655, 667, 870, 715)
STAT_SCORE_BOX = (463, 658, 617, 724)
STAT_DATE_BOX = (486, 892, 648, 942)

FLASH_PHOTO_BOX = (79, 234, 1001, 606)  # 922 x 372
FLASH_TITLE_BOX = (125, 644, 792, 699)
FLASH_SOURCE_BOX = (125, 704, 603, 736)
FLASH_DATE_BOX = (884, 704, 992, 738)
FLASH_SUMMARY_BOX = (267, 797, 956, 868)
FLASH_CTA_BOX = (336, 932, 810, 980)

POLL_QUESTION_BOX = (129, 349, 952, 435)
POLL_OPTION_BOXES = (
    (293, 508, 861, 560),
    (293, 634, 861, 686),
    (293, 760, 861, 812),
)
POLL_ICON_CENTERS = ((155, 534), (155, 660), (155, 786))
POLL_DATE_BOX = (470, 864, 670, 912)

# Nouveau template Compositions officielles natif 1374 x 1145.
# Les coordonnées ci-dessous ont été remesurées sur le fond 11 lignes.
COMPOSITION_HOME_LOGO = (343, 381)
COMPOSITION_AWAY_LOGO = (1029, 381)
COMPOSITION_HOME_NAME = (92, 454, 594, 511)
COMPOSITION_AWAY_NAME = (766, 454, 1274, 511)
COMPOSITION_COMPETITION_BOX = (516, 224, 741, 274)
COMPOSITION_TIME_BOX = (786, 224, 910, 274)
COMPOSITION_SOURCE_BOX = (78, 1073, 214, 1112)

# Les numéros 1..11 et les cadres sont déjà imprimés dans le template.
# Le renderer écrit uniquement les noms des joueurs dans ces zones.
COMPOSITION_HOME_PLAYER_X = (158, 586)
COMPOSITION_AWAY_PLAYER_X = (860, 1288)
COMPOSITION_ROWS = tuple(
    (532 + index * 46, 577 + index * 46)
    for index in range(11)
)

# Zones contenant uniquement les placeholders texte du fond source.
# Elles sont effacées par reconstruction du fond (pas par rectangles).
COMPOSITION_ERASE_HOME_NAME = (174, 458, 514, 507)
COMPOSITION_ERASE_AWAY_NAME = (860, 458, 1206, 507)
COMPOSITION_ERASE_COMPETITION = (510, 226, 741, 273)
COMPOSITION_ERASE_TIME = (782, 226, 914, 273)
COMPOSITION_ERASE_SOURCE = (76, 1072, 220, 1113)


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
    target_size = TEMPLATE_SIZES.get(category, (W, H))
    if image.size != target_size:
        image = ImageOps.fit(image, target_size, method=Image.Resampling.LANCZOS)
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
    """Télécharge la photo brute.

    Le cadrage est volontairement fait ensuite par _safe_article_frame afin
    d'éviter de couper automatiquement les visages/sujets lorsque le ratio de
    la photo source est très différent du cadre Flash Foot.
    """
    if not clean(url).startswith(("https://", "http://")):
        return None
    try:
        response = requests.get(
            clean(url),
            timeout=(6, 18),
            headers={"User-Agent": "Mozilla/5.0 MrXPRONOS-template/3.0"},
        )
        response.raise_for_status()
        if len(response.content) > 7_000_000:
            return None
        return Image.open(io.BytesIO(response.content)).convert("RGB")
    except Exception:
        return None


def _safe_article_frame(photo: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Construit une photo de news sans crop agressif.

    - ratios proches du cadre: crop léger, avec priorité au haut de l'image;
    - ratios 16:9 / portrait: fond flouté plein cadre + sujet principal presque
      entier au centre. Cela évite de couper les têtes comme sur les premières
      cartes Telegram.
    """
    width, height = size
    source = photo.convert("RGB")
    sw, sh = source.size
    if sw <= 0 or sh <= 0:
        return Image.new("RGB", size, (7, 24, 38))

    target_ratio = width / height
    source_ratio = sw / sh
    ratio_gap = abs(source_ratio - target_ratio) / target_ratio

    # Une source déjà très panoramique peut remplir le cadre sans perte forte.
    if ratio_gap <= 0.14:
        return ImageOps.fit(
            source,
            size,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.34),
        )

    # Fond de remplissage: même photo, cropée et floutée.
    background = ImageOps.fit(
        source,
        size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.36),
    )
    background = background.filter(ImageFilter.GaussianBlur(radius=18))
    background = ImageEnhance.Brightness(background).enhance(0.72)

    # Premier plan: conserver environ 90-94% de la hauteur de la source
    # visible dans la fenêtre. Pour une image 16:9 cela crée seulement de
    # petites bandes latérales floutées mais évite de couper les visages.
    if source_ratio < target_ratio:
        desired_h = int(height * 1.10)
        desired_w = max(1, int(desired_h * source_ratio))
        foreground = source.resize((desired_w, desired_h), Image.Resampling.LANCZOS)

        crop_h = max(0, desired_h - height)
        # Favoriser le haut: seulement ~20% du crop retiré en haut.
        top = min(crop_h, int(crop_h * 0.20))
        foreground = foreground.crop((0, top, desired_w, top + height))

        x = (width - foreground.width) // 2
        background.paste(foreground, (x, 0))
        return background

    # Source plus large que le cadre: crop horizontal classique.
    return ImageOps.fit(
        source,
        size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.36),
    )


def paste_rounded_photo(
    image: Image.Image,
    photo: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
) -> None:
    width, height = _box_size(box)
    framed = _safe_article_frame(photo, (width, height))
    mask = Image.new("L", (width, height), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=255)
    image.paste(framed, (box[0], box[1]), mask)


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


def _blend_erase_text(
    image: Image.Image,
    box: tuple[int, int, int, int],
    *,
    sample_px: int = 10,
    feather: int = 6,
) -> None:
    """Efface un texte imprimé en reconstruisant le fond depuis les bords.

    Évite les rectangles plats visibles sur le template Stat.
    """
    x1, y1, x2, y2 = box
    width, height = x2 - x1, y2 - y1
    if width <= 0 or height <= 0:
        return

    src = image.convert("RGB")
    patch = Image.new("RGB", (width, height))
    pd = ImageDraw.Draw(patch)

    image_w, image_h = src.size
    for row in range(height):
        yy = min(max(y1 + row, 0), image_h - 1)
        left_x1 = max(0, x1 - sample_px)
        left_x2 = max(left_x1 + 1, x1 - 2)
        right_x1 = min(image_w - 1, x2 + 2)
        right_x2 = min(image_w, x2 + sample_px)
        if right_x2 <= right_x1:
            right_x1, right_x2 = min(image_w - 2, x2), min(image_w, x2 + 2)

        left_crop = src.crop((left_x1, yy, left_x2, yy + 1))
        right_crop = src.crop((right_x1, yy, right_x2, yy + 1))

        def avg_color(crop: Image.Image) -> tuple[int, int, int]:
            pixels = list(crop.getdata())
            if not pixels:
                return (10, 32, 50)
            return tuple(sum(px[i] for px in pixels) // len(pixels) for i in range(3))

        lc = avg_color(left_crop)
        rc = avg_color(right_crop)
        for col in range(width):
            t = col / max(1, width - 1)
            color = tuple(int(lc[i] * (1 - t) + rc[i] * t) for i in range(3))
            pd.point((col, row), fill=color)

    mask = Image.new("L", (width, height), 255)
    md = ImageDraw.Draw(mask)
    for i in range(min(feather, width // 2, height // 2)):
        alpha = int(255 * (i + 1) / max(1, feather))
        md.rectangle((i, i, width - 1 - i, height - 1 - i), outline=alpha)

    image.paste(patch, (x1, y1), mask)


def _clear_logo_placeholder(
    image: Image.Image,
    center: tuple[int, int],
    radius: int,
    *,
    fill: str = "#0A2032",
) -> None:
    """Efface seulement le faux blason imprimé, sans toucher à l'anneau du template."""
    draw = ImageDraw.Draw(image)
    cx, cy = center
    draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=fill)


def _prepare_programme_placeholders(image: Image.Image) -> None:
    # Date placeholder.
    _local_dark_patch(image, (500, 255, 660, 296), radius=8, fill="#071A29")
    for meta in PROGRAMME_ROWS:
        y = meta["y"]
        _clear_logo_placeholder(image, (PROGRAMME_HOME_LOGO_X, y), 29)
        _clear_logo_placeholder(image, (PROGRAMME_AWAY_LOGO_X, y), 29)
        _local_dark_patch(image, meta["home_box"], radius=5, fill="#0A2032")
        _local_dark_patch(image, meta["away_box"], radius=5, fill="#0A2032")
        _gold_capsule(image, (486, y-21, 594, y+17), radius=10)


def _prepare_prematch_placeholders(image: Image.Image) -> None:
    _clear_logo_placeholder(image, PREMATCH_HOME_LOGO, 58)
    _clear_logo_placeholder(image, PREMATCH_AWAY_LOGO, 58)
    _local_dark_patch(image, PREMATCH_HOME_NAME, radius=5, fill="#0A2032")
    _local_dark_patch(image, PREMATCH_AWAY_NAME, radius=5, fill="#0A2032")
    _gold_capsule(image, (465, 407, 615, 460), radius=14)
    # Les 10 cercles de forme sont réutilisés; effacer seulement les lettres d'exemple.
    for center in PREMATCH_FORM_LEFT + PREMATCH_FORM_RIGHT:
        _clear_logo_placeholder(image, center, 18, fill="#071A29")
    _local_dark_patch(image, (500, 843, 672, 880), radius=4, fill="#071A29")


def _prepare_result_placeholders(image: Image.Image) -> None:
    _clear_logo_placeholder(image, RESULT_HOME_LOGO, 72)
    _clear_logo_placeholder(image, RESULT_AWAY_LOGO, 72)
    _local_dark_patch(image, RESULT_HOME_NAME, radius=5, fill="#0A2032")
    _local_dark_patch(image, RESULT_AWAY_NAME, radius=5, fill="#0A2032")
    _gold_capsule(image, (407, 442, 674, 570), radius=24)
    _local_dark_patch(image, RESULT_WINNER_BOX, radius=5, fill="#0A2032")
    _local_dark_patch(image, (525, 837, 648, 871), radius=4, fill="#071A29")


def _prepare_flash_placeholders(image: Image.Image) -> None:
    # La photo recouvre le placeholder image entier.
    _local_dark_patch(image, FLASH_TITLE_BOX, radius=3, fill="#0A2032")
    _local_dark_patch(image, FLASH_SOURCE_BOX, radius=3, fill="#0A2032")
    _local_dark_patch(image, FLASH_DATE_BOX, radius=3, fill="#0A2032")
    _local_dark_patch(image, FLASH_SUMMARY_BOX, radius=5, fill="#0A2032")
    _local_dark_patch(image, FLASH_CTA_BOX, radius=4, fill="#081A29")


def _prepare_poll_placeholders(image: Image.Image) -> None:
    _local_dark_patch(image, POLL_QUESTION_BOX, radius=5, fill="#0A2032")
    for center, box in zip(POLL_ICON_CENTERS, POLL_OPTION_BOXES):
        _clear_logo_placeholder(image, center, 27)
        _local_dark_patch(image, box, radius=5, fill="#0A2032")
    _local_dark_patch(image, (515, 873, 660, 904), radius=4, fill="#071A29")


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
    # Les cercles de forme sont natifs au template Avant-match.
    # Aucune forme ni fond n'est redessiné: seule la donnée V/N/D est posée.
    for index, center in enumerate(centers):
        verdict = verdicts[index] if index < len(verdicts) else ""
        if not verdict:
            continue
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

        paste_logo(
            image, home_logo,
            (PROGRAMME_HOME_LOGO_X, meta["y"] + PROGRAMME_LOGO_Y_OFFSET),
            60,
        )
        paste_logo(
            image, away_logo,
            (PROGRAMME_AWAY_LOGO_X, meta["y"] + PROGRAMME_LOGO_Y_OFFSET),
            60,
        )

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
            (
                484,
                meta["y"] - 22 + PROGRAMME_TIME_Y_OFFSET,
                596,
                meta["y"] + 18 + PROGRAMME_TIME_Y_OFFSET,
            ),
            preferred_size=23,
            min_size=20,
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
        preferred_size=21,
        min_size=18,
        bold=True,
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

    # La source est une donnée dynamique: on efface seulement le texte imprimé,
    # sans ajouter de rectangle, puis on écrit la vraie source.
    _blend_erase_text(image, RESULT_SOURCE_ERASE, sample_px=12, feather=7)
    source = clean(payload.get("source") or "BSD V2")
    draw_single_line(
        draw,
        "SCORE CONFIRMÉ PAR " + source.upper(),
        RESULT_SOURCE_BOX,
        preferred_size=18,
        min_size=14,
        bold=False,
        fill=WHITE,
        max_chars=42,
    )

    draw_single_line(
        draw,
        payload.get("day", ""),
        RESULT_DATE_BOX,
        preferred_size=21,
        min_size=18,
        bold=True,
        fill=GREY,
        max_chars=10,
    )
    return image


def _prepare_stat_placeholder_zones(image: Image.Image) -> None:
    """Efface uniquement les placeholders intégrés à ce template précis."""
    # X dans la grande capsule.
    _gold_capsule(image, (365, 414, 714, 565), radius=26)

    # BUTS / TIRS / PASSES : effacement fondu, sans rectangle visible.
    _blend_erase_text(image, (385, 578, 700, 614), sample_px=12, feather=7)

    # Boucliers d'exemple dans les deux cercles: préserver l'anneau gold.
    draw = ImageDraw.Draw(image)
    for cx, cy in (STAT_HOME_LOGO, STAT_AWAY_LOGO):
        draw.ellipse((cx - 31, cy - 31, cx + 31, cy + 31), fill="#0A2032")

    # ÉQUIPE A / ÉQUIPE B : masquer uniquement les mots imprimés.
    _blend_erase_text(image, (255, 676, 410, 706), sample_px=10, feather=6)
    _blend_erase_text(image, (675, 676, 830, 706), sample_px=10, feather=6)

    # 0 - 0.
    _gold_capsule(image, (467, 662, 613, 720), radius=13)

    # DATE : effacer tout le placeholder sans toucher au calendrier.
    _blend_erase_text(image, (530, 900, 625, 936), sample_px=12, feather=6)


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
        preferred_size=20,
        min_size=18,
        bold=True,
        fill=GREY,
        max_chars=10,
    )
    return image


def _flash_topic(title: str) -> str:
    """Classe un sujet en catégories graphiques sans inventer de faits."""
    value=clean(title).casefold()
    categories=(
        ("MERCATO", ("transfert", "mercato", "recrut", "signature", "prêt ", "officialis")),
        ("COMPÉTITION", ("ligue des champions", "coupe", "finale", "trophée", "titre de champion")),
        ("MATCH", ("match", "but ", "score", "victoire", "défaite", "penalty")),
        ("DISCIPLINE", ("carton", "suspension", "sanction", "blessure", "absence")),
    )
    for category, keywords in categories:
        if any(word in value for word in keywords):
            return category
    return "ACTUALITÉ"


def _flash_editorial_illustration(dimensions: tuple[int, int], title: str = "") -> Image.Image:
    """Scène premium originale, adaptée au thème ; sans photo sous droits."""
    w,h=dimensions
    category=_flash_topic(title)
    themes={
        "MERCATO":((25,66,91),(28,160,168)),
        "COMPÉTITION":((43,57,90),(245,188,72)),
        "MATCH":((10,66,70),(83,187,137)),
        "DISCIPLINE":((74,48,66),(219,112,113)),
        "ACTUALITÉ":((10,46,78),(75,147,205)),
    }
    bg,accent=themes[category]
    art=Image.new("RGB",(w,h),bg)
    d=ImageDraw.Draw(art)
    for y in range(h):
        t=y/max(1,h-1)
        tone=tuple(int(bg[i]*(1-.47*t)) for i in range(3))
        d.line((0,y,w,y),fill=tone)
    # Perspective du terrain synthétique : fond texturé, pas de photo.
    pad=max(20,int(w*.06))
    d.rounded_rectangle((pad,pad,w-pad,h-pad),radius=30,outline=(51,95,112),width=3)
    d.line((w//2,pad,w//2,h-pad),fill=(45,86,102),width=3)
    rad=int(min(w,h)*.34)
    d.ellipse((w//2-rad,h//2-rad,w//2+rad,h//2+rad),outline=(59,104,119),width=3)
    for i in range(5):
        x=int(.12*w)+i*int(w*.18)
        d.line((x,pad+8,x+int(h*.28),h-pad-8),fill=(29,73,93),width=2)
    # Ornements contextuels dans un bloc facilement identifiable.
    cx,cy=int(w*.51),int(h*.51)
    icon_size=int(min(w,h)*.28)
    if category=="MERCATO":
        # Silhouette de maillot + flèches de mouvement.
        pts=[(cx-icon_size*.52,cy-icon_size*.35),(cx-icon_size*.82,cy-icon_size*.10),
             (cx-icon_size*.54,cy+icon_size*.20),(cx-icon_size*.38,cy+icon_size*.05),
             (cx-icon_size*.38,cy+icon_size*.74),(cx+icon_size*.38,cy+icon_size*.74),
             (cx+icon_size*.38,cy+icon_size*.05),(cx+icon_size*.54,cy+icon_size*.20),
             (cx+icon_size*.82,cy-icon_size*.10),(cx+icon_size*.52,cy-icon_size*.35)]
        d.polygon(pts,fill=(230,239,240),outline=accent,width=5)
        d.arc((cx-icon_size*.26,cy-icon_size*.47,cx+icon_size*.26,cy-icon_size*.05),0,180,fill=accent,width=7)
        yarrow=cy-icon_size*.78
        d.line((cx-icon_size*.57,yarrow,cx+icon_size*.45,yarrow),fill=accent,width=8)
        d.polygon([(cx+icon_size*.45,yarrow-icon_size*.13),(cx+icon_size*.68,yarrow),(cx+icon_size*.45,yarrow+icon_size*.13)],fill=accent)
    elif category=="COMPÉTITION":
        # Coupe/trophée stylisé sans emblème d'une compétition réelle.
        d.polygon([(cx-icon_size*.47,cy-icon_size*.44),(cx+icon_size*.47,cy-icon_size*.44),
                   (cx+icon_size*.29,cy+icon_size*.19),(cx,cy+icon_size*.39),
                   (cx-icon_size*.29,cy+icon_size*.19)],fill=(233,190,82))
        d.arc((cx-icon_size*.89,cy-icon_size*.52,cx-icon_size*.26,cy+icon_size*.26),80,280,fill=accent,width=10)
        d.arc((cx+icon_size*.26,cy-icon_size*.52,cx+icon_size*.89,cy+icon_size*.26),-100,100,fill=accent,width=10)
        d.rectangle((cx-icon_size*.12,cy+icon_size*.39,cx+icon_size*.12,cy+icon_size*.71),fill=accent)
        d.rounded_rectangle((cx-icon_size*.48,cy+icon_size*.70,cx+icon_size*.48,cy+icon_size*.82),radius=12,fill=(239,211,133))
    elif category=="DISCIPLINE":
        # Carte d'arbitre et sifflet géométrique.
        d.rounded_rectangle((cx-icon_size*.55,cy-icon_size*.70,cx+icon_size*.35,cy+icon_size*.68),
                            radius=22,fill=(230,209,97),outline=accent,width=7)
        d.line((cx-icon_size*.20,cy-icon_size*.30,cx+icon_size*.02,cy-icon_size*.30),fill=(68,42,42),width=9)
        d.ellipse((cx+icon_size*.33,cy+icon_size*.28,cx+icon_size*.82,cy+icon_size*.66),fill=(230,233,235),outline=accent,width=6)
    else:
        # Ballon original et anneaux de mouvement.
        radius_ball=int(icon_size*.54)
        d.ellipse((cx-radius_ball,cy-radius_ball,cx+radius_ball,cy+radius_ball),fill=(237,243,242))
        d.polygon([(cx-radius_ball*.23,cy-radius_ball*.36),(cx+radius_ball*.29,cy-radius_ball*.36),
                   (cx+radius_ball*.56,cy+radius_ball*.12),(cx,cy+radius_ball*.70),
                   (cx-radius_ball*.57,cy+radius_ball*.12)],fill=(16,40,56))
        for dx,dy in ((-.69,-.67),(.66,-.65),(-.79,.58),(.76,.62)):
            px=cx+int(dx*radius_ball);py=cy+int(dy*radius_ball)
            d.ellipse((px-15,py-15,px+15,py+15),fill=(14,37,50))
    # Cartouche robuste, utilisable même sans police Lato.
    label_x,label_y=int(w*.055),int(h*.80)
    width=int(w*.44)
    d.rounded_rectangle((label_x,label_y,label_x+width,label_y+max(55,int(h*.115))),
                        radius=16,fill=(7,23,36),outline=accent,width=3)
    d.text((label_x+18,label_y+max(13,int(h*.023))),category,
           font=_font(max(21,int(w*.026)),True),fill=(247,249,252))
    return art


def _draw_lineup_players(
    image: Image.Image,
    players: list[str],
    player_x: tuple[int, int],
) -> None:
    """Écrit uniquement les 11 noms dans les lignes natives du template."""
    draw = ImageDraw.Draw(image)
    x1, x2 = player_x
    for index, (top, bottom) in enumerate(COMPOSITION_ROWS):
        player = clean(players[index]) if index < len(players) else ""
        if not player:
            continue
        preferred = _preferred_size_by_chars(
            player,
            ((18, 22), (24, 20), (31, 18), (38, 16)),
            15,
        )
        draw_single_line(
            draw,
            player,
            (x1, top + 2, x2, bottom - 2),
            preferred_size=preferred,
            min_size=14,
            bold=True,
            fill=WHITE,
            max_chars=46,
            align="left",
        )


def render_composition(payload: dict[str, Any]) -> Image.Image:
    image = template("composition")
    draw = ImageDraw.Draw(image)

    home = clean(payload.get("home"))
    away = clean(payload.get("away"))
    home_players = [clean(x) for x in (payload.get("home_players") or []) if clean(x)][:11]
    away_players = [clean(x) for x in (payload.get("away_players") or []) if clean(x)][:11]
    home_logo = clean(payload.get("home_logo"))
    away_logo = clean(payload.get("away_logo"))

    if not home or not away:
        raise ValueError("Composition sans équipes")
    if len(home_players) != 11 or len(away_players) != 11:
        raise ValueError("Composition officielle incomplète: 11 titulaires requis par équipe")
    if not home_logo or not away_logo:
        raise ValueError("Composition officielle sans les deux logos")

    # Le nouveau fond contient déjà les 11 lignes, les colonnes de numéros,
    # les cercles logos, le VS et tous les cadres. On ne redessine rien.
    # Seuls les textes placeholders sont effacés par interpolation locale.
    for box in (
        COMPOSITION_ERASE_HOME_NAME,
        COMPOSITION_ERASE_AWAY_NAME,
        COMPOSITION_ERASE_COMPETITION,
        COMPOSITION_ERASE_TIME,
        COMPOSITION_ERASE_SOURCE,
    ):
        _blend_erase_text(image, box, sample_px=12, feather=7)

    home_size = _preferred_size_by_chars(home, ((18, 31), (24, 28), (31, 24), (40, 20)), 18)
    away_size = _preferred_size_by_chars(away, ((18, 31), (24, 28), (31, 24), (40, 20)), 18)
    draw_single_line(
        draw, home, COMPOSITION_HOME_NAME,
        preferred_size=home_size, min_size=18,
        bold=True, fill=WHITE, max_chars=48,
    )
    draw_single_line(
        draw, away, COMPOSITION_AWAY_NAME,
        preferred_size=away_size, min_size=18,
        bold=True, fill=WHITE, max_chars=48,
    )

    competition = clean(payload.get("competition") or payload.get("league") or "Football")
    draw_single_line(
        draw,
        competition.upper(),
        COMPOSITION_COMPETITION_BOX,
        preferred_size=25,
        min_size=15,
        bold=True,
        fill=WHITE,
        max_chars=38,
    )

    kickoff = clean(payload.get("time")).replace("h", "H")
    if kickoff:
        draw_single_line(
            draw,
            kickoff,
            COMPOSITION_TIME_BOX,
            preferred_size=29,
            min_size=21,
            bold=True,
            fill=GOLD,
            max_chars=8,
        )

    paste_logo(image, home_logo, COMPOSITION_HOME_LOGO, 160)
    paste_logo(image, away_logo, COMPOSITION_AWAY_LOGO, 160)

    _draw_lineup_players(image, home_players, COMPOSITION_HOME_PLAYER_X)
    _draw_lineup_players(image, away_players, COMPOSITION_AWAY_PLAYER_X)

    source = clean(payload.get("source") or "ESPN")
    draw_single_line(
        draw,
        "Source : " + source,
        COMPOSITION_SOURCE_BOX,
        preferred_size=15,
        min_size=12,
        bold=False,
        fill=WHITE,
        max_chars=30,
        align="left",
    )
    return image

def render_flash(payload: dict[str, Any]) -> Image.Image:
    image = template("flash")
    draw = ImageDraw.Draw(image)

    # Prefer the already-licensed, locally downloaded article image;
    # no extra network fetch and never leave the repository boundary.
    photo = None
    relative_path = clean(payload.get("image_path", ""))
    if relative_path.startswith("assets/images/footnews/"):
        candidate = (ROOT / relative_path).resolve()
        if candidate.is_relative_to(ROOT.resolve()) and candidate.is_file():
            with Image.open(candidate) as source:
                photo = ImageOps.exif_transpose(source).convert("RGB")
    if photo is None:
        photo = remote_photo(payload.get("image_url", ""), _box_size(FLASH_PHOTO_BOX))
    if photo is None:
        photo = _flash_editorial_illustration(_box_size(FLASH_PHOTO_BOX),clean(payload.get("title")))
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
        preferred_size=17,
        min_size=15,
        bold=True,
        fill=WHITE,
        max_chars=10,
        align="left",
    )

    summary = clean(payload.get("summary"))
    draw_multiline(
        draw,
        summary,
        FLASH_SUMMARY_BOX,
        preferred_size=19,
        min_size=16,
        max_lines=3,
        bold=True,
        fill=WHITE,
        max_chars=170,
        align="left",
        line_gap=3,
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

    question_preferred = 36 if len(question) <= 52 else 31
    draw_multiline(
        draw,
        question,
        POLL_QUESTION_BOX,
        preferred_size=question_preferred,
        min_size=27,
        max_lines=2,
        bold=True,
        fill=WHITE,
        max_chars=100,
        align="center",
        line_gap=4,
    )

    home_logo = clean(payload.get("home_logo"))
    away_logo = clean(payload.get("away_logo"))

    for index, box in enumerate(POLL_OPTION_BOXES):
        if index >= len(options):
            continue
        option = options[index]
        preferred = 31 if len(option) <= 24 else (27 if len(option) <= 32 else 23)
        draw_single_line(
            draw,
            option,
            box,
            preferred_size=preferred,
            min_size=20,
            bold=True,
            fill=WHITE,
            max_chars=45,
        )

        center = POLL_ICON_CENTERS[index]
        if index == 0 and home_logo:
            paste_logo(image, home_logo, center, 56)
        elif index == 2 and away_logo:
            paste_logo(image, away_logo, center, 56)
        elif index == 1 and option.casefold() == "match nul":
            draw.text(center, "=", font=_font(26, True), fill=GOLD, anchor="mm")
        else:
            draw.text(center, str(index + 1), font=_font(22, True), fill=WHITE, anchor="mm")

    draw_single_line(
        draw,
        payload.get("day", ""),
        POLL_DATE_BOX,
        preferred_size=20,
        min_size=18,
        bold=True,
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
    "composition": render_composition,
}


def render(category: str, payload: dict[str, Any]) -> Image.Image:
    # Ces 4 publications utilisent toujours leurs templates premium dédiés.
    # Elles ne doivent jamais être détournées vers les anciens fonds Arty.
    if category in {"programme", "avant_match", "resultat", "composition"}:
        renderer = RENDERERS[category]
        image = renderer(payload)
        expected_size = TEMPLATE_SIZES.get(category, (W, H))
        if image.size != expected_size:
            raise AssertionError(
                f"Le renderer {category} doit produire {expected_size}, reçu {image.size}"
            )
        return image

    # 1122x1402 Actu Foot event backgrounds are audited separately.
    from actu_foot_event_templates import is_event_category, render_event
    if is_event_category(category):
        image = render_event(category, payload)
        if image.size != (1122, 1402):
            raise AssertionError("Actu Foot event graphic must be 1122x1402")
        return image

    # Autres catégories Arty.
    from arty_football_templates import SUPPORTED as ARTY_CATEGORIES, overlay
    if category in ARTY_CATEGORIES:
        image = overlay(category, payload)
        if image.size != (1080, 1350):
            raise AssertionError("Arty Football graphic must be 1080x1350")
        return image

    renderer = RENDERERS.get(category)
    if renderer is None:
        raise ValueError("Rubrique sans template: " + category)
    image = renderer(payload)
    expected_size = TEMPLATE_SIZES.get(category, (W, H))
    if image.size != expected_size:
        raise AssertionError(
            f"Le renderer {category} doit produire {expected_size}, reçu {image.size}"
        )
    return image
