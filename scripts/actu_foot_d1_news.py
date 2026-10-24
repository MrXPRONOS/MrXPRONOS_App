#!/usr/bin/env python3
"""Neon-independent Actu Foot Flash publishing with durable Cloudflare D1 claims.

Reads only freshly sourced football articles gathered by fetch_foot_news.py.
Claims are atomic, and uncertain Telegram failures NEVER release a claim.
No fabricated news, no forced posts, and no writes to the old Supabase database.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import requests
from PIL import Image, ImageOps

from d1_publication_ledger import D1Ledger
from telegram_rich import post_photo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILE = ROOT / "telegram_out" / "actu_foot_source_news.json"
KIND = "actu_foot_flash_v2"
SLOT_KIND = "actu_foot_flash_3h_slot_v2"


def _time(value):
    try:
        value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _safe_url(value):
    try:
        parts = urlsplit(str(value or "").strip())
        return parts.scheme == "https" and bool(parts.hostname) and not parts.username and not parts.password
    except ValueError:
        return False


def select_stories(news, now, *, max_age_hours=30):
    """Return only recently published original stories with available source photos."""
    choices = []
    for item in news if isinstance(news, list) else []:
        if not isinstance(item, dict):
            continue
        stamp = _time(item.get("published"))
        if stamp is None or not now - timedelta(hours=max_age_hours) <= stamp <= now + timedelta(minutes=10):
            continue
        title = str(item.get("title") or "").strip()
        summary = str(item.get("telegram_summary") or item.get("summary") or "").strip()
        link = str(item.get("link") or item.get("source_url") or "").strip()
        slug = str(item.get("slug") or hashlib.sha256(link.encode()).hexdigest()[:24]).strip()
        image = str(item.get("image") or "").strip()
        path = (ROOT / image).resolve()
        if (not title or not summary or not _safe_url(link)
                or not slug or len(slug) > 100
                or item.get("image_origin") != "source"
                or not image.startswith("assets/images/footnews/")
                or not path.is_relative_to(ROOT.resolve()) or not path.is_file()):
            continue
        choices.append((stamp,item,path,slug,link))
    choices.sort(key=lambda x:x[0],reverse=True)
    return choices


def send_article(session, token, chat, item, image_path, link):
    title = html.escape(str(item["title"])[:220])
    summary = html.escape(str(item.get("telegram_summary") or item.get("summary") or "")[:470])
    source = html.escape(str(item.get("source") or "Source football")[:60])
    slug = str(item["slug"])
    page_url = "https://mrxpronos.github.io/MrXPRONOS_App/infos.html?news=" + slug
    buttons={"inline_keyboard":[
        [{"text":"📰 Lire l’actualité","url":page_url}],
        [{"text":"🔎 Source de l'information","url":link}],
    ]}
    caption="<b>⚽ ACTU FOOT | "+title+"</b>\n\n"+summary+"\n\n<i>Source : "+source+"</i>"
    with TemporaryDirectory(prefix="actu-foot-d1-") as folder:
        dest=Path(folder)/"actu-foot.jpg"
        with Image.open(image_path) as raw:
            ImageOps.exif_transpose(raw).convert("RGB").save(dest,"JPEG",quality=89,optimize=True)
        return post_photo(session,token,chat,dest,caption,buttons,timeout=80,mime="image/jpeg")


def dispatch(news, now, *, dry_run, token=None, chat=None, ledger=None, session=None):
    now=now.astimezone(timezone.utc)
    report={"eligible":0,"sent":0,"already_sent":0,"errors":0,"no_fresh_news":False}
    stories=select_stories(news,now)
    report["eligible"]=len(stories)
    if not stories:
        report["no_fresh_news"]=True
        return report
    if dry_run:
        report["would_send"]=stories[0][3]
        return report
    if not (token and chat):
        raise RuntimeError("FOOTBALL_NEWS_BOT_TOKEN/FOOTBALL_NEWS_CHAT_ID manquants")
    ledger=ledger or D1Ledger()
    session=session or requests.Session()
    day=now.date().isoformat()
    slot=f"{chat}:{now.strftime('%Y-%m-%d')}:{now.hour // 3}"
    selected=None
    for stamp,item,image,slug,link in stories:
        article_day=stamp.date().isoformat()
        if ledger.rows(KIND,article_day,ref_id=str(chat)+":"+slug):
            report["already_sent"]+=1
            continue
        selected=(stamp,item,image,slug,link)
        break
    if selected is None:
        return report
    if not ledger.claim(SLOT_KIND,slot,day):
        report["slot_already_claimed"]=True
        return report
    stamp,item,image,slug,link=selected
    ref=str(chat)+":"+slug
    ref_day=stamp.date().isoformat()
    if not ledger.claim(KIND,ref,ref_day):
        report["already_sent"]+=1
        return report
    try:
        msg=send_article(session,token,chat,item,image,link)
        ledger.mark(KIND,ref,ref_day,message_id=msg)
        ledger.mark(SLOT_KIND,slot,day,message_id=msg)
        report["sent"]=1
        report["telegram_message_id"]=msg
        report["story_slug"]=slug
    except Exception as error:
        # The server may have published despite any timeout / failed receipt.
        # Keep both reservations until they can be reconciled manually.
        report["errors"]=1
        report["error_type"]=type(error).__name__
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--news",type=Path,default=DEFAULT_FILE)
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args()
    if not args.news.is_file():
        raise RuntimeError("Actu Foot source feed not produced; publication blocked")
    news=json.loads(args.news.read_text(encoding="utf-8"))
    if not isinstance(news,list):
        raise RuntimeError("Actu Foot feed malformed")
    report=dispatch(news,datetime.now(timezone.utc),dry_run=args.dry_run,
        token=os.getenv("FOOTBALL_NEWS_BOT_TOKEN"),
        chat=os.getenv("FOOTBALL_NEWS_CHAT_ID"))
    print("ACTU_FOOT_D1_TELEGRAM",json.dumps(report,ensure_ascii=False))
    if report["errors"]:
        raise SystemExit("Actu Foot Telegram delivery failed; D1 claims retained")

if __name__=="__main__":
    main()
