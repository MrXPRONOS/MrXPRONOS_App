#!/usr/bin/env python3
"""Vérifie les droits des bots Mr XPRONOS sur le canal Telegram de test.

Aucun message n'est envoyé. Les tokens ne sont jamais affichés.
"""
from __future__ import annotations
import json,os,sys
import requests

CHAT=os.getenv("TELEGRAM_TEST_CHAT_ID","@predict_mrxp").strip() or "@predict_mrxp"
BOTS=[
    ("FOOTBALL_NEWS_BOT_TOKEN",os.getenv("FOOTBALL_NEWS_BOT_TOKEN","").strip()),
    ("TELEGRAM_BOT_TOKEN",os.getenv("TELEGRAM_BOT_TOKEN","").strip()),
    ("EDITORIAL_TELEGRAM_BOT_TOKEN",os.getenv("EDITORIAL_TELEGRAM_BOT_TOKEN","").strip()),
]

def call(token,method,params=None):
    r=requests.get("https://api.telegram.org/bot"+token+"/"+method,params=params or {},timeout=(8,20))
    r.raise_for_status()
    data=r.json()
    if data.get("ok") is not True:
        raise RuntimeError(data.get("description") or method+" failed")
    return data["result"]

def check_one(name,token):
    if not token:
        return {"secret":name,"configured":False,"ready":False,"reason":"missing_secret"}
    me=call(token,"getMe")
    member=call(token,"getChatMember",{"chat_id":CHAT,"user_id":me["id"]})
    status=member.get("status")
    can_post=bool(member.get("can_post_messages")) if status=="administrator" else status=="creator"
    return {
      "secret":name,
      "configured":True,
      "username":me.get("username"),
      "status":status,
      "can_post_messages":can_post,
      "ready":status in ("administrator","creator") and can_post,
    }

def main():
    # getChat est appelé via le premier bot configuré pour confirmer la destination publique.
    configured=next((token for _,token in BOTS if token),None)
    if configured:
        chat=call(configured,"getChat",{"chat_id":CHAT})
        print("TELEGRAM_TEST_CHAT",json.dumps({
            "id":chat.get("id"),"username":chat.get("username"),"type":chat.get("type")
        },ensure_ascii=False))
    results=[]
    failed=False
    for name,token in BOTS:
        try:
            result=check_one(name,token)
        except (requests.RequestException,RuntimeError,ValueError) as exc:
            result={"secret":name,"configured":bool(token),"ready":False,"reason":type(exc).__name__}
        results.append(result)
        if result.get("configured") and not result.get("ready"):
            failed=True
        print("TELEGRAM_TEST_BOT",json.dumps(result,ensure_ascii=False))
    configured_count=sum(bool(x.get("configured")) for x in results)
    ready_count=sum(bool(x.get("ready")) for x in results)
    print("TELEGRAM_TEST_READINESS",json.dumps({
        "chat":CHAT,"configured_bots":configured_count,"ready_bots":ready_count
    }))
    if configured_count==0:
        raise SystemExit("Aucun token Telegram configuré")
    raise SystemExit(1 if failed else 0)

if __name__=="__main__":
    main()
