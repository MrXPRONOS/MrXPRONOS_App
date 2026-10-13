"""Audited MR XPRONOS Actu Foot event templates (batches 1 through 5).

This module renders only verified dynamic data on top of native 1122x1402
backgrounds generated for the Actu Foot event library.

Important:
- backgrounds already contain all decoration and titles;
- this code never redraws frames;
- coordinates are safe interior boxes from the 2026-10-13 visual audit;
- absent data stays absent: never invent a score, player, reason or source.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "images" / "arty_football" / "events"
W, H = 1122, 1402

PALE = (247, 249, 252)
GOLD = (241, 193, 92)
MUTED = (190, 198, 207)

FONT_BOLD = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)
FONT_REG = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
)

EVENT_TEMPLATE_FILES = {
    "poteau": "poteau.png",
    "occasion_manquee": "occasion_manquee.png",
    "arret_decisif": "arret_decisif.png",
    "carton_jaune_full": "carton_jaune_full.png",
    "carton_jaune_unknown": "carton_jaune_unknown.png",
    "carton_rouge_full": "carton_rouge_full.png",
    "carton_rouge_unknown": "carton_rouge_unknown.png",
    "remplacement_full": "remplacement_full.png",
    "remplacement_entrant": "remplacement_entrant.png",
    "remplacement_sortant": "remplacement_sortant.png",
    "intervention_medicale": "intervention_medicale.png",
    "blessure_confirmee": "blessure_confirmee.png",
    "retour_au_jeu": "retour_au_jeu.png",
    "match_suspendu": "match_suspendu.png",
    "match_interrompu_full": "match_interrompu_full.png",
    "match_interrompu_unknown": "match_interrompu_unknown.png",
    "match_reporte": "match_reporte.png",
    "match_annule": "match_annule.png",
    "reprise_match": "reprise_match.png",
    "temps_additionnel": "temps_additionnel.png",
    "fin_1re_mi_temps": "fin_1re_mi_temps.png",
    "debut_2e_mi_temps": "debut_2e_mi_temps.png",
    "fin_temps_reglementaire": "fin_temps_reglementaire.png",
    "prolongation": "prolongation.png",
    "mi_temps_prolongation": "mi_temps_prolongation.png",
}
EVENT_CATEGORIES = tuple(EVENT_TEMPLATE_FILES)
EVENT_ALIASES = {
    "carton_jaune", "carton_rouge", "remplacement", "match_interrompu",
    "match_reporté", "match_annulé", "reprise_du_match",
    "fin_de_la_1re_mi_temps", "début_de_la_2e_mi_temps",
    "fin_du_temps_réglementaire", "mi_temps_de_la_prolongation"
}

# Each box is the safe interior area, not the visible outer gold frame.
SPECS: dict[str, dict[str, tuple[int, int, int, int]]] = {
    "poteau": {
        "logo_home": (86, 816, 186, 916),
        "team_home": (72, 922, 332, 960),
        "score_home": (398, 820, 516, 925),
        "score_away": (594, 820, 712, 925),
        "logo_away": (936, 816, 1036, 916),
        "team_away": (785, 922, 1045, 960),
        "minute": (433, 956, 687, 1001),
        "competition": (130, 1050, 992, 1094),
        "player": (100, 1125, 1022, 1180),
        "player_team": (170, 1190, 952, 1235),
        "info": (90, 1245, 1032, 1318),
    },
    "occasion_manquee": {
        "logo_home": (86, 790, 184, 884),
        "team_home": (70, 888, 332, 924),
        "score_home": (394, 788, 514, 894),
        "score_away": (593, 788, 713, 894),
        "logo_away": (938, 790, 1036, 884),
        "team_away": (786, 888, 1048, 924),
        "player": (70, 936, 410, 985),
        "minute": (462, 936, 660, 985),
        "player_team": (718, 936, 1050, 985),
        "competition": (405, 1005, 765, 1046),
        "info": (75, 1070, 1047, 1315),
    },
    "arret_decisif": {
        "logo_home": (86, 812, 184, 906),
        "team_home": (70, 914, 332, 952),
        "score_home": (394, 807, 516, 920),
        "score_away": (592, 807, 714, 920),
        "logo_away": (938, 812, 1036, 906),
        "team_away": (786, 914, 1048, 952),
        "minute": (426, 949, 693, 994),
        "competition": (130, 1045, 992, 1090),
        "player": (100, 1120, 1022, 1178),
        "player_team": (170, 1190, 952, 1235),
        "info": (90, 1245, 1032, 1315),
    },
    "carton_jaune_full": {
        "logo_home": (84, 777, 182, 875),
        "team_home": (70, 884, 333, 922),
        "score_home": (395, 775, 517, 878),
        "score_away": (592, 775, 714, 878),
        "logo_away": (940, 777, 1038, 875),
        "team_away": (786, 884, 1050, 922),
        "minute": (458, 906, 700, 952),
        "player": (188, 999, 606, 1053),
        "reason": (714, 999, 1044, 1053),
        "competition": (130, 1105, 992, 1145),
        "info": (85, 1160, 1037, 1295),
    },
    "carton_jaune_unknown": {
        "logo_home": (84, 777, 182, 875),
        "team_home": (70, 884, 333, 922),
        "score_home": (395, 775, 517, 878),
        "score_away": (592, 775, 714, 878),
        "logo_away": (940, 777, 1038, 875),
        "team_away": (786, 884, 1050, 922),
        "minute": (458, 906, 700, 952),
        "competition": (270, 1045, 1038, 1090),
        "context": (270, 1110, 1038, 1210),
        "source": (270, 1230, 1038, 1280),
    },
    "carton_rouge_full": {
        "logo_home": (84, 768, 182, 866),
        "team_home": (70, 911, 333, 950),
        "score_home": (395, 776, 517, 895),
        "score_away": (605, 776, 727, 895),
        "logo_away": (940, 768, 1038, 866),
        "team_away": (789, 911, 1052, 950),
        "minute": (458, 914, 700, 966),
        "player": (203, 996, 615, 1059),
        "reason": (731, 996, 1045, 1059),
        "competition": (130, 1098, 992, 1144),
        "info": (93, 1175, 1029, 1290),
    },
    "carton_rouge_unknown": {
        "logo_home": (84, 768, 182, 866),
        "team_home": (70, 911, 333, 950),
        "score_home": (395, 776, 517, 895),
        "score_away": (605, 776, 727, 895),
        "logo_away": (940, 768, 1038, 866),
        "team_away": (789, 911, 1052, 950),
        "minute": (458, 914, 700, 966),
        "competition": (275, 1017, 1038, 1062),
        "context": (275, 1100, 1038, 1207),
        "source": (275, 1240, 1038, 1284),
    },
    "remplacement_full": {
        "logo_home": (86, 728, 195, 837),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 744, 520, 864),
        "score_away": (602, 744, 727, 864),
        "logo_away": (927, 728, 1036, 837),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 930),
        "competition": (360, 952, 762, 996),
        "entrant": (150, 1050, 500, 1175),
        "sortant": (622, 1050, 972, 1175),
        "source": (158, 1236, 964, 1282),
    },
    "remplacement_entrant": {
        "logo_home": (86, 728, 195, 837),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 744, 520, 864),
        "score_away": (602, 744, 727, 864),
        "logo_away": (927, 728, 1036, 837),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 930),
        "competition": (360, 952, 762, 996),
        "player": (225, 1050, 900, 1185),
        "source": (158, 1236, 964, 1282),
    },
    "remplacement_sortant": {
        "logo_home": (86, 728, 195, 837),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 744, 520, 864),
        "score_away": (602, 744, 727, 864),
        "logo_away": (927, 728, 1036, 837),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 930),
        "competition": (360, 952, 762, 996),
        "player": (225, 1050, 900, 1185),
        "source": (158, 1236, 964, 1282),
    },
    "intervention_medicale": {
        "logo_home": (86, 736, 195, 845),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 740, 517, 860),
        "score_away": (605, 740, 727, 860),
        "logo_away": (927, 736, 1036, 845),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 920),
        "competition": (350, 952, 772, 996),
        "player": (170, 1036, 952, 1084),
        "context": (170, 1120, 952, 1204),
        "source": (175, 1241, 947, 1279),
    },
    "blessure_confirmee": {
        "logo_home": (86, 736, 195, 845),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 740, 517, 860),
        "score_away": (605, 740, 727, 860),
        "logo_away": (927, 736, 1036, 845),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 920),
        "competition": (350, 952, 772, 996),
        "player": (170, 1036, 580, 1084),
        "status": (658, 1036, 956, 1084),
        "info": (170, 1120, 952, 1207),
        "source": (175, 1242, 947, 1280),
    },
    "retour_au_jeu": {
        "logo_home": (86, 736, 195, 845),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 740, 517, 860),
        "score_away": (605, 740, 727, 860),
        "logo_away": (927, 736, 1036, 845),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 920),
        "competition": (350, 952, 772, 996),
        "player": (200, 1036, 922, 1088),
        "player_team": (270, 1120, 852, 1165),
        "info": (170, 1200, 952, 1279),
    },
    "match_suspendu": {
        "logo_home": (86, 736, 195, 845),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 740, 517, 860),
        "score_away": (605, 740, 727, 860),
        "logo_away": (927, 736, 1036, 845),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 920),
        "competition": (350, 952, 772, 996),
        "context": (170, 1040, 952, 1184),
        "source": (175, 1226, 947, 1277),
    },
    "match_interrompu_full": {
        "logo_home": (86, 736, 195, 845),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 740, 517, 860),
        "score_away": (605, 740, 727, 860),
        "logo_away": (927, 736, 1036, 845),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 920),
        "competition": (350, 952, 772, 996),
        "reason": (170, 1038, 952, 1102),
        "status": (170, 1136, 952, 1208),
        "source": (175, 1242, 947, 1280),
    },
    "match_interrompu_unknown": {
        "logo_home": (86, 736, 195, 845),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 740, 517, 860),
        "score_away": (605, 740, 727, 860),
        "logo_away": (927, 736, 1036, 845),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 920),
        "competition": (350, 952, 772, 996),
        "status": (170, 1047, 952, 1178),
        "source": (175, 1226, 947, 1278),
    },
    "match_reporte": {
        "logo_home": (86, 736, 195, 845),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 740, 517, 860),
        "score_away": (605, 740, 727, 860),
        "logo_away": (927, 736, 1036, 845),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 920),
        "competition": (350, 952, 772, 996),
        "new_date": (170, 1042, 530, 1102),
        "new_time": (592, 1042, 952, 1102),
        "info": (170, 1138, 952, 1208),
        "source": (175, 1243, 947, 1282),
    },
    "match_annule": {
        "logo_home": (86, 736, 195, 845),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 740, 517, 860),
        "score_away": (605, 740, 727, 860),
        "logo_away": (927, 736, 1036, 845),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 920),
        "competition": (350, 952, 772, 996),
        "reason": (170, 1043, 952, 1101),
        "info": (170, 1138, 952, 1208),
        "source": (175, 1243, 947, 1282),
    },
    "reprise_match": {
        "logo_home": (86, 736, 195, 845),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 740, 517, 860),
        "score_away": (605, 740, 727, 860),
        "logo_away": (927, 736, 1036, 845),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 920),
        "competition": (350, 952, 772, 996),
        "status": (200, 1046, 922, 1096),
        "info": (170, 1132, 952, 1206),
        "source": (175, 1243, 947, 1282),
    },
    "temps_additionnel": {
        "logo_home": (86, 736, 195, 845),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 740, 517, 860),
        "score_away": (605, 740, 727, 860),
        "logo_away": (927, 736, 1036, 845),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 920),
        "competition": (350, 952, 772, 996),
        "added_time": (350, 1043, 772, 1158),
        "info": (170, 1200, 952, 1278),
    },
    "fin_1re_mi_temps": {
        "logo_home": (86, 736, 195, 845),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 740, 517, 860),
        "score_away": (605, 740, 727, 860),
        "logo_away": (927, 736, 1036, 845),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 920),
        "competition": (350, 952, 772, 996),
        "status": (200, 1044, 922, 1102),
        "info": (170, 1140, 952, 1208),
        "source": (175, 1243, 947, 1282),
    },
    "debut_2e_mi_temps": {
        "logo_home": (86, 736, 195, 845),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 740, 517, 860),
        "score_away": (605, 740, 727, 860),
        "logo_away": (927, 736, 1036, 845),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 920),
        "competition": (350, 952, 772, 996),
        "status": (200, 1044, 922, 1102),
        "info": (170, 1140, 952, 1208),
        "source": (175, 1243, 947, 1282),
    },
    "fin_temps_reglementaire": {
        "logo_home": (86, 736, 195, 845),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 740, 517, 860),
        "score_away": (605, 740, 727, 860),
        "logo_away": (927, 736, 1036, 845),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 920),
        "competition": (350, 952, 772, 996),
        "status": (170, 1040, 952, 1168),
        "source": (175, 1223, 947, 1278),
    },
    "prolongation": {
        "logo_home": (86, 736, 195, 845),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 740, 517, 860),
        "score_away": (605, 740, 727, 860),
        "logo_away": (927, 736, 1036, 845),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 920),
        "competition": (350, 952, 772, 996),
        "status": (200, 1044, 922, 1102),
        "info": (170, 1140, 952, 1208),
        "source": (175, 1243, 947, 1282),
    },
    "mi_temps_prolongation": {
        "logo_home": (86, 736, 195, 845),
        "team_home": (70, 875, 342, 916),
        "score_home": (395, 740, 517, 860),
        "score_away": (605, 740, 727, 860),
        "logo_away": (927, 736, 1036, 845),
        "team_away": (780, 875, 1052, 916),
        "minute": (455, 878, 667, 920),
        "competition": (350, 952, 772, 996),
        "status": (200, 1044, 922, 1102),
        "info": (170, 1140, 952, 1208),
        "source": (175, 1243, 947, 1282),
    },
}

# Audit-derived typography rules.
TEXT_STYLE = {
    "team": dict(size=29, min_size=16, max_lines=1, bold=True),
    "score": dict(size=78, min_size=38, max_lines=1, bold=True, color=PALE),
    "minute": dict(size=28, min_size=16, max_lines=1, bold=True, color=GOLD),
    "competition": dict(size=25, min_size=15, max_lines=1, bold=True, color=GOLD),
    "player": dict(size=35, min_size=18, max_lines=1, bold=True),
    "player_small": dict(size=27, min_size=15, max_lines=1, bold=True),
    "team_context": dict(size=24, min_size=15, max_lines=1, bold=True),
    "reason": dict(size=24, min_size=15, max_lines=1, bold=True),
    "info": dict(size=25, min_size=15, max_lines=2, bold=False),
    "info_large": dict(size=31, min_size=16, max_lines=6, bold=False),
    "context": dict(size=29, min_size=16, max_lines=3, bold=True),
    "source": dict(size=20, min_size=14, max_lines=1, bold=False, color=MUTED),
}


def clean(value: Any, cap: int = 1000) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", str(value or ""))).strip()[:cap]


@lru_cache(maxsize=128)
def _font(size: int, bold: bool = True) -> ImageFont.ImageFont:
    for path in (FONT_BOLD if bold else FONT_REG):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.ImageFont, width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    row = ""
    for word in words:
        candidate = (row + " " + word).strip()
        bb = draw.textbbox((0, 0), candidate, font=face)
        if bb[2] - bb[0] <= width:
            row = candidate
        elif row:
            lines.append(row)
            row = word
        else:
            # One unbreakable token: keep it and let the minimum-size fallback ellipsize.
            lines.append(word)
            row = ""
    if row:
        lines.append(row)
    return lines


def draw_fit(
    draw: ImageDraw.ImageDraw,
    value: Any,
    box: tuple[int, int, int, int],
    *,
    size: int,
    min_size: int,
    max_lines: int = 1,
    bold: bool = True,
    color=PALE,
    align: str = "center",
) -> str:
    text = clean(value)
    if not text:
        return ""
    x1, y1, x2, y2 = box
    safe_x = 10
    safe_y = 6
    avail_w = max(1, x2 - x1 - safe_x * 2)
    avail_h = max(1, y2 - y1 - safe_y * 2)

    lines: list[str] = []
    face = _font(min_size, bold)
    line_h = min_size + 4
    for px in range(size, min_size - 1, -1):
        candidate_face = _font(px, bold)
        candidate_lines = _wrap(draw, text, candidate_face, avail_w)
        bb = draw.textbbox((0, 0), "Ag", font=candidate_face)
        candidate_h = max(1, bb[3] - bb[1]) + max(3, int(px * 0.20))
        if (
            candidate_lines
            and len(candidate_lines) <= max_lines
            and candidate_h * len(candidate_lines) <= avail_h
            and all(
                draw.textbbox((0, 0), row, font=candidate_face)[2]
                - draw.textbbox((0, 0), row, font=candidate_face)[0]
                <= avail_w
                for row in candidate_lines
            )
        ):
            face = candidate_face
            lines = candidate_lines
            line_h = candidate_h
            break

    if not lines:
        face = _font(min_size, bold)
        lines = _wrap(draw, text, face, avail_w)[:max_lines] or [text]
        # Ellipsize the final visible line if the content still overflows.
        visible = " ".join(lines)
        if len(visible) < len(text) or any(
            draw.textbbox((0, 0), row, font=face)[2] > avail_w for row in lines
        ):
            last = lines[-1]
            while last and draw.textbbox((0, 0), last + "…", font=face)[2] > avail_w:
                last = last[:-1]
            lines[-1] = (last.rstrip() + "…") if last else "…"
        bb = draw.textbbox((0, 0), "Ag", font=face)
        line_h = max(1, bb[3] - bb[1]) + max(3, int(min_size * 0.20))

    total_h = line_h * len(lines)
    yy = (y1 + y2 - total_h) / 2 + line_h / 2
    for row in lines:
        if align == "left":
            xx, anchor = x1 + safe_x, "lm"
        elif align == "right":
            xx, anchor = x2 - safe_x, "rm"
        else:
            xx, anchor = (x1 + x2) / 2, "mm"
        draw.text((xx, yy), row, font=face, fill=color, anchor=anchor)
        yy += line_h
    return "\n".join(lines)


def _logo(image: Image.Image, value: Any, box: tuple[int, int, int, int], padding: int = 10) -> bool:
    url = clean(value, 500)
    if not url:
        return False
    from programme_styles import load_logo

    x1, y1, x2, y2 = box
    max_w = max(1, x2 - x1 - padding * 2)
    max_h = max(1, y2 - y1 - padding * 2)
    source = load_logo(url, max(max_w, max_h))
    if source is None:
        return False
    source = source.convert("RGBA")
    source.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    image.paste(source, (cx - source.width // 2, cy - source.height // 2), source)
    return True


def _score_pair(payload: dict[str, Any]) -> tuple[str, str]:
    scores = payload.get("scores")
    if isinstance(scores, (tuple, list)) and len(scores) >= 2:
        return clean(scores[0], 4), clean(scores[1], 4)
    home_score = clean(payload.get("home_score"), 4)
    away_score = clean(payload.get("away_score"), 4)
    if home_score or away_score:
        return home_score, away_score
    raw = clean(payload.get("score"), 20)
    match = re.search(r"(\d{1,3})\s*[-–—:]\s*(\d{1,3})", raw)
    return (match.group(1), match.group(2)) if match else ("", "")


def _category(category: str, payload: dict[str, Any]) -> str:
    if category in {"carton_jaune", "carton_rouge"}:
        player = clean(
            payload.get("player")
            or payload.get("card_player")
            or payload.get("booked_player")
            or payload.get("sent_off_player")
        )
        suffix = "full" if player else "unknown"
        return f"{category}_{suffix}"
    if category == "remplacement":
        entrant = clean(
            payload.get("entrant")
            or payload.get("incoming")
            or payload.get("player_in")
        )
        sortant = clean(
            payload.get("sortant")
            or payload.get("outgoing")
            or payload.get("player_out")
        )
        if entrant and sortant:
            return "remplacement_full"
        if entrant:
            return "remplacement_entrant"
        if sortant:
            return "remplacement_sortant"
        raise ValueError("Remplacement: au moins un joueur entrant ou sortant vérifié est requis")
    if category == "match_interrompu":
        reason = clean(payload.get("reason") or payload.get("interruption_reason") or payload.get("detail"))
        return "match_interrompu_full" if reason else "match_interrompu_unknown"
    if category == "match_reporté":
        return "match_reporte"
    if category == "match_annulé":
        return "match_annule"
    if category == "reprise_du_match":
        return "reprise_match"
    if category == "fin_de_la_1re_mi_temps":
        return "fin_1re_mi_temps"
    if category == "début_de_la_2e_mi_temps":
        return "debut_2e_mi_temps"
    if category == "fin_du_temps_réglementaire":
        return "fin_temps_reglementaire"
    if category == "mi_temps_de_la_prolongation":
        return "mi_temps_prolongation"
    return category


def is_event_category(category: str) -> bool:
    return category in EVENT_TEMPLATE_FILES or category in EVENT_ALIASES


def template_path(category: str, payload: dict[str, Any] | None = None) -> Path:
    resolved = _category(category, payload or {})
    if resolved not in EVENT_TEMPLATE_FILES:
        raise ValueError("Unknown Actu Foot event template: " + str(category))
    return ASSETS / EVENT_TEMPLATE_FILES[resolved]


def _generated_batch5_background(resolved: str) -> Image.Image | None:
    builders = {
        "fin_1re_mi_temps": "build_end_first_half",
        "debut_2e_mi_temps": "build_start_second_half",
        "fin_temps_reglementaire": "build_end_regulation",
        "prolongation": "build_extra_time",
        "mi_temps_prolongation": "build_extra_time_halftime",
    }
    fn_name = builders.get(resolved)
    if not fn_name:
        return None
    import build_event_batch_5_assets as batch5
    image = getattr(batch5, fn_name)()
    if image.size != (W, H):
        raise ValueError(f"Invalid generated Actu Foot template size for {resolved}: {image.size}")
    return image.convert("RGB")


def background(category: str, payload: dict[str, Any] | None = None) -> Image.Image:
    resolved = _category(category, payload or {})
    path = ASSETS / EVENT_TEMPLATE_FILES.get(resolved, "")
    if path.is_file():
        with Image.open(path) as source:
            image = source.convert("RGB")
    else:
        image = _generated_batch5_background(resolved)
        if image is None:
            raise FileNotFoundError("Missing audited Actu Foot template asset: " + str(path))
    if image.size != (W, H):
        raise ValueError(f"Invalid Actu Foot template size for {resolved}: {image.size}")
    return image


def _common(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    spec: dict[str, tuple[int, int, int, int]],
    payload: dict[str, Any],
) -> None:
    home = clean(payload.get("home"), 80)
    away = clean(payload.get("away"), 80)
    hs, aws = _score_pair(payload)
    _logo(image, payload.get("home_logo"), spec["logo_home"])
    _logo(image, payload.get("away_logo"), spec["logo_away"])
    draw_fit(draw, home, spec["team_home"], **TEXT_STYLE["team"])
    draw_fit(draw, away, spec["team_away"], **TEXT_STYLE["team"])
    if hs:
        draw_fit(draw, hs, spec["score_home"], **TEXT_STYLE["score"])
    if aws:
        draw_fit(draw, aws, spec["score_away"], **TEXT_STYLE["score"])
    if "minute" in spec:
        minute = clean(payload.get("minute") or payload.get("time"), 25)
        if minute and minute.isdigit():
            minute += "'"
        draw_fit(draw, minute, spec["minute"], **TEXT_STYLE["minute"])


def render_event(category: str, payload: dict[str, Any]) -> Image.Image:
    resolved = _category(category, payload)
    if resolved not in EVENT_TEMPLATE_FILES:
        raise ValueError("Unknown Actu Foot event template: " + str(category))
    if resolved == "match_interrompu_full":
        verified_reason = clean(
            payload.get("reason")
            or payload.get("interruption_reason")
            or payload.get("detail")
        )
        if not verified_reason:
            raise ValueError("Match interrompu complet: raison vérifiée requise")

    image = background(resolved, payload)
    draw = ImageDraw.Draw(image)
    spec = SPECS[resolved]
    _common(image, draw, spec, payload)

    competition = clean(payload.get("competition") or payload.get("league"), 100)
    source = clean(payload.get("source"), 120)
    info = clean(
        payload.get("info")
        or payload.get("commentary")
        or payload.get("description")
        or payload.get("status"),
        700,
    )

    if resolved == "poteau":
        player = clean(payload.get("player") or payload.get("shooter"), 100)
        player_team = clean(payload.get("player_team") or payload.get("team"), 100)
        draw_fit(draw, competition, spec["competition"], **TEXT_STYLE["competition"])
        draw_fit(draw, player, spec["player"], **TEXT_STYLE["player"])
        draw_fit(draw, player_team, spec["player_team"], **TEXT_STYLE["team_context"])
        draw_fit(draw, info or source, spec["info"], **TEXT_STYLE["info"])
    elif resolved == "occasion_manquee":
        player = clean(payload.get("player") or payload.get("shooter"), 100)
        player_team = clean(payload.get("player_team") or payload.get("team"), 100)
        draw_fit(draw, player, spec["player"], **TEXT_STYLE["player_small"])
        draw_fit(draw, player_team, spec["player_team"], **TEXT_STYLE["team_context"])
        draw_fit(draw, competition, spec["competition"], size=22, min_size=15, max_lines=1,
                 bold=True, color=GOLD)
        draw_fit(draw, info or source, spec["info"], **TEXT_STYLE["info_large"])
    elif resolved == "arret_decisif":
        goalkeeper = clean(
            payload.get("goalkeeper")
            or payload.get("keeper")
            or payload.get("player"),
            100,
        )
        goalkeeper_team = clean(
            payload.get("goalkeeper_team")
            or payload.get("player_team")
            or payload.get("team"),
            100,
        )
        draw_fit(draw, competition, spec["competition"], **TEXT_STYLE["competition"])
        draw_fit(draw, goalkeeper, spec["player"], **TEXT_STYLE["player"])
        draw_fit(draw, goalkeeper_team, spec["player_team"], **TEXT_STYLE["team_context"])
        draw_fit(draw, info or source, spec["info"], **TEXT_STYLE["info"])
    elif resolved in {"carton_jaune_full", "carton_rouge_full"}:
        player = clean(
            payload.get("player")
            or payload.get("card_player")
            or payload.get("booked_player")
            or payload.get("sent_off_player"),
            100,
        )
        reason = clean(payload.get("reason") or payload.get("foul") or payload.get("detail"), 180)
        detail = info
        if source and source not in detail:
            detail = (detail + " • " + source).strip(" •")
        draw_fit(draw, player, spec["player"], **TEXT_STYLE["player_small"], align="left")
        draw_fit(draw, reason, spec["reason"], **TEXT_STYLE["reason"], align="left")
        draw_fit(draw, competition, spec["competition"], size=24, min_size=15,
                 max_lines=1, bold=True, color=GOLD)
        draw_fit(draw, detail, spec["info"], size=27, min_size=15, max_lines=4, bold=False)
    elif resolved in {"carton_jaune_unknown", "carton_rouge_unknown"}:
        context = clean(payload.get("reason") or payload.get("detail") or info, 400)
        draw_fit(draw, competition, spec["competition"], size=24, min_size=15,
                 max_lines=1, bold=True, color=GOLD, align="left")
        draw_fit(draw, context, spec["context"], **TEXT_STYLE["context"], align="left")
        draw_fit(draw, source, spec["source"], **TEXT_STYLE["source"], align="left")
    elif resolved.startswith("remplacement_"):
        entrant = clean(
            payload.get("entrant")
            or payload.get("incoming")
            or payload.get("player_in"),
            100,
        )
        sortant = clean(
            payload.get("sortant")
            or payload.get("outgoing")
            or payload.get("player_out"),
            100,
        )
        draw_fit(draw, competition, spec["competition"], size=24, min_size=15,
                 max_lines=1, bold=True, color=GOLD)
        if resolved == "remplacement_full":
            draw_fit(draw, entrant, spec["entrant"], size=33, min_size=15,
                     max_lines=3, bold=True, align="center")
            draw_fit(draw, sortant, spec["sortant"], size=33, min_size=15,
                     max_lines=3, bold=True, align="center")
        else:
            player = entrant if resolved == "remplacement_entrant" else sortant
            draw_fit(draw, player, spec["player"], size=36, min_size=18,
                     max_lines=3, bold=True, align="center")
        draw_fit(draw, source, spec["source"], **TEXT_STYLE["source"], align="center")
    elif resolved == "intervention_medicale":
        player = clean(payload.get("player") or payload.get("treated_player"), 100)
        context = clean(
            payload.get("treatment")
            or payload.get("context")
            or payload.get("detail")
            or info,
            500,
        )
        draw_fit(draw, competition, spec["competition"], size=24, min_size=15,
                 max_lines=1, bold=True, color=GOLD)
        draw_fit(draw, player, spec["player"], size=31, min_size=16,
                 max_lines=1, bold=True)
        draw_fit(draw, context, spec["context"], size=28, min_size=15,
                 max_lines=3, bold=False)
        draw_fit(draw, source, spec["source"], **TEXT_STYLE["source"])
    elif resolved == "blessure_confirmee":
        player = clean(payload.get("player") or payload.get("injured_player"), 100)
        injury_status = clean(
            payload.get("injury_status")
            or payload.get("diagnosis")
            or payload.get("status"),
            180,
        )
        detail = clean(payload.get("detail") or payload.get("info") or payload.get("description"), 500)
        draw_fit(draw, competition, spec["competition"], size=24, min_size=15,
                 max_lines=1, bold=True, color=GOLD)
        draw_fit(draw, player, spec["player"], size=28, min_size=15,
                 max_lines=1, bold=True, align="left")
        draw_fit(draw, injury_status, spec["status"], size=24, min_size=14,
                 max_lines=1, bold=True)
        draw_fit(draw, detail, spec["info"], size=27, min_size=15,
                 max_lines=3, bold=False)
        draw_fit(draw, source, spec["source"], **TEXT_STYLE["source"])
    elif resolved == "retour_au_jeu":
        player = clean(payload.get("player") or payload.get("returning_player"), 100)
        player_team = clean(payload.get("player_team") or payload.get("team"), 100)
        detail = clean(payload.get("detail") or payload.get("info") or payload.get("status"), 420)
        if source and source not in detail:
            detail = (detail + " • " + source).strip(" •")
        draw_fit(draw, competition, spec["competition"], size=24, min_size=15,
                 max_lines=1, bold=True, color=GOLD)
        draw_fit(draw, player, spec["player"], size=34, min_size=18,
                 max_lines=1, bold=True)
        draw_fit(draw, player_team, spec["player_team"], size=24, min_size=15,
                 max_lines=1, bold=True)
        draw_fit(draw, detail, spec["info"], size=25, min_size=15,
                 max_lines=3, bold=False)
    elif resolved == "match_suspendu":
        context = clean(
            payload.get("reason")
            or payload.get("status")
            or payload.get("detail")
            or info,
            600,
        )
        draw_fit(draw, competition, spec["competition"], size=24, min_size=15,
                 max_lines=1, bold=True, color=GOLD)
        draw_fit(draw, context, spec["context"], size=31, min_size=16,
                 max_lines=4, bold=True)
        draw_fit(draw, source, spec["source"], **TEXT_STYLE["source"])
    elif resolved == "match_interrompu_full":
        reason = clean(payload.get("reason") or payload.get("interruption_reason") or payload.get("detail"), 260)
        status = clean(
            payload.get("restart")
            or payload.get("resume")
            or payload.get("status")
            or payload.get("info")
            or payload.get("description"),
            420,
        )
        draw_fit(draw, competition, spec["competition"], size=24, min_size=15,
                 max_lines=1, bold=True, color=GOLD)
        draw_fit(draw, reason, spec["reason"], size=29, min_size=15,
                 max_lines=2, bold=True)
        draw_fit(draw, status, spec["status"], size=26, min_size=15,
                 max_lines=3, bold=False)
        draw_fit(draw, source, spec["source"], **TEXT_STYLE["source"])
    elif resolved == "match_interrompu_unknown":
        status = clean(
            payload.get("restart")
            or payload.get("resume")
            or payload.get("status")
            or payload.get("info")
            or payload.get("description"),
            520,
        )
        draw_fit(draw, competition, spec["competition"], size=24, min_size=15,
                 max_lines=1, bold=True, color=GOLD)
        draw_fit(draw, status, spec["status"], size=29, min_size=16,
                 max_lines=4, bold=False)
        draw_fit(draw, source, spec["source"], **TEXT_STYLE["source"])
    elif resolved == "match_reporte":
        new_date = clean(payload.get("new_date") or payload.get("rescheduled_date"), 80)
        new_time = clean(payload.get("new_time") or payload.get("rescheduled_time"), 40)
        detail = clean(payload.get("info") or payload.get("status") or payload.get("description"), 420)
        draw_fit(draw, competition, spec["competition"], size=24, min_size=15,
                 max_lines=1, bold=True, color=GOLD)
        draw_fit(draw, new_date, spec["new_date"], size=28, min_size=15,
                 max_lines=1, bold=True)
        draw_fit(draw, new_time, spec["new_time"], size=28, min_size=15,
                 max_lines=1, bold=True)
        draw_fit(draw, detail, spec["info"], size=25, min_size=15,
                 max_lines=3, bold=False)
        draw_fit(draw, source, spec["source"], **TEXT_STYLE["source"])
    elif resolved == "match_annule":
        reason = clean(payload.get("reason") or payload.get("cancellation_reason") or payload.get("detail"), 260)
        detail = clean(payload.get("info") or payload.get("status") or payload.get("description"), 420)
        draw_fit(draw, competition, spec["competition"], size=24, min_size=15,
                 max_lines=1, bold=True, color=GOLD)
        draw_fit(draw, reason, spec["reason"], size=27, min_size=15,
                 max_lines=2, bold=True)
        draw_fit(draw, detail, spec["info"], size=25, min_size=15,
                 max_lines=3, bold=False)
        draw_fit(draw, source, spec["source"], **TEXT_STYLE["source"])
    elif resolved == "reprise_match":
        status = clean(payload.get("status") or payload.get("resume") or payload.get("restart"), 220)
        detail = clean(payload.get("info") or payload.get("description"), 420)
        draw_fit(draw, competition, spec["competition"], size=24, min_size=15,
                 max_lines=1, bold=True, color=GOLD)
        draw_fit(draw, status, spec["status"], size=29, min_size=16,
                 max_lines=1, bold=True)
        draw_fit(draw, detail, spec["info"], size=25, min_size=15,
                 max_lines=3, bold=False)
        draw_fit(draw, source, spec["source"], **TEXT_STYLE["source"])
    elif resolved == "temps_additionnel":
        added = clean(payload.get("added_time") or payload.get("stoppage_time") or payload.get("extra_minutes"), 24)
        if added and added.isdigit():
            added = "+" + added + "'"
        detail = clean(payload.get("info") or payload.get("status") or payload.get("description"), 420)
        if source and source not in detail:
            detail = (detail + " • " + source).strip(" •")
        draw_fit(draw, competition, spec["competition"], size=24, min_size=15,
                 max_lines=1, bold=True, color=GOLD)
        draw_fit(draw, added, spec["added_time"], size=62, min_size=28,
                 max_lines=1, bold=True, color=GOLD)
        draw_fit(draw, detail, spec["info"], size=25, min_size=15,
                 max_lines=3, bold=False)
    elif resolved in {"fin_1re_mi_temps", "debut_2e_mi_temps", "prolongation", "mi_temps_prolongation"}:
        status = clean(payload.get("status") or payload.get("phase_status") or payload.get("detail"), 220)
        detail = clean(payload.get("info") or payload.get("description"), 420)
        draw_fit(draw, competition, spec["competition"], size=24, min_size=15,
                 max_lines=1, bold=True, color=GOLD)
        draw_fit(draw, status, spec["status"], size=29, min_size=16,
                 max_lines=1, bold=True)
        draw_fit(draw, detail, spec["info"], size=25, min_size=15,
                 max_lines=3, bold=False)
        draw_fit(draw, source, spec["source"], **TEXT_STYLE["source"])
    elif resolved == "fin_temps_reglementaire":
        status = clean(
            payload.get("status")
            or payload.get("next_phase")
            or payload.get("detail")
            or payload.get("info"),
            520,
        )
        draw_fit(draw, competition, spec["competition"], size=24, min_size=15,
                 max_lines=1, bold=True, color=GOLD)
        draw_fit(draw, status, spec["status"], size=31, min_size=16,
                 max_lines=4, bold=True)
        draw_fit(draw, source, spec["source"], **TEXT_STYLE["source"])
    else:
        raise ValueError("Unhandled Actu Foot event template: " + resolved)

    return image


__all__ = [
    "W", "H", "EVENT_CATEGORIES", "EVENT_TEMPLATE_FILES", "SPECS",
    "is_event_category", "template_path", "background", "render_event",
]
