#!/usr/bin/env python3
"""One-time protected visual review: never post to the production channel."""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import requests
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from arty_football_templates import SUPPORTED, overlay
from telegram_test_guard import validate_test_channel
from telegram_rich import post_photo
import programme_styles

def dummy_logo(url, maximum):
    im=Image.new("RGBA",(200,200),(0,0,0,0))
    draw=ImageDraw.Draw(im)
    color=(241,193,92,255) if "/a" in url else (220,230,240,255)
    draw.ellipse((9,9,191,191),outline=color,width=8)
    letter="A" if "/a" in url else "B"
    try: ft=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",98)
    except OSError: ft=ImageFont.load_default()
    draw.text((100,100),letter,fill=color,font=ft,anchor="mm")
    im.thumbnail((maximum,maximum))
    return im

def main():
    token=os.environ.get("FOOTBALL_NEWS_BOT_TOKEN","").strip()
    chat=os.environ.get("FOOTBALL_NEWS_CHAT_ID","").strip()
    target=os.environ.get("TELEGRAM_TEST_CHAT_ID","").strip()
    if not token or not chat or not target or chat!=target:
        raise RuntimeError("TEST REFUSED: destination and token not verified")
    guard=validate_test_channel(chat,token)
    if guard.get("username")!="predict_mrxp":
        raise RuntimeError("TEST REFUSED: unexpected Telegram channel")
    payload={
        "home":"ÉQUIPE A • TEST","away":"ÉQUIPE B • TEST",
        "home_logo":"https://example.invalid/a","away_logo":"https://example.invalid/b",
        "score":"1-1","scores":(1,1),
        "competition":"CHAMPIONNAT • SIMULATION","league":"CHAMPIONNAT • SIMULATION",
        "time":"18h30","minute":"45'",
        "source":"DÉMONSTRATION - DONNÉES FICTIVES",
        "headline":"DÉMONSTRATION D'UNE STATISTIQUE FOOTBALL",
        "value":"35","lines":["35 BUTS • TEST","20 MATCHS • TEST","15 POINTS • TEST","5 VICTOIRES • TEST"],
        "goal":{"player":"JOUEUR TEST","minute_text":"45'"},
        "question":"QUELLE OPTION CHOISIS-TU POUR CE MATCH FICTIF ?",
        "summary":"Zone de texte destinée aux commentaires, à une actualité vérifiée ou à une réaction après-match.",
        "reaction":"EXEMPLE DE RÉACTION • CE TEXTE EST UNE DÉMONSTRATION, PAS UNE ACTUALITÉ.",
        "status":"SIMULATION : RENCONTRE REPORTÉE",
        "options":["A • TEST","Match nul • TEST","B • TEST","Autre réponse"],
        "home_players":[f"Joueur test domicile {i}" for i in range(1,12)],
        "away_players":[f"Joueur test extérieur {i}" for i in range(1,12)],
    }
    session=requests.Session()
    result={}
    with patch.object(programme_styles,"load_logo",side_effect=dummy_logo):
        with tempfile.TemporaryDirectory(prefix="arty-review-") as tmp:
            for idx,kind in enumerate(SUPPORTED,1):
                path=Path(tmp)/(kind+".png")
                overlay(kind,payload).save(path,"PNG",optimize=True)
                caption=(
                  "<b>🧪 TEST VISUEL • ARTY FOOTBALL</b>\n"
                  f"<b>{idx:02d}/{len(SUPPORTED)} — {kind.upper()}</b>\n\n"
                  "<i>Simulation graphique. Équipes, score et informations fictifs :"
                  " ne pas interpréter comme une actualité réelle.</i>"
                )
                mid=post_photo(session,token,chat,path,caption,{},timeout=90,mime="image/png")
                result[kind]=mid
                print("ARTY_TEST_SENT",kind,mid,flush=True)
    print("ARTY_VISUAL_REPORT",json.dumps(result,ensure_ascii=False),flush=True)
    if len(result)!=len(SUPPORTED):
        raise RuntimeError("Not all visual tests were sent")
if __name__=="__main__":
    main()
