"""Data-only placement on the TEN original Arty Football portrait designs.

Source PNGs are 1122x1402 and contain ALL visual frames/decorations.
Do not add panels, headings, circles, extra numbers, or opaque patches here.
The independent procedural fallback stays in arty_football_templates.py.

The geometry below was measured for image-gen-1 ... image-gen-10.
All coordinates are in native 1122x1402 units. Export is 1080x1350.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

NATIVE = (1122, 1402)
OUTPUT = (1080, 1350)
WHITE = (250, 249, 246, 255)
GOLD = (249, 205, 111, 255)
FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)


def _clean(value: Any, limit: int = 750) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(value or ""))).strip()[:limit]


def _font(px: int):
    for path in FONTS:
        if Path(path).is_file():
            return ImageFont.truetype(path, px)
    return ImageFont.load_default()


def _width(draw, text, face):
    box = draw.textbbox((0, 0), text, font=face)
    return box[2] - box[0]


def _shorten(draw, text, face, limit):
    """Guarantee that even a single very long word stays inside a slot."""
    if _width(draw, text, face) <= limit:
        return text
    while text and _width(draw, text + "…", face) > limit:
        text = text[:-1]
    return text.rstrip() + "…" if text else ""


def _wrap(draw, text, face, width, count):
    rows, row = [], ""
    for word in text.split():
        candidate = (row + " " + word).strip()
        if _width(draw, candidate, face) <= width:
            row = candidate
        else:
            if row:
                rows.append(row)
            row = _shorten(draw, word, face, width)
    if row:
        rows.append(row)
    if len(rows) > count:
        rows = rows[:count]
        rows[-1] = _shorten(draw, rows[-1] + "…", face, width)
    return rows


def text(image, value, bounds, *, size=30, min_size=16, lines=1, color=WHITE):
    """Fit, clip and center dynamic text without drawing a backing rectangle."""
    value = _clean(value)
    if not value:
        return ""
    x1, y1, x2, y2 = (int(v) for v in bounds)
    if not (0 <= x1 < x2 <= image.width and 0 <= y1 < y2 <= image.height):
        raise ValueError(f"Invalid premium slot {bounds}")
    slot_w, slot_h = x2-x1, y2-y1
    layer = Image.new("RGBA", (slot_w, slot_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    margin = 8
    usable = max(1, slot_w - 2*margin)
    picked = None
    for px in range(size, max(10, min_size)-1, -1):
        face = _font(px)
        rows = _wrap(draw, value, face, usable, lines)
        line_height = int(px * 1.24)
        if len(rows) * line_height <= slot_h - 8 and all(
            _width(draw, row, face) <= usable for row in rows
        ):
            picked = (face, rows, line_height)
            break
    if picked is None:
        face = _font(max(10, min_size))
        lh = int(max(10, min_size) * 1.24)
        rows = _wrap(draw, value, face, usable, max(1, min(lines, (slot_h-8)//max(1, lh))))
        picked = (face, rows, lh)
    face, rows, line_height = picked
    start_y = max(0, (slot_h - line_height*len(rows))//2)
    for idx, row in enumerate(rows):
        row = _shorten(draw, row, face, usable)
        draw.text((slot_w//2, start_y+idx*line_height+line_height//2),
                  row, font=face, anchor="mm", fill=color)
    image.paste(layer, (x1, y1), layer)
    return "\n".join(rows)


def logo(image, url, bounds, required=False):
    """Place a real team logo using contain; never stretch or draw the circle."""
    url = _clean(url)
    if not url:
        if required:
            raise ValueError("Logo officiel manquant")
        return False
    from programme_styles import load_logo
    x1, y1, x2, y2 = bounds
    px = max(x2-x1, y2-y1)
    source = load_logo(url, px)
    if source is None:
        if required:
            raise ValueError("Logo officiel impossible à charger")
        return False
    source = source.convert("RGBA")
    source.thumbnail((x2-x1, y2-y1), Image.Resampling.LANCZOS)
    # Transparent logos only; preserve all original decorative masks/frames.
    image.paste(source, (x1+(x2-x1-source.width)//2,
                         y1+(y2-y1-source.height)//2), source)
    return True


def _pair(payload):
    v = payload.get("scores", payload.get("score"))
    if isinstance(v, (tuple, list)) and len(v) == 2:
        return str(v[0]), str(v[1])
    found = re.fullmatch(r"\s*(\d+)\s*[-–—:]\s*(\d+)\s*", str(v or ""))
    return (found.group(1), found.group(2)) if found else ("", "")


MATCH = {
    "kickoff": {
        "logos": ((85, 466, 284, 680), (846, 466, 1042, 680)),
        "names": ((60, 721, 467, 780), (656, 721, 1060, 780)),
        "score": ((412, 546, 533, 658), (601, 546, 724, 658)),
        "league": (360, 334, 834, 384), "time": (470, 839, 742, 890),
        "source": (246, 943, 888, 1006),
    },
    "goal": {
        "logos": ((78, 492, 281, 721), (838, 492, 1046, 721)),
        "names": None,
        "score": ((358, 539, 510, 717), (619, 539, 773, 717)),
        "scorer": (314, 806, 983, 923), "minute": (420, 990, 868, 1078),
        "league": (355, 1143, 947, 1194), "source": (294, 1155, 945, 1200),
    },
    "mi_temps": {
        "logos": ((179, 393, 393, 601), (727, 393, 940, 601)),
        "names": ((75, 648, 468, 706), (656, 648, 1048, 706)),
        "score": ((267, 750, 530, 899), (593, 750, 861, 899)),
        "league": (341, 939, 903, 1004), "time": (486, 935, 854, 1005),
    },
    "score_update": {
        "logos": ((119, 472, 317, 680), (804, 472, 1001, 680)),
        "names": ((53, 725, 412, 796), (717, 725, 1074, 796)),
        "score": ((421, 555, 531, 678), (603, 555, 711, 678)),
        "time": (429, 833, 754, 907),
        "league": (287, 953, 914, 1005), "source": (299, 953, 933, 1005),
    },
    "community_vote": {
        "logos": ((175, 280, 394, 491), (727, 280, 950, 491)),
        "names": ((85, 524, 480, 594), (640, 524, 1041, 594)),
        "league": (293, 638, 638, 699), "time": (762, 638, 969, 699),
        "question": (92, 757, 1034, 929),
        "options": ((73, 1125, 372, 1190), (411, 1125, 719, 1190), (755, 1125, 1052, 1190)),
    },
    "reaction": {
        "logos": ((138, 394, 301, 560), (826, 394, 989, 560)),
        "names": ((57, 589, 413, 654), (713, 589, 1069, 654)),
        "score": ((415, 473, 545, 610), (586, 473, 718, 610)),
        "league": (365, 337, 814, 390),
        "reaction": (93, 772, 1031, 1150),
    },
}


def render_premium(category: str, payload: dict[str, Any], path: Path) -> Image.Image:
    with Image.open(path) as source:
        original = ImageOps.exif_transpose(source).convert("RGB")
        if original.width < 900 or original.height < 1100:
            raise ValueError("Original Arty trop petit")
        original = ImageOps.fit(original, NATIVE, method=Image.Resampling.LANCZOS)
    img = original
    home = _clean(payload.get("home"), 100)
    away = _clean(payload.get("away"), 100)
    comp = _clean(payload.get("competition") or payload.get("league"), 100)
    source = _clean(payload.get("source"), 100)
    h, a = _pair(payload)

    if category == "composition":
        players_home = [_clean(p, 90) for p in payload.get("home_players") or []]
        players_away = [_clean(p, 90) for p in payload.get("away_players") or []]
        if len(players_home) != 11 or len(players_away) != 11 or not home or not away:
            raise ValueError("Compositions premium: équipes et 11 titulaires par équipe requis")
        logo(img, payload.get("home_logo"), (103, 97, 253, 253), required=True)
        logo(img, payload.get("away_logo"), (869, 97, 1019, 253), required=True)
        text(img, home, (37, 290, 361, 336), size=28, min_size=14)
        text(img, away, (758, 290, 1087, 336), size=28, min_size=14)
        text(img, comp + (" • " + _clean(payload.get("time"), 30) if payload.get("time") else ""),
             (373, 264, 745, 326), size=23, min_size=15, color=GOLD)
        for idx in range(11):
            y = 438 + 59*idx
            text(img, players_home[idx], (131, y, 484, y+47),
                 size=25, min_size=14)
            text(img, players_away[idx], (703, y, 1058, y+47),
                 size=25, min_size=14)
    elif category in MATCH:
        slots = MATCH[category]
        logos = slots["logos"]
        logo(img, payload.get("home_logo"), logos[0])
        logo(img, payload.get("away_logo"), logos[1])
        names = slots.get("names")
        if names:
            text(img, home, names[0], size=32, min_size=14)
            text(img, away, names[1], size=32, min_size=14)
        if slots.get("score"):
            if h and a:
                text(img, h, slots["score"][0], size=90, min_size=40, color=GOLD)
                text(img, a, slots["score"][1], size=90, min_size=40, color=GOLD)
        if category == "community_vote":
            text(img, payload.get("question"), slots["question"],
                 size=40, min_size=20, lines=3)
            for idx, option in enumerate((payload.get("options") or [])[:3]):
                text(img, re.sub(r"^[^\wÀ-ÿ]+", "", _clean(option)),
                     slots["options"][idx], size=24, min_size=14, lines=2)
        elif category == "goal":
            goal_data = payload.get("goal") or {}
            text(img, goal_data.get("player") or payload.get("scorer"),
                 slots["scorer"], size=38, min_size=19, lines=2)
            text(img, goal_data.get("minute_text") or payload.get("minute"),
                 slots["minute"], size=29, min_size=16)
        elif category == "reaction":
            text(img, payload.get("reaction") or payload.get("question") or payload.get("commentary"),
                 slots["reaction"], size=40, min_size=20, lines=8)
        else:
            if "time" in slots:
                text(img, payload.get("minute") or payload.get("time"),
                     slots["time"], size=29, min_size=16, color=GOLD)
            if "source" in slots:
                text(img, source or payload.get("status"),
                     slots["source"], size=21, min_size=14)
        if category not in ("goal", "reaction") and "league" in slots:
            text(img, comp, slots["league"], size=23, min_size=14, color=GOLD)
        elif category == "reaction":
            text(img, comp, slots["league"], size=22, min_size=14, color=GOLD)
        elif category == "goal":
            text(img, comp or source, slots["league"], size=22, min_size=13, color=GOLD)
    elif category == "statistique_avancee":
        text(img, payload.get("headline") or payload.get("title"),
             (121, 212, 1007, 310), size=41, min_size=20, lines=2)
        text(img, comp or source, (181, 342, 947, 394),
             size=27, min_size=16, color=GOLD)
        value = payload.get("value") or payload.get("stat_value") or payload.get("stat")
        text(img, value, (135, 478, 984, 830), size=126, min_size=43, lines=3, color=GOLD)
        for idx, metric in enumerate((payload.get("lines") or payload.get("metrics") or [])[:4]):
            x = 98 + 504*(idx % 2)
            y = 979 + 184*(idx // 2)
            text(img, metric, (x, y, x+426, y+97), size=28, min_size=17, lines=2)
    elif category == "quiz":
        text(img, payload.get("question"), (108, 352, 1014, 637),
             size=50, min_size=23, lines=5)
        for idx, option in enumerate((payload.get("options") or [])[:4]):
            x = 195 if idx%2 == 0 else 699
            y = 740 if idx//2 == 0 else 903
            text(img, f"{'ABCD'[idx]}. {_clean(option)}",
                 (x, y, x+348, y+96), size=25, min_size=15, lines=2)
        text(img, source, (203, 1069, 1010, 1128), size=22, min_size=14)
    elif category == "debat":
        text(img, payload.get("question") or payload.get("headline"),
             (86, 377, 1029, 684), size=50, min_size=24, lines=5)
        text(img, payload.get("summary") or payload.get("description"),
             (95, 839, 1015, 1108), size=35, min_size=19, lines=6)
        text(img, source, (105, 1210, 1023, 1255), size=23, min_size=14)
    else:
        raise ValueError(f"Original Arty non supporté: {category}")

    return img.resize(OUTPUT, Image.Resampling.LANCZOS)
