"""MR XPRONOS generic horizontal banners.

Three native 2006x784 source templates:
- match: two team logos + two team names + event label;
- club: one club logo + club name + event label + optional meta;
- general: large headline + smaller category/meta label.

The measured safe zones below intentionally stay inside the dark native panels.
No rectangles, masks or extra backgrounds are drawn over the templates.
"""
from __future__ import annotations

import base64
import io
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "images" / "generic_football_banners"
W, H = 1024, 400

WHITE = (247, 249, 252)
GOLD = (245, 199, 91)
MUTED = (198, 205, 216)

FONT_BOLD = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)
FONT_REG = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
)

TEMPLATE_DIRS = {
    "match": ASSETS / "match.b64",
    "club": ASSETS / "club.b64",
    "general": ASSETS / "general.b64",
}

# Exact data surfaces were measured on the 2006x784 source art, then
# projected to the 1024x400 Telegram source assets. The red audit boxes were:
# match  : logo 96,241,331,472 | name 355,290,749,420 | event 798,290,1196,422 |
#          name 1226,290,1641,420 | logo 1663,241,1899,472
# club   : logo 83,276,343,475 | club 370,295,912,435 |
#          event 963,294,1565,436 | meta 1606,294,1908,435
# general: headline 170,267,1836,433 | meta 656,456,1353,539
# LAYOUT below is the projected 1024x400 safe geometry.
LAYOUT = {
    "match": {
        "home_logo": {"surface": (49, 123, 169, 241), "safe": (53, 127, 165, 237), "center": (109, 182), "max_px": 104},
        "home_name": {"surface": (181, 148, 382, 214), "safe": (188, 154, 375, 208)},
        "event": {"surface": (407, 148, 611, 215), "safe": (414, 154, 604, 209)},
        "away_name": {"surface": (626, 148, 838, 214), "safe": (633, 154, 831, 208)},
        "away_logo": {"surface": (849, 123, 969, 241), "safe": (853, 127, 965, 237), "center": (909, 182), "max_px": 104},
    },
    "club": {
        "logo": {"surface": (42, 141, 175, 242), "safe": (48, 147, 169, 236), "center": (108, 191), "max_px": 84},
        "club": {"surface": (189, 151, 466, 222), "safe": (198, 158, 457, 215)},
        "event": {"surface": (492, 150, 799, 222), "safe": (501, 157, 790, 215)},
        "meta": {"surface": (820, 150, 974, 222), "safe": (828, 157, 966, 215)},
    },
    "general": {
        "headline": {"surface": (87, 136, 937, 221), "safe": (98, 146, 926, 211)},
        "meta": {"surface": (335, 233, 691, 275), "safe": (346, 240, 680, 268)},
    },
}

MATCH_LABELS = {
    "kickoff": "COUP D’ENVOI",
    "goal": "BUT !",
    "but": "BUT !",
    "but_full": "BUT !",
    "but_scorer_only": "BUT !",
    "mi_temps": "MI-TEMPS",
    "score_update": "SCORE LIVE",
    "score_live_confirmé": "SCORE LIVE",
    "score_live_confirme": "SCORE LIVE",
    "score_live_two_logos": "SCORE LIVE",
    "score_live_one_logo": "SCORE LIVE",
    "score_live_no_logos": "SCORE LIVE",
    "score_live_no_minute": "SCORE LIVE",
    "poteau": "POTEAU !",
    "occasion_manquee": "OCCASION MANQUÉE",
    "arret_decisif": "ARRÊT DÉCISIF",
    "carton_jaune": "CARTON JAUNE",
    "carton_jaune_full": "CARTON JAUNE",
    "carton_jaune_unknown": "CARTON JAUNE",
    "carton_rouge": "CARTON ROUGE",
    "carton_rouge_full": "CARTON ROUGE",
    "carton_rouge_unknown": "CARTON ROUGE",
    "remplacement": "REMPLACEMENT",
    "remplacement_full": "REMPLACEMENT",
    "remplacement_entrant": "REMPLACEMENT",
    "remplacement_sortant": "REMPLACEMENT",
    "intervention_medicale": "INTERVENTION MÉDICALE",
    "blessure_confirmee": "BLESSURE",
    "retour_au_jeu": "RETOUR AU JEU",
    "match_suspendu": "MATCH SUSPENDU",
    "match_interrompu": "MATCH INTERROMPU",
    "match_interrompu_full": "MATCH INTERROMPU",
    "match_interrompu_unknown": "MATCH INTERROMPU",
    "suivi_interrompu": "MATCH INTERROMPU",
    "match_reporté": "MATCH REPORTÉ",
    "match_reporte": "MATCH REPORTÉ",
    "match_annulé": "MATCH ANNULÉ",
    "match_annule": "MATCH ANNULÉ",
    "reprise_du_match": "REPRISE DU MATCH",
    "reprise_match": "REPRISE DU MATCH",
    "temps_additionnel": "TEMPS ADDITIONNEL",
    "fin_de_la_1re_mi_temps": "FIN 1RE MI-TEMPS",
    "fin_1re_mi_temps": "FIN 1RE MI-TEMPS",
    "début_de_la_2e_mi_temps": "2E MI-TEMPS",
    "debut_2e_mi_temps": "2E MI-TEMPS",
    "fin_du_temps_réglementaire": "90 MINUTES",
    "fin_temps_reglementaire": "90 MINUTES",
    "prolongation": "PROLONGATIONS",
    "mi_temps_de_la_prolongation": "MI-TEMPS PROLONGATION",
    "mi_temps_prolongation": "MI-TEMPS PROLONGATION",
    "tirs_au_but": "TIRS AU BUT",
    "tir_au_but_marqué": "TIR AU BUT MARQUÉ",
    "tir_au_but_marque": "TIR AU BUT MARQUÉ",
    "tir_au_but_manqué": "TIR AU BUT MANQUÉ",
    "tir_au_but_manque": "TIR AU BUT MANQUÉ",
    "fin_des_tirs_au_but": "FIN TIRS AU BUT",
    "fin_tirs_au_but": "FIN TIRS AU BUT",
    "reaction": "VOTRE RÉACTION ?",
    "community_vote": "À VOUS DE VOTER",
}

