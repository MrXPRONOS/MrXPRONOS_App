#!/usr/bin/env python3
"""Read-only evidence audit: four CineX media delivery slots per full day.

Private channel identities and their result details are sent only to the
account owner's Saved Messages. No new channel joins, media downloads or
content publication. Public logs contain only coarse aggregated counts.
"""
from __future__ import annotations

import asyncio
import io
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import FloodWaitError, PeerFloodError
from telethon.sessions import StringSession
from telethon.tl.types import Channel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from telegram_admin_cinema_catalog import classify_channel, fold

CATEGORY_TITLE_TERMS = ("cinex", "cine x", "anime", "manga", "films", "film", "serie",
                        "séries", "k-drama", "hollywood", "africa cine")
MAX_TARGETS = 55
MAX_RECENT_MESSAGES = 180
SLOTS = ((0, 6), (6, 12), (12, 18), (18, 24))
OBS_DAYS = 3


def is_video(msg) -> bool:
    if getattr(msg, "video", None) is not None:
        return True
    doc = getattr(getattr(msg, "media", None), "document", None)
    return bool(doc and str(getattr(doc, "mime_type", "")).lower().startswith("video/"))


def slot_index(date: datetime) -> int:
    return date.hour // 6


def inspect_messages(messages, day: str) -> dict:
    video_slots = [0, 0, 0, 0]
    all_slots = [0, 0, 0, 0]
    first_recent = None
    last_video = None
    for msg in messages:
        dt = getattr(msg, "date", None)
        if dt is None:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        if dt.strftime("%Y-%m-%d") != day:
            continue
        all_slots[slot_index(dt)] += 1
        first_recent = min(first_recent,dt) if first_recent else dt
        if is_video(msg):
            video_slots[slot_index(dt)] += 1
            last_video = max(last_video, dt) if last_video else dt
    return {"videos": sum(video_slots), "video_slots":video_slots,
            "slots_with_video":sum(x>0 for x in video_slots),
            "posts":sum(all_slots), "all_slots":all_slots,
            "first":str(first_recent or ""), "last_video":str(last_video or "")}


def target_is_general(row: dict) -> bool:
    if row.get("dedicated_title"):
        return False
    if not set(row.get("categories", [])) & {"films", "series", "animes"}:
        return False
    name = fold(row.get("title", ""))
    return any(x in name for x in CATEGORY_TITLE_TERMS)


