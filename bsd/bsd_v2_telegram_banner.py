"""Add XPVIP sponsor strip to an *already rendered* Telegram coupon PNG.

Site images and the underlying ticket are never modified. Only an outgoing
Telegram attachment is composed. Source image is a 3D design asset.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BANNER = Path(__file__).resolve().parent.parent / "assets/images/telegram-xpvip-banner.webp"

ROOT = Path(__file__).resolve().parent.parent

def _font(size, bold=True):
    for name in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ):
        if Path(name).is_file():
            return ImageFont.truetype(name,size)
    return ImageFont.load_default()

def _build_embedded_banner(partners=("1xbet", "melbet")):
    """Bundled fallback constructed from the actual partner logos in the repo.

    Prefer the official 3D artwork at BANNER when present.
    """
    w,h=1080,155
    banner=Image.new("RGB",(w,h),"#030508")
    draw=ImageDraw.Draw(banner)
    # Logos and promo code are placed in an independent top strip.
    for name,box in zip(partners, ((30,36,295,119),(430,36,705,119))):
        logo_path=ROOT/"assets/images"/(name+".png")
        if logo_path.exists():
            try:
                with Image.open(logo_path) as item:
                    logo=item.convert("RGBA")
                    logo.thumbnail((box[2]-box[0],box[3]-box[1]),Image.Resampling.LANCZOS)
                    x=box[0]+((box[2]-box[0])-logo.width)//2
                    y=box[1]+((box[3]-box[1])-logo.height)//2
                    banner.paste(logo,(x,y),logo)
                continue
            except OSError:
                pass
        draw.text((box[0]+15,59),name.upper(),font=_font(42),fill="#FFFFFF",stroke_width=1)
    draw.text((337,63),"OU",font=_font(34),fill="#D8DCE6")
    draw.rounded_rectangle((735,34,1058,124),radius=18,fill="#BD8300")
    draw.rounded_rectangle((739,28,1052,117),radius=15,fill="#FFD12A",
                           outline="#FFF1A2",width=4)
    draw.text((753,41),"CODE",font=_font(20),fill="#161207")
    draw.text((753,67),"PROMO",font=_font(20),fill="#161207")
    draw.text((829,49),"XPVIP",font=_font(43),fill="#171008",
              stroke_width=1,stroke_fill="#E6A000")
    return banner


def attach_banner(coupon_path, pack="1xbet_melbet"):
    """Replace the temporary outgoing PNG with strip+untouched coupon pixels.

    Called exactly once per outgoing message. The original coupon is not
    resized or cropped; only the separate upper stripe is resized.
    """
    source = Path(coupon_path)
    with Image.open(source) as original:
        coupon = original.convert("RGB")
        banner = (Image.open(BANNER).convert("RGB") if BANNER.is_file() else _build_embedded_banner()) if pack == "1xbet_melbet" else _build_embedded_banner(("1win", "betwinner"))
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