CLUB_LABELS = {
    "composition_probable": "COMPOSITION PROBABLE",
    "composition_probable_full": "COMPOSITION PROBABLE",
    "composition_probable_partial": "COMPOSITION PROBABLE",
    "changement_de_composition": "CHANGEMENT DE XI",
    "changement_composition": "CHANGEMENT DE XI",
    "absence_confirmée": "ABSENCE CONFIRMÉE",
    "absence_confirmee": "ABSENCE CONFIRMÉE",
    "retour_dans_le_groupe": "RETOUR DANS LE GROUPE",
    "retour_groupe": "RETOUR DANS LE GROUPE",
}

GENERAL_LABELS = {
    "statistique_avancee": "LA STAT DU JOUR",
    "quiz": "QUIZ FOOT",
    "debat": "DÉBAT FOOT",
    "sondage": "VOTE DU JOUR",
    "statistique": "STAT DU MATCH",
}


def clean(value: Any, cap: int = 500) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", str(value or ""))).strip()[:cap]


@lru_cache(maxsize=64)
def _font(size: int, bold: bool = True) -> ImageFont.ImageFont:
    for path in (FONT_BOLD if bold else FONT_REG):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


@lru_cache(maxsize=3)
def _template(kind: str) -> Image.Image:
    folder = TEMPLATE_DIRS[kind]
    parts = sorted(folder.glob("*.txt"))
    if not parts:
        raise FileNotFoundError(f"Template bannière absent: {folder}")
    raw = base64.b64decode("".join(p.read_text(encoding="ascii").strip() for p in parts), validate=True)
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    if image.size != (W, H):
        raise ValueError(f"Template {kind} invalide: {image.size}")
    return image


def template(kind: str) -> Image.Image:
    return _template(kind).copy()


def _fit_text(
    draw: ImageDraw.ImageDraw,
    value: Any,
    box: tuple[int, int, int, int],
    *,
    preferred: int,
    minimum: int,
    max_lines: int = 1,
    bold: bool = True,
    color=WHITE,
    align: str = "center",
) -> str:
    text = clean(value)
    if not text:
        return ""
    x1, y1, x2, y2 = box
    avail_w = max(1, x2 - x1 - 20)
    avail_h = max(1, y2 - y1 - 12)

    def wrap(face: ImageFont.ImageFont) -> list[str]:
        if max_lines == 1:
            return [text]
        words = text.split()
        rows, row = [], ""
        for word in words:
            trial = (row + " " + word).strip()
            bb = draw.textbbox((0, 0), trial, font=face)
            if bb[2] - bb[0] <= avail_w:
                row = trial
            elif row:
                rows.append(row)
                row = word
            else:
                rows.append(word)
                row = ""
        if row:
            rows.append(row)
        return rows

    face = _font(minimum, bold)
    lines = [text]
    for size in range(preferred, minimum - 1, -1):
        candidate = _font(size, bold)
        candidate_lines = wrap(candidate)
        bb = draw.textbbox((0, 0), "Ag", font=candidate)
        line_h = max(1, bb[3] - bb[1]) + max(4, int(size * .18))
        widths = [draw.textbbox((0, 0), row, font=candidate)[2] for row in candidate_lines]
        if len(candidate_lines) <= max_lines and max(widths or [0]) <= avail_w and line_h * len(candidate_lines) <= avail_h:
            face, lines = candidate, candidate_lines
            break

    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if lines:
        while lines[-1] and draw.textbbox((0, 0), lines[-1] + "…", font=face)[2] > avail_w:
            lines[-1] = lines[-1][:-1]
        if " ".join(lines) != text and lines[-1]:
            lines[-1] = lines[-1].rstrip() + "…"

    bb = draw.textbbox((0, 0), "Ag", font=face)
    line_h = max(1, bb[3] - bb[1]) + max(4, int(getattr(face, "size", minimum) * .18))
    total_h = line_h * len(lines)
    yy = (y1 + y2 - total_h) / 2 + line_h / 2
    for row in lines:
        row_box = draw.textbbox((0, 0), row, font=face)
        tw = row_box[2] - row_box[0]
        if align == "left":
            xx, anchor = x1 + 10, "lm"
        elif align == "right":
            xx, anchor = x2 - 10, "rm"
        else:
            xx, anchor = (x1 + x2) / 2, "mm"
        draw.text((xx, yy), row, font=face, fill=color, anchor=anchor)
        yy += line_h
    return "\n".join(lines)


