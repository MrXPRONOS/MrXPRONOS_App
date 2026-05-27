#!/usr/bin/env python3
# scripts/create_shorts_video.py
import os
import glob
import json
from datetime import datetime
from moviepy import (
    ImageClip, CompositeVideoClip, TextClip, concatenate_videoclips,
    ColorClip, vfx
)

OUT_DIR = "telegram_out"
VIDEO_OUT = "daily_pronos_shorts.mp4"
DURATION_PER_IMAGE = 4          # secondes
FPS = 24
SHORTS_W, SHORTS_H = 1080, 1920   # 9:16

BG_COLOR = (10, 10, 10)          # noir profond
GOLD = (212, 175, 55)

def load_manifest():
    path = os.path.join(OUT_DIR, "manifest.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

def create_background():
    return ColorClip(size=(SHORTS_W, SHORTS_H), color=BG_COLOR, duration=1)

def create_intro_clip(date_str):
    txt_clip = TextClip(
        text=f"🔥 PRONOSTICS MR XPRONOS\n📅 {date_str}",
        font_size=70, color='white', stroke_color=GOLD, stroke_width=2,
        font='Arial-Bold', size=(SHORTS_W, None), method='caption'
    ).with_position('center').with_duration(3)
    txt_clip = txt_clip.with_effects([vfx.FadeIn(0.5), vfx.FadeOut(0.5)])
    bg = create_background().with_duration(3)
    return CompositeVideoClip([bg, txt_clip])

def create_outro_clip():
    txt = f"📲 Plus de coupons :\n{os.environ.get('MORE_URL', 'mrxpronos.com')}\n\nCode promo : XPVIP"
    txt_clip = TextClip(
        text=txt, font_size=55, color=GOLD, font='Arial',
        size=(SHORTS_W, None), method='caption'
    ).with_position('center').with_duration(4)
    txt_clip = txt_clip.with_effects([vfx.FadeIn(0.5), vfx.FadeOut(0.5)])
    bg = create_background().with_duration(4)
    return CompositeVideoClip([bg, txt_clip])

def process_image(img_path):
    img = ImageClip(img_path)
    scale_w = SHORTS_W / img.w
    scale_h = SHORTS_H / img.h
    scale = min(scale_w, scale_h)
    new_w = int(img.w * scale)
    new_h = int(img.h * scale)
    img = img.resized((new_w, new_h))
    x_pos = (SHORTS_W - new_w) // 2
    y_pos = (SHORTS_H - new_h) // 2
    img = img.with_position((x_pos, y_pos))
    img = img.with_effects([vfx.FadeIn(0.5), vfx.FadeOut(0.5)])
    # zoom progressif
    img = img.resized(lambda t: 1 + 0.03 * (t / DURATION_PER_IMAGE)).with_duration(DURATION_PER_IMAGE)
    bg = create_background().with_duration(DURATION_PER_IMAGE)
    return CompositeVideoClip([bg, img])

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
        clips.append(process_image(img_path))
    clips.append(create_outro_clip())

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(VIDEO_OUT, fps=FPS, codec='libx264', audio_codec='aac', bitrate="2000k")
    print(f"✅ Vidéo Shorts créée : {VIDEO_OUT}")

if __name__ == "__main__":
    main()