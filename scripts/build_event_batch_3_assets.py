"""Build the third 1122x1402 Actu Foot event template batch."""
from __future__ import annotations

from PIL import ImageDraw
from build_event_batch_2_assets import (
    OUT, W, H, GOLD, GOLD_DARK, WHITE, RED, GREEN,
    gradient, glow, panel, outer_frame, title, match_block, footer_brand,
)

CYAN = (55, 176, 210)
AMBER = (239, 167, 64)
ORANGE = (226, 104, 48)


def stadium_base(im, accent):
    d = ImageDraw.Draw(im)
    # Same premium broadcast family, different event scene.
    for r in (710, 650, 590, 530):
        d.arc((W//2-r, 210-r//2, W//2+r, 210+r), 190, 350, fill=(38, 46, 54), width=2)
    for x in (95, 1027):
        for rr in (48, 35, 22):
            d.ellipse((x-rr, 292-rr, x+rr, 292+rr), outline=(142, 120, 75), width=2)
    for yy in (575, 620, 665, 710):
        d.line((0, yy, W, yy), fill=(18, 42, 50), width=2)
    d.polygon([(210, 728), (912, 728), (760, 500), (362, 500)], outline=(31, 73, 74))
    glow(im, (W//2, 445), 275, accent, 58)


def medical_cross(d, cx, cy, size, color):
    w = max(22, size // 3)
    d.rounded_rectangle((cx-w//2, cy-size//2, cx+w//2, cy+size//2),
                        radius=w//3, fill=color, outline=(238, 246, 248), width=3)
    d.rounded_rectangle((cx-size//2, cy-w//2, cx+size//2, cy+w//2),
                        radius=w//3, fill=color, outline=(238, 246, 248), width=3)


def player_silhouette(d, cx, cy, scale=1.0, outline=WHITE):
    r=int(38*scale)
    d.ellipse((cx-r, cy-155*scale-r, cx+r, cy-155*scale+r), outline=outline, width=max(3,int(5*scale)))
    d.line((cx, cy-115*scale, cx, cy+20*scale), fill=outline, width=max(4,int(7*scale)))
    d.line((cx, cy-65*scale, cx-70*scale, cy-5*scale), fill=outline, width=max(4,int(7*scale)))
    d.line((cx, cy-65*scale, cx+70*scale, cy-5*scale), fill=outline, width=max(4,int(7*scale)))
    d.line((cx, cy+20*scale, cx-52*scale, cy+118*scale), fill=outline, width=max(4,int(7*scale)))
    d.line((cx, cy+20*scale, cx+52*scale, cy+118*scale), fill=outline, width=max(4,int(7*scale)))


def build_intervention_medicale():
    im=gradient()
    stadium_base(im, CYAN)
    d=ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "INTERVENTION MÉDICALE", CYAN)
    # medical bag + cross; does not assert an injury
    d.rounded_rectangle((414, 332, 708, 585), radius=38, fill=(11, 31, 43),
                        outline=CYAN, width=6)
    d.rounded_rectangle((487, 290, 635, 350), radius=20, fill=(11,31,43),
                        outline=CYAN, width=5)
    medical_cross(d, W//2, 460, 135, CYAN)
    match_block(d, y=724)
    panel(d, (340, 944, 782, 1004), radius=14, width=2)
    panel(d, (150, 1028, 972, 1092), radius=16, width=2)
    panel(d, (150, 1112, 972, 1212), radius=20, width=2)
    panel(d, (160, 1234, 962, 1286), radius=13, width=2)
    footer_brand(d)
    return im


def build_blessure_confirmee():
    im=gradient()
    stadium_base(im, ORANGE)
    d=ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "BLESSURE CONFIRMÉE", ORANGE)
    player_silhouette(d, 500, 482, 1.0, WHITE)
    # fixed medical marker only
    medical_cross(d, 690, 448, 92, ORANGE)
    d.arc((580, 480, 760, 635), 195, 345, fill=ORANGE, width=8)
    match_block(d, y=724)
    panel(d, (340, 944, 782, 1004), radius=14, width=2)
    panel(d, (150, 1028, 600, 1092), radius=16, width=2)
    panel(d, (642, 1028, 972, 1092), radius=16, width=2)
    panel(d, (150, 1112, 972, 1215), radius=20, width=2)
    panel(d, (160, 1235, 962, 1287), radius=13, width=2)
    footer_brand(d)
    return im


def build_retour_jeu():
    im=gradient()
    stadium_base(im, GREEN)
    d=ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "RETOUR AU JEU", GREEN)
    player_silhouette(d, 485, 488, 1.0, WHITE)
    # green comeback arrow
    d.arc((505, 338, 770, 600), 225, 515, fill=GREEN, width=13)
    d.polygon([(735, 350), (782, 356), (757, 398)], fill=GREEN)
    match_block(d, y=724)
    panel(d, (340, 944, 782, 1004), radius=14, width=2)
    panel(d, (180, 1028, 942, 1096), radius=18, width=2)
    panel(d, (250, 1112, 872, 1173), radius=16, width=2)
    panel(d, (150, 1192, 972, 1287), radius=20, width=2)
    footer_brand(d)
    return im


def build_match_suspendu():
    im=gradient()
    stadium_base(im, AMBER)
    d=ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "MATCH SUSPENDU", AMBER)
    # pause symbol + caution framing
    d.rounded_rectangle((400, 335, 722, 590), radius=34, fill=(16, 29, 38),
                        outline=AMBER, width=6)
    d.rounded_rectangle((470, 392, 525, 535), radius=12, fill=AMBER)
    d.rounded_rectangle((597, 392, 652, 535), radius=12, fill=AMBER)
    d.line((430, 565, 692, 365), fill=GOLD_DARK, width=3)
    match_block(d, y=724)
    panel(d, (340, 944, 782, 1004), radius=14, width=2)
    panel(d, (150, 1032, 972, 1192), radius=22, width=2)
    panel(d, (160, 1218, 962, 1284), radius=14, width=2)
    footer_brand(d)
    return im


def build_match_interrompu_full():
    im=gradient()
    stadium_base(im, RED)
    d=ImageDraw.Draw(im)
    outer_frame(d)
    title(d, "MATCH INTERROMPU", RED)
    # stop icon, clearly distinct from suspension
    d.regular_polygon((W//2, 458, 142), n_sides=8, rotation=22.5,
                      fill=(60, 20, 26), outline=RED)
    d.rounded_rectangle((W//2-18, 370, W//2+18, 492), radius=14, fill=WHITE)
    d.ellipse((W//2-20, 515, W//2+20, 555), fill=WHITE)
    match_block(d, y=724)
    panel(d, (340, 944, 782, 1004), radius=14, width=2)
    panel(d, (150, 1030, 972, 1110), radius=17, width=2)
    panel(d, (150, 1128, 972, 1216), radius=19, width=2)
    panel(d, (160, 1236, 962, 1288), radius=13, width=2)
    footer_brand(d)
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assets = {
        "intervention_medicale.png": build_intervention_medicale(),
        "blessure_confirmee.png": build_blessure_confirmee(),
        "retour_au_jeu.png": build_retour_jeu(),
        "match_suspendu.png": build_match_suspendu(),
        "match_interrompu_full.png": build_match_interrompu_full(),
    }
    for name, im in assets.items():
        path = OUT / name
        im.save(path, "PNG", optimize=True)
        print("BUILT", path, im.size, path.stat().st_size)


if __name__ == "__main__":
    main()
