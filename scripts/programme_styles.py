"""7 styles code-friendly pour la carte 'Matchs du jour' de Mr XPRONOS.

Rotation: lundi=1 ... dimanche=7. Chaque style est compose de modules simples
(header, date, rows, footer) afin de pouvoir faire evoluer les visuels sans
reconstruire tout le moteur.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import re

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
    "real madrid": ("#F7F7F3", "#D7B56D"),
    "barcelona": ("#143C8C", "#A5163A"),
    "psg": ("#0B1F5B", "#D81E36"),
    "marseille": ("#F6F8F8", "#43A9D6"),
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


def background(style: int):
    image = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(image)
    # Shared geometric stadium atmosphere; every primitive is code-reproducible.
    for y in range(H):
        t = y / H
        c = (
            int(6 + 6*t),
            int(19 + 16*t),
            int(31 + 23*t),
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
        d.rounded_rectangle((36, 320, 1044, 910), radius=34, fill="#0A1C29", outline="#466273", width=2)
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


def header(d: ImageDraw.ImageDraw, style: int, day: str):
    # Brand
    text(d, "♛", (540, 34), size=30, bold=True, fill=GOLD, anchor="ma")
    text(d, "MR XPRONOS", (540, 62), size=30, bold=True, fill=WHITE, anchor="ma")
    d.line((315, 75, 410, 75), fill=GOLD2, width=2)
    d.line((670, 75, 765, 75), fill=GOLD2, width=2)
    # Title
    text(d, "MATCHS", (530, 112), size=74, bold=True, fill=WHITE, anchor="ra")
    text(d, "DU JOUR", (550, 112), size=74, bold=True, fill=GOLD, anchor="la")
    text(d, "LES RENDEZ-VOUS A NE PAS MANQUER", (540, 202), size=21, bold=True,
         fill=GREY, anchor="ma")
    # Date module varies slightly by style but stays componentized.
    if style in (4, 7):
        pts = [(327,235),(753,235),(783,269),(753,303),(327,303),(297,269)]
        d.polygon(pts, fill="#0B2436", outline=GOLD)
    else:
        d.rounded_rectangle((310, 235, 770, 303), radius=30, fill="#0A2030", outline=GOLD, width=2)
    # Calendar icon
    d.rounded_rectangle((345, 250, 382, 287), radius=5, outline=GOLD, width=2)
    d.line((345,260,382,260), fill=GOLD, width=2)
    d.line((354,244,354,255), fill=GOLD, width=3)
    d.line((373,244,373,255), fill=GOLD, width=3)
    text(d, day.upper(), (410, 269), size=26, bold=True, anchor="lm", width=325)


def footer(d: ImageDraw.ImageDraw, style: int):
    y = 930 if style != 5 else 916
    d.line((310, y, 430, y), fill=GOLD2, width=2)
    d.ellipse((465, y-17, 499, y+17), outline=GOLD, width=2)
    d.line((482,y,482,y-9), fill=GOLD, width=2)
    d.line((482,y,491,y+4), fill=GOLD, width=2)
    text(d, "Heure du Togo (GMT)", (520, y), size=20, fill=GREY, anchor="lm")
    d.line((760, y, 875, y), fill=GOLD2, width=2)
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


def match_texts(d, item, y, *, home_x=338, away_x=742, center=540, name_width=255,
                time_fill=GOLD, time_text=NAVY):
    text(d, item.get("home",""), (home_x,y), size=27, bold=True, anchor="mm",
         width=name_width, min_size=17)
    text(d, item.get("away",""), (away_x,y), size=27, bold=True, anchor="mm",
         width=name_width, min_size=17)
    d.rounded_rectangle((center-72,y-26,center+72,y+20), radius=12, fill=time_fill)
    text(d, item.get("time","--h--"), (center,y-3), size=25, bold=True, fill=time_text, anchor="mm")
    text(d, "VS", (center,y+31), size=15, bold=True, fill=GOLD, anchor="mm")


def rows_style_1(d, rows):
    """Broadcast luxury: long rounded capsules."""
    y0=370
    for i,item in enumerate(rows[:5]):
        y=y0+i*105
        d.rounded_rectangle((64,y-43,1016,y+43), radius=32, fill="#0A2234", outline=GOLD, width=2)
        jersey(d, 112, y, item.get("home",""), scale=.83)
        jersey(d, 968, y, item.get("away",""), scale=.83)
        match_texts(d,item,y,home_x=330,away_x=750,name_width=275)


def rows_style_2(d, rows):
    """Editorial minimal: circular kit badges, thin separators, lots of breathing room."""
    y0=365
    for i,item in enumerate(rows[:5]):
        y=y0+i*108
        d.rounded_rectangle((82,y-45,998,y+45), radius=28, fill="#081B28", outline="#4B6575", width=1)
        jersey(d, 130,y,item.get("home",""),scale=.72,circle=True)
        jersey(d, 950,y,item.get("away",""),scale=.72,circle=True)
        d.line((480,y-28,480,y+28),fill=GOLD2,width=1)
        d.line((600,y-28,600,y+28),fill=GOLD2,width=1)
        match_texts(d,item,y,home_x=325,away_x=755,name_width=270)


def rows_style_3(d, rows):
    """Glass: one translucent-looking container with separated rows."""
    # fake glass on RGB: layered blue panels + highlights
    d.rounded_rectangle((60,330,1020,894),radius=34,fill="#132D3D",outline="#718896",width=2)
    d.rounded_rectangle((75,345,1005,879),radius=28,outline="#2E556C",width=1)
    y0=382
    for i,item in enumerate(rows[:5]):
        y=y0+i*101
        if i:
            d.line((95,y-51,985,y-51),fill="#486474",width=1)
        jersey(d,125,y,item.get("home",""),scale=.72)
        jersey(d,955,y,item.get("away",""),scale=.72)
        match_texts(d,item,y,home_x=335,away_x=745,name_width=270,
                    time_fill="#E8B84E")


def rows_style_4(d, rows):
    """Futuristic dashboard: angled tech rows."""
    y0=370
    for i,item in enumerate(rows[:5]):
        y=y0+i*104
        pts=[(65,y-42),(95,y-50),(985,y-50),(1015,y-42),(990,y+44),(90,y+44)]
        d.polygon(pts,fill="#0A2233",outline=GOLD)
        d.line((65,y-42,130,y-42),fill="#22A7F0",width=3)
        d.line((950,y+44,1015,y+44),fill="#22A7F0",width=3)
        jersey(d,115,y,item.get("home",""),scale=.7)
        jersey(d,965,y,item.get("away",""),scale=.7)
        # Hexagonal time module
        t=[(500,y-29),(580,y-29),(595,y-4),(580,y+21),(500,y+21),(485,y-4)]
        d.polygon(t,fill=GOLD)
        text(d,item.get("time",""),(540,y-4),size=24,bold=True,fill=NAVY,anchor="mm")
        text(d,"VS",(540,y+31),size=14,bold=True,fill=GOLD,anchor="mm")
        text(d,item.get("home",""),(330,y),size=26,bold=True,anchor="mm",width=260,min_size=17)
        text(d,item.get("away",""),(750,y),size=26,bold=True,anchor="mm",width=260,min_size=17)


def rows_style_5(d, rows):
    """Magazine: stronger central spine and numbered fixtures."""
    y0=360
    d.line((540,330,540,875),fill=GOLD2,width=2)
    for i,item in enumerate(rows[:5]):
        y=y0+i*106
        d.rounded_rectangle((70,y-42,1010,y+42),radius=18,fill="#0A1E2E",outline="#3E596B",width=1)
        text(d,str(i+1).zfill(2),(94,y),size=20,bold=True,fill=GOLD,anchor="mm")
        jersey(d,145,y,item.get("home",""),scale=.66)
        jersey(d,935,y,item.get("away",""),scale=.66)
        text(d,item.get("home",""),(330,y),size=26,bold=True,anchor="mm",width=255,min_size=17)
        text(d,item.get("away",""),(750,y),size=26,bold=True,anchor="mm",width=255,min_size=17)
        d.rounded_rectangle((486,y-25,594,y+22),radius=8,fill=GOLD)
        text(d,item.get("time",""),(540,y-2),size=23,bold=True,fill=NAVY,anchor="mm")


def rows_style_6(d, rows):
    """Luxury card stack: thicker shadows and individual elevated cards."""
    y0=365
    for i,item in enumerate(rows[:5]):
        y=y0+i*106
        d.rounded_rectangle((75,y-39,1017,y+51),radius=28,fill="#031019")
        d.rounded_rectangle((63,y-47,1005,y+43),radius=28,fill="#0D2A3C",outline=GOLD,width=2)
        jersey(d,120,y-2,item.get("home",""),scale=.74)
        jersey(d,948,y-2,item.get("away",""),scale=.74)
        match_texts(d,item,y-2,home_x=325,away_x=750,name_width=275)


def rows_style_7(d, rows):
    """Split-panel: left/right team fields meet at a strong central time block."""
    y0=370
    for i,item in enumerate(rows[:5]):
        y=y0+i*104
        d.rounded_rectangle((66,y-43,1014,y+43),radius=28,fill="#091E2C",outline=GOLD,width=2)
        d.polygon([(470,y-42),(540,y-42),(515,y+42),(445,y+42)],fill="#103752")
        d.polygon([(540,y-42),(610,y-42),(635,y+42),(565,y+42)],fill="#103752")
        jersey(d,112,y,item.get("home",""),scale=.7)
        jersey(d,968,y,item.get("away",""),scale=.7)
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
    header(d,style,clean(payload.get("day","")))
    ROW_RENDERERS[style](d,rows)
    footer(d,style)
    # Discreet style marker only in metadata-like footer, useful in QA.
    text(d,"STYLE "+str(style),(1018,1056),size=13,fill="#5D7585",anchor="ra")
    return image
