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
W, H = 1280, 500

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
    "match": ASSETS / "match1280.b64",
    "club": ASSETS / "club1280.b64",
    "general": ASSETS / "general1280.b64",
}

# Exact data surfaces measured on the generated 2006x784 source art and
# projected to the 1280x500 Telegram source assets.
LAYOUT = {
    "match": {
        "home_logo": {"surface": (61,154,211,301), "safe": (67,160,205,295), "center": (136,228), "max_px": 126},
        "home_name": {"surface": (227,185,478,268), "safe": (236,193,469,260)},
        "event": {"surface": (509,185,763,269), "safe": (518,193,754,261)},
        "away_name": {"surface": (782,185,1047,268), "safe": (791,193,1038,260)},
        "away_logo": {"surface": (1061,154,1212,301), "safe": (1067,160,1206,295), "center": (1137,228), "max_px": 126},
    },
    "club": {
        "logo": {"surface": (53,176,219,303), "safe": (60,183,212,296), "center": (136,240), "max_px": 112},
        "club": {"surface": (236,188,582,278), "safe": (246,197,572,269)},
        "event": {"surface": (614,188,999,278), "safe": (624,197,989,269)},
        "meta": {"surface": (1025,188,1217,278), "safe": (1034,197,1208,269)},
    },
    "general": {
        "headline": {"surface": (108,170,1172,276), "safe": (122,181,1158,265)},
        "meta": {"surface": (419,291,863,344), "safe": (432,299,850,336)},
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
    full = folder / "full.txt"
    parts = [full] if full.is_file() else sorted(folder.glob("*.txt"))
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
    _fit_text(draw, home, layout["home_name"]["safe"], preferred=66, minimum=34, bold=True)
    _fit_text(draw, away, layout["away_name"]["safe"], preferred=46, minimum=24, bold=True)
    label = _event_label(category, payload)
    preferred = 66 if len(label) <= 17 else 56 if len(label) <= 24 else 46
    _fit_text(draw, label, layout["event"]["safe"], preferred=preferred, minimum=32, max_lines=2, bold=True, color=GOLD)
    return image


def render_club(category: str, payload: dict[str, Any]) -> Image.Image:
    image = template("club")
    draw = ImageDraw.Draw(image)
    layout = LAYOUT["club"]
    club = clean(payload.get("team") or payload.get("club") or payload.get("home"), 80)
    logo = payload.get("team_logo") or payload.get("club_logo") or payload.get("home_logo")
    _logo(image, logo, layout["logo"])
    _fit_text(draw, club, layout["club"]["safe"], preferred=66, minimum=34, bold=True)
    label = _event_label(category, payload)
    _fit_text(draw, label, layout["event"]["safe"], preferred=64, minimum=32, max_lines=2, bold=True, color=GOLD)
    meta = clean(payload.get("competition") or payload.get("league") or payload.get("meta"), 60)
    if meta:
        _fit_text(draw, meta.upper(), layout["meta"]["safe"], preferred=38, minimum=22, max_lines=2, bold=True, color=MUTED)
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
    preferred = 76 if len(headline) <= 42 else 62 if len(headline) <= 70 else 50
    _fit_text(draw, headline, layout["headline"]["safe"], preferred=preferred, minimum=34, max_lines=2, bold=True)
    meta = clean(
        payload.get("meta")
        or payload.get("league")
        or payload.get("source")
        or _event_label(category, payload),
        100,
    )
    if meta:
        _fit_text(draw, meta.upper(), layout["meta"]["safe"], preferred=42, minimum=24, max_lines=1, bold=True, color=GOLD)
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
