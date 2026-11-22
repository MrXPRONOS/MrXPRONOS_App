#!/usr/bin/env python3
"""Actu Foot V1: broadcast *confirmed main-channel RSS posts* to topical channels.

The existing main channel stays the authoritative editorial stream. No new RSS
collection is made; specialist channels receive only articles for which the
main channel has a confirmed 'sent' Cloudflare D1 receipt. Independent D1
claims provide per-channel idempotency, quota and slot safety. Never resend
Telegram sends with unknown delivery receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

from actu_foot_d1_news import (
    ROOT, DEFAULT_FILE, KIND as MAIN_KIND, MAX_NIM_ATTEMPTS_PER_RUN,
    MAX_POSTS_PER_DAY, MAX_POSTS_PER_RUN, select_stories,
    send_article, story_parts,
)
from d1_publication_ledger import D1Ledger
from football_rss_editor import prepare, EditorialHold

CONFIG_FILE = ROOT / "config" / "actufoot_v1_channels.json"
POST_KIND = "actu_foot_multichannel_v1_article"
SLOT_KIND = "actu_foot_multichannel_v1_halfhour"
DAILY_KIND = "actu_foot_multichannel_v1_daily"
ROLES = (
    "flash", "mercato", "champions", "premier", "liga",
    "ligue1", "africa", "national", "scores", "debrief",
)
# Editorial categorization is deliberately independent of the RSS provider's
# *single* "category": an item can match several channels.
ALIASES = {
    "champions": (
        r"ligue des champions", r"champions league", r"uefa champions",
        r"\\bldc\\b", r"\\bc1\\b", r"\\bucl\\b",
    ),
    "premier": (
        r"premier league", r"championnat anglais", r"\\barsenal\\b",
        r"\\bchelsea\\b", r"\\bliverpool\\b", r"manchester city",
        r"manchester united", r"\\bman city\\b", r"\\bman utd\\b",
        r"\\btottenham\\b", r"\\bspurs\\b", r"\\bnewcastle\\b",
        r"aston villa", r"\\bfulham\\b", r"west ham", r"nottingham forest",
        r"crystal palace", r"\\beverton\\b", r"\\bbrentford\\b",
        r"\\bbrighton\\b", r"\\bbournemouth\\b",
    ),
    "liga": (
        r"\\bla liga\\b", r"\\blaliga\\b", r"championnat espagnol",
        r"real madrid", r"\\bbarca\\b", r"\\bbarcelona\\b",
        r"\\bfc barcelone\\b", r"\\batletico\\b", r"\\bvillarreal\\b",
        r"\\bsevilla\\b", r"\\bseville\\b", r"athletic bilbao",
        r"real betis", r"\\bvalencia\\b", r"real sociedad",
    ),
    "ligue1": (
        r"ligue 1", r"\\bl1\\b", r"championnat francais", r"\\bpsg\\b",
        r"paris saint germain", r"\\bmarseille\\b", r"\\bom\\b",
        r"\\bolympique lyonnais\\b", r"\\bol\\b", r"\\blyon\\b",
        r"\\bmonaco\\b", r"\\blens\\b", r"\\blille\\b",
        r"\\brennes\\b", r"\\bnice\\b", r"\\bnantes\\b",
        r"\\btoulouse\\b", r"\\bbrest\\b", r"\\blorient\\b",
    ),
    "africa": (
        r"\\bcan\\b", r"afcon", r"coupe d afrique", r"\\bcaf\\b",
        r"afrique", r"\\btogo\\b", r"\\bbenin\\b",
        r"\\bsenegal\\b", r"cote d ivoire", r"\\bnigeria\\b",
        r"\\bghana\\b", r"\\bcameroun\\b", r"\\bmaroc\\b",
        r"\\balgerie\\b", r"\\btunisie\\b", r"\\bmali\\b",
        r"burkina faso", r"african football",
    ),
}
MERCATO = (r"\\bmercato\\b", r"\\btransfert", r"\\brecrut",
           r"\\bsignature\\b", r"\\bsigne\\b", r"\\bpret\\b",
           r"\\bprolongation", r"\\bprolonge", r"\\bnegociat",
           r"\\boffre de transfert", r"\\baccord de transfert",
           r"\\bcontrat\\b", r"\\bdepart\\b")
NATIONAL = (r"\\bselection", r"equipes? nationales?", r"\\bu ?1[579]\\b",
            r"coupe du monde", r"world cup", r"\\bmondial\\b",
            r"\\bcan\\b", r"afcon", r"\\beuro 20", r"copa america",
            r"\\bqualifications?\\b", r"\\bqualificatif", r"\\bfifa\\b",
            r"equipe de france", r"equipe du senegal", r"equipe du maroc")
RESULT = (r"\\bresultat", r"\\bclassement", r"\\bcalendrier",
          r"\\bprogramme des matchs", r"\\bscore", r"\\bvictoire",
          r"\\bdefaite", r"\\bbuts?\\b", r"\\bmi temps",
          r"\\bcompositions? officielles?", r"\\b[0-9]+\\s*[-:]\\s*[0-9]+\\b",
          r"\\bqualifie")
DEBRIEF = (r"\\bdebrief", r"\\banalys", r"\\bbilan",
           r"\\btactiqu", r"\\bperformance", r"\\bstatistiques?",
           r"\\bpossession", r"\\bxg\\b", r"\\bapres match")
URGENT = (r"\\bofficiel", r"\\bbreaking", r"\\burgent",
          r"\\blimoge", r"\\blicencie", r"\\bsuspendu",
          r"\\bsanction", r"\\bblessure grave", r"\\bforfait",
          r"\\bcoup dur", r"\\bdeces", r"\\bannonce majeure")


def norm(value):
    txt=unicodedata.normalize("NFKD", str(value or "").casefold())
    txt="".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"\\s+"," ",re.sub(r"[^a-z0-9 ]+"," ",txt)).strip()


def has(text,patterns):
    return any(re.search(x,text) is not None for x in patterns)


def destinations_for(item):
    """Set of exact topical roles, not one coarse RSS category."""
    headline = norm(item.get("telegram_title_fr") or item.get("title"))
    excerpt = norm(item.get("telegram_content_fr") or item.get("content") or
                   item.get("telegram_summary") or item.get("summary"))
    # Headlines have priority; body expansion increases recall only when the
    # topic is in title or other structured hints.
    full = headline + " " + excerpt[:950]
    category = norm(item.get("category"))
    result=set()
    for role in ("champions","premier","liga","ligue1"):
        if has(headline,ALIASES[role]) or has(full,ALIASES[role]):
            result.add(role)
    if category=="afrique" or has(headline,ALIASES["africa"]) or (
        has(full,ALIASES["africa"]) and "afrique" in full
    ):
        result.add("africa")
    # A transfer story mentioning a routine player's injury alone is not an
    # actual transfer; require a concrete deal-related signal.
    if has(headline,MERCATO) or (
        category=="mercato" and has(full,MERCATO) and
        not (has(headline,(r"\\bblessure",r"\\bforfait")) and
             not has(headline,(r"\\btransfert",r"\\btransfert",r"\\bsigne",
                               r"\\brecrut",r"\\bprolongation")))
    ):
        result.add("mercato")
    if has(headline,NATIONAL) or (category=="convocations" and has(full,NATIONAL)):
        result.add("national")
    if has(headline,RESULT) or (
        category=="matchs" and has(full,RESULT)
    ):
        result.add("scores")
    if has(headline,DEBRIEF) and (
        has(full,RESULT) or "match" in full or "apres" in full
    ):
        result.add("debrief")
    # Flash is for true high-impact news; generic official club announcements
    # are already routed to league/mercato channels.
    try:
        quality=int(item.get("editorial_score") or 0)
    except (TypeError,ValueError):
        quality=0
    if has(headline,URGENT) and (
        quality >= 3 or has(headline,(r"\\bblessure grave",r"\\blimoge",
                                    r"\\blicencie",r"\\bsanction",r"\\bdeces"))
    ) and not has(headline,(r"\\brumeur",r"\\bserait",r"\\bpourrait")):
        result.add("flash")
    # Big news about selections in Africa is legitimately multi-category.
    if has(headline,(r"\\bcan\\b",r"afcon",r"coupe d afrique")):
        result.update(("africa","national"))
    return result


def load_config(path=CONFIG_FILE):
    obj=json.loads(Path(path).read_text(encoding="utf-8"))
    if obj.get("version") != 1 or not isinstance(obj.get("channels"),dict):
        raise RuntimeError("actufoot_v1_config_schema_invalid")
    channels=obj["channels"]
    if set(channels)!=set(ROLES):
        raise RuntimeError("actufoot_v1_channel_roles_incomplete")
    if any(not isinstance(v,str) or re.fullmatch(r"@[A-Za-z][A-Za-z0-9_]{4,31}",v) is None
           for v in channels.values()):
        raise RuntimeError("actufoot_v1_unsafe_or_private_channel_handle")
    if len(set(v.casefold() for v in channels.values())) != 10:
        raise RuntimeError("actufoot_v1_duplicate_channels")
    if any(v.casefold()=="@actufoot_mrxp" for v in channels.values()):
        raise RuntimeError("actufoot_v1_main_channel_in_specialists")
    return channels


def bot_call(session,token,method,data=None):
    # Bot tokens are part of the API URL. Never expose request exception text.
    try:
        response=session.post(
            "https://api.telegram.org/bot"+token+"/"+method,
            data=data or {},timeout=(8,22))
        body=response.json()
        if response.status_code!=200 or body.get("ok") is not True:
            raise ValueError("bot_api_rejected")
        return body["result"]
    except (requests.RequestException,ValueError,KeyError):
        raise RuntimeError("telegram_destination_preflight_failed") from None


def verify_channels(session,token,main_chat,config):
    me=bot_call(session,token,"getMe")
    if me.get("is_bot") is not True or not isinstance(me.get("id"),int):
        raise RuntimeError("actufoot_publisher_bot_not_verified")
    original=bot_call(session,token,"getChat",{"chat_id":main_chat})
    if original.get("type")!="channel" or (str(original.get("username") or "").casefold()
                                           != "actufoot_mrxp"):
        raise RuntimeError("actufoot_main_destination_mismatch")
    accepted={}
    seen_ids={int(original["id"])}
    failed=[]
    for role,handle in config.items():
        try:
            chat=bot_call(session,token,"getChat",{"chat_id":handle})
            member=bot_call(session,token,"getChatMember",{
                "chat_id":handle,"user_id":str(me["id"])})
            if (chat.get("type")!="channel" or
                "@"+str(chat.get("username") or "").casefold()!=handle.casefold()
                or int(chat["id"]) in seen_ids
                or member.get("status") not in ("administrator","creator")
                or (member.get("status")=="administrator"
                    and member.get("can_post_messages") is not True)):
                raise RuntimeError("destination_identity_or_rights_mismatch")
            seen_ids.add(int(chat["id"]))
            accepted[role]=handle
        except (RuntimeError,ValueError,TypeError,KeyError):
            failed.append(role)
    return accepted,failed


def delivery_id(value):
    try:
        if int(value)>0:
            return int(value)
    except (TypeError, ValueError):
        pass
    raise RuntimeError("telegram_photo_message_receipt_missing")


def main_confirmed(ledger, stories, main_chat):
    """Main publication is authoritative; specialists never invent extra news."""
    days={stamp.date().isoformat() for stamp, *_ in stories}
    valid=set()
    for day in sorted(days):
        for row in ledger.rows(MAIN_KIND,day):
            if row.get("delivery_status")=="sent":
                ref=str(row.get("ref_id") or "")
                if ref.startswith(str(main_chat)+":"):
                    valid.add((day,ref[len(str(main_chat))+1:]))
    return valid


def dispatch(news,now,*,dry_run=False,config=None,token=None,main_chat=None,
             ledger=None,session=None):
    now=now.astimezone(timezone.utc)
    channels=config if config is not None else load_config()
    if set(channels)!=set(ROLES):
        raise RuntimeError("actufoot_v1_roles_not_configured")
    report={"mode":"dry_run" if dry_run else "production","eligible":0,
            "main_confirmed":0,"sent":0,"already_sent":0,"errors":0,
            "editorial_skipped":0,"no_match":0,"per_channel":{r:0 for r in ROLES},
            "preflight_failed":[]}
    selected=select_stories(news,now)
    report["eligible"]=len(selected)
    if dry_run:
        report["routes"]={slug:sorted(destinations_for(item))
                          for _,item,_,slug,_ in selected}
        return report
    if not token or not main_chat:
        raise RuntimeError("actufoot_v1_missing_publisher_bot_or_main_chat")
    ledger=ledger or D1Ledger()
    session=session or requests.Session()
    allowed,failed=verify_channels(session,token,main_chat,channels)
    report["preflight_failed"]=failed
    confirmed=main_confirmed(ledger,selected,main_chat)
    report["main_confirmed"]=len(confirmed)
    days={stamp.date().isoformat() for stamp, *_ in selected}
    recorded=set()
    for day in sorted(days):
        for row in ledger.rows(POST_KIND,day):
            recorded.add((day,str(row.get("ref_id") or "")))
    day=now.date().isoformat()
    daily={str(row.get("ref_id") or "") for row in ledger.rows(DAILY_KIND,day)}
    slots={str(row.get("ref_id") or "") for row in ledger.rows(SLOT_KIND,day)}
    per_run=Counter()
    nim_attempts=0
    for stamp,item,image,slug,link in selected:
        article_day=stamp.date().isoformat()
        if (article_day,slug) not in confirmed:
            continue
        raw_roles=destinations_for(item)
        roles=[r for r in ROLES if r in raw_roles and r in allowed and
               per_run[r]<MAX_POSTS_PER_RUN]
        if not roles:
            report["no_match"]+=1
            continue
        try:
            edited=prepare(item,session=session,
                           api_key=None if nim_attempts<MAX_NIM_ATTEMPTS_PER_RUN else "")
            nim_attempts+=1
            # Never publish to a topic if the title changed substantively after
            # editing without re-checking its semantic routing.
            roles=[r for r in roles if r in destinations_for(edited)]
            if not roles:
                report["no_match"]+=1
                continue
        except EditorialHold:
            report["editorial_skipped"]+=1
            continue
        for role in roles:
            handle=allowed[role]
            ref=handle+":"+slug
            if (article_day,ref) in recorded:
                report["already_sent"]+=1
                continue
            used={x for x in daily if x.startswith(handle+":")}
            if len(used)>=MAX_POSTS_PER_DAY:
                continue
            slot=None
            for index in range(MAX_POSTS_PER_RUN):
                candidate=f"{handle}:{day}:{now.hour:02d}:{now.minute//30}:{index}"
                if candidate in slots:
                    continue
                if ledger.claim(SLOT_KIND,candidate,day):
                    slots.add(candidate)
                    slot=candidate
                    break
                slots.add(candidate)
            if slot is None:
                continue
            daily_ref=next((f"{handle}:{i:02d}" for i in range(MAX_POSTS_PER_DAY)
                            if f"{handle}:{i:02d}" not in daily),None)
            if daily_ref is None or not ledger.claim(DAILY_KIND,daily_ref,day):
                continue
            daily.add(daily_ref)
            if not ledger.claim(POST_KIND,ref,article_day):
                recorded.add((article_day,ref))
                report["already_sent"]+=1
                continue
            recorded.add((article_day,ref))
            per_run[role]+=1
            try:
                message_id=delivery_id(send_article(session,token,handle,
                                                     edited,image,link))
                ledger.mark(POST_KIND,ref,article_day,message_id=message_id)
                ledger.mark(SLOT_KIND,slot,day,message_id=message_id)
                ledger.mark(DAILY_KIND,daily_ref,day,message_id=message_id)
                report["sent"]+=1
                report["per_channel"][role]+=1
            except Exception as exc:
                # D1 reservations are intentionally never released after a
                # potentially ambiguous Telegram send.
                report["errors"]+=1
                report.setdefault("failure_types",[]).append({
                    "role":role,"type":type(exc).__name__})
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--news",type=Path,default=DEFAULT_FILE)
    parser.add_argument("--dry-run",action="store_true")
    parser.add_argument("--config",type=Path,default=CONFIG_FILE)
    args=parser.parse_args()
    if not args.news.is_file():
        raise RuntimeError("actufoot_v1_news_snapshot_missing")
    obj=json.loads(args.news.read_text(encoding="utf-8"))
    if not isinstance(obj,list):
        raise RuntimeError("actufoot_v1_news_snapshot_invalid")
    config=load_config(args.config)
    report=dispatch(obj,datetime.now(timezone.utc),dry_run=args.dry_run,
                    config=config,token=os.environ.get("FOOTBALL_NEWS_BOT_TOKEN"),
                    main_chat=os.environ.get("FOOTBALL_NEWS_CHAT_ID"))
    print("ACTUFOOT_V1_ROUTER",json.dumps(report,ensure_ascii=False,sort_keys=True))
    if report["errors"] or report["preflight_failed"]:
        raise SystemExit("Actu Foot V1 detected delivery or permission errors")


if __name__=="__main__":
    main()
