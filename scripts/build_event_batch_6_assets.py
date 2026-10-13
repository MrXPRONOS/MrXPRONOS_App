"""Build the sixth 1122x1402 Actu Foot event template batch.

Batch 6:
- TIRS AU BUT
- TIR AU BUT MARQUÉ
- TIR AU BUT MANQUÉ
- FIN DES TIRS AU BUT
- COMPOSITION PROBABLE — onze complet

The penalty-shootout designs deliberately separate the match score from the
shootout score. The probable-lineup design is a true 4-3-3 pitch layout with
11 independent dynamic player slots.
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


def stadium_base(im, accent):
    d = ImageDraw.Draw(im)
    for r in (710, 650, 590, 530):
        d.arc((W//2-r, 210-r//2, W//2+r, 210+r), 190, 350, fill=(38, 46, 54), width=2)
    for x in (95, 1027):
        for rr in (48, 35, 22):
            d.ellipse((x-rr, 292-rr, x+rr, 292+rr), outline=(142, 120, 75), width=2)
    for yy in (575, 620, 665, 710):
        d.line((0, yy, W, yy), fill=(18, 42, 50), width=2)
    glow(im, (W//2, 430), 290, accent, 52)


def target_icon(d, cx, cy, accent):
    for r, width in ((142, 7), (100, 5), (58, 4)):
        d.ellipse((cx-r, cy-r, cx+r, cy+r), outline=accent, width=width)
    d.ellipse((cx-16, cy-16, cx+16, cy+16), fill=WHITE)
    d.line((cx-190, cy, cx+190, cy), fill=(64, 82, 92), width=2)
    d.line((cx, cy-190, cx, cy+190), fill=(64, 82, 92), width=2)


def shootout_match_row(d, y=707):
    # circular team-logo zones
    for box in ((70, y, 205, y+135), (917, y, 1052, y+135)):
        d.ellipse(box, fill=PANEL_BG, outline=GOLD_DARK, width=4)
        d.ellipse((box[0]+10, box[1]+10, box[2]-10, box[3]-10),
                  outline=(67, 74, 79), width=2)
    panel(d, (52, y+146, 356, y+203), radius=14, width=2)
    panel(d, (766, y+146, 1070, y+203), radius=14, width=2)
    # small regulation/match score
    panel(d, (388, y+17, 512, y+113), radius=18, width=2)
    panel(d, (610, y+17, 734, y+113), radius=18, width=2)
    # shootout score: bigger central boxes
    panel(d, (382, y+133, 515, y+239), radius=18, width=3)
    panel(d, (607, y+133, 740, y+239), radius=18, width=3)


def shot_dots(d, y, success_left=0, miss_left=0, success_right=0, miss_right=0):
    # Decorative neutral shootout markers only. Unfilled outlines are not data.
    for base_x in (305, 664):
        for i in range(5):
            x = base_x + i*34
            d.ellipse((x, y, x+18, y+18), outline=GOLD_DARK, width=2)


def build_shootout():
    im = gradient()
    stadium_base(im, GOLD)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "TIRS AU BUT", GOLD)
    target_icon(d, W//2, 425, GOLD)
    shootout_match_row(d, y=695)
    shot_dots(d, 967)
    panel(d, (170, 1015, 952, 1080), radius=16, width=2)
    panel(d, (150, 1105, 972, 1215), radius=20, width=2)
    panel(d, (160, 1238, 962, 1287), radius=13, width=2)
    footer_brand(d)
    return im


def build_shootout_scored():
    im = gradient()
    stadium_base(im, GREEN)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "TIR AU BUT MARQUÉ", GREEN)
    target_icon(d, W//2, 425, GREEN)
    # successful impact
    d.ellipse((W//2-30, 395, W//2+30, 455), fill=GREEN, outline=WHITE, width=4)
    shootout_match_row(d, y=695)
    panel(d, (170, 1015, 952, 1080), radius=16, width=2)  # player
    panel(d, (220, 1105, 902, 1170), radius=16, width=2)  # team/context
    panel(d, (150, 1192, 972, 1287), radius=20, width=2)  # info/source
    footer_brand(d)
    return im


def build_shootout_missed():
    im = gradient()
    stadium_base(im, RED)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "TIR AU BUT MANQUÉ", RED)
    target_icon(d, W//2, 425, RED)
    d.line((485, 350, 637, 502), fill=RED, width=20)
    d.line((637, 350, 485, 502), fill=RED, width=20)
    shootout_match_row(d, y=695)
    panel(d, (170, 1015, 952, 1080), radius=16, width=2)  # player
    panel(d, (220, 1105, 902, 1170), radius=16, width=2)  # reason/result detail
    panel(d, (150, 1192, 972, 1287), radius=20, width=2)  # info/source
    footer_brand(d)
    return im


def build_shootout_end():
    im = gradient()
    stadium_base(im, AMBER)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "FIN DES TIRS AU BUT", AMBER)
    target_icon(d, W//2, 425, AMBER)
    # trophy silhouette
    d.arc((485, 346, 637, 486), 0, 180, fill=WHITE, width=8)
    d.line((520, 417, 520, 505), fill=WHITE, width=8)
    d.line((602, 417, 602, 505), fill=WHITE, width=8)
    d.line((520, 505, 602, 505), fill=WHITE, width=8)
    shootout_match_row(d, y=695)
    panel(d, (190, 1012, 932, 1084), radius=18, width=2)  # winner
    panel(d, (150, 1110, 972, 1213), radius=20, width=2)  # result/context
    panel(d, (160, 1238, 962, 1287), radius=13, width=2)
    footer_brand(d)
    return im


def probable_pitch(d):
    # Dedicated tactical pitch, no fake text/players.
    x1, y1, x2, y2 = 112, 365, 1010, 1115
    d.rounded_rectangle((x1, y1, x2, y2), radius=36, fill=(7, 45, 42),
                        outline=GOLD_DARK, width=4)
    d.rectangle((x1+32, y1+32, x2-32, y2-32), outline=(168, 191, 176), width=3)
    mid=(y1+y2)//2
    d.line((x1+32, mid, x2-32, mid), fill=(168,191,176), width=3)
    d.ellipse((W//2-92, mid-92, W//2+92, mid+92), outline=(168,191,176), width=3)
    d.rectangle((W//2-255, y1+32, W//2+255, y1+155), outline=(168,191,176), width=3)
    d.rectangle((W//2-255, y2-155, W//2+255, y2-32), outline=(168,191,176), width=3)


def player_slot(d, box):
    d.rounded_rectangle(box, radius=18, fill=(5, 24, 35), outline=GOLD_DARK, width=2)
    cx=(box[0]+box[2])//2
    d.ellipse((cx-16, box[1]+10, cx+16, box[1]+42), outline=WHITE, width=2)


def build_probable_xi():
    im = gradient()
    glow(im, (W//2, 650), 420, GREEN, 42)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "COMPOSITION PROBABLE", GOLD)
    # team / competition header fields
    d.ellipse((70, 260, 180, 370), fill=PANEL_BG, outline=GOLD_DARK, width=4)
    panel(d, (202, 270, 620, 326), radius=14, width=2)  # team
    panel(d, (642, 270, 1048, 326), radius=14, width=2) # competition/opponent context
    probable_pitch(d)

    # 4-3-3 slots: 3 forwards, 3 mids, 4 defenders, 1 keeper
    slots = [
        (210, 410, 440, 478), (446, 392, 676, 460), (682, 410, 912, 478),
        (245, 590, 475, 658), (446, 625, 676, 693), (647, 590, 877, 658),
        (145, 810, 355, 878), (365, 845, 555, 913),
        (567, 845, 757, 913), (767, 810, 977, 878),
        (446, 1000, 676, 1068),
    ]
    for box in slots:
        player_slot(d, box)
    panel(d, (160, 1160, 962, 1220), radius=14, width=2)  # formation / coach / status
    panel(d, (160, 1240, 962, 1290), radius=13, width=2)  # source
    footer_brand(d)
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assets = {
        "tirs_au_but.png": build_shootout(),
        "tir_au_but_marque.png": build_shootout_scored(),
        "tir_au_but_manque.png": build_shootout_missed(),
        "fin_tirs_au_but.png": build_shootout_end(),
        "composition_probable_full.png": build_probable_xi(),
    }
    for name, im in assets.items():
        path = OUT / name
        im.save(path, "PNG", optimize=True)
        print("BUILT", path, im.size, path.stat().st_size)


if __name__ == "__main__":
    main()