def _logo(image: Image.Image, value: Any, spec: dict[str, Any]) -> bool:
    url = clean(value, 500)
    if not url:
        return False
    from programme_styles import load_logo
    source = load_logo(url, int(spec["max_px"]))
    if source is None:
        return False
    source = source.convert("RGBA")
    x1, y1, x2, y2 = spec["safe"]
    source.thumbnail((x2 - x1, y2 - y1), Image.Resampling.LANCZOS)
    cx, cy = spec["center"]
    image.paste(source, (int(cx - source.width / 2), int(cy - source.height / 2)), source)
    return True


def _event_label(category: str, payload: dict[str, Any]) -> str:
    explicit = clean(payload.get("banner_label") or payload.get("event_label"), 80)
    if explicit:
        return explicit.upper()
    return MATCH_LABELS.get(category) or CLUB_LABELS.get(category) or GENERAL_LABELS.get(category) or category.replace("_", " ").upper()


def banner_kind(category: str, payload: dict[str, Any]) -> str | None:
    if category in {"programme", "avant_match", "resultat", "composition", "flash", "viral"}:
        return None
    if category in CLUB_LABELS:
        return "club"
    if category in MATCH_LABELS:
        return "match"
    if category in {"reaction", "community_vote", "sondage", "statistique"}:
        home = clean(payload.get("home"))
        away = clean(payload.get("away"))
        if home and away:
            return "match"
    if category in GENERAL_LABELS or category in {"quiz", "debat", "statistique_avancee"}:
        return "general"
    return None


def render_match(category: str, payload: dict[str, Any]) -> Image.Image:
    image = template("match")
    draw = ImageDraw.Draw(image)
    layout = LAYOUT["match"]
    home = clean(payload.get("home"), 70)
    away = clean(payload.get("away"), 70)
    _logo(image, payload.get("home_logo"), layout["home_logo"])
    _logo(image, payload.get("away_logo"), layout["away_logo"])
    _fit_text(draw, home, layout["home_name"]["safe"], preferred=46, minimum=24, bold=True)
    _fit_text(draw, away, layout["away_name"]["safe"], preferred=46, minimum=24, bold=True)
    label = _event_label(category, payload)
    preferred = 56 if len(label) <= 17 else 46 if len(label) <= 24 else 38
    _fit_text(draw, label, layout["event"]["safe"], preferred=preferred, minimum=25, max_lines=2, bold=True, color=GOLD)
    return image


def render_club(category: str, payload: dict[str, Any]) -> Image.Image:
    image = template("club")
    draw = ImageDraw.Draw(image)
    layout = LAYOUT["club"]
    club = clean(payload.get("team") or payload.get("club") or payload.get("home"), 80)
    logo = payload.get("team_logo") or payload.get("club_logo") or payload.get("home_logo")
    _logo(image, logo, layout["logo"])
    _fit_text(draw, club, layout["club"]["safe"], preferred=48, minimum=25, bold=True)
    label = _event_label(category, payload)
    _fit_text(draw, label, layout["event"]["safe"], preferred=50, minimum=24, max_lines=2, bold=True, color=GOLD)
    meta = clean(payload.get("competition") or payload.get("league") or payload.get("meta"), 60)
    if meta:
        _fit_text(draw, meta.upper(), layout["meta"]["safe"], preferred=30, minimum=18, max_lines=2, bold=True, color=MUTED)
    return image


def render_general(category: str, payload: dict[str, Any]) -> Image.Image:
    image = template("general")
    draw = ImageDraw.Draw(image)
    layout = LAYOUT["general"]
    headline = clean(
        payload.get("headline")
        or payload.get("question")
        or payload.get("title")
        or _event_label(category, payload),
        220,
    )
    preferred = 64 if len(headline) <= 42 else 52 if len(headline) <= 70 else 42
    _fit_text(draw, headline, layout["headline"]["safe"], preferred=preferred, minimum=27, max_lines=2, bold=True)
    meta = clean(
        payload.get("meta")
        or payload.get("league")
        or payload.get("source")
        or _event_label(category, payload),
        100,
    )
    if meta:
        _fit_text(draw, meta.upper(), layout["meta"]["safe"], preferred=34, minimum=20, max_lines=1, bold=True, color=GOLD)
    return image


def render_banner(category: str, payload: dict[str, Any]) -> Image.Image:
    kind = banner_kind(category, payload)
    if kind == "match":
        return render_match(category, payload)
    if kind == "club":
        return render_club(category, payload)
    if kind == "general":
        return render_general(category, payload)
    raise ValueError("Catégorie sans bannière générique: " + category)


def is_banner_category(category: str, payload: dict[str, Any]) -> bool:
    return banner_kind(category, payload) is not None
