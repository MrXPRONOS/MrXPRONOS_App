"""Carte de prix Actu Crypto – illustration 3D dessinée avec Pillow.

Aucun service externe, police ou logo sous licence requis. Les médaillons sont
une interprétation graphique des symboles, pas des logos officiels téléchargés.
Le rendu ne simule aucune donnée : prix et variations proviennent de l'appelant.
"""
from __future__ import annotations

from datetime import datetime
from math import cos, pi, sin
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH, HEIGHT = 1080, 1350
SYMBOLS = ("BTC", "ETH", "SOL", "BNB", "XRP")
NAMES = {"BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "BNB": "BNB", "XRP": "XRP"}
COLORS = {"BTC": (247, 169, 47), "ETH": (139, 163, 245), "SOL": (76, 220, 195),
          "BNB": (243, 193, 65), "XRP": (144, 181, 207)}
WHITE = (242, 249, 255)
MUTED = (158, 180, 203)
GREEN = (71, 231, 172)
RED = (255, 107, 135)


def _font(size, bold=False):
    names = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "C:/Windows/Fonts/arialbd.ttf") if bold else (
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "C:/Windows/Fonts/arial.ttf")
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _mix(a, b, t):
    return tuple(max(0, min(255, int(a[i]*(1-t) + b[i]*t))) for i in range(3))


def _text(d, pos, text, size=28, color=WHITE, bold=False, anchor=None,
          width=None, shadow=True, stroke=0):
    text = str(text)
    while width and size > 16 and d.textbbox((0, 0), text, font=_font(size, bold))[2] > width:
        size -= 1
    f = _font(size, bold)
    x, y = pos
    if shadow:
        d.text((x+3, y+4), text, font=f, fill=(1, 7, 18, 225), anchor=anchor,
               stroke_width=stroke, stroke_fill=(1, 7, 18))
    d.text((x, y), text, font=f, fill=color, anchor=anchor,
           stroke_width=stroke, stroke_fill=_mix(color, (15, 29, 53), .35) if stroke else None)


def _glow(img, box, rgb, blur, opacity=115):
    layer = Image.new("RGBA", img.size)
    d = ImageDraw.Draw(layer)
    d.ellipse(box, fill=(*rgb, opacity))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(layer)


def _background():
    im = Image.new("RGBA", (WIDTH, HEIGHT))
    px = ImageDraw.Draw(im)
    for y in range(HEIGHT):
        t = y/HEIGHT
        px.line((0, y, WIDTH, y), fill=(int(5+7*t), int(16+9*t), int(32+12*t), 255))
    _glow(im, (570, -230, 1400, 610), (25, 98, 191), 155, 150)
    _glow(im, (-450, 600, 330, 1460), (11, 109, 140), 160, 100)
    _glow(im, (625, 820, 1390, 1580), (65, 43, 122), 180, 95)
    d = ImageDraw.Draw(im)
    # Grille de projection presque invisible, sans graphiques de cours inventés.
    for k in range(-1000, 1900, 100):
        d.line((k, 0, k+750, HEIGHT), fill=(37, 83, 119, 22), width=1)
    for y in range(100, HEIGHT, 94):
        d.line((36, y, 1044, y), fill=(43, 82, 118, 18), width=1)
    for j in range(40):
        x = 63+(j*229)%962
        y = 60+(j*327)%1250
        r = 1+(j % 3 == 0)
        d.ellipse((x-r, y-r, x+r, y+r), fill=(148, 210, 247, 35+(j%3)*17))
    d.rounded_rectangle((32, 30, 1048, 1320), radius=40,
                        outline=(95, 154, 203, 90), width=2)
    d.line((96, 48, 440, 48), fill=(64, 160, 226, 110), width=3)
    d.line((922, 1301, 1009, 1301), fill=(78, 199, 206, 125), width=3)
    return im


