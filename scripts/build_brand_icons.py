#!/usr/bin/env python3
"""Regenerate all PNG PWA icons from the official MX crown SVG."""
from io import BytesIO
from pathlib import Path
import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "assets" / "images"
MARK = IMAGES / "mrxpronos-mark.svg"

def render(size):
    canvas = Image.new("RGBA", (size, size), (5, 16, 34, 255))
    side = round(size * .94)
    data = cairosvg.svg2png(url=str(MARK), output_width=side, output_height=side)
    art = Image.open(BytesIO(data)).convert("RGBA")
    canvas.alpha_composite(art, ((size-side)//2, (size-side)//2))
    return canvas.convert("RGB")

def main():
    for size in (72, 96, 128, 144, 152, 192, 384, 512):
        render(size).save(IMAGES / f"icon-{size}x{size}.png", "PNG", optimize=True)
    render(180).save(IMAGES / "apple-touch-icon.png", "PNG", optimize=True)
    render(64).save(IMAGES / "favicon.png", "PNG", optimize=True)
    render(64).save(IMAGES / "favicon.webp", "WEBP", quality=95)
    print("MX icons generated")

if __name__ == "__main__":
    main()
