"""Build the fifth 1122x1402 Actu Foot event template batch."""
from __future__ import annotations

from PIL import ImageDraw
from build_event_batch_2_assets import (
    OUT, W, H, GOLD, GOLD_DARK, WHITE, GREEN,
    gradient, glow, panel, outer_frame, title, match_block, footer_brand,
)

CYAN = (55, 176, 210)
AMBER = (239, 167, 64)
PURPLE = (137, 97, 214)


def stadium_base(im, accent):
    d = ImageDraw.Draw(im)
    for r in (710, 650, 590, 530):
        d.arc((W//2-r, 210-r//2, W//2+r, 210+r), 190, 350, fill=(38, 46, 54), width=2)
    for x in (95, 1027):
        for rr in (48, 35, 22):
            d.ellipse((x-rr, 292-rr, x+rr, 292+rr), outline=(142, 120, 75), width=2)
    for yy in (575, 620, 665, 710):
        d.line((0, yy, W, yy), fill=(18, 42, 50), width=2)
    d.polygon([(210, 728), (912, 728), (760, 500), (362, 500)], outline=(31, 73, 74))
    glow(im, (W//2, 445), 275, accent, 58)


def clock_face(d, cx, cy, radius, accent, minute_angle="top"):
    d.ellipse((cx-radius, cy-radius, cx+radius, cy+radius),
              fill=(12, 31, 42), outline=accent, width=7)
    for angle in range(0, 12):
        # cardinal-ish ticks without trigonometry dependency
        pass
    d.line((cx, cy, cx, cy-radius+42), fill=WHITE, width=9)
    if minute_angle == "right":
        d.line((cx, cy, cx+radius-48, cy), fill=WHITE, width=9)
    elif minute_angle == "left":
        d.line((cx, cy, cx-radius+48, cy), fill=WHITE, width=9)
    else:
        d.line((cx, cy, cx+52, cy+66), fill=WHITE, width=9)
    d.ellipse((cx-11, cy-11, cx+11, cy+11), fill=accent)


def phase_badge(d, text, y, accent):
    panel(d, (390, y, 732, y+92), radius=22, width=3)
    d.text((W//2, y+46), text, fill=accent,
           font=__import__("build_event_batch_2_assets").font(42), anchor="mm")


def build_end_first_half():
    im = gradient()
    stadium_base(im, AMBER)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "FIN DE LA 1RE MI-TEMPS", AMBER)
    clock_face(d, W//2, 442, 145, AMBER, "right")
    phase_badge(d, "45′", 585, AMBER)
    match_block(d, y=724)
    panel(d, (340, 944, 782, 1004), radius=14, width=2)
    panel(d, (180, 1036, 942, 1110), radius=18, width=2)
    panel(d, (150, 1132, 972, 1215), radius=20, width=2)
    panel(d, (160, 1238, 962, 1288), radius=13, width=2)
    footer_brand(d)
    return im


def build_start_second_half():
    im = gradient()
    stadium_base(im, GREEN)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "DÉBUT DE LA 2E MI-TEMPS", GREEN)
    # play circle + 46'
    d.ellipse((420, 320, 702, 602), fill=(12,31,42), outline=GREEN, width=7)
    d.polygon([(524, 386), (524, 536), (650, 461)], fill=WHITE)
    phase_badge(d, "46′", 585, GREEN)
    match_block(d, y=724)
    panel(d, (340, 944, 782, 1004), radius=14, width=2)
    panel(d, (180, 1036, 942, 1110), radius=18, width=2)
    panel(d, (150, 1132, 972, 1215), radius=20, width=2)
    panel(d, (160, 1238, 962, 1288), radius=13, width=2)
    footer_brand(d)
    return im


def build_end_regulation():
    im = gradient()
    stadium_base(im, CYAN)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "FIN DU TEMPS RÉGLEMENTAIRE", CYAN)
    clock_face(d, W//2, 442, 145, CYAN, "top")
    phase_badge(d, "90′", 585, CYAN)
    match_block(d, y=724)
    panel(d, (340, 944, 782, 1004), radius=14, width=2)
    # One large status area: e.g. prolongation à suivre / qualification / en attente.
    panel(d, (150, 1032, 972, 1178), radius=22, width=2)
    panel(d, (160, 1214, 962, 1284), radius=14, width=2)
    footer_brand(d)
    return im


def build_extra_time():
    im = gradient()
    stadium_base(im, PURPLE)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "PROLONGATION", PURPLE)
    clock_face(d, W//2, 442, 145, PURPLE, "left")
    # static "+30" motif, not a dynamic score
    phase_badge(d, "+30′", 585, PURPLE)
    match_block(d, y=724)
    panel(d, (340, 944, 782, 1004), radius=14, width=2)
    panel(d, (180, 1036, 942, 1110), radius=18, width=2)
    panel(d, (150, 1132, 972, 1215), radius=20, width=2)
    panel(d, (160, 1238, 962, 1288), radius=13, width=2)
    footer_brand(d)
    return im


def build_extra_time_halftime():
    im = gradient()
    stadium_base(im, GOLD)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "MI-TEMPS DE LA PROLONGATION", GOLD)
    # split-clock motif and 105'
    d.ellipse((420, 320, 702, 602), fill=(12,31,42), outline=GOLD, width=7)
    d.line((561, 343, 561, 579), fill=GOLD, width=6)
    d.rounded_rectangle((488, 401, 530, 523), radius=10, fill=WHITE)
    d.rounded_rectangle((592, 401, 634, 523), radius=10, fill=WHITE)
    phase_badge(d, "105′", 585, GOLD)
    match_block(d, y=724)
    panel(d, (340, 944, 782, 1004), radius=14, width=2)
    panel(d, (180, 1036, 942, 1110), radius=18, width=2)
    panel(d, (150, 1132, 972, 1215), radius=20, width=2)
    panel(d, (160, 1238, 962, 1288), radius=13, width=2)
    footer_brand(d)
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assets = {
        "fin_1re_mi_temps.png": build_end_first_half(),
        "debut_2e_mi_temps.png": build_start_second_half(),
        "fin_temps_reglementaire.png": build_end_regulation(),
        "prolongation.png": build_extra_time(),
        "mi_temps_prolongation.png": build_extra_time_halftime(),
    }
    for name, im in assets.items():
        path = OUT / name
        im.save(path, "PNG", optimize=True)
        print("BUILT", path, im.size, path.stat().st_size)


if __name__ == "__main__":
    main()
