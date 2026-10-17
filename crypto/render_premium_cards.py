"""Cartes Telegram Actu Crypto (1080 x 1350) - rendu gratuit 100 % Pillow."""
from __future__ import annotations

from datetime import datetime
from math import cos, radians, sin
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
WHITE = (247, 250, 255)
MUTED = (180, 198, 219)
GREEN = (35, 202, 133)
RED = (251, 86, 107)
AMBER = (248, 170, 35)
NAVY = (10, 20, 39)
PANEL = (22, 39, 64)
CYAN = (104, 205, 255)
COINS = {"BTC": (243, 155, 36), "ETH": (95, 111, 230),
         "SOL": (67, 193, 189), "BNB": (238, 185, 53),
         "XRP": (95, 127, 165)}

def font(size, bold=False):
    names = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()

def txt(d, x, y, value, size=28, color=WHITE, bold=False, anchor=None, max_width=None):
    value = str(value)
    while size > 15 and max_width and d.textbbox((0, 0), value, font=font(size, bold))[2] > max_width:
        size -= 1
    d.text((x, y), value, fill=color, font=font(size, bold), anchor=anchor)

def bg():
    im = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    for y in range(H):
        q = y / H
        d.line((0, y, W, y), fill=(int(9 + 10*q), int(20 + 21*q), int(38 + 28*q)))
    d.ellipse((750, -220, 1300, 360), fill=(26, 54, 89))
    d.ellipse((-400, 950, 230, 1560), fill=(26, 46, 76))
    d.rounded_rectangle((44, 44, 1036, 1306), radius=38, outline=(58, 83, 116), width=2)
    return im, d

def title(d, heading, kicker, now):
    txt(d, 82, 100, "ACTU CRYPTO", 33, CYAN, True)
    txt(d, 82, 158, kicker.upper(), 22, MUTED, True)
    txt(d, 82, 214, heading, 47, WHITE, True, max_width=905)
    txt(d, 82, 275, now.strftime("%d/%m/%Y   •   %H:%M UTC"), 26, MUTED)
    d.line((82, 315, 998, 315), fill=(64, 86, 119), width=2)

def footer(d, source, note):
    d.line((82, 1210, 998, 1210), fill=(64, 86, 119), width=2)
    txt(d, 82, 1234, note, 22, MUTED, max_width=920)
    txt(d, 82, 1270, "SOURCE : " + source, 20, CYAN)

def save(im, p):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    im.save(p, format="PNG", optimize=True)
    return p

def usd(v):
    return (f"${v:,.2f}".replace(",", " ") if v >= 1000
            else f"${v:.2f}" if v >= 1
            else f"${v:.6f}".rstrip("0").rstrip("."))

def percent(v):
    return f"{v:+.2f}%"

def coin(d, symbol, x, y, radius=37):
    color = COINS.get(symbol, (51, 115, 190))
    d.ellipse((x-radius, y-radius, x+radius, y+radius), fill=color)
    txt(d, x, y-1, symbol, 22 if len(symbol) > 3 else 25, WHITE, True, "mm")

def pill(d, x, y, change, width=148):
    color = GREEN if change >= 0 else RED
    d.rounded_rectangle((x, y, x+width, y+48), radius=24, fill=color)
    txt(d, x+width/2, y+24, percent(change), 25, WHITE, True, "mm")

def bar(d, x, y, width, change, scale):
    d.rounded_rectangle((x, y, x+width, y+15), radius=7, fill=(60, 78, 105))
    fill = max(8, min(width, round(abs(change) / max(scale, 1) * width)))
    d.rounded_rectangle((x, y, x+fill, y+15), radius=7, fill=GREEN if change >= 0 else RED)

def render_prices_card(rows, source, now, out_path):
    im, d = bg()
    title(d, "Cours des principales cryptos", "Briefing du marché", now)
    for i, r in enumerate(rows):
        y = 345 + i*164
        d.rounded_rectangle((76, y, 1004, y+146), radius=27,
                            fill=PANEL if i % 2 == 0 else (27, 47, 74))
        coin(d, r["symbol"], 137, y+73)
        txt(d, 205, y+31, r["symbol"], 33, WHITE, True)
        txt(d, 205, y+84, usd(r["price"]), 31, WHITE, True)
        pill(d, 812, y+28, r["change"], 160)
        txt(d, 642, y+93, "VARIATION 24 H", 18, MUTED)
        bar(d, 642, y+120, 320, r["change"], 15)
    footer(d, source, "Données indicatives en USD • Variation glissante sur 24 h")
    return save(im, out_path)

