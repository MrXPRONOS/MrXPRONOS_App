#!/usr/bin/env python3
"""Generate MX PWA icons from the official approved transparent PNG, not the obsolete SVG."""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "assets" / "images"
SOURCE = IMAGES / "mrxpronos-mark.png"
BACKGROUND = (3, 17, 38, 255)

def render(size):
    mark = Image.open(SOURCE).convert("RGBA")
    canvas = Image.new("RGBA", (size, size), BACKGROUND)
    side = int(size * (0.72 if size >= 128 else 0.79))
    artwork = mark.resize((side, side), Image.Resampling.LANCZOS)
    canvas.alpha_composite(artwork, ((size-side)//2, (size-side)//2))
    return canvas.convert("RGB")

def main():
    for size in (72, 96, 128, 144, 152, 192, 384, 512):
        render(size).save(IMAGES / f"icon-{size}x{size}.png", "PNG", optimize=True)
    render(180).save(IMAGES / "apple-touch-icon.png", "PNG", optimize=True)
    render(64).save(IMAGES / "favicon.png", "PNG", optimize=True)
    render(64).save(IMAGES / "favicon.webp", "WEBP", quality=95)
    print("Official crowned MX icons generated")

if __name__ == "__main__":
    main()
