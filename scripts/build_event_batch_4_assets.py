"""Build the fourth 1122x1402 Actu Foot event template batch."""
from __future__ import annotations

from PIL import ImageDraw
from build_event_batch_2_assets import (
    OUT, W, H, GOLD, GOLD_DARK, WHITE, RED, GREEN,
    gradient, glow, panel, outer_frame, title, match_block, footer_brand,
)

AMBER = (239, 167, 64)
CYAN = (55, 176, 210)
ORANGE = (226, 104, 48)


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


def calendar_icon(d, cx, cy, color):
    d.rounded_rectangle((cx-145, cy-118, cx+145, cy+118), radius=28,
                        fill=(12, 30, 42), outline=color, width=6)
    d.line((cx-145, cy-58, cx+145, cy-58), fill=color, width=5)
    for x in (cx-76, cx+76):
        d.rounded_rectangle((x-13, cy-145, x+13, cy-90), radius=10, fill=color)
    for yy in (cy-22, cy+28, cy+78):
        for xx in (cx-80, cx, cx+80):
            d.ellipse((xx-7, yy-7, xx+7, yy+7), fill=(190, 198, 207))


def build_interrupted_unknown():
    im = gradient()
    stadium_base(im, RED)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "MATCH INTERROMPU", RED)
    # stop icon without any implied reason
    d.regular_polygon((W//2, 458, 142), n_sides=8, rotation=22.5,
                      fill=(60, 20, 26), outline=RED)
    d.rounded_rectangle((W//2-18, 370, W//2+18, 492), radius=14, fill=WHITE)
    d.ellipse((W//2-20, 515, W//2+20, 555), fill=WHITE)
    match_block(d, y=724)
    panel(d, (340, 944, 782, 1004), radius=14, width=2)
    # no "reason" field by design
    panel(d, (150, 1038, 972, 1188), radius=22, width=2)
    panel(d, (160, 1218, 962, 1284), radius=14, width=2)
    footer_brand(d)
    return im


def build_reported():
    im = gradient()
    stadium_base(im, CYAN)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "MATCH REPORTÉ", CYAN)
    calendar_icon(d, W//2, 455, CYAN)
    # circular move arrow around calendar
    d.arc((360, 280, 762, 680), 205, 505, fill=GOLD, width=10)
    d.polygon([(730, 315), (777, 323), (752, 365)], fill=GOLD)
    match_block(d, y=724)
    panel(d, (340, 944, 782, 1004), radius=14, width=2)
    # date and time get distinct fields
    panel(d, (150, 1034, 548, 1110), radius=16, width=2)
    panel(d, (574, 1034, 972, 1110), radius=16, width=2)
    panel(d, (150, 1130, 972, 1214), radius=19, width=2)
    panel(d, (160, 1238, 962, 1288), radius=13, width=2)
    footer_brand(d)
    return im


def build_cancelled():
    im = gradient()
    stadium_base(im, RED)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "MATCH ANNULÉ", RED)
    # ball-like circle crossed out; no cause implied
    d.ellipse((432, 330, 690, 588), fill=(14, 30, 43), outline=WHITE, width=6)
    d.polygon([(508, 390), (614, 390), (654, 482), (561, 548), (468, 482)],
              outline=(100, 113, 120))
    d.line((410, 315, 712, 603), fill=RED, width=25)
    d.line((431, 315, 733, 603), fill=(255, 123, 123), width=5)
    match_block(d, y=724)
    panel(d, (340, 944, 782, 1004), radius=14, width=2)
    panel(d, (150, 1035, 972, 1110), radius=17, width=2)
    panel(d, (150, 1130, 972, 1214), radius=19, width=2)
    panel(d, (160, 1238, 962, 1288), radius=13, width=2)
    footer_brand(d)
    return im


def build_resumed():
    im = gradient()
    stadium_base(im, GREEN)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "REPRISE DU MATCH", GREEN)
    # play button + circular return arrow
    d.ellipse((424, 325, 698, 599), fill=(12, 31, 42), outline=GREEN, width=6)
    d.polygon([(530, 390), (530, 536), (650, 463)], fill=WHITE)
    d.arc((365, 278, 757, 670), 195, 500, fill=GREEN, width=11)
    d.polygon([(727, 312), (773, 321), (747, 363)], fill=GREEN)
    match_block(d, y=724)
    panel(d, (340, 944, 782, 1004), radius=14, width=2)
    panel(d, (180, 1038, 942, 1103), radius=17, width=2)
    panel(d, (150, 1125, 972, 1213), radius=19, width=2)
    panel(d, (160, 1238, 962, 1288), radius=13, width=2)
    footer_brand(d)
    return im


def build_added_time():
    im = gradient()
    stadium_base(im, GOLD)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "TEMPS ADDITIONNEL", GOLD)
    # stopwatch with plus, static pictogram only
    d.ellipse((420, 326, 702, 608), fill=(12, 31, 42), outline=GOLD, width=7)
    d.rounded_rectangle((530, 285, 592, 334), radius=12, fill=GOLD)
    d.line((561, 377, 561, 464), fill=WHITE, width=9)
    d.line((561, 464, 625, 504), fill=WHITE, width=9)
    d.line((485, 540, 637, 540), fill=GOLD, width=10)
    d.line((561, 464, 561, 616), fill=GOLD, width=10)
    match_block(d, y=724)
    panel(d, (340, 944, 782, 1004), radius=14, width=2)
    # large added-time value
    panel(d, (330, 1032, 792, 1168), radius=24, width=3)
    panel(d, (150, 1192, 972, 1288), radius=20, width=2)
    footer_brand(d)
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assets = {
        "match_interrompu_unknown.png": build_interrupted_unknown(),
        "match_reporte.png": build_reported(),
        "match_annule.png": build_cancelled(),
        "reprise_match.png": build_resumed(),
        "temps_additionnel.png": build_added_time(),
    }
    for name, im in assets.items():
        path = OUT / name
        im.save(path, "PNG", optimize=True)
        print("BUILT", path, im.size, path.stat().st_size)


if __name__ == "__main__":
    main()
