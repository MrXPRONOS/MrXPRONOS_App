#!/usr/bin/env python3
"""Publication ponctuelle : visuel + légende + bouton Telegram bleu."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFont

HANDLE = "@mr_xpronos"
REF = "PARTENARIAT-CANAL"
PREFILL = ("Bonjour 👋 Je suis intéressé par votre offre de partenariat "
           "pour les canaux Telegram. 🤝\nRéférence : " + REF)
URL = "https://t.me/mr_xpronos?text=" + quote(PREFILL, safe="")
CAPTION = (
    "<b>🚀 Faites grandir votre canal Telegram, sans effort !</b>\n\n"
    "Vous gérez un canal de films, d'animés, de sport ou autre ? "
    "Je peux l'alimenter gratuitement avec des publications régulières "
    "et adaptées à votre audience.\n\n"
    "✅ Du contenu régulier et de qualité\n"
    "✅ Un canal plus actif, sans travail supplémentaire\n"
    "✅ Vous restez propriétaire et gardez le contrôle\n\n"
    "🤝 <b>En échange :</b> vous m'autorisez à publier occasionnellement "
    "mes propres publicités, selon des modalités convenues ensemble.\n\n"
    "💬 <b>Intéressé ?</b> Cliquez sur le bouton bleu ci-dessous ou "
    "contactez <b>@mr_xpronos</b>.\n"
    "<i>Réf. : PARTENARIAT-CANAL</i>"
)
KEYBOARD = {"inline_keyboard": [[{
    "text": "💬 Proposer un partenariat",
    "url": URL,
    "style": "primary"
}]]}

def font(size, bold=False):
    sources = (["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"] if bold
               else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                     "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"])
    for path in sources:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def center(draw, x, y, value, size, color, bold=False):
    f = font(size, bold)
    bbox = draw.textbbox((0, 0), value, font=f)
    draw.text((x-(bbox[2]-bbox[0])/2, y), value, font=f, fill=color)

def poster(path):
    w = h = 1080
    im = Image.new("RGB", (w, h), (3, 19, 43))
    # Discret fond dégradé bleu marine.
    pix = im.load()
    for y in range(h):
        for x in range(w):
            v = x / w
            pix[x, y] = (int(4+7*v), int(20+24*v), int(47+45*v))
    d = ImageDraw.Draw(im)
    cyan=(44,210,255); white=(248,253,255)
    d.ellipse((685,-210,1310,435),outline=(9,91,168),width=4)
    d.ellipse((-280,650,410,1270),outline=(14,90,176),width=4)
    d.rounded_rectangle((54,43,1026,105),20,fill=(12,54,103),outline=(22,156,243),width=2)
    d.ellipse((72,55,112,95),fill=(24,171,249))
    d.polygon([(80,75),(104,64),(93,90),(88,79)],fill=white)
    d.text((127,59),"PARTENARIAT TELEGRAM",font=font(29,True),fill=white)
    d.text((864,61),"ÉCHANGE",font=font(19,True),fill=cyan)
    center(d,540,151,"FAITES GRANDIR VOTRE",56,white,True)
    center(d,540,216,"CANAL TELEGRAM",78,cyan,True)
    d.rounded_rectangle((230,316,850,399),radius=26,fill=(11,112,206),outline=(67,229,254),width=3)
    center(d,540,322,"SANS EFFORT !",65,white,True)
    center(d,540,432,"Je m’occupe de vos publications",34,white,True)
    center(d,540,475,"et de l’animation de votre canal.",31,(182,211,237))
    for i, label in enumerate(["FILMS & SÉRIES","ANIMÉS","SPORT","AUTRES"]):
        x=54+i*248
        d.rounded_rectangle((x,552,x+227,647),radius=23,fill=(11,46,91),outline=(34,156,236),width=2)
        center(d,x+113,575,label,22,white,True)
        d.rounded_rectangle((x+21,614,x+207,618),radius=2,fill=(23,180,245))
    d.rounded_rectangle((54,678,1026,841),radius=28,fill=(8,37,75),outline=(30,105,172),width=3)
    for i, txt in enumerate(["Contenu régulier et adapté","Canal actif et attractif",
                              "Contrôle conservé à 100 %"]):
        yy=710+i*42
        d.ellipse((84,yy,110,yy+26),fill=cyan)
        d.line((91,yy+13,97,yy+20),fill=(5,38,73),width=3)
        d.line((97,yy+20,105,yy+7),fill=(5,38,73),width=3)
        d.text((131,yy-2),txt,font=font(27,True),fill=white)
    d.rounded_rectangle((54,865,1026,942),radius=25,fill=(11,83,151),outline=(19,190,255),width=3)
    center(d,540,878,"EN ÉCHANGE : PUBLICITÉS OCCASIONNELLES",28,white,True)
    center(d,540,914,"Selon des modalités convenues ensemble",17,(190,232,254))
    d.rounded_rectangle((240,956,840,1036),radius=28,fill=(17,175,243),outline=(129,239,255),width=3)
    center(d,540,966,"ÉCRIVEZ À @mr_xpronos",35,(2,23,56),True)
    center(d,540,1010,REF,16,(1,47,83),True)
    path.parent.mkdir(parents=True,exist_ok=True)
    im.save(path,"JPEG",quality=92,optimize=True,subsampling=0)
    return path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--image",type=Path,default=None,
                        help="Visuel JPEG/PNG déjà présent dans le dépôt, sinon généré")
    parser.add_argument("--output",type=Path,default=Path("/tmp/mrxpronos-partenariat-canal.jpg"))
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args()
    image=args.image if args.image else poster(args.output)
    if not image.exists():
        raise SystemExit("Visuel introuvable: "+str(image))
    if len(CAPTION.encode("utf-8"))>1024:
        raise SystemExit("Légende dépassant 1024 octets")
    print("PHOTO:",image,"LÉGENDE:",CAPTION,"BOUTON:",json.dumps(KEYBOARD,ensure_ascii=False))
    if args.dry_run:
        print("PREVIEW_OK — Aucun message publié.")
        return
    token=os.getenv("PARTNERSHIP_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    chat=(os.getenv("PARTNERSHIP_CHAT_ID") or "").strip()
    if not token or not chat:
        raise SystemExit("Secrets/token et chat de destination nécessaires")
    mime="image/png" if image.suffix.lower()==".png" else "image/jpeg"
    with image.open("rb") as f:
        resp=requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data={"chat_id":chat,"caption":CAPTION,"parse_mode":"HTML",
                  "reply_markup":json.dumps(KEYBOARD,ensure_ascii=False)},
            files={"photo":(image.name,f,mime)},
            timeout=(10,90))
    resp.raise_for_status()
    body=resp.json()
    if not body.get("ok"):
        raise SystemExit("Telegram a refusé l'envoi : "+str(body.get("description")))
    print("PUBLICATION_OK message_id="+str(body["result"]["message_id"]))

if __name__=="__main__":
    main()
