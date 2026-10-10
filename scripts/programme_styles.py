"""7 styles code-friendly pour la carte 'Matchs du jour' de Mr XPRONOS.

Rotation: lundi=1 ... dimanche=7. Chaque style est compose de modules simples
(header, date, rows, footer) afin de pouvoir faire evoluer les visuels sans
reconstruire tout le moteur.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import io
import re

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W = H = 1080
NAVY = "#06131F"
NAVY2 = "#0B2133"
NAVY3 = "#102D43"
BLUE = "#144A70"
GOLD = "#F1C55A"
GOLD2 = "#D99D2B"
WHITE = "#F7F9FC"
GREY = "#A9BAC6"
LINE = "#375266"

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

TEAM_COLORS = {
    "arsenal": ("#D71920", "#F4F4F4"),
    "chelsea": ("#034694", "#0E68C7"),
    "manchester united": ("#DA291C", "#111111"),
    "tottenham": ("#F7F7F7", "#132257"),
    "real madrid": ("#F7F7F3", "#D7B56D"),
    "barcelona": ("#143C8C", "#A5163A"),
    "getafe": ("#0A4AA1", "#66A7E8"),
    "psg": ("#0B1F5B", "#D81E36"),
    "paris saint-germain": ("#0B1F5B", "#D81E36"),
    "marseille": ("#F6F8F8", "#43A9D6"),
    "le mans": ("#F2C500", "#D71920"),
    "villarreal": ("#F4D500", "#2458A6"),
    "porto": ("#F6F7F8", "#1650A8"),
    "maritimo": ("#16713C", "#D3212D"),
    "marítimo": ("#16713C", "#D3212D"),
    "napoli": ("#4AA8DF", "#FFFFFF"),
    "ajax": ("#F7F7F7", "#D2122E"),
    "nijmegen": ("#D71920", "#151515"),
    "nec": ("#D71920", "#151515"),
    "bayern": ("#D0021B", "#9E071C"),
    "dortmund": ("#F6D400", "#171717"),
    "inter": ("#071A42", "#0F76CB"),
    "ac milan": ("#B90E1C", "#111111"),
}


def font(size: int, bold: bool = False):
    for p in (FONT_BOLD if bold else FONT_REG):
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def clean(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "").strip())


def fit(draw: ImageDraw.ImageDraw, value: Any, width: int, size: int, min_size: int = 17,
        bold: bool = True):
    raw = clean(value)
    for n in range(size, min_size - 1, -1):
        f = font(n, bold)
        if draw.textbbox((0, 0), raw, font=f)[2] <= width:
            return raw, f
    f = font(min_size, bold)
    text = raw
    while len(text) > 2 and draw.textbbox((0, 0), text + "…", font=f)[2] > width:
        text = text[:-1]
    return text.rstrip() + "…", f


def text(draw, value, xy, *, size=28, bold=False, fill=WHITE, anchor="la", width=None,
         min_size=17):
    if width:
        value, f = fit(draw, value, width, size, min_size, bold)
    else:
        value, f = clean(value), font(size, bold)
    draw.text(xy, value, fill=fill, font=f, anchor=anchor)


def team_colors(name: str):
    n = clean(name).casefold()
    for key, colors in TEAM_COLORS.items():
        if key in n:
            return colors
    return ("#466172", "#89A2B1")


def jersey(draw: ImageDraw.ImageDraw, cx: int, cy: int, team: str, *, scale=1.0,
           circle=False):
    primary, secondary = team_colors(team)
    if circle:
        r = int(42 * scale)
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill="#081A28", outline=GOLD, width=max(1,int(2*scale)))
    s = scale
    # Simple t-shirt: easy to replace later with an image/crest.
    pts = [
        (cx-23*s, cy-26*s), (cx-47*s, cy-12*s), (cx-36*s, cy+2*s),
        (cx-25*s, cy-4*s), (cx-23*s, cy+31*s), (cx+23*s, cy+31*s),
        (cx+25*s, cy-4*s), (cx+36*s, cy+2*s), (cx+47*s, cy-12*s),
        (cx+23*s, cy-26*s), (cx+12*s, cy-19*s), (cx-12*s, cy-19*s),
    ]
    draw.polygon([(int(x), int(y)) for x,y in pts], fill=primary, outline=WHITE)
    draw.rectangle((int(cx-5*s), int(cy-19*s), int(cx+5*s), int(cy+31*s)), fill=secondary)
    draw.arc((int(cx-11*s), int(cy-27*s), int(cx+11*s), int(cy-11*s)), 0, 180,
             fill="#E7EDF2", width=max(1,int(2*s)))



_LOGO_CACHE: dict[str, Image.Image | None] = {}

def gold_gradient(size: tuple[int, int]) -> Image.Image:
    w, h = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    stops = (
        (255, 244, 174),
        (249, 213, 98),
        (225, 163, 44),
        (255, 232, 135),
    )
    for y in range(h):
        t = y / max(1, h - 1)
        if t < 0.34:
            a, b, u = stops[0], stops[1], t / 0.34
        elif t < 0.72:
            a, b, u = stops[1], stops[2], (t - 0.34) / 0.38
        else:
            a, b, u = stops[2], stops[3], (t - 0.72) / 0.28
        color = tuple(int(a[i] * (1-u) + b[i] * u) for i in range(3))
        draw.line((0, y, w, y), fill=color)
    return image


def gradient_round_rect(image: Image.Image, box: tuple[int, int, int, int],
                        radius: int, outline: str = "#FFE19A", width: int = 1) -> None:
    x1, y1, x2, y2 = box
    mask = Image.new("L", (x2-x1, y2-y1), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, x2-x1-1, y2-y1-1), radius=radius, fill=255)
    image.paste(gold_gradient((x2-x1, y2-y1)), (x1, y1), mask)
    ImageDraw.Draw(image).rounded_rectangle(box, radius=radius, outline=outline, width=width)


def gradient_outline_round_rect(image: Image.Image, box: tuple[int, int, int, int],
                                radius: int, width: int = 3, glow: bool = False) -> None:
    x1, y1, x2, y2 = box
    bw, bh = x2-x1, y2-y1
    outer = Image.new("L", (bw, bh), 0)
    od = ImageDraw.Draw(outer)
    od.rounded_rectangle((0, 0, bw-1, bh-1), radius=radius, fill=255)
    inner = Image.new("L", (bw, bh), 0)
    idr = ImageDraw.Draw(inner)
    inset = max(1, width)
    idr.rounded_rectangle((inset, inset, bw-1-inset, bh-1-inset),
                          radius=max(1, radius-inset), fill=255)
    # Border mask = outer - inner.
    border = Image.new("L", (bw, bh), 0)
    bp = border.load(); op = outer.load(); ip = inner.load()
    for yy in range(bh):
        for xx in range(bw):
            bp[xx, yy] = max(0, op[xx, yy] - ip[xx, yy])
    if glow:
        glow_mask = border.filter(ImageFilter.GaussianBlur(8))
        glow_layer = Image.new("RGBA", image.size, (0,0,0,0))
        glow_color = Image.new("RGBA", (bw,bh), (247,190,63,100))
        glow_layer.paste(glow_color, (x1,y1), glow_mask)
        image.paste(glow_layer, (0,0), glow_layer)
    image.paste(gold_gradient((bw,bh)), (x1,y1), border)


def gradient_text(image: Image.Image, value: Any, xy: tuple[int, int], *,
                  size: int, anchor: str = "la") -> None:
    value = clean(value)
    face = font(size, True)
    base = ImageDraw.Draw(image)
    bbox = base.textbbox(xy, value, font=face, anchor=anchor)
    x1, y1, x2, y2 = bbox
    pad = 4
    mask = Image.new("L", (max(1, x2-x1+pad*2), max(1, y2-y1+pad*2)), 0)
    md = ImageDraw.Draw(mask)
    md.text((pad-x1+xy[0], pad-y1+xy[1]), value, font=face, fill=255, anchor=anchor)
    image.paste(gold_gradient(mask.size), (x1-pad, y1-pad), mask)


def load_logo(url: str, max_px: int = 82) -> Image.Image | None:
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        return None
    if url in _LOGO_CACHE:
        cached = _LOGO_CACHE[url]
        return cached.copy() if cached else None
    try:
        response = requests.get(
            url, timeout=(5, 10),
            headers={"User-Agent": "MrXPRONOS-card/1.0"},
        )
        response.raise_for_status()
        if len(response.content) > 3_000_000:
            raise ValueError("logo too large")
        logo = Image.open(io.BytesIO(response.content)).convert("RGBA")
        logo.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
        _LOGO_CACHE[url] = logo.copy()
        return logo
    except Exception:
        _LOGO_CACHE[url] = None
        return None


def team_visual(image: Image.Image, draw: ImageDraw.ImageDraw, cx: int, cy: int,
                item: dict[str, Any], side: str, *, scale: float = .75,
                circle: bool = False) -> None:
    logo = load_logo(clean(item.get(side + "_logo", "")), int(92 * scale))
    if logo:
        if circle:
            r = int(48 * scale)
            draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill="#071723", outline=GOLD, width=2)
        image.paste(logo, (cx-logo.width//2, cy-logo.height//2), logo)
    else:
        jersey(draw, cx, cy, item.get(side, ""), scale=scale, circle=circle)

def background(style: int):
    image = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(image)
    # Deep navy/blue gradient, richer than a flat fill but still deterministic.
    for y in range(H):
        t = y / H
        glow = max(0.0, 1.0 - abs(t - 0.42) * 2.3)
        c = (
            int(3 + 6*t),
            int(16 + 28*t + 5*glow),
            int(34 + 50*t + 16*glow),
        )
        d.line((0, y, W, y), fill=c)
    if style in (1, 5):
        d.polygon([(0,0),(250,0),(90,420),(0,520)], fill="#0B2840")
        d.polygon([(1080,0),(830,0),(990,420),(1080,520)], fill="#0B2840")
    elif style == 2:
        for x in range(0, W, 70):
            d.line((x, 0, x-230, H), fill="#0D2A3E", width=1)
    elif style == 3:
        for r in (520, 430, 340):
            d.arc((540-r, 720-r//3, 540+r, 720+r//3), 190, 350, fill="#17435B", width=3)
    elif style == 4:
        for x in range(70, 1010, 120):
            d.line((x, 90, x+80, 990), fill="#0E3854", width=1)
        for y in range(130, 960, 90):
            d.line((55, y, 1025, y), fill="#0B3049", width=1)
    elif style == 6:
        d.polygon([(0,0),(180,0),(62,355),(0,420)], fill="#0A3159")
        d.polygon([(1080,0),(900,0),(1018,355),(1080,420)], fill="#0A3159")
        d.polygon([(0,720),(110,820),(60,1080),(0,1080)], fill="#082746")
        d.polygon([(1080,720),(970,820),(1020,1080),(1080,1080)], fill="#082746")
        d.rounded_rectangle((38, 315, 1042, 908), radius=34,
                            fill="#071A29", outline="#6F5420", width=2)
    elif style == 7:
        d.polygon([(0,0),(1080,0),(980,310),(100,310)], fill="#081B2A")
        d.polygon([(0,900),(1080,900),(1080,1080),(0,1080)], fill="#081C2B")
    # Stadium light bars.
    for i in range(7):
        y = 930 + i*18
        alpha = 95 - i*10
        col = (max(20, alpha), max(45, alpha+5), max(65, alpha+20))
        d.arc((-220, y-110, 1300, y+160), 190, 350, fill=col, width=2)
    # Gold corner strokes.
    d.line((0, 100, 160, 0), fill=GOLD2, width=5)
    d.line((1080, 100, 920, 0), fill=GOLD2, width=5)
    return image, d


def header(image: Image.Image, d: ImageDraw.ImageDraw, style: int, day: str):
    # Brand
    text(d, "♛", (540, 34), size=30, bold=True, fill=GOLD, anchor="ma")
    text(d, "MR", (495, 62), size=30, bold=True, fill=WHITE, anchor="ra")
    gradient_text(image, "XPRONOS", (505, 62), size=30, anchor="la")
    d.line((315, 75, 410, 75), fill=GOLD2, width=2)
    d.line((670, 75, 765, 75), fill=GOLD2, width=2)
    # Title
    text(d, "MATCHS", (530, 112), size=74, bold=True, fill=WHITE, anchor="ra")
    gradient_text(image, "DU JOUR", (550, 112), size=74, anchor="la")
    text(d, "LES RENDEZ-VOUS A NE PAS MANQUER", (540, 202), size=21, bold=True,
         fill=GREY, anchor="ma")
    # Date module varies slightly by style but stays componentized.
    if style in (4, 7):
        pts = [(327,235),(753,235),(783,269),(753,303),(327,303),(297,269)]
        d.polygon(pts, fill="#0B2436", outline=GOLD)
    else:
        d.rounded_rectangle((325, 235, 755, 303), radius=30, fill="#0A2030", outline=GOLD, width=2)
    # Calendar icon + date are centered as a single group.
    d.rounded_rectangle((392, 250, 429, 287), radius=5, outline=GOLD, width=2)
    d.line((392,260,429,260), fill=GOLD, width=2)
    d.line((401,244,401,255), fill=GOLD, width=3)
    d.line((420,244,420,255), fill=GOLD, width=3)
    text(d, day.upper(), (565, 269), size=25, bold=True, anchor="mm", width=250)


def footer(d: ImageDraw.ImageDraw, style: int):
    y = 930 if style != 5 else 916
    d.line((275, y, 405, y), fill=GOLD2, width=2)
    d.ellipse((425, y-17, 459, y+17), outline=GOLD, width=2)
    d.line((442,y,442,y-9), fill=GOLD, width=2)
    d.line((442,y,451,y+4), fill=GOLD, width=2)
    text(d, "Heure du Togo (GMT)", (565, y), size=20, fill=GREY, anchor="mm")
    d.line((720, y, 850, y), fill=GOLD2, width=2)
    if style == 4:
        box = [(230,964),(850,964),(880,1003),(850,1042),(230,1042),(200,1003)]
        d.polygon(box, fill="#0A2030", outline=GOLD)
    else:
        d.rounded_rectangle((190, 964, 890, 1042), radius=34, fill="#091E2D", outline=GOLD, width=2)
    # comment bubble
    d.rounded_rectangle((230, 987, 270, 1018), radius=10, outline=GOLD, width=3)
    d.polygon([(242,1018),(240,1028),(252,1018)], fill=GOLD)
    text(d, "QUEL MATCH ATTENDEZ-VOUS LE PLUS ?", (295, 1003), size=22, bold=True,
         width=560, anchor="lm")


def match_texts(image, d, item, y, *, home_x=338, away_x=742, center=540, name_width=255,
                time_fill=GOLD, time_text=NAVY):
    text(d, item.get("home",""), (home_x,y), size=27, bold=True, anchor="mm",
         width=name_width, min_size=17)
    text(d, item.get("away",""), (away_x,y), size=27, bold=True, anchor="mm",
         width=name_width, min_size=17)
    gradient_round_rect(image, (center-58,y-22,center+58,y+16), 10)
    text(d, item.get("time","--h--"), (center,y-3), size=21, bold=True, fill=time_text, anchor="mm")
    text(d, "VS", (center,y+31), size=19, bold=True, fill=GOLD, anchor="mm")


def rows_style_1(image, d, rows):
    """Broadcast luxury: long rounded capsules."""
    y0=370
    for i,item in enumerate(rows[:5]):
        y=y0+i*105
        d.rounded_rectangle((64,y-43,1016,y+43), radius=32, fill="#0A2234", outline=GOLD, width=2)
        team_visual(image, d, 112, y, item, "home", scale=.83)
        team_visual(image, d, 968, y, item, "away", scale=.83)
        match_texts(image,d,item,y,home_x=330,away_x=750,name_width=275)


def rows_style_2(image, d, rows):
    """Editorial minimal: circular kit badges, thin separators, lots of breathing room."""
    y0=365
    for i,item in enumerate(rows[:5]):
        y=y0+i*108
        d.rounded_rectangle((82,y-45,998,y+45), radius=28, fill="#081B28", outline="#4B6575", width=1)
        team_visual(image, d, 130, y, item, "home", scale=.72, circle=True)
        team_visual(image, d, 950, y, item, "away", scale=.72, circle=True)
        d.line((480,y-28,480,y+28),fill=GOLD2,width=1)
        d.line((600,y-28,600,y+28),fill=GOLD2,width=1)
        match_texts(image,d,item,y,home_x=325,away_x=755,name_width=270)


def rows_style_3(image, d, rows):
    """Glass: one translucent-looking container with separated rows."""
    # fake glass on RGB: layered blue panels + highlights
    d.rounded_rectangle((60,330,1020,894),radius=34,fill="#132D3D",outline="#718896",width=2)
    d.rounded_rectangle((75,345,1005,879),radius=28,outline="#2E556C",width=1)
    y0=382
    for i,item in enumerate(rows[:5]):
        y=y0+i*101
        if i:
            d.line((95,y-51,985,y-51),fill="#486474",width=1)
        team_visual(image, d, 125, y, item, "home", scale=.72)
        team_visual(image, d, 955, y, item, "away", scale=.72)
        match_texts(image,d,item,y,home_x=335,away_x=745,name_width=270,
                    time_fill="#E8B84E")


def rows_style_4(image, d, rows):
    """Futuristic dashboard: angled tech rows."""
    y0=370
    for i,item in enumerate(rows[:5]):
        y=y0+i*104
        pts=[(65,y-42),(95,y-50),(985,y-50),(1015,y-42),(990,y+44),(90,y+44)]
        d.polygon(pts,fill="#0A2233",outline=GOLD)
        d.line((65,y-42,130,y-42),fill="#22A7F0",width=3)
        d.line((950,y+44,1015,y+44),fill="#22A7F0",width=3)
        team_visual(image, d, 115, y, item, "home", scale=.7)
        team_visual(image, d, 965, y, item, "away", scale=.7)
        # Hexagonal time module
        t=[(500,y-29),(580,y-29),(595,y-4),(580,y+21),(500,y+21),(485,y-4)]
        d.polygon(t,fill=GOLD)
        text(d,item.get("time",""),(540,y-4),size=24,bold=True,fill=NAVY,anchor="mm")
        text(d,"VS",(540,y+31),size=14,bold=True,fill=GOLD,anchor="mm")
        text(d,item.get("home",""),(330,y),size=26,bold=True,anchor="mm",width=260,min_size=17)
        text(d,item.get("away",""),(750,y),size=26,bold=True,anchor="mm",width=260,min_size=17)


def rows_style_5(image, d, rows):
    """Magazine: stronger central spine and numbered fixtures."""
    y0=360
    d.line((540,330,540,875),fill=GOLD2,width=2)
    for i,item in enumerate(rows[:5]):
        y=y0+i*106
        d.rounded_rectangle((70,y-42,1010,y+42),radius=18,fill="#0A1E2E",outline="#3E596B",width=1)
        text(d,str(i+1).zfill(2),(94,y),size=20,bold=True,fill=GOLD,anchor="mm")
        team_visual(image, d, 145, y, item, "home", scale=.66)
        team_visual(image, d, 935, y, item, "away", scale=.66)
        text(d,item.get("home",""),(330,y),size=26,bold=True,anchor="mm",width=255,min_size=17)
        text(d,item.get("away",""),(750,y),size=26,bold=True,anchor="mm",width=255,min_size=17)
        d.rounded_rectangle((486,y-25,594,y+22),radius=8,fill=GOLD)
        text(d,item.get("time",""),(540,y-2),size=23,bold=True,fill=NAVY,anchor="mm")


def rows_style_6(image, d, rows):
    """Saturday premium card stack, close to the approved visual mockup."""
    y0=365
    for i,item in enumerate(rows[:5]):
        y=y0+i*106
        d.rounded_rectangle((74,y-38,1016,y+52),radius=30,fill="#020B13")
        d.rounded_rectangle((61,y-48,1003,y+42),radius=30,fill="#06192A")
        gradient_outline_round_rect(image,(61,y-48,1003,y+42),30,width=3,glow=True)
        d.line((95,y-42,968,y-42),fill="#FFF0BE",width=1)
        d.line((472,y-29,472,y+24),fill="#A87523",width=1)
        d.line((608,y-29,608,y+24),fill="#A87523",width=1)
        team_visual(image, d, 116, y-3, item, "home", scale=.82)
        team_visual(image, d, 948, y-3, item, "away", scale=.82)
        match_texts(image,d,item,y-3,home_x=330,away_x=750,name_width=268)


def rows_style_7(image, d, rows):
    """Split-panel: left/right team fields meet at a strong central time block."""
    y0=370
    for i,item in enumerate(rows[:5]):
        y=y0+i*104
        d.rounded_rectangle((66,y-43,1014,y+43),radius=28,fill="#091E2C",outline=GOLD,width=2)
        d.polygon([(470,y-42),(540,y-42),(515,y+42),(445,y+42)],fill="#103752")
        d.polygon([(540,y-42),(610,y-42),(635,y+42),(565,y+42)],fill="#103752")
        team_visual(image, d, 112, y, item, "home", scale=.7)
        team_visual(image, d, 968, y, item, "away", scale=.7)
        text(d,item.get("home",""),(318,y),size=26,bold=True,anchor="mm",width=270,min_size=17)
        text(d,item.get("away",""),(762,y),size=26,bold=True,anchor="mm",width=270,min_size=17)
        d.rounded_rectangle((490,y-27,590,y+17),radius=10,fill=GOLD)
        text(d,item.get("time",""),(540,y-5),size=22,bold=True,fill=NAVY,anchor="mm")
        text(d,"VS",(540,y+30),size=14,bold=True,fill=GOLD,anchor="mm")


ROW_RENDERERS={
    1: rows_style_1, 2: rows_style_2, 3: rows_style_3, 4: rows_style_4,
    5: rows_style_5, 6: rows_style_6, 7: rows_style_7,
}


def parse_day(value: str):
    value=clean(value)
    for fmt in ("%d/%m/%Y","%Y-%m-%d"):
        try:
            return datetime.strptime(value,fmt).date()
        except ValueError:
            pass
    return None


def style_for_day(day: str) -> int:
    parsed=parse_day(day)
    return (parsed.weekday()+1) if parsed else 1


def render_programme(payload: dict[str, Any], *, style: int | None = None) -> Image.Image:
    rows=payload.get("matches") or []
    if not rows:
        raise ValueError("Programme sans matchs")
    if style is None:
        raw=payload.get("style")
        style=int(raw) if raw is not None else style_for_day(clean(payload.get("day","")))
    if style not in ROW_RENDERERS:
        raise ValueError("Style programme invalide: "+str(style))
    image,d=background(style)
    header(image,d,style,clean(payload.get("day","")))
    ROW_RENDERERS[style](image,d,rows)
    footer(d,style)
    return image