def _metal_coin(img, symbol, x, y, radius, alpha=255):
    """Médaillon gravé, ombre portée, épaisseur, rebords et reflets directionnels."""
    rgb = COLORS.get(symbol, (133, 174, 213))
    layer = Image.new("RGBA", img.size)
    sh = Image.new("RGBA", img.size)
    sd = ImageDraw.Draw(sh)
    sd.ellipse((x-radius+13, y-radius+23, x+radius+13, y+radius+23),
               fill=(0, 0, 0, min(alpha, 150)))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(max(5, radius//6))))
    d = ImageDraw.Draw(layer)
    # Flanc inférieur de la pièce (épaisseur visible).
    for z in range(max(5, radius//6), -1, -1):
        c = _mix(rgb, (10, 16, 31), .67+.20*(z/max(1, radius//6)))
        d.ellipse((x-radius, y-radius+z, x+radius, y+radius+z), fill=(*c, alpha))
    # Cerclages successifs, donnant une géométrie convexe.
    for inset in range(max(5, radius//9)):
        t = inset / max(1, radius//9)
        c = _mix((229, 246, 255), rgb, .35 + .56*t)
        d.ellipse((x-radius+inset, y-radius+inset,
                   x+radius-inset, y+radius-inset), fill=(*c, alpha))
    q = max(7, radius//8)
    inner = radius - q
    for inset in range(inner, 0, -1):
        t = inset/max(1, inner)
        c = _mix(rgb, (21, 35, 59), .30*(1-t))
        d.ellipse((x-inset, y-inset, x+inset, y+inset), fill=(*c, alpha))
    # Liserés intérieur et extérieur : faible, pour préserver la lisibilité.
    d.arc((x-radius+2, y-radius+2, x+radius-2, y+radius-2), 193, 315,
          fill=(255, 252, 230, alpha), width=max(2, radius//19))
    d.arc((x-radius+5, y-radius+5, x+radius-5, y+radius-5), 5, 145,
          fill=(*_mix(rgb, (7, 13, 27), .66), alpha), width=max(2, radius//15))
    d.ellipse((x-inner, y-inner, x+inner, y+inner), outline=(*_mix(rgb, (245, 252, 255), .43), alpha), width=2)
    # Éléments stylisés gravés en relief (pas d'image externe / faux logo).
    white = (252, 253, 255, alpha)
    dark = (*_mix(rgb, (18, 32, 53), .57), alpha)
    if symbol == "BTC":
        # Un glyphe ₿ absent de certaines polices Linux afficherait un carré.
        # Utiliser un B stylisé et ses deux tiges gravées, de manière portable.
        _text(d, (x+2, y+3), "B", int(radius*1.10), color=dark, bold=True, anchor="mm", shadow=False)
        _text(d, (x, y), "B", int(radius*1.10), color=white, bold=True, anchor="mm", shadow=False)
        for offset in (-radius*.13, radius*.10):
            for a,b in ((-.64,-.42),(.40,.64)):
                d.line((x+offset, y+radius*a, x+offset, y+radius*b),
                       fill=white, width=max(2, radius//13))
    elif symbol == "ETH":
        size = radius*.65
        top=(x, y-size); left=(x-size*.48, y+size*.1)
        right=(x+size*.48, y+size*.1); bottom=(x, y+size*.83)
        d.polygon([top, left, (x, y-size*.05)], fill=(233, 241, 255, alpha))
        d.polygon([top, right, (x, y-size*.05)], fill=(115, 131, 184, alpha))
        d.polygon([left, (x, y+size*.1), bottom], fill=(186, 205, 245, alpha))
        d.polygon([right, (x, y+size*.1), bottom], fill=(72, 89, 159, alpha))
    elif symbol == "SOL":
        for i, c in enumerate(((129, 255, 191), (133, 219, 245), (180, 144, 250))):
            yy=y- radius*.39+i*radius*.38
            d.polygon([(x-radius*.46+radius*.15, yy), (x+radius*.49, yy),
                       (x+radius*.33, yy+radius*.23), (x-radius*.49, yy+radius*.23)], fill=(*c, alpha))
    elif symbol == "BNB":
        s=radius*.48
        d.polygon([(x, y-s), (x+s, y), (x, y+s), (x-s, y)], fill=white)
        s2=s*.52
        d.polygon([(x, y-s2), (x+s2, y), (x, y+s2), (x-s2, y)], fill=(*rgb, alpha))
        s3=s*.19
        d.polygon([(x, y-s3), (x+s3, y), (x, y+s3), (x-s3, y)], fill=white)
    else:  # XRP: symbole croisé minimaliste.
        for off in (-2, -1, 0, 1, 2):
            d.arc((x-radius*.47, y-radius*.46+off,
                   x+radius*.47, y+radius*.13+off), 12, 169, fill=white, width=max(2, radius//10))
            d.arc((x-radius*.47, y-radius*.08+off,
                   x+radius*.47, y+radius*.49+off), 190, 351, fill=white, width=max(2, radius//10))
    if alpha != 255:
        # L'alpha global a déjà été appliqué aux formes.
        pass
    img.alpha_composite(layer)


def _hero(im, now, demo):
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((76, 73, 373, 120), radius=23,
                        fill=(34, 64, 102, 220), outline=(73, 142, 202, 120), width=2)
    d.ellipse((94, 91, 105, 102), fill=(91, 228, 205, 255))
    _text(d, (119, 82), "MR XPRONOS  /  CRYPTO", 17, WHITE, True)
    d.rounded_rectangle((831, 78, 1002, 118), radius=20,
                        fill=(11, 37, 52, 217), outline=(61, 148, 168, 119), width=2)
    _text(d, (916, 98), "COURS  ·  USD", 17, (150, 246, 230), True, "mm")
    _text(d, (86, 175), "COURS DU", 57, WHITE, True, stroke=1)
    _text(d, (86, 246), "MARCHÉ", 68, (144, 221, 255), True, stroke=1)
    _text(d, (88, 342), "BTC  /  ETH  /  SOL  /  BNB  /  XRP", 22, (181, 208, 230), True)
    _text(d, (88, 377), now.strftime("%d/%m/%Y   ·   %H:%M UTC"), 21, MUTED)
    # Des médaillons se détachent du fond avec une profondeur 3D.
    _glow(im, (690, 115, 1040, 470), (73, 165, 239), 65, 110)
    _metal_coin(im, "ETH", 732, 306, 56, 220)
    _metal_coin(im, "BTC", 874, 265, 105)
    if demo:
        # Marque explicite dans l'image en plus de la légende de Telegram.
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((84, 404, 320, 431), radius=12, fill=(103, 49, 54, 240))
        _text(d, (202, 418), "TEST  ·  DONNÉES FICTIVES", 13, WHITE, True, "mm")


def _row(im, row, y, idx):
    symbol=row["symbol"]
    change=float(row["change"])
    positive=change>=0
    color=GREEN if positive else RED
    w=(72, y, 1008, y+141)
    # Ombre douce d'une carte en verre surélevée.
    shadow=Image.new("RGBA", im.size)
    sd=ImageDraw.Draw(shadow)
    sd.rounded_rectangle((78, y+9, 1002, y+155), 27, fill=(0, 2, 11, 135))
    im.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(14)))
    d=ImageDraw.Draw(im)
    d.rounded_rectangle(w, radius=25, fill=(21+idx%2*3, 40+idx%2*4, 67+idx%2*4, 242),
                        outline=(85, 137, 174, 94), width=2)
    d.rounded_rectangle((83, y+8, 996, y+52), radius=19,
                        fill=(48, 76, 109, 46))
    d.line((89, y+13, 89, y+125), fill=(*color, 189), width=4)
    _metal_coin(im, symbol, 156, y+70, 45)
    d=ImageDraw.Draw(im)
    _text(d, (230, y+29), symbol, 36, WHITE, True)
    _text(d, (230, y+83), NAMES.get(symbol, row.get("name", symbol)), 21, MUTED)
    # Prix et variation font partie de la même grille, sans superposition.
    _text(d, (530, y+44), _usd(float(row["price"])), 35, WHITE, True,
          width=285)
    _text(d, (533, y+98), "PRIX ACTUEL", 15, MUTED, True)
    d.rounded_rectangle((821, y+28, 977, y+89), radius=24,
                        fill=(*_mix(color, (9, 32, 48), .76), 244),
                        outline=(*color, 147), width=2)
    _text(d, (899, y+58), _percent(change), 24, color, True, "mm", width=145)
    _text(d, (899, y+108), "VARIATION 24H", 16, MUTED, True, "mm")


def _usd(value):
    if value >= 1000:
        return f"${value:,.2f}".replace(",", " ")
    if value >= 1:
        return f"${value:.2f}"
    return f"${value:.6f}".rstrip("0").rstrip(".")


def _percent(value):
    return f"{value:+.2f}%"


def render_premium_prices_card(rows, source, now: datetime, out_path):
    """Exige 5 symboles fiables ; n'invente ni données ni graphiques historiques."""
    by_symbol={str(r["symbol"]).upper():r for r in rows}
    if any(sym not in by_symbol for sym in SYMBOLS):
        raise ValueError("Cours du marché : 5 actifs obligatoires (BTC, ETH, SOL, BNB, XRP)")
    im=_background()
    demo="simulation" in str(source).lower() or "demo" in str(source).lower()
    _hero(im, now, demo)
    for i, sym in enumerate(SYMBOLS):
        _row(im, by_symbol[sym], 451+i*152, i)
    d=ImageDraw.Draw(im)
    d.line((90, 1230, 989, 1230), fill=(92, 145, 176, 100), width=2)
    _text(d, (89, 1246), "Prix indicatifs  ·  Variation glissante sur 24 h", 20, MUTED)
    _text(d, (89, 1280), "SOURCE : " + str(source).upper(), 17, (128, 225, 242), True, width=900)
    out=Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(out, "PNG", optimize=True)
    return out