def full_day_status(analysis: dict, *, cutoff_hour: int = 24) -> str:
    needed = 4 if cutoff_hour>=24 else max(0,(cutoff_hour+5)//6)
    count = sum(x > 0 for x in analysis["video_slots"][:needed])
    if needed == 0:
        return "pas encore applicable"
    if count == needed:
        return f"{count}/{needed} plages couvertes"
    return f"{count}/{needed} plages couvertes — objectif NON atteint"


async def run() -> int:
    sid = (os.getenv("TG_SESSION_STRING") or os.getenv("TG_STRING_SESSION")
           or os.getenv("TG_STREAM_SESSION") or "").strip()
    api_id=(os.getenv("TG_API_ID") or "").strip()
    api_hash=(os.getenv("TG_API_HASH") or "").strip()
    if not sid or not api_id.isdigit() or not api_hash:
        print("CATEGORY_DELIVERY_AUDIT_CONFIG_MISSING")
        return 1
    client=TelegramClient(StringSession(sid),int(api_id),api_hash,
                          request_retries=0,connection_retries=1,
                          flood_sleep_threshold=0,receive_updates=False)
    today=datetime.now(timezone.utc)
    days=[(today-timedelta(days=delta)).strftime("%Y-%m-%d") for delta in (2,1,0)]
    targets=[]
    public_reports=[]
    private_reports=[]
    failures=0
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("CATEGORY_DELIVERY_AUDIT_NOT_AUTHORIZED")
            return 1
        async for dialog in client.iter_dialogs():
            ch=dialog.entity
            if not isinstance(ch,Channel) or not bool(getattr(ch,"broadcast",False)):
                continue
            if not (getattr(ch,"creator",False) or getattr(ch,"admin_rights",None)):
                continue
            row=classify_channel(getattr(ch,"title",""),getattr(ch,"username",None))
            if row and target_is_general(row):
                targets.append((ch,row))
        if len(targets)>MAX_TARGETS:
            print("CATEGORY_DELIVERY_AUDIT_TARGET_CAP_EXCEEDED",len(targets))
            return 1
        cutoff=today-timedelta(days=OBS_DAYS)
        for n,(ch,row) in enumerate(targets,1):
            messages=[]
            error=None
            try:
                async for msg in client.iter_messages(ch,limit=MAX_RECENT_MESSAGES):
                    dt=getattr(msg,"date",None)
                    if dt is not None:
                        if dt.tzinfo is None:
                            dt=dt.replace(tzinfo=timezone.utc)
                        if dt < cutoff:
                            break
                    messages.append(msg)
                analyses={day:inspect_messages(messages,day) for day in days}
                truncated=(len(messages)>=MAX_RECENT_MESSAGES and
                           bool(messages) and
                           getattr(messages[-1],"date",today)>cutoff)
                if truncated:
                    # Recent messages can crowd out an older full day. Never label
                    # absence as 0 if history window was truncated.
                    error="historique incomplet (limite de 180 messages)"
            except (FloodWaitError,PeerFloodError):
                print("CATEGORY_DELIVERY_AUDIT_TELEGRAM_RATE_LIMIT_STOPPED")
                return 2
            except Exception:
                error="lecture indisponible"
                analyses={}
                failures+=1
            if error:
                result=f"• {row['title']} | {','.join(row['categories'])} | VÉRIFICATION INCOMPLÈTE : {error}"
            else:
                full=[full_day_status(analyses[d]) for d in days[:2]]
                current=analyses[days[2]]
                result=(f"• {row['title']} | {','.join(row['categories'])}\n"
                    f"  {days[0]}: {analyses[days[0]]['videos']} vidéos | {full[0]} | plages {analyses[days[0]]['video_slots']}\n"
                    f"  {days[1]}: {analyses[days[1]]['videos']} vidéos | {full[1]} | plages {analyses[days[1]]['video_slots']}\n"
                    f"  {days[2]} (en cours): {current['videos']} vidéos | plages {current['video_slots']}\n"
                    "  Vérification catégorie précise par titre vidéo : non automatisée")
            if row["visibility"]=="public":
                if row.get("username"):
                    result+="\n  https://t.me/"+row["username"]
                public_reports.append(result)
            else:
                private_reports.append(result)
            await asyncio.sleep(3)
        report=(
            "CINEX — AUDIT DES 4 PASSAGES / JOUR — "+today.strftime("%Y-%m-%d %H:%M UTC")+"\n"
            "Objectif: au moins une véritable vidéo dans chacune des plages 00–05, 06–11, 12–17, 18–23 UTC.\n"
            "Aucune affiche, publicité ni simple exécution du workflow n'est comptée comme une vidéo.\n"
            "Les 2 jours complets sont "+days[0]+" et "+days[1]+".\n"
            "L'absence de vidéo dans les messages observés n'établit pas l'absence d'une vidéo supprimée.\n"
            "CAN AUX DÉDIÉS À UNE SEULE ŒUVRE : volontairement exclus.\n\n"
            f"CANAUX PUBLICS ({len(public_reports)})\n"+
            "\n\n".join(public_reports)+"\n\n"+
            f"CANAUX PRIVÉS ({len(private_reports)})\n"+
            "\n\n".join(private_reports)+"\n"
        ).replace("CAN AUX","CANAUX")
        stream=io.BytesIO(report.encode("utf-8"))
        stream.name="cinex-audit-4-creneaux-"+days[2]+".txt"
        await client.send_file("me",stream,caption="CINEX-AUDIT-4-SLOTS-"+days[2]+" — résultats détaillés dans ce fichier",force_document=True)
        print("CATEGORY_DELIVERY_AUDIT_SUMMARY",{
            "public_target_channels":len(public_reports),
            "private_target_channels":len(private_reports),
            "read_failures":failures,
            "period":days,
            "private_report_saved_messages":True,
            "film_content_published_by_audit":False,
        })
        for result in public_reports:
            print("PUBLIC_CHANNEL_AUDIT",result.replace("\n"," | "))
        return 0
    finally:
        await client.disconnect()


if __name__=="__main__":
    raise SystemExit(asyncio.run(run()))
