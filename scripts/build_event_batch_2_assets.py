"""Build the second 1122x1402 Actu Foot event template batch.

Static assets only: titles, decoration, borders and event pictograms are baked in.
All dynamic data zones stay blank for the renderer.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "images" / "arty_football" / "events"
W, H = 1122, 1402

NAVY_TOP = (3, 12, 25)
NAVY_BOTTOM = (7, 25, 42)
PANEL = (6, 20, 34)
PANEL_2 = (9, 29, 47)
GOLD = (239, 190, 83)
GOLD_DARK = (126, 90, 38)
WHITE = (238, 242, 244)
RED = (224, 44, 52)
GREEN = (35, 193, 104)
MUTED = (81, 96, 108)

FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
)


def font(size: int):
    for p in FONT_PATHS:
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def gradient() -> Image.Image:
    im = Image.new("RGB", (W, H), NAVY_TOP)
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / max(1, H - 1)
        c = tuple(int(NAVY_TOP[i] * (1 - t) + NAVY_BOTTOM[i] * t) for i in range(3))
        d.line((0, y, W, y), fill=c)
    return im


def glow(base: Image.Image, center: tuple[int, int], radius: int, color: tuple[int, int, int], alpha: int = 120):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    cx, cy = center
    ld.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=(*color, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(max(10, radius // 3)))
    base.paste(layer, (0, 0), layer)


def panel(d: ImageDraw.ImageDraw, box, radius=20, width=3, fill=PANEL):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=GOLD_DARK, width=width)
    x1, y1, x2, _ = box
    d.line((x1 + 22, y1 + 1, min(x2 - 22, x1 + 170), y1 + 1), fill=GOLD, width=2)


def outer_frame(d: ImageDraw.ImageDraw):
    d.rounded_rectangle((24, 22, W-24, H-24), radius=38, outline=GOLD_DARK, width=3)
    d.rounded_rectangle((34, 32, W-34, H-34), radius=33, outline=(59, 61, 55), width=1)
    d.line((68, 1340, 402, 1340), fill=GOLD_DARK, width=2)
    d.line((720, 1340, 1054, 1340), fill=GOLD_DARK, width=2)


def title(d: ImageDraw.ImageDraw, text: str, accent=GOLD):
    panel(d, (86, 72, 1036, 226), radius=24, width=3, fill=(5, 18, 31))
    face = font(61 if len(text) <= 18 else 54)
    d.text((W//2, 149), text, fill=accent, font=face, anchor="mm")


def stadium_scene(im: Image.Image, accent: tuple[int, int, int], card_color=None, substitution=False):
    d = ImageDraw.Draw(im)
    # stadium rings + floodlights
    for r in (710, 650, 590, 530):
        d.arc((W//2-r, 220-r//2, W//2+r, 220+r), 190, 350, fill=(38, 46, 54), width=2)
    for x in (95, 1027):
        for rr in (48, 35, 22):
            d.ellipse((x-rr, 292-rr, x+rr, 292+rr), outline=(142, 120, 75), width=2)
    # stylized pitch perspective
    for yy in (580, 625, 670, 715):
        d.line((0, yy, W, yy), fill=(18, 42, 50), width=2)
    d.polygon([(210, 735), (912, 735), (760, 505), (362, 505)], outline=(31, 73, 74))
    if substitution:
        glow(im, (W//2, 470), 235, GREEN, 62)
        glow(im, (W//2, 470), 235, RED, 55)
        d = ImageDraw.Draw(im)
        # two jersey silhouettes, deliberately generic
        for cx, col in ((430, GREEN), (692, RED)):
            pts = [
                (cx-72, 392), (cx-120, 430), (cx-88, 492), (cx-54, 472),
                (cx-54, 575), (cx+54, 575), (cx+54, 472), (cx+88, 492),
                (cx+120, 430), (cx+72, 392), (cx+40, 410), (cx-40, 410),
            ]
            d.polygon(pts, fill=(18, 35, 47), outline=col)
            d.line((cx-37, 414, cx+37, 414), fill=GOLD_DARK, width=2)
        # central arrows: up green, down red
        d.line((530, 565, 530, 435), fill=GREEN, width=12)
        d.polygon([(530, 405), (505, 445), (555, 445)], fill=GREEN)
        d.line((592, 415, 592, 545), fill=RED, width=12)
        d.polygon([(592, 575), (567, 535), (617, 535)], fill=RED)
    elif card_color:
        glow(im, (W//2, 470), 245, card_color, 82)
        d = ImageDraw.Draw(im)
        # red-card silhouette, no dynamic text
        d.rounded_rectangle((478, 330, 645, 575), radius=18, fill=card_color,
                            outline=(255, 184, 142), width=4)
        d.rounded_rectangle((500, 355, 623, 550), radius=12,
                            outline=(255, 120, 120), width=2)
        # referee whistle motif
        d.ellipse((690, 450, 808, 550), outline=WHITE, width=8)
        d.line((617, 415, 713, 485), fill=WHITE, width=9)


def match_block(d: ImageDraw.ImageDraw, y=760):
    # team logos
    for box in ((74, y, 207, y+133), (915, y, 1048, y+133)):
        d.ellipse(box, fill=(5, 18, 31), outline=GOLD_DARK, width=4)
        inner=(box[0]+10,box[1]+10,box[2]-10,box[3]-10)
        d.ellipse(inner, outline=(65, 71, 73), width=2)
    # team names
    panel(d, (54, y+143, 357, y+201), radius=14, width=2)
    panel(d, (765, y+143, 1068, y+201), radius=14, width=2)
    # scores
    panel(d, (382, y+8, 530, y+135), radius=18, width=3)
    panel(d, (592, y+8, 740, y+135), radius=18, width=3)
    # minute
    panel(d, (440, y+146, 682, y+204), radius=15, width=2)


def footer_brand(d: ImageDraw.ImageDraw):
    d.text((W//2, 1340), "MR XPRONOS  •  ACTU FOOT", fill=GOLD,
           font=font(18), anchor="mm")


def build_red(full: bool) -> Image.Image:
    im=gradient()
    glow(im,(W//2,410),340,RED,70)
    stadium_scene(im, RED, card_color=RED)
    d=ImageDraw.Draw(im)
    outer_frame(d)
    title(d,"CARTON ROUGE",RED)
    match_block(d, y=768)
    if full:
        # two compact event fields; pictograms are fixed, text areas stay blank
        panel(d,(150, 988, 625, 1067),radius=16,width=2)
        panel(d,(687, 988, 1056, 1067),radius=16,width=2)
        # person pictogram
        d.ellipse((167,1006,189,1028),outline=WHITE,width=3)
        d.line((178,1028,178,1050),fill=WHITE,width=3)
        # red card pictogram
        d.rounded_rectangle((700,1004,720,1042),radius=3,fill=RED,outline=(255,130,130),width=2)
        panel(d,(118,1091,1004,1149),radius=14,width=2)
        panel(d,(76,1166,1046,1300),radius=22,width=2)
    else:
        # large red card art on left, only verified context on right
        d.rounded_rectangle((86,1010,236,1240),radius=16,fill=RED,
                            outline=(255,159,130),width=3)
        panel(d,(262,1010,1048,1070),radius=14,width=2)
        panel(d,(262,1092,1048,1215),radius=20,width=2)
        panel(d,(262,1234,1048,1290),radius=14,width=2)
    footer_brand(d)
    return im


def build_substitution(mode: str) -> Image.Image:
    im=gradient()
    glow(im,(W//2,420),340,GREEN,45)
    glow(im,(W//2,420),300,RED,38)
    stadium_scene(im, GOLD, substitution=True)
    d=ImageDraw.Draw(im)
    outer_frame(d)
    title(d,"REMPLACEMENT",GOLD)
    match_block(d,y=728)
    panel(d,(350,944,772,1004),radius=14,width=2)
    if mode=="full":
        panel(d,(92,1030,526,1194),radius=22,width=2)
        panel(d,(596,1030,1030,1194),radius=22,width=2)
        # fixed arrows only, no labels
        d.line((126,1150,126,1070),fill=GREEN,width=8)
        d.polygon([(126,1048),(108,1077),(144,1077)],fill=GREEN)
        d.line((996,1058,996,1138),fill=RED,width=8)
        d.polygon([(996,1160),(978,1131),(1014,1131)],fill=RED)
    else:
        panel(d,(154,1030,968,1202),radius=24,width=2)
        if mode=="entrant":
            d.line((194,1160,194,1070),fill=GREEN,width=9)
            d.polygon([(194,1045),(174,1079),(214,1079)],fill=GREEN)
        else:
            d.line((928,1058,928,1148),fill=RED,width=9)
            d.polygon([(928,1173),(908,1139),(948,1139)],fill=RED)
    panel(d,(140,1228,982,1290),radius=14,width=2)
    footer_brand(d)
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assets={
        "carton_rouge_full.png": build_red(True),
        "carton_rouge_unknown.png": build_red(False),
        "remplacement_full.png": build_substitution("full"),
        "remplacement_entrant.png": build_substitution("entrant"),
        "remplacement_sortant.png": build_substitution("sortant"),
    }
    for name,im in assets.items():
        path=OUT/name
        im.save(path,"PNG",optimize=True)
        print("BUILT",path,im.size,path.stat().st_size)


if __name__=="__main__":
    main()
