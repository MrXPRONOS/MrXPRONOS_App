#!/usr/bin/env python3
# scripts/create_shorts_video.py
# Assemble les captures Telegram en une vidéo YouTube Shorts (verticale)
# sans upload automatique.

import os
import glob
import json
from datetime import datetime
from moviepy.editor import (
    ImageClip, CompositeVideoClip, TextClip, concatenate_videoclips,
    vfx, ColorClip
)

# Configuration
OUT_DIR = "telegram_out"                # Dossier contenant les images simple_*.png
VIDEO_OUT = "daily_pronos_shorts.mp4"   # Nom de la vidéo de sortie
DURATION_PER_IMAGE = 4                  # secondes par coupon
FPS = 24
SHORTS_W, SHORTS_H = 1080, 1920         # 9:16 pour YouTube Shorts

# Couleurs
BG_COLOR = (10, 10, 10)                # fond noir par défaut (tu pourras remplacer par une image)
GOLD = (212, 175, 55)

# Optionnel : chemin vers un fond personnalisé (par exemple une image ou un dégradé)
CUSTOM_BG_PATH = "assets/images/shorts_bg.png"   # mets ton propre fond ici (dimensions 1080x1920)
USE_CUSTOM_BG = os.path.exists(CUSTOM_BG_PATH)

def load_manifest():
    """Charge manifest.json créé par export_simple_coupons.mjs"""
    path = os.path.join(OUT_DIR, "manifest.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_background_clip(duration):
    """Retourne un clip de fond (image personnalisée ou couleur unie)"""
    if USE_CUSTOM_BG:
        bg = ImageClip(CUSTOM_BG_PATH).resize((SHORTS_W, SHORTS_H))
        return bg.set_duration(duration)
    else:
        return ColorClip(size=(SHORTS_W, SHORTS_H), color=BG_COLOR, duration=duration)

def create_intro_clip(date_str):
    """Intro avec titre et date"""
    txt = TextClip(
        f"🔥 PRONOSTICS MR XPRONOS\n📅 {date_str}",
        fontsize=70, color='white', stroke_color=GOLD, stroke_width=2,
        font='Arial-Bold', size=(SHORTS_W, None), method='caption'
    ).set_position('center').set_duration(3)

    txt = txt.fx(vfx.fadein, 0.5).fx(vfx.fadeout, 0.5)
    bg = get_background_clip(3)
    return CompositeVideoClip([bg, txt])

def create_outro_clip():
    """Outro avec lien et code promo"""
    more_url = os.environ.get("MORE_URL", "https://mrxpronos.github.io/MrXPRONOS_App/pronos.html")
    txt = f"📲 Plus de coupons :\n{more_url}\n\nCode promo : XPVIP"
    txt_clip = TextClip(
        txt, fontsize=55, color=GOLD, font='Arial',
        size=(SHORTS_W, None), method='caption'
    ).set_position('center').set_duration(4)
    txt_clip = txt_clip.fx(vfx.fadein, 0.5).fx(vfx.fadeout, 0.5)

    bg = get_background_clip(4)
    return CompositeVideoClip([bg, txt_clip])

def process_image(img_path):
    """
    Charge une image, la redimensionne pour tenir dans le format Shorts
    sans déformation, et l'anime (zoom doux + fondu).
    """
    img = ImageClip(img_path)
    # Calcul du facteur d'échelle pour que l'image tienne dans la zone centrale
    scale_w = SHORTS_W / img.w
    scale_h = SHORTS_H / img.h
    scale = min(scale_w, scale_h) * 0.85   # 85% de la taille max pour laisser un peu d'espace
    new_w = int(img.w * scale)
    new_h = int(img.h * scale)
    img = img.resize((new_w, new_h))

    # Position centrée
    x_pos = (SHORTS_W - new_w) // 2
    y_pos = (SHORTS_H - new_h) // 2
    img = img.set_position((x_pos, y_pos))

    # Animation : fondu entrant/sortant + zoom progressif
    img = img.fx(vfx.fadein, 0.5).fx(vfx.fadeout, 0.5)
    img = img.resize(lambda t: 1 + 0.03 * (t / DURATION_PER_IMAGE)).set_duration(DURATION_PER_IMAGE)

    # Optionnel : ajouter un cadre doré autour de l'image
    # (à faire avec une bordure via CompositeVideoClip ou overlay)

    return img

def main():
    print("🎬 Génération de la vidéo YouTube Shorts...")
    manifest = load_manifest()
    if not manifest:
        print("❌ Aucun manifest.json trouvé. Assure-toi que export_simple_coupons.mjs a été exécuté.")
        return

    date_str = manifest.get("date", datetime.now().strftime("%Y-%m-%d"))
    images = sorted(glob.glob(os.path.join(OUT_DIR, "simple_*.png")))

    if not images:
        print("❌ Aucune image PNG trouvée dans", OUT_DIR)
        return

    print(f"📸 {len(images)} images trouvées pour le {date_str}")

    # Construction des clips
    clips = [create_intro_clip(date_str)]

    for idx, img_path in enumerate(images, 1):
        print(f"  Traitement image {idx}/{len(images)} : {os.path.basename(img_path)}")
        img_clip = process_image(img_path)
        bg = get_background_clip(DURATION_PER_IMAGE)
        final_clip = CompositeVideoClip([bg, img_clip])
        clips.append(final_clip)

    clips.append(create_outro_clip())

    print("✂️ Assemblage des clips...")
    final_video = concatenate_videoclips(clips, method="compose")
    print("💾 Export de la vidéo...")
    final_video.write_videofile(
        VIDEO_OUT,
        fps=FPS,
        codec='libx264',
        audio_codec='aac',
        bitrate="2000k",
        threads=4
    )
    print(f"✅ Vidéo générée : {VIDEO_OUT}")

if __name__ == "__main__":
    main()