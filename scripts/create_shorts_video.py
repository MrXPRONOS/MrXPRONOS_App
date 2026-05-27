#!/usr/bin/env python3
# scripts/create_shorts_video.py
import os
import glob
import json
from datetime import datetime
from moviepy.editor import (
    ImageClip, CompositeVideoClip, TextClip, concatenate_videoclips,
    vfx, ColorClip
)
from moviepy.video.fx import resize

OUT_DIR = "telegram_out"
VIDEO_OUT = "daily_pronos_shorts.mp4"
DURATION_PER_IMAGE = 4          # secondes
FPS = 24
SHORTS_W, SHORTS_H = 1080, 1920   # 9:16

# Couleurs
BG_COLOR = (10, 10, 10)          # noir profond
GOLD = (212, 175, 55)

def load_manifest():
    path = os.path.join(OUT_DIR, "manifest.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

def create_background():
    """Crée un clip de fond uni (noir) aux dimensions Shorts."""
    return ColorClip(size=(SHORTS_W, SHORTS_H), color=BG_COLOR, duration=1)

def add_logo_overlay(clip):
    """Ajoute un logo en bas à droite (optionnel)."""
    try:
        logo = ImageClip("assets/images/logo_shorts.png").resize(height=80)
        logo = logo.set_position(("right", "bottom")).margin(right=20, bottom=20, opacity=1)
        return CompositeVideoClip([clip, logo])
    except:
        return clip

def create_intro_clip(date_str):
    """Génère une intro avec titre et date."""
    txt_clip = TextClip(
        f"🔥 PRONOSTICS MR XPRONOS\n📅 {date_str}",
        fontsize=70, color='white', stroke_color=GOLD, stroke_width=2,
        font='Arial-Bold', size=(SHORTS_W, None), method='caption'
    ).set_position('center').set_duration(3)

    # Effet d'apparition
    txt_clip = txt_clip.fx(vfx.fadein, 0.5).fx(vfx.fadeout, 0.5)

    bg = create_background().set_duration(3)
    return CompositeVideoClip([bg, txt_clip])

def create_outro_clip():
    """Outro avec lien vers le site."""
    txt = f"📲 Plus de coupons :\n{os.environ.get('MORE_URL', 'mrxpronos.com')}\n\nCode promo : XPVIP"
    txt_clip = TextClip(
        txt, fontsize=55, color=GOLD, font='Arial',
        size=(SHORTS_W, None), method='caption'
    ).set_position('center').set_duration(4)

    txt_clip = txt_clip.fx(vfx.fadein, 0.5).fx(vfx.fadeout, 0.5)

    bg = create_background().set_duration(4)
    return CompositeVideoClip([bg, txt_clip])

def process_image(img_path):
    """
    Charge l'image, la redimensionne pour tenir dans Shorts (1080x1920)
    sans déformer, et la centre.
    """
    img = ImageClip(img_path)
    # On calcule le facteur d'échelle pour que l'image tienne dans la largeur max
    scale_w = SHORTS_W / img.w
    scale_h = SHORTS_H / img.h
    scale = min(scale_w, scale_h)  # on garde le ratio
    new_w = int(img.w * scale)
    new_h = int(img.h * scale)
    img = img.resize((new_w, new_h))

    # Position centrée
    x_pos = (SHORTS_W - new_w) // 2
    y_pos = (SHORTS_H - new_h) // 2
    img = img.set_position((x_pos, y_pos))

    # Animation d'entrée : léger zoom + fondu
    img = img.fx(vfx.fadein, 0.5).fx(vfx.fadeout, 0.5)
    # Zoom progressif (optionnel)
    img = img.resize(lambda t: 1 + 0.03 * (t / DURATION_PER_IMAGE)).set_duration(DURATION_PER_IMAGE)

    # Ajouter un cadre doré autour de l'image (optionnel)
    # (on pourrait aussi ajouter un texte overlay avec la date du match)

    return img

def main():
    manifest = load_manifest()
    if not manifest:
        print("Manifest introuvable, aucune vidéo créée.")
        return

    date_str = manifest.get("date", datetime.now().strftime("%Y-%m-%d"))
    images = sorted(glob.glob(os.path.join(OUT_DIR, "simple_*.png")))

    if not images:
        print("Aucune image trouvée.")
        return

    clips = [create_intro_clip(date_str)]

    for img_path in images:
        clip = process_image(img_path)
        # On met l'image par-dessus un fond (pour être sûr)
        bg = create_background().set_duration(clip.duration)
        final_clip = CompositeVideoClip([bg, clip])
        clips.append(final_clip)

    clips.append(create_outro_clip())

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(VIDEO_OUT, fps=FPS, codec='libx264', audio_codec='aac', bitrate="2000k")

    print(f"✅ Vidéo Shorts créée : {VIDEO_OUT}")

if __name__ == "__main__":
    main()