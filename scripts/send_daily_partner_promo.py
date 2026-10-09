#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import base64
import textwrap
import requests
from telegram_rich import post_photo
from telegram_promo_channels import promo_channels, deliver_to_both
from telegram_promo_colors import colorized_button
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

TOKEN=os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID=os.environ.get("TELEGRAM_CHAT_ID")
SECONDARY_CHAT_ID=os.environ.get("TELEGRAM_CHAT_ID_SECONDARY")
IMAGE_PATH=os.environ.get("PROMO_IMAGE","assets/images/xpvip-partners-daily.jpg")
BASE64_IMAGE_DIR=Path("assets/images/xpvip-partners-daily.b64")
BASE64_IMAGE_PARTS=("01.txt","02.txt","03.txt")

CAPTION=os.environ.get(
    "PROMO_CAPTION",
    "🔥 <b>XPVIP — PARTENAIRES MrXPRONOS</b>\n\n"
    "Retrouve ci-dessous les liens d’inscription de nos bookmakers partenaires.\n\n"
    "<blockquote>🎁 <b>CODE PROMO : XPVIP</b>\n"
    "<i>Avant de terminer ton inscription, vérifie que XPVIP est bien renseigné "
    "lorsque le champ « Code promo » est proposé.</i></blockquote>\n\n"
    "✨ <b>Un seul code. Plusieurs partenaires.</b>\n"
    "👇 <i>Choisis simplement ton bookmaker avec l’un des boutons ci-dessous.</i>\n\n"
    "⚠️ <b>18+</b> · <i>Les offres et conditions peuvent varier selon le pays et le compte. "
    "Joue de façon responsable.</i>"
)

PARTNERS=[
    ("1xBet","https://reffpa.com/L?tag=d_2054511m_1573c_&site=2054511&ad=1573","assets/images/1xbet.png"),
    ("1Win","https://1wrbgb.com/?open=register&p=qqcw","assets/images/1win.png"),
    ("MelBet","https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041","assets/images/melbet.png"),
    ("LineBet","https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3072389&ad=22611","assets/images/linebet.png"),
    ("Betclic","https://betpari-click.com/2vY0?extid=USD","assets/images/betclic.png"),
    ("BetWinner","https://bwredir.com/299Y","assets/images/betwinner.png"),
]

