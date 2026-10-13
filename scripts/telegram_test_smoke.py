#!/usr/bin/env python3
"""Smoke test visuel pour le canal Telegram de test Mr XPRONOS."""
from __future__ import annotations
import io,os
from datetime import datetime,timezone
import requests
from PIL import Image,ImageDraw,ImageFont

def font(size,bold=False):
    paths=[
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in paths:
        try:return ImageFont.truetype(path,size)
        except OSError:pass
    return ImageFont.load_default()

def build():
    im=Image.new("RGB",(1080,1080),(6,23,37))
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((60,60,1020,1020),radius=42,outline=(231,174,68),width=5)
    d.text((95,115),"MR XPRONOS",font=font(58,True),fill=(245,248,250))
    d.text((95,220),"CANAL DE TEST TELEGRAM",font=font(48,True),fill=(231,174,68))
    d.rounded_rectangle((95,340,985,750),radius=35,fill=(14,48,69))
    d.text((145,410),"✅ ROUTAGE TEST ACTIF",font=font(52,True),fill=(238,244,246))
    d.text((145,505),"Les visuels de validation manuelle",font=font(34),fill=(212,224,230))
    d.text((145,560),"seront envoyés ici, jamais sur le",font=font(34),fill=(212,224,230))
    d.text((145,615),"canal de production.",font=font(34),fill=(212,224,230))
    stamp=datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    d.text((95,900),stamp,font=font(30),fill=(159,184,197))
    return im

def main():
    token=os.getenv("FOOTBALL_NEWS_BOT_TOKEN","").strip()
    chat=os.getenv("TELEGRAM_TEST_CHAT_ID","").strip()
    if not token or not chat:
        raise SystemExit("FOOTBALL_NEWS_BOT_TOKEN ou TELEGRAM_TEST_CHAT_ID manquant")
    buf=io.BytesIO()
    build().save(buf,"PNG",optimize=True)
    buf.seek(0)
    response=requests.post(
        "https://api.telegram.org/bot"+token+"/sendPhoto",
        data={"chat_id":chat,
              "caption":"🧪 Mr XPRONOS — canal de test opérationnel.\nCe message ne doit jamais apparaître sur le canal de production."},
        files={"photo":("mrxpronos-test.png",buf,"image/png")},
        timeout=(10,45),
    )
    response.raise_for_status()
    data=response.json()
    if data.get("ok") is not True:
        raise SystemExit("Telegram n'a pas confirmé l'envoi")
    print("TELEGRAM_TEST_SMOKE_OK message_id",data.get("result",{}).get("message_id"))

if __name__=="__main__":main()
