"""MR XPRONOS — trois bannières horizontales génériques.

Règle:
- le fond fournit déjà cadres, cercles, lumière, logo MR XPRONOS et décoration;
- le code ne redessine aucun panneau;
- il injecte uniquement les données dynamiques dans des surfaces mesurées;
- les logos réels sont prioritaires; s'ils manquent, un monogramme neutre dérivé
  du nom de l'équipe évite un cercle vide sans prétendre être le logo officiel;
- la donnée principale (nom de la publication) reste toujours la plus visible.

Les trois sources utilisées ici sont les templates 1280x500 validés dans le canal
TEST: match, club, général.
"""
from __future__ import annotations

import base64
import io
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "images" / "generic_football_banners"
W, H = 1280, 500

WHITE = (247, 249, 252)
GOLD = (245, 199, 91)
MUTED = (198, 205, 216)
RED = (244, 92, 92)

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
    "match": ASSETS / "match_latest.b64",
    "club": ASSETS / "club_latest.b64",
    "general": ASSETS / "general_latest.b64",
}

# Mesures natives sur les 3 templates 1280x500 générés le 14/10/2026.
# surface = panneau visible; safe = zone de texte/photo réellement exploitable.
# Aucun fond additionnel n'est dessiné par le renderer.
LAYOUT = {
    "match": {
        "home_logo": {"surface": (28, 181, 159, 326), "safe": (40, 195, 150, 305), "center": (95, 250), "max_px": 100},
        "home_name": {"surface": (165, 207, 441, 299), "safe": (180, 220, 426, 284)},
        "event": {"surface": (437, 186, 844, 316), "safe": (464, 202, 817, 299)},
        "away_name": {"surface": (839, 207, 1115, 299), "safe": (855, 220, 1099, 284)},
        "away_logo": {"surface": (1121, 181, 1255, 326), "safe": (1133, 195, 1237, 305), "center": (1185, 250), "max_px": 100},
    },
    "club": {
        "logo": {"surface": (52, 158, 329, 411), "safe": (95, 195, 290, 380), "center": (192, 287), "max_px": 158},
        "club": {"surface": (269, 239, 614, 365), "safe": (325, 260, 585, 348)},
        "event": {"surface": (610, 187, 1230, 383), "safe": (651, 211, 1188, 356)},
        "meta": {"surface": (948, 139, 1213, 199), "safe": (1038, 151, 1188, 191)},
    },
    "general": {
        "headline": {"surface": (41, 145, 914, 354), "safe": (66, 164, 887, 331)},
        "photo": {"surface": (922, 111, 1235, 421), "safe": (946, 128, 1214, 401)},
        "meta": {"surface": (301, 365, 650, 425), "safe": (322, 375, 630, 416)},
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
    "blessure_confirmee": "BLESSURE CONFIRMÉE",
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
    "fin_de_la_1re_mi_temps": "FIN DE LA 1RE MI-TEMPS",
    "fin_1re_mi_temps": "FIN DE LA 1RE MI-TEMPS",
    "début_de_la_2e_mi_temps": "DÉBUT DE LA 2E MI-TEMPS",
    "debut_2e_mi_temps": "DÉBUT DE LA 2E MI-TEMPS",
    "fin_du_temps_réglementaire": "FIN DU TEMPS RÉGLEMENTAIRE",
    "fin_temps_reglementaire": "FIN DU TEMPS RÉGLEMENTAIRE",
    "prolongation": "PROLONGATIONS",
    "mi_temps_de_la_prolongation": "MI-TEMPS DES PROLONGATIONS",
    "mi_temps_prolongation": "MI-TEMPS DES PROLONGATIONS",
    "tirs_au_but": "TIRS AU BUT",
    "tir_au_but_marqué": "TIR AU BUT MARQUÉ",
    "tir_au_but_marque": "TIR AU BUT MARQUÉ",
    "tir_au_but_manqué": "TIR AU BUT MANQUÉ",
    "tir_au_but_manque": "TIR AU BUT MANQUÉ",
    "fin_des_tirs_au_but": "FIN DES TIRS AU BUT",
    "fin_tirs_au_but": "FIN DES TIRS AU BUT",
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


@lru_cache(maxsize=96)
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
        raise ValueError(f"Template {kind} invalide: {image.size}, attendu {(W, H)}")
    return image


def template(kind: str) -> Image.Image:
    return _template(kind).copy()


def _text_width(draw: ImageDraw.ImageDraw, value: str, face: ImageFont.ImageFont) -> int:
    bb = draw.textbbox((0, 0), value, font=face)
    return max(0, bb[2] - bb[0])


def _lines_for(
    draw: ImageDraw.ImageDraw,
    text: str,
    face: ImageFont.ImageFont,
    avail_w: int,
    max_lines: int,
) -> list[str]:
    if max_lines <= 1:
        return [text]
    if _text_width(draw, text, face) <= avail_w:
        return [text]

    words = text.split()
    if len(words) <= 1:
        return [text]

    if max_lines == 2:
        candidates: list[tuple[int, list[str]]] = []
        for cut in range(1, len(words)):
            rows = [" ".join(words[:cut]), " ".join(words[cut:])]
            widths = [_text_width(draw, row, face) for row in rows]
            if max(widths) <= avail_w:
                candidates.append((max(widths), rows))
        if candidates:
            return min(candidates, key=lambda item: item[0])[1]

    rows: list[str] = []
    row = ""
    for word in words:
        trial = (row + " " + word).strip()
        if not row or _text_width(draw, trial, face) <= avail_w:
            row = trial
        else:
            rows.append(row)
            row = word
    if row:
        rows.append(row)
    return rows


def _ellipsis(draw: ImageDraw.ImageDraw, value: str, face: ImageFont.ImageFont, avail_w: int) -> str:
    value = value.strip()
    if _text_width(draw, value, face) <= avail_w:
        return value
    suffix = "…"
    while value and _text_width(draw, value + suffix, face) > avail_w:
        value = value[:-1].rstrip()
    return (value + suffix) if value else suffix


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
    avail_w = max(1, x2 - x1 - 12)
    avail_h = max(1, y2 - y1 - 8)

    face = _font(minimum, bold)
    lines = _lines_for(draw, text, face, avail_w, max_lines)

    for size in range(preferred, minimum - 1, -1):
        candidate = _font(size, bold)
        candidate_lines = _lines_for(draw, text, candidate, avail_w, max_lines)
        bb = draw.textbbox((0, 0), "Ag", font=candidate)
        glyph_h = max(1, bb[3] - bb[1])
        line_h = glyph_h + max(3, int(size * 0.12))
        if (
            len(candidate_lines) <= max_lines
            and max((_text_width(draw, row, candidate) for row in candidate_lines), default=0) <= avail_w
            and line_h * len(candidate_lines) <= avail_h
        ):
            face, lines = candidate, candidate_lines
            break

    # Filet de sécurité: si même la taille minimum déborde, conserver les
    # premières lignes et tronquer uniquement le dernier fragment.
    if len(lines) > max_lines:
        kept = lines[: max_lines - 1]
        tail = " ".join(lines[max_lines - 1 :])
        lines = kept + [_ellipsis(draw, tail, face, avail_w)]
    else:
        lines = [_ellipsis(draw, row, face, avail_w) for row in lines]

    bb = draw.textbbox((0, 0), "Ag", font=face)
    glyph_h = max(1, bb[3] - bb[1])
    line_h = glyph_h + max(3, int(getattr(face, "size", minimum) * 0.12))
    total_h = line_h * len(lines)
    yy = (y1 + y2 - total_h) / 2 + line_h / 2

    for row in lines:
        if align == "left":
            xx, anchor = x1 + 6, "lm"
        elif align == "right":
            xx, anchor = x2 - 6, "rm"
        else:
            xx, anchor = (x1 + x2) / 2, "mm"
        draw.text((xx, yy), row, font=face, fill=color, anchor=anchor)
        yy += line_h
    return "\n".join(lines)


def _initials(name: str) -> str:
    words = [re.sub(r"[^A-Za-zÀ-ÿ0-9]", "", x) for x in clean(name, 80).split()]
    words = [x for x in words if x]
    if not words:
        return "MX"
    if len(words) == 1:
        return words[0][:3].upper()
    if len(words) == 2:
        return (words[0][0] + words[1][0]).upper()
    return "".join(x[0] for x in words[:3]).upper()


def _logo(image: Image.Image, value: Any, spec: dict[str, Any], fallback_name: str) -> bool:
    url = clean(value, 700)
    source = None
    if url:
        from programme_styles import load_logo
        source = load_logo(url, int(spec["max_px"]))
    if source is not None:
        source = source.convert("RGBA")
        x1, y1, x2, y2 = spec["safe"]
        source.thumbnail((x2 - x1, y2 - y1), Image.Resampling.LANCZOS)
        cx, cy = spec["center"]
        image.paste(source, (int(cx - source.width / 2), int(cy - source.height / 2)), source)
        return True

    # Fallback non trompeur: initiales de l'équipe dans le cercle natif.
    draw = ImageDraw.Draw(image)
    cx, cy = spec["center"]
    initials = _initials(fallback_name)
    size = 40 if int(spec["max_px"]) <= 110 else 54
    draw.text((cx, cy), initials, font=_font(size, True), fill=GOLD, anchor="mm")
    return False


def _load_photo(value: Any) -> Image.Image | None:
    raw = clean(value, 900)
    if not raw:
        return None
    try:
        local = Path(raw)
        if not local.is_absolute():
            local = (ROOT / raw).resolve()
        if local.is_file() and local.is_relative_to(ROOT.resolve()):
            return Image.open(local).convert("RGB")
    except (OSError, ValueError):
        pass
    if not raw.startswith(("https://", "http://")):
        return None
    try:
        response = requests.get(raw, timeout=(6, 12), headers={"User-Agent": "MrXPRONOS-banner/1.0"})
        response.raise_for_status()
        if len(response.content) > 5_000_000:
            return None
        return Image.open(io.BytesIO(response.content)).convert("RGB")
    except Exception:
        return None


def _fallback_ball(image: Image.Image, box: tuple[int, int, int, int]) -> None:
    draw = ImageDraw.Draw(image)
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    radius = int(min(x2 - x1, y2 - y1) * 0.23)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=GOLD, width=4)
    r2 = int(radius * 0.38)
    pts = []
    import math
    for i in range(5):
        a = math.radians(-90 + i * 72)
        pts.append((cx + int(r2 * math.cos(a)), cy + int(r2 * math.sin(a))))
    draw.polygon(pts, outline=GOLD)
    for px, py in pts:
        dx, dy = px - cx, py - cy
        norm = max(1.0, (dx * dx + dy * dy) ** 0.5)
        ex = cx + int(dx / norm * radius * 0.92)
        ey = cy + int(dy / norm * radius * 0.92)
        draw.line((px, py, ex, ey), fill=GOLD, width=3)


def _photo(image: Image.Image, payload: dict[str, Any], spec: dict[str, Any]) -> bool:
    value = (
        payload.get("image_path")
        or payload.get("photo_path")
        or payload.get("image_url")
        or payload.get("photo_url")
        or payload.get("photo")
        or payload.get("image")
    )
    source = _load_photo(value)
    box = spec["safe"]
    if source is None:
        _fallback_ball(image, box)
        return False
    w, h = box[2] - box[0], box[3] - box[1]
    source = ImageOps.fit(source, (w, h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.42))
    image.paste(source, (box[0], box[1]))
    return True


def _event_label(category: str, payload: dict[str, Any]) -> str:
    explicit = clean(payload.get("banner_label") or payload.get("event_label"), 90)
    if explicit:
        return explicit.upper()
    return (
        MATCH_LABELS.get(category)
        or CLUB_LABELS.get(category)
        or GENERAL_LABELS.get(category)
        or category.replace("_", " ").upper()
        or "INFO FOOT"
    )


def _event_color(category: str) -> tuple[int, int, int]:
    if category.startswith("carton_rouge"):
        return RED
    return GOLD


def banner_kind(category: str, payload: dict[str, Any]) -> str | None:
    if category in {"programme", "avant_match", "resultat", "composition", "flash", "viral"}:
        return None
    if category in CLUB_LABELS:
        return "club"
    if category in MATCH_LABELS:
        return "match"
    if category in {"reaction", "community_vote", "sondage", "statistique"}:
        if clean(payload.get("home")) and clean(payload.get("away")):
            return "match"
        return "general"
    if category in GENERAL_LABELS or category in {"quiz", "debat", "statistique_avancee"}:
        return "general"
    return None


def render_match(category: str, payload: dict[str, Any]) -> Image.Image:
    image = template("match")
    draw = ImageDraw.Draw(image)
    layout = LAYOUT["match"]

    home = clean(payload.get("home"), 70) or "ÉQUIPE À CONFIRMER"
    away = clean(payload.get("away"), 70) or "ÉQUIPE À CONFIRMER"
    _logo(image, payload.get("home_logo"), layout["home_logo"], home)
    _logo(image, payload.get("away_logo"), layout["away_logo"], away)

    _fit_text(draw, home, layout["home_name"]["safe"], preferred=38, minimum=18, max_lines=2, bold=True)
    _fit_text(draw, away, layout["away_name"]["safe"], preferred=38, minimum=18, max_lines=2, bold=True)

    label = _event_label(category, payload)
    preferred = 66 if len(label) <= 12 else 56 if len(label) <= 21 else 46
    _fit_text(
        draw,
        label,
        layout["event"]["safe"],
        preferred=preferred,
        minimum=22,
        max_lines=2,
        bold=True,
        color=_event_color(category),
    )
    return image


def render_club(category: str, payload: dict[str, Any]) -> Image.Image:
    image = template("club")
    draw = ImageDraw.Draw(image)
    layout = LAYOUT["club"]

    club = clean(payload.get("team") or payload.get("club") or payload.get("home"), 80) or "CLUB À CONFIRMER"
    logo = payload.get("team_logo") or payload.get("club_logo") or payload.get("logo") or payload.get("home_logo")
    _logo(image, logo, layout["logo"], club)

    _fit_text(draw, club, layout["club"]["safe"], preferred=40, minimum=19, max_lines=2, bold=True)

    label = _event_label(category, payload)
    preferred = 68 if len(label) <= 15 else 56 if len(label) <= 24 else 46
    _fit_text(
        draw,
        label,
        layout["event"]["safe"],
        preferred=preferred,
        minimum=24,
        max_lines=2,
        bold=True,
        color=GOLD,
    )

    meta = clean(
        payload.get("day")
        or payload.get("date")
        or payload.get("meta")
        or payload.get("competition")
        or payload.get("league")
        or "FOOTBALL",
        50,
    )
    _fit_text(draw, meta.upper(), layout["meta"]["safe"], preferred=21, minimum=13, max_lines=1, bold=True, color=MUTED)
    return image


def render_general(category: str, payload: dict[str, Any]) -> Image.Image:
    image = template("general")
    draw = ImageDraw.Draw(image)
    layout = LAYOUT["general"]

    headline = clean(
        payload.get("headline")
        or payload.get("question")
        or payload.get("title")
        or payload.get("info"),
        260,
    ) or "INFORMATION FOOTBALL"

    preferred = 64 if len(headline) <= 40 else 54 if len(headline) <= 72 else 44
    _fit_text(
        draw,
        headline,
        layout["headline"]["safe"],
        preferred=preferred,
        minimum=25,
        max_lines=3,
        bold=True,
        color=WHITE,
        align="left",
    )

    meta = clean(payload.get("meta"), 80) or _event_label(category, payload)
    _fit_text(
        draw,
        meta.upper(),
        layout["meta"]["safe"],
        preferred=27,
        minimum=16,
        max_lines=1,
        bold=True,
        color=GOLD,
    )
    _photo(image, payload, layout["photo"])
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
