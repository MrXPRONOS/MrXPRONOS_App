"""Add XPVIP sponsor strip to an *already rendered* Telegram coupon PNG.

Site images and the underlying ticket are never modified. Only an outgoing
Telegram attachment is composed. Source image is a 3D design asset.
"""
from pathlib import Path
from PIL import Image

BANNER = Path(__file__).resolve().parent.parent / "assets/images/telegram-xpvip-banner.webp"

def attach_banner(coupon_path):
    """Replace the temporary outgoing PNG with strip+untouched coupon pixels.

    Called exactly once per outgoing message. The original coupon is not
    resized or cropped; only the separate upper stripe is resized.
    """
    source = Path(coupon_path)
    if not BANNER.is_file():
        raise FileNotFoundError("Missing XPVIP banner: " + str(BANNER))
    with Image.open(source) as original, Image.open(BANNER) as artwork:
        coupon = original.convert("RGB")
        banner = artwork.convert("RGB")
        width = coupon.width
        height = round(banner.height * width / banner.width)
        if height <= 0 or height > width // 3:
            raise ValueError("XPVIP banner has unsupported proportions")
        banner = banner.resize((width,height),Image.Resampling.LANCZOS)
        result = Image.new("RGB", (width,height+coupon.height), "white")
        result.paste(banner,(0,0))
        result.paste(coupon,(0,height))
        result.save(source,"PNG",optimize=True)
    return source
