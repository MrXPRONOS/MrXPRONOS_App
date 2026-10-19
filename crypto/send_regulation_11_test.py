"""Send exactly one #11 premium photo to @predict_mrxp TEST channel ONLY.

Never sends to ACTU_CRYPTO_CHAT_ID. Real is disabled by default; only explicit
manual opt-in can send real news after identity, date and PNG verification.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import requests
from scripts.telegram_test_guard import validate_test_channel
from crypto import export_regulation_11 as pub

CHANNEL="@predict_mrxp"
ROOT=Path("crypto/generated/test")


def deliver(demo=True,requester=requests.post):
    stem="regulation_11_demo" if demo else "regulation_11"
    datafile=ROOT/(stem+".json" if demo else "regulation_11_data.json")
    png=ROOT/(stem+".png")
    if not datafile.is_file() or not png.is_file() or png.stat().st_size<10_000:
        raise RuntimeError("Source JSON or #11 PNG missing; no Telegram publication")
    d=json.loads(datafile.read_text(encoding="utf8"))
    if demo:
        if d.get("publication")!=11 or d.get("status")!="demo" or d.get("is_demo") is not True:
            raise RuntimeError("Fake design must be explicitly marked as DEMO")
        caption=("🧪 MR XPRONOS · ACTU CRYPTO #11 — AFRIQUE\n\n"
                 "⚠️ SIMULATION DE DESIGN · EXEMPLE FICTIF\n"
                 "Ce visuel n'annonce aucune réglementation réelle.\n\n"
                 "Contrôle PNG premium 1080×1350 sur le canal de test.")
    else:
        pub.validate_real(d)
        a=d["main"]
        caption=("🌍 MR XPRONOS · ACTU CRYPTO #11 — AFRIQUE\n\n"
                 +d["synopsis_fr"]+"\n\n"
                 +"Thème : "+a["topic"]+"\n"
                 +"Zone mentionnée : "+a["region"]+"\n"
                 +"📰 Titre original : "+a["title"]+"\n"
                 +"🔗 Selon "+a["source"]+" : "+a["url"]+"\n"
                 +"🕒 "+a["published_at"][:16]+" UTC\n\n"
                 +"Information attribuée au média, pas une confirmation "
                 "juridique. Consulter les textes officiels applicables.")
    if len(caption)>1024:raise RuntimeError("Telegram photo caption too long")
    token=(os.environ.get("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    route=validate_test_channel(CHANNEL,token)
    with png.open("rb") as file:
        try:
            res=requester("https://api.telegram.org/bot"+token+"/sendPhoto",
                data={"chat_id":route["chat_id"],"caption":caption,
                      "disable_notification":True},
                files={"photo":(png.name,file,"image/png")},timeout=(10,90))
            res.raise_for_status()
            outcome=res.json()
        except (requests.RequestException,ValueError):
            raise RuntimeError("Telegram send outcome uncertain; do not retry") from None
    if not isinstance(outcome,dict) or outcome.get("ok") is not True:
        raise RuntimeError("Telegram refused #11 test")
    msg=outcome.get("result",{})
    if (not isinstance(msg,dict) or not isinstance(msg.get("message_id"),int)
        or msg.get("chat",{}).get("id")!=route["chat_id"]
        or not msg.get("photo")):
        raise RuntimeError("Telegram message not verified as photo in test channel")
    print("REG11_TELEGRAM_TEST_PHOTO_CONFIRMED",msg["message_id"],
          "mode=DEMO" if demo else "mode=REAL")
    return msg["message_id"]


if __name__=="__main__":
    a=argparse.ArgumentParser()
    group=a.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo",action="store_true")
    group.add_argument("--real",action="store_true")
    args=a.parse_args()
    deliver(demo=args.demo)