def font(size,bold=False):
    candidates=[
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for f in candidates:
        if Path(f).exists():
            return ImageFont.truetype(f,size=size)
    return ImageFont.load_default()

def chat_ids():
    vals=[("primary",CHAT_ID)]
    if SECONDARY_CHAT_ID and SECONDARY_CHAT_ID.strip():
        vals.append(("secondary",SECONDARY_CHAT_ID.strip()))
    seen=set()
    out=[]
    for role,value in vals:
        if value and value.strip() and value.strip() not in seen:
            seen.add(value.strip())
            out.append((role,value.strip()))
    return out

def keyboard(image_path):
    buttons=[]
    for name,url,_ in PARTNERS:
        buttons.append(colorized_button(f"⚽ S’inscrire sur {name}",url,image_path))
    return {"inline_keyboard":[buttons[0:2],buttons[2:4],buttons[4:6]]}

def _fit_logo(path,max_w,max_h):
    try:
        img=Image.open(path).convert("RGBA")
        bbox=img.getbbox()
        if bbox:
            img=img.crop(bbox)
        ratio=min(max_w/max(1,img.width),max_h/max(1,img.height))
        if ratio<1:
            img=img.resize((max(1,int(img.width*ratio)),max(1,int(img.height*ratio))),Image.LANCZOS)
        return img
    except Exception as exc:
        print(f"⚠️ Logo ignoré {path}: {exc}")
        return None

def generate_fallback_common(out_path):
    W,H=1080,1080
    navy=(6,32,72)
    blue=(16,101,224)
    cyan=(37,199,245)
    white=(248,250,255)
    muted=(190,208,232)

    img=Image.new("RGB",(W,H),navy)
    draw=ImageDraw.Draw(img)

    # En-tête Prono Live
    draw.rectangle((0,0,W,16),fill=cyan)
    draw.text((70,55),"PRONO LIVE",font=font(38,True),fill=white)
    draw.text((70,112),"CODE PROMO PARTENAIRES",font=font(60,True),fill=white)
    draw.text((70,184),"Un seul code • 6 bookmakers partenaires",font=font(30),fill=muted)

    # Bloc XPVIP
    draw.rounded_rectangle((70,250,1010,430),radius=38,fill=(245,249,255),outline=cyan,width=5)
    draw.text((110,282),"CODE PROMO",font=font(34,True),fill=navy)
    draw.text((110,335),"XPVIP",font=font(78,True),fill=blue)
    draw.text((585,335),"18+",font=font(34,True),fill=(95,111,135))

    # Grille 2 x 3 des partenaires
    positions=[(70,485),(555,485),(70,650),(555,650),(70,815),(555,815)]
    for (name,_,logo_path),(x,y) in zip(PARTNERS,positions):
        draw.rounded_rectangle((x,y,x+455,y+130),radius=28,fill=white,outline=(117,164,226),width=3)
        logo=_fit_logo(logo_path,230,76)
        if logo:
            img.paste(logo,(x+24,y+27),logo)
        else:
            draw.text((x+25,y+42),name,font=font(34,True),fill=navy)
        draw.text((x+290,y+48),"XPVIP",font=font(29,True),fill=blue)

    draw.text((70,995),"Vérifie le code promo avant de valider • Joue responsablement",font=font(23),fill=muted)
    img.save(out_path,"JPEG",quality=90,optimize=True,progressive=False)
    return out_path

def restore_real_promo_image():
    encoded_parts=[]
    for name in BASE64_IMAGE_PARTS:
        part=BASE64_IMAGE_DIR / name
        if not part.exists():
            raise SystemExit(f"Morceau image XPVIP introuvable: {part}")
        encoded_parts.append(part.read_text(encoding="utf-8").strip())

    encoded="".join(encoded_parts)
    try:
        raw=base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise SystemExit(f"Image XPVIP encodée invalide: {exc}")

    source=Path(".tmp_xpvip_source.jpg")
    source.write_bytes(raw)

    try:
        with Image.open(source) as check:
            check.verify()
    except Exception as exc:
        raise SystemExit(f"Image XPVIP reconstruite invalide: {exc}")

    print(f"✅ Vraie image XPVIP reconstruite depuis {len(BASE64_IMAGE_PARTS)} morceaux")
    return source


def prepare_telegram_image(source):
    source=restore_real_promo_image()
    out=Path(".tmp_xpvip_telegram.jpg")

    try:
        with Image.open(source) as im:
            im=ImageOps.exif_transpose(im).convert("RGB")
            max_side=2000
            if max(im.size)>max_side:
                ratio=max_side/max(im.size)
                im=im.resize((max(1,int(im.width*ratio)),max(1,int(im.height*ratio))),Image.LANCZOS)
            im.save(out,"JPEG",quality=92,optimize=True,progressive=False)

        with Image.open(out) as check:
            check.verify()

        print(f"🖼️ Vraie image promo XPVIP prête pour Telegram: {out}")
        return out
    except Exception as exc:
        raise SystemExit(f"Impossible de préparer la vraie image XPVIP: {exc}")

def main():
    if not TOKEN or not CHAT_ID:
        raise SystemExit("Secrets manquants: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")

    image_path=prepare_telegram_image(IMAGE_PATH)
    markup=keyboard(image_path)
    def send_to(cid):
        post_photo(requests,TOKEN,cid,Path(image_path),CAPTION,markup,
                   timeout=120,mime="image/jpeg")
    deliver_to_both(promo_channels(CHAT_ID,SECONDARY_CHAT_ID),
                    send_to,label="Promo XPVIP commune")

if __name__=="__main__":
    main()
