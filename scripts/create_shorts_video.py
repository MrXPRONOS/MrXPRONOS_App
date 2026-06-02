#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import glob
from PIL import Image, ImageOps, ImageDraw
from moviepy.editor import ImageClip, concatenate_videoclips

OUT_DIR = os.environ.get("OUT_DIR", "telegram_out")
VIDEO_OUT = os.environ.get("VIDEO_OUT", os.path.join(OUT_DIR, "pronos_du_jour.mp4"))

WIDTH = 1080
HEIGHT = 1920
DURATION_PER_IMAGE = 4

def prepare_image(input_path, output_path):
    img = Image.open(input_path).convert("RGB")

    background = Image.new("RGB", (WIDTH, HEIGHT), (13, 13, 13))

    # Redimensionner l’image sans la déformer
    img.thumbnail((WIDTH - 100, HEIGHT - 260), Image.LANCZOS)

    x = (WIDTH - img.width) // 2
    y = (HEIGHT - img.height) // 2

    background.paste(img, (x, y))

    draw = ImageDraw.Draw(background)
    draw.text((60, 60), "MR XPRONOS", fill=(212, 175, 55))
    draw.text((60, HEIGHT - 120), "Plus de coupons sur mrxpronos.github.io", fill=(255, 255, 255))

    background.save(output_path, quality=95)

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    images = sorted(glob.glob(os.path.join(OUT_DIR, "*.png")))

    if not images:
        raise SystemExit(f"Aucune image trouvée dans {OUT_DIR}")

    prepared = []

    for index, image_path in enumerate(images, start=1):
        prepared_path = os.path.join(OUT_DIR, f"video_slide_{index:02d}.jpg")
        prepare_image(image_path, prepared_path)
        prepared.append(prepared_path)

    clips = [
        ImageClip(path).set_duration(DURATION_PER_IMAGE)
        for path in prepared
    ]

    video = concatenate_videoclips(clips, method="compose")
    video.write_videofile(
        VIDEO_OUT,
        fps=30,
        codec="libx264",
        audio=False,
        preset="medium",
        threads=2
    )

    print(f"Vidéo créée : {VIDEO_OUT}")

if __name__ == "__main__":
    main()