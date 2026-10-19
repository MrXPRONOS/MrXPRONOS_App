"""Replace the existing #11 sample photo (message 1549) in TEST channel ONLY.

No sendPhoto calls, and no production channel. The previously published
fictional demo remains explicitly marked as fictional after the image update.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import requests
from scripts.telegram_test_guard import validate_test_channel

CHANNEL="@predict_mrxp"
MESSAGE_ID=1549
PNG=Path("crypto/generated/test/regulation_11_demo.png")
DATA=Path("crypto/generated/test/regulation_11_demo.json")


def edit(requester=requests.post):
    if not PNG.is_file() or PNG.stat().st_size<10_000 or not DATA.is_file():
        raise ValueError("Missing updated demo photo and source")
    data=json.loads(DATA.read_text(encoding="utf8"))
    if data.get("publication")!=11 or data.get("is_demo") is not True or data.get("status")!="demo":
        raise ValueError("Only fictitious explicitly marked demo can replace the test photo")
    bot_token=(os.environ.get("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    dest=validate_test_channel(CHANNEL,bot_token)
    caption=("🧪 MR XPRONOS · ACTU CRYPTO #11 — AFRIQUE\n\n"
             "⚠️ NOUVELLE VERSION GRAPHIQUE — SIMULATION FICTIVE\n"
             "Le Bénin n'a pas annoncé de projet par cette publication.\n"
             "Aucun fait réel n'est présenté sur cette image.\n\n"
             "Vérification du design premium 1080 × 1350 sur @predict_mrxp.")
    media=json.dumps({"type":"photo","media":"attach://new_photo","caption":caption},
                    ensure_ascii=False)
    with PNG.open("rb") as f:
        try:
            response=requester("https://api.telegram.org/bot"+bot_token+"/editMessageMedia",
                data={"chat_id":dest["chat_id"],"message_id":MESSAGE_ID,
                      "media":media},
                files={"new_photo":(PNG.name,f,"image/png")},timeout=(10,90))
            response.raise_for_status()
            result=response.json()
        except (requests.RequestException,ValueError):
            raise RuntimeError("Telegram edit outcome uncertain; check test channel directly") from None
    if not isinstance(result,dict) or result.get("ok") is not True:
        raise RuntimeError("Telegram denied test poster edit")
    edited=result.get("result",{})
    if (not isinstance(edited,dict) or edited.get("message_id")!=MESSAGE_ID
        or edited.get("chat",{}).get("id")!=dest["chat_id"]
        or not isinstance(edited.get("photo"),list) or not edited["photo"]):
        raise RuntimeError("Updated image or original test message not confirmed")
    print("REG11_CORRECTED_EXISTING_TEST_PHOTO_CONFIRMED",MESSAGE_ID,"@predict_mrxp")


if __name__=="__main__":
    edit()
