#!/usr/bin/env python3
"""Compile approved weekly promotions; never send while generating."""
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/"scripts"))


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in ("br", "p", "h3", "blockquote"):
            self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag in ("p", "h3", "blockquote"):
            self.parts.append("\n")
    def handle_data(self, value):
        self.parts.append(value)


def flatten(html):
    p = PlainHTML()
    p.feed(html)
    return re.sub(r"\n{3,}", "\n\n", "".join(p.parts)).strip()


def checked_link(url):
    value = str(url).strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Partner link must be HTTPS")
    return value


def attach_links(caption, named):
    links = "\n".join(f"{name}: {checked_link(url)}" for name,url in named)
    result = flatten(caption) + "\n\n" + links
    if len(result) > 1024:
        raise ValueError("Promotional caption exceeds Telegram photo limit")
    return result


def next_monday(now):
    now = now.astimezone(timezone.utc)
    day = now.date() + timedelta(days=(7-now.weekday()) % 7)
    if now.weekday() == 0:
        day += timedelta(days=7)
    return day


def _slots(day, hour, minute):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=timezone.utc)


def prepare(now, dests, approvals):
    # Import existing approved campaigns; never invent offers or destination channels.
    from send_day_based_bookmaker_promos import PROMOS, ASSETS_DIR, partner, caption_for
    from send_daily_bookmaker_bonus_ads import BOOKMAKERS, WEEK_ROTATION, html_caption
    from send_daily_bookmaker_guide import PARTNERS as GUIDES, WEEK_ROTATION as GUIDE_ROTATION
    from send_daily_bookmaker_guide import caption_for as guide_caption
    from send_daily_partner_promo import PARTNERS as COMMON_PARTNERS
    from send_daily_partner_promo import CAPTION as COMMON_CAPTION
    from send_daily_partner_promo import prepare_telegram_image

    monday = next_monday(now)
    posts, skipped = [], []
    common_image = prepare_telegram_image(None)
    common_links = [(name,url) for name,url,_ in COMMON_PARTNERS]
    common_text = attach_links(COMMON_CAPTION,common_links)
    def add(peer, day, hh, mm, key, caption, file):
        image = (ROOT / file).resolve()
        if not image.is_relative_to(ROOT) or not image.is_file() or image.stat().st_size < 1:
            raise ValueError(f"Approved image missing: {file}")
        posts.append({"peer":int(peer),"at":_slots(day,hh,mm).isoformat(),
            "key":key, "kind":"image", "file":str(image.relative_to(ROOT)),
            "text":caption, "parse_mode":None})

    if not dests or len(dests)!=len(set(dests)) or any(x>=0 for x in dests):
        raise ValueError("Two distinct marked channel IDs required")
    for daynum in range(7):
        day = monday + timedelta(days=daynum)
        for peer in dests:
            add(peer,day,7,0,f"xpvip:{day.isoformat()}",common_text,common_image)
            for promo in PROMOS:
                if promo.weekday!=daynum:
                    continue
                if promo.image not in approvals["day"]:
                    skipped.append({"day":day.isoformat(),"campaign":"day","reason":"not approved","item":promo.image})
                    continue
                book=partner(promo.bookmaker)
                if book is None:
                    skipped.append({"day":day.isoformat(),"campaign":"day","reason":"partner disabled","item":promo.image})
                    continue
                text=attach_links(caption_for(promo),[(book.get("name") or promo.bookmaker,book["url"])])
                add(peer,day,6,0,f"weekday:{promo.image}:{day.isoformat()}",text,ASSETS_DIR/promo.image)
            bonus_key=WEEK_ROTATION[daynum]
            if bonus_key in approvals["bonus"]:
                bonus=BOOKMAKERS[bonus_key]
                txt=attach_links(html_caption(bonus),[(bonus["name"],bonus["signup_url"])])
                add(peer,day,7,30,f"bonus:{bonus_key}:{day.isoformat()}",txt,bonus["image"])
            else:
                skipped.append({"day":day.isoformat(),"campaign":"bonus","reason":"not approved","item":bonus_key})
            guide_key=GUIDE_ROTATION[daynum]
            if guide_key!="common" and guide_key in approvals["guide"]:
                guide=GUIDES[guide_key]
                txt=attach_links(guide_caption(guide),[(guide["name"],guide["url"])])
                add(peer,day,8,0,f"guide:{guide_key}:{day.isoformat()}",txt,guide["image"])
            elif guide_key != "common":
                skipped.append({"day":day.isoformat(),"campaign":"guide","reason":"not approved","item":guide_key})
    return {"horizon_hours":168,"posts":sorted(posts,key=lambda x:(x["at"],x["peer"],x["key"]))}, skipped


def approvals_from_env():
    def csv(name):
        return frozenset(s.strip().lower() for s in os.getenv(name,"").split(",") if s.strip())
    return {"day":csv("TELEGRAM_APPROVED_DAY_PROMOS"),
            "bonus":csv("TELEGRAM_APPROVED_BONUS_BOOKMAKERS"),
            "guide":csv("TELEGRAM_APPROVED_GUIDE_BOOKMAKERS")}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",default="telegram_out/scheduler/weekly_promotions.json")
    ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args()
    # A Sunday execution covers next Mon-Sun. Outside Sundays, safe offline preview only.
    now=datetime.now(timezone.utc)
    if not args.dry_run and now.weekday()!=6:
        raise SystemExit("Live weekly generation is permitted only on Sunday")
    raw=[os.getenv("TELEGRAM_CHAT_ID",""),os.getenv("TELEGRAM_CHAT_ID_SECONDARY","")]
    if any(not re.fullmatch(r"-100[0-9]+",v.strip()) for v in raw):
        raise SystemExit("Both Telegram channel IDs must be marked numeric IDs (-100...)")
    payload,skipped=prepare(now,tuple(int(v) for v in raw),approvals_from_env())
    # Full preflight also enforces the rolling horizon and safe local media.
    from telegram_scheduler.manifest import load_manifest
    output=(ROOT/args.out).resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError("Output must stay inside repository")
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    hours,posts=load_manifest(output,now=now,root=ROOT)
    print(json.dumps({"posts":len(posts),"days":7,"unapproved_skips":len(skipped),
                     "first":posts[0]["at"].isoformat() if posts else None},ensure_ascii=False))
    if not args.dry_run and skipped:
        raise SystemExit("Weekly batch incomplete: approval is required for all applicable items")
    if not posts:
        raise SystemExit("No approved weekly posts")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
