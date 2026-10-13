#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Envoi d'une vidéo de test uniquement vers @predict_mrxp."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import requests
from telegram_test_guard import validate_test_channel

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--video",required=True)
    ap.add_argument("--caption",default="Test vidéo Mr XPRONOS")
    args=ap.parse_args()

    token=(os.getenv("TELEGRAM_TEST_GUARD_BOT_TOKEN") or "").strip()
    chat=(os.getenv("TELEGRAM_TEST_CHAT_ID") or "@predict_mrxp").strip()
    check=validate_test_channel(chat,token)
    print("TELEGRAM_TEST_ROUTE_VERIFIED",json.dumps(check,ensure_ascii=False))

    p=Path(args.video)
    if not p.exists() or p.stat().st_size<1000:
        raise SystemExit("Vidéo de test absente ou invalide")

    url="https://api.telegram.org/bot"+token+"/sendVideo"
    data={
        "chat_id":chat,
        "caption":args.caption[:1024],
        "supports_streaming":"true",
    }
    with p.open("rb") as f:
        r=requests.post(url,data=data,files={"video":(p.name,f,"video/mp4")},timeout=600)
    r.raise_for_status()
    body=r.json()
    if body.get("ok") is not True:
        raise RuntimeError("Telegram a refusé la vidéo de test")
    msg=body.get("result") or {}
    print("TELEGRAM_TEST_VIDEO_SENT",json.dumps({
        "message_id":msg.get("message_id"),
        "chat_id":(msg.get("chat") or {}).get("id"),
        "video_file_id":(msg.get("video") or {}).get("file_id"),
    },ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
