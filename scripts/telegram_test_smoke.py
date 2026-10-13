#!/usr/bin/env python3
"""Smoke test visuel pour le canal Telegram de test Mr XPRONOS."""
from __future__ import annotations
import io,os
from datetime import datetime,timezone
import requests
import sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"bsd"))
sys.path.insert(0,str(ROOT/"scripts"))
from bsd_v2_captions import combo_caption
from football_channel import structured_plain, esc
from telegram_rich import post_photo

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
    test_image=build()
    test_image.save(buf,"PNG",optimize=True)
    test_path=Path("/tmp/mrxpronos-format-test.png")
    test_image.save(test_path,"PNG",optimize=True)
    buf.seek(0)
    session=requests.Session()
    response=session.post(
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

    # Test réel du chemin combiné: même caption builder + même transport Rich Message.
    combo={
        "event_date":"2026-10-13T18:00:00+00:00",
        "combined_odds":1.96,
        "legs":[
            {"home_team":"Arsenal","away_team":"Chelsea","event_date":"2026-10-13T18:00:00+00:00",
             "prediction":{"selection_key":"HOME_OR_DRAW","type":"Double chance","odds":1.42}},
            {"home_team":"Milan","away_team":"Inter","event_date":"2026-10-13T20:00:00+00:00",
             "prediction":{"selection_key":"OVER_15","type":"Plus de 1,5","odds":1.38}},
        ],
    }
    combo_id=post_photo(
        session,token,chat,test_path,combo_caption(combo),
        {"inline_keyboard":[]},timeout=60,mime="image/png"
    )
    print("TELEGRAM_TEST_COMBO_FORMAT_OK message_id",combo_id)

    # Test Actu Foot: récupère volontairement un texte compact 1:/2./3)
    # puis passe par la fonction corrigée avant le transport Telegram.
    compact=(
        "Trois points à retenir : 1: Arsenal récupère deux titulaires "
        "2. Chelsea conserve son onze habituel "
        "3) Le coup d'envoi reste confirmé à 12:30 malgré le score précédent 1:0."
    )
    summary=structured_plain(compact,430)
    news_caption=(
        "<b>🧪 TEST ACTU FOOT — LISTE NUMÉROTÉE</b>\n\n"
        "<blockquote>"+esc(summary)+"</blockquote>\n\n"
        "<i>Canal de test uniquement.</i>"
    )
    news_id=post_photo(
        session,token,chat,test_path,news_caption,
        {"inline_keyboard":[]},timeout=60,mime="image/png"
    )
    print("TELEGRAM_TEST_ACTU_FORMAT_OK message_id",news_id)

if __name__=="__main__":main()
