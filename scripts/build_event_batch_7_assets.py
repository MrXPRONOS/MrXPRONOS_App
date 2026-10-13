"""Build the seventh 1122x1402 Actu Foot event template batch.

Batch 7:
- COMPOSITION PROBABLE — composition partielle
- CHANGEMENT DE COMPOSITION
- ABSENCE CONFIRMÉE
- RETOUR DANS LE GROUPE
- SCORE LIVE CONFIRMÉ — deux logos disponibles

The partial probable-lineup background has no individual player placeholders.
Only verified players are drawn at render time inside continuous list zones.
"""
from __future__ import annotations

from PIL import ImageDraw
from build_event_batch_2_assets import (
    OUT, W, H, GOLD, GOLD_DARK, WHITE, RED, GREEN,
    gradient, glow, panel, outer_frame, title, footer_brand, font,
)

CYAN = (55, 176, 210)
AMBER = (239, 167, 64)
PANEL_BG = (6, 20, 34)
MUTED = (91, 108, 118)


def stadium_base(im, accent):
    d = ImageDraw.Draw(im)
    for r in (710, 650, 590, 530):
        d.arc((W//2-r, 210-r//2, W//2+r, 210+r), 190, 350, fill=(38, 46, 54), width=2)
    for x in (95, 1027):
        for rr in (48, 35, 22):
            d.ellipse((x-rr, 292-rr, x+rr, 292+rr), outline=(142, 120, 75), width=2)
    for yy in (575, 620, 665, 710):
        d.line((0, yy, W, yy), fill=(18, 42, 50), width=2)
    glow(im, (W//2, 440), 295, accent, 55)


def probable_pitch(d):
    x1, y1, x2, y2 = 100, 360, 1022, 1128
    d.rounded_rectangle((x1, y1, x2, y2), radius=36, fill=(7, 45, 42),
                        outline=GOLD_DARK, width=4)
    d.rectangle((x1+32, y1+32, x2-32, y2-32), outline=(168, 191, 176), width=3)
    mid=(y1+y2)//2
    d.line((x1+32, mid, x2-32, mid), fill=(168,191,176), width=3)
    d.ellipse((W//2-92, mid-92, W//2+92, mid+92), outline=(168,191,176), width=3)
    d.rectangle((W//2-255, y1+32, W//2+255, y1+155), outline=(168,191,176), width=3)
    d.rectangle((W//2-255, y2-155, W//2+255, y2-32), outline=(168,191,176), width=3)
    # One continuous player area: the renderer chooses one or two columns
    # depending on how many verified players exist. There are no empty slots.
    d.rounded_rectangle((145, 435, 977, 1038), radius=24,
                        fill=(5, 24, 35), outline=(74, 93, 92), width=2)


def build_probable_partial():
    im = gradient()
    glow(im, (W//2, 680), 430, GREEN, 40)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "COMPOSITION PROBABLE", GOLD)
    d.ellipse((70, 260, 180, 370), fill=PANEL_BG, outline=GOLD_DARK, width=4)
    panel(d, (202, 270, 620, 326), radius=14, width=2)
    panel(d, (642, 270, 1048, 326), radius=14, width=2)
    probable_pitch(d)
    panel(d, (160, 1160, 962, 1220), radius=14, width=2)
    panel(d, (160, 1240, 962, 1290), radius=13, width=2)
    footer_brand(d)
    return im


def player_silhouette(d, cx, cy, accent=WHITE):
    d.ellipse((cx-38, cy-150, cx+38, cy-74), outline=accent, width=5)
    d.line((cx, cy-72, cx, cy+35), fill=accent, width=7)
    d.line((cx, cy-35, cx-64, cy+18), fill=accent, width=7)
    d.line((cx, cy-35, cx+64, cy+18), fill=accent, width=7)
    d.line((cx, cy+35, cx-48, cy+120), fill=accent, width=7)
    d.line((cx, cy+35, cx+48, cy+120), fill=accent, width=7)


def build_lineup_change():
    im = gradient()
    stadium_base(im, AMBER)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "CHANGEMENT DE COMPOSITION", AMBER)
    # two generic player silhouettes + directional arrows, no labels
    player_silhouette(d, 410, 470, WHITE)
    player_silhouette(d, 712, 470, WHITE)
    d.line((495, 430, 625, 430), fill=GREEN, width=11)
    d.polygon([(650,430),(616,410),(616,450)], fill=GREEN)
    d.line((625, 520, 495, 520), fill=RED, width=11)
    d.polygon([(470,520),(504,500),(504,540)], fill=RED)
    # team / competition
    d.ellipse((70, 700, 185, 815), fill=PANEL_BG, outline=GOLD_DARK, width=4)
    panel(d, (205, 712, 600, 766), radius=14, width=2)
    panel(d, (622, 712, 1048, 766), radius=14, width=2)
    # changed players
    panel(d, (112, 835, 520, 968), radius=20, width=2)
    panel(d, (602, 835, 1010, 968), radius=20, width=2)
    # context / source
    panel(d, (150, 1005, 972, 1125), radius=20, width=2)
    panel(d, (160, 1160, 962, 1218), radius=14, width=2)
    panel(d, (160, 1242, 962, 1290), radius=13, width=2)
    footer_brand(d)
    return im


def build_absence_confirmed():
    im = gradient()
    stadium_base(im, RED)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "ABSENCE CONFIRMÉE", RED)
    player_silhouette(d, W//2, 470, WHITE)
    d.line((390, 315, 732, 645), fill=RED, width=25)
    d.line((412, 315, 754, 645), fill=(255, 126, 126), width=5)
    d.ellipse((70, 700, 185, 815), fill=PANEL_BG, outline=GOLD_DARK, width=4)
    panel(d, (205, 712, 600, 766), radius=14, width=2)
    panel(d, (622, 712, 1048, 766), radius=14, width=2)
    panel(d, (150, 835, 972, 900), radius=17, width=2)
    panel(d, (150, 925, 972, 1038), radius=20, width=2)
    panel(d, (150, 1062, 972, 1185), radius=20, width=2)
    panel(d, (160, 1220, 962, 1286), radius=14, width=2)
    footer_brand(d)
    return im


def build_return_group():
    im = gradient()
    stadium_base(im, GREEN)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "RETOUR DANS LE GROUPE", GREEN)
    player_silhouette(d, 495, 470, WHITE)
    d.arc((515, 305, 790, 610), 205, 505, fill=GREEN, width=12)
    d.polygon([(758,332),(806,342),(778,384)], fill=GREEN)
    d.ellipse((70, 700, 185, 815), fill=PANEL_BG, outline=GOLD_DARK, width=4)
    panel(d, (205, 712, 600, 766), radius=14, width=2)
    panel(d, (622, 712, 1048, 766), radius=14, width=2)
    panel(d, (150, 835, 972, 900), radius=17, width=2)
    panel(d, (150, 925, 972, 1038), radius=20, width=2)
    panel(d, (150, 1062, 972, 1185), radius=20, width=2)
    panel(d, (160, 1220, 962, 1286), radius=14, width=2)
    footer_brand(d)
    return im


def build_score_live_two_logos():
    im = gradient()
    stadium_base(im, CYAN)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "SCORE LIVE CONFIRMÉ", CYAN)
    # very large logo areas
    for box in ((80, 335, 335, 590), (787, 335, 1042, 590)):
        d.ellipse(box, fill=PANEL_BG, outline=GOLD_DARK, width=5)
        d.ellipse((box[0]+14, box[1]+14, box[2]-14, box[3]-14),
                  outline=(70, 84, 90), width=2)
    # names
    panel(d, (62, 615, 360, 680), radius=15, width=2)
    panel(d, (762, 615, 1060, 680), radius=15, width=2)
    # big score
    panel(d, (380, 370, 530, 520), radius=22, width=4)
    panel(d, (592, 370, 742, 520), radius=22, width=4)
    # live minute
    panel(d, (430, 545, 692, 615), radius=18, width=3)
    # competition and source/info
    panel(d, (150, 735, 972, 800), radius=16, width=2)
    panel(d, (150, 830, 972, 950), radius=20, width=2)
    panel(d, (150, 980, 972, 1110), radius=20, width=2)
    panel(d, (160, 1150, 962, 1210), radius=14, width=2)
    footer_brand(d)
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assets = {
        "composition_probable_partial.png": build_probable_partial(),
        "changement_composition.png": build_lineup_change(),
        "absence_confirmee.png": build_absence_confirmed(),
        "retour_groupe.png": build_return_group(),
        "score_live_two_logos.png": build_score_live_two_logos(),
    }
    for name, im in assets.items():
        path = OUT / name
        im.save(path, "PNG", optimize=True)
        print("BUILT", path, im.size, path.stat().st_size)


if __name__ == "__main__":
    main()