def render_movers_card(rows, source, now, direction, out_path):
    im, d = bg()
    rising = direction == "up"
    title(d, "Top 5 des hausses" if rising else "Top 5 des baisses",
          "Performance des cryptos • 24 H", now)
    scale = max(abs(x["change"]) for x in rows) if rows else 1
    for i, r in enumerate(rows):
        y = 345 + i*164
        d.rounded_rectangle((76, y, 1004, y+146), radius=27,
                            fill=PANEL if i % 2 == 0 else (27, 47, 74))
        txt(d, 111, y+69, str(i+1), 35, WHITE, True, "mm")
        coin(d, r["symbol"], 177, y+69, 30)
        txt(d, 228, y+33, r["name"], 29, WHITE, True, max_width=345)
        txt(d, 228, y+85, f'{r["symbol"]}   •   {usd(r["price"])}', 24, MUTED, max_width=345)
        pill(d, 828, y+27, r["change"], 145)
        bar(d, 608, y+109, 365, r["change"], scale)
    footer(d, source, "Top 100 en capitalisation • Vol. 24 h ≥ 1 M$ • Informatif")
    return save(im, out_path)

def render_fear_card(value, observed_at, now, out_path):
    im, d = bg()
    title(d, "Fear & Greed du marché", "Indice de sentiment crypto", now)
    cx, cy, r = 540, 735, 286
    for i in range(100):
        v = i / 100
        color = RED if v < 0.25 else (AMBER if v < 0.5 else (246, 219, 74) if v < 0.75 else GREEN)
        a = 180 + i*1.8
        d.arc((cx-r, cy-r, cx+r, cy+r), start=a, end=a+2.5, width=37, fill=color)
    angle = radians(180 + value*1.8)
    d.line((cx, cy, cx+232*cos(angle), cy+232*sin(angle)), fill=WHITE, width=8)
    d.ellipse((cx-16, cy-16, cx+16, cy+16), fill=WHITE)
    txt(d, cx, 603, str(value), 95, WHITE, True, "mm")
    txt(d, cx, 670, "/ 100", 29, MUTED, False, "mm")
    mood = ("PEUR EXTRÊME" if value <= 24 else "PEUR" if value <= 44 else
            "NEUTRE" if value <= 54 else "AVIDITÉ" if value <= 74 else "AVIDITÉ EXTRÊME")
    color = RED if value <= 24 else AMBER if value <= 44 else GREEN
    d.rounded_rectangle((300, 835, 780, 907), radius=34, fill=color)
    txt(d, cx, 871, mood, 34, WHITE, True, "mm")
    txt(d, cx, 992, "0 = peur extrême      50 = neutre      100 = avidité extrême", 25, MUTED, anchor="mm")
    txt(d, cx, 1065, "Un indicateur de sentiment, pas une prévision de prix.", 23, MUTED, anchor="mm")
    footer(d, "Alternative.me", "Indice observé le " + observed_at.strftime("%d/%m/%Y"))
    return save(im, out_path)

def render_alert_card(row, source, now, level, out_path, demo=False):
    im, d = bg()
    sign = "+" if row["change"] >= 0 else "-"
    title(d, "Alerte variation • " + row["symbol"], "SIMULATION TEST" if demo else "Surveillance marché 24 h", now)
    d.rounded_rectangle((115, 385, 965, 1035), radius=42, fill=PANEL)
    coin(d, row["symbol"], 540, 525, 83)
    txt(d, 540, 648, usd(row["price"]), 64, WHITE, True, "mm")
    d.rounded_rectangle((340, 722, 740, 792), radius=35, fill=GREEN if row["change"] >= 0 else RED)
    txt(d, 540, 757, percent(row["change"]), 41, WHITE, True, "mm")
    txt(d, 540, 872, f"SEUIL {sign}{level}% SUR 24 H", 29, MUTED, True, "mm")
    bar(d, 280, 941, 520, row["change"], 20)
    footer(d, source, "SIMULATION — NE PAS DIFFUSER" if demo else "Alerte calculée sur la variation glissante 24 h")
    return save(im, out_path)
