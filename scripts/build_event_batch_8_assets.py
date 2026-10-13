"""Build the eighth 1122x1402 Actu Foot event template batch.

Batch 8:
- SCORE LIVE CONFIRMÉ — un seul logo
- SCORE LIVE CONFIRMÉ — aucun logo
- SCORE LIVE CONFIRMÉ — minute absente
- BUT — buteur + passeur disponibles
- BUT — buteur connu / passeur inconnu

The backgrounds intentionally avoid visible empty logo/minute/player placeholders.
"""
from __future__ import annotations

from PIL import ImageDraw
from build_event_batch_2_assets import (
    OUT, W, H, GOLD, GOLD_DARK, WHITE, GREEN,
    gradient, glow, panel, outer_frame, title, footer_brand,
)

CYAN = (55, 176, 210)
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
    glow(im, (W//2, 440), 295, accent, 55)


def score_core(d, *, y=365, wide_names=False):
    if wide_names:
        panel(d, (76, y+250, 520, y+322), radius=16, width=2)
        panel(d, (602, y+250, 1046, y+322), radius=16, width=2)
    else:
        panel(d, (86, y+250, 436, y+318), radius=16, width=2)
        panel(d, (686, y+250, 1036, y+318), radius=16, width=2)
    panel(d, (382, y+28, 530, y+183), radius=22, width=4)
    panel(d, (592, y+28, 740, y+183), radius=22, width=4)


def build_score_one_logo():
    im = gradient()
    stadium_base(im, CYAN)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "SCORE LIVE CONFIRMÉ", CYAN)
    # No visible logo circles. Only the available logo is pasted by the renderer
    # into its side's invisible safe box.
    score_core(d, y=340, wide_names=False)
    panel(d, (430, 555, 692, 625), radius=18, width=3)  # minute
    panel(d, (150, 720, 972, 790), radius=16, width=2)  # competition
    panel(d, (150, 825, 972, 950), radius=20, width=2)  # status
    panel(d, (150, 985, 972, 1115), radius=20, width=2) # info
    panel(d, (160, 1160, 962, 1218), radius=14, width=2)
    footer_brand(d)
    return im


def build_score_no_logos():
    im = gradient()
    stadium_base(im, CYAN)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "SCORE LIVE CONFIRMÉ", CYAN)
    # Names are deliberately wider because there are no logos at all.
    score_core(d, y=340, wide_names=True)
    panel(d, (430, 555, 692, 625), radius=18, width=3)
    panel(d, (150, 720, 972, 790), radius=16, width=2)
    panel(d, (150, 825, 972, 950), radius=20, width=2)
    panel(d, (150, 985, 972, 1115), radius=20, width=2)
    panel(d, (160, 1160, 962, 1218), radius=14, width=2)
    footer_brand(d)
    return im


def build_score_no_minute():
    im = gradient()
    stadium_base(im, GOLD)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "SCORE LIVE CONFIRMÉ", GOLD)
    # No minute panel anywhere. Optional logos can be overlaid without visible
    # placeholder circles, so 0/1/2 logos remain visually clean.
    score_core(d, y=355, wide_names=False)
    panel(d, (150, 705, 972, 775), radius=16, width=2)
    panel(d, (150, 815, 972, 950), radius=20, width=2)
    panel(d, (150, 990, 972, 1125), radius=20, width=2)
    panel(d, (160, 1170, 962, 1228), radius=14, width=2)
    footer_brand(d)
    return im


def goal_scene(im, accent=GREEN):
    d = ImageDraw.Draw(im)
    # goal frame
    d.rectangle((314, 310, 808, 590), outline=WHITE, width=9)
    for x in range(350, 808, 58):
        d.line((x, 310, x, 590), fill=(80, 93, 102), width=2)
    for y in range(350, 590, 48):
        d.line((314, y, 808, y), fill=(80, 93, 102), width=2)
    # ball impact
    d.ellipse((530, 392, 592, 454), fill=WHITE, outline=accent, width=5)
    glow(im, (561, 423), 120, accent, 75)


def goal_match_strip(d):
    # No visible logo circles: logos, if available, overlay discreetly.
    panel(d, (68, 710, 350, 772), radius=15, width=2)
    panel(d, (772, 710, 1054, 772), radius=15, width=2)
    panel(d, (390, 665, 518, 790), radius=18, width=3)
    panel(d, (604, 665, 732, 790), radius=18, width=3)
    panel(d, (438, 805, 684, 864), radius=15, width=2)


def build_goal_full():
    im = gradient()
    stadium_base(im, GREEN)
    goal_scene(im, GREEN)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "BUT", GREEN)
    goal_match_strip(d)
    # scorer + assister: two real fields because both are known.
    panel(d, (120, 925, 540, 1020), radius=19, width=2)
    panel(d, (582, 925, 1002, 1020), radius=19, width=2)
    panel(d, (150, 1050, 972, 1120), radius=16, width=2)
    panel(d, (150, 1145, 972, 1230), radius=19, width=2)
    panel(d, (160, 1250, 962, 1292), radius=12, width=2)
    footer_brand(d)
    return im


def build_goal_scorer_only():
    im = gradient()
    stadium_base(im, GREEN)
    goal_scene(im, GREEN)
    d = ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "BUT", GREEN)
    goal_match_strip(d)
    # One wide scorer field; there is deliberately no assist field.
    panel(d, (170, 925, 952, 1025), radius=20, width=2)
    panel(d, (150, 1055, 972, 1125), radius=16, width=2)
    panel(d, (150, 1150, 972, 1235), radius=19, width=2)
    panel(d, (160, 1252, 962, 1292), radius=12, width=2)
    footer_brand(d)
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assets = {
        "score_live_one_logo.png": build_score_one_logo(),
        "score_live_no_logos.png": build_score_no_logos(),
        "score_live_no_minute.png": build_score_no_minute(),
        "but_full.png": build_goal_full(),
        "but_scorer_only.png": build_goal_scorer_only(),
    }
    for name, im in assets.items():
        path = OUT / name
        im.save(path, "PNG", optimize=True)
        print("BUILT", path, im.size, path.stat().st_size)


if __name__ == "__main__":
    main()
