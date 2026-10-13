#!/usr/bin/env python3
"""Livraison Telegram gratuite et anti-doublons (statut persisté dans la file).

Aucun envoi sans --publish ET 2 variables EDITORIAL_TELEGRAM_*.
Pas de rattrapage massif: seuls les contenus très récents sont éligibles.
Ne réutilise pas les canaux de pronostics ou de Flash Foot sans consentement.
"""
from __future__ import annotations
import argparse,html,io,json,os
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlencode,urlsplit,urlunsplit,parse_qsl
import requests
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/"assets/data/editorial_share_queue.json"
BASE="https://mrxpronos.github.io/MrXPRONOS_App/"

def parsed_dt(text):
    try:
        dt=datetime.fromisoformat(str(text).replace("Z","+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (ValueError,TypeError):return None

def eligible(item,now,window_hours=48):
    if not isinstance(item,dict) or item.get("retired") or item.get("kind") not in ("article","conseil"):
        return False
    if not item.get("id") or not item.get("url","").startswith(BASE):return False
    if item.get("platform_status",{}).get("telegram") in ("sent","sending"):return False
    published=parsed_dt(item.get("source_date"))
    if published is None or published > now+timedelta(hours=2) or published < now-timedelta(hours=window_hours):return False
    return bool(item.get("image"))

def tagged_url(item, source="telegram"):
    url=urlsplit(item["url"])
    params=dict(parse_qsl(url.query))
    if source not in ("telegram","facebook","threads","instagram","whatsapp","youtube","tiktok"):
        raise ValueError("Source sociale non autorisée")
    params.update({"utm_source":source,"utm_medium":"social",
                   "utm_campaign":"editorial_free","utm_content":item.get("visual_variant","legacy")})
    return urlunsplit((url.scheme,url.netloc,url.path,urlencode(params),""))

def encode_photo(path):
    with Image.open(path) as image:
        image= image.convert("RGB")
        output=io.BytesIO()
        image.save(output,"JPEG",quality=88,optimize=True)
        output.seek(0)
        return output

def choose(items,now,limit=1):
    return [x for x in items if eligible(x,now)][:max(0,limit)]

def publish(queue_path=QUEUE,root=ROOT,enabled=False,max_items=1,now=None,request_post=requests.post):
    now=now or datetime.now(timezone.utc)
    if not queue_path.is_file():
        print("EDITORIAL_TELEGRAM_NO_QUEUE");return {"sent":0,"skipped":True}
    data=json.loads(queue_path.read_text(encoding="utf-8"))
    selection=choose(data,now,max_items)
    if not enabled:
        print("EDITORIAL_TELEGRAM_DRY_RUN",json.dumps({"eligible":len(selection),
             "ids":[x["id"] for x in selection]},ensure_ascii=False))
        return {"sent":0,"dry_run":True,"eligible":len(selection)}
    token=os.getenv("EDITORIAL_TELEGRAM_BOT_TOKEN","").strip()
    chat=os.getenv("EDITORIAL_TELEGRAM_CHAT_ID","").strip()
    if not token or not chat:
        print("EDITORIAL_TELEGRAM_NOT_CONFIGURED: no messages sent")
        return {"sent":0,"skipped":True}
    sent=0;failed=0
    for item in selection:
        media_path=(root/str(item["image"])).resolve()
        if not media_path.is_relative_to(root.resolve()) or not media_path.is_file():
            print("EDITORIAL_TELEGRAM_MEDIA_MISSING",item["id"]);failed+=1;continue
        caption=f"<b>{html.escape(item['title'][:240])}</b>\n\n📰 Mr XPRONOS • {html.escape(item['kind'])}\n18+ • Jeu responsable"
        keyboard={"inline_keyboard":[[{"text":"Lire sur Mr XPRONOS ↗","url":tagged_url(item)}]]}
        try:
            photo=encode_photo(media_path)
            with photo:
                response=request_post("https://api.telegram.org/bot"+token+"/sendPhoto",
                    data={"chat_id":chat,"caption":caption,"parse_mode":"HTML",
                          "reply_markup":json.dumps(keyboard,ensure_ascii=False)},
                    files={"photo":("mrxpronos.jpg",photo,"image/jpeg")},timeout=(10,50))
            response.raise_for_status()
            payload=response.json()
            if payload.get("ok") is not True:raise ValueError("Telegram delivery not confirmed")
            message_id=payload.get("result",{}).get("message_id")
            if message_id is None:raise ValueError("Telegram message_id absent")
            item.setdefault("platform_status",{})["telegram"]="sent"
            item.setdefault("delivered",{})["telegram"]={"message_id":message_id,"at":now.isoformat()}
            # Écriture immédiatement après confirmation, avant toute autre diffusion.
            queue_path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            sent+=1
            print("EDITORIAL_TELEGRAM_SENT",item["id"],"message_id",message_id)
        except (requests.RequestException,ValueError,OSError) as exc:
            failed+=1
            print("EDITORIAL_TELEGRAM_FAILED",item["id"],type(exc).__name__)
            break
    return {"sent":sent,"failed":failed,"eligible":len(selection)}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--publish",action="store_true",help="Déclenche un véritable envoi (secrets requis)")
    p.add_argument("--max-items",type=int,default=1)
    args=p.parse_args()
    report=publish(enabled=args.publish,max_items=min(max(args.max_items,0),3))
    raise SystemExit(1 if report.get("failed") else 0)
