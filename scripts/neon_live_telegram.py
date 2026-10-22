#!/usr/bin/env python3
"""Mr XPRONOS - forward verified NEW Neon live predictions to Telegram.

Only the latest eligible Neon-model rows. Historical Supabase signals are NEVER resent.
D1 delivery ledger (GitHub OIDC) claims one (prediction, destination) before publishing.
Only commit a ledger claim on confirmed Telegram 200; release definitive send failures.
An ambiguous transport failure deliberately retains the claim to prevent duplicates.
The bot token is kept in GitHub Actions secrets, never in source or logs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import re
import sys
import time
from typing import Any
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFont

API = "https://br-winter-truth-b9of9tss-live.compute.c-7.eu-central-1.aws.neon.tech"
LEDGER = "https://mrxpronos-telegram-ledger-staging.cinecanaux-xpronos.workers.dev"
SITE = "https://mrxpronos.github.io/MrXPRONOS_App/live.html"
MODEL = "neon-live-value-v2.3-playability-espn"
AUDIENCE = "mrxpronos-telegram-ledger"
SECONDARY_FALLBACK = "@mrxpronosfr"
MAX_AGE_SECONDS = 900
SEND_LIMIT_PER_RUN = 4
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
HEADERS = {"Accept": "application/json", "User-Agent": "MrXPRONOS-Neon-LIVE-Telegram/1.0"}

def get_json(url: str, *, headers: dict[str,str] | None = None, timeout: int = 22):
    resp = requests.get(url, headers=headers or HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.json()

def ledger_token():
    endpoint=os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL","")
    secret=os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN","")
    if not endpoint or not secret:
        raise RuntimeError("GitHub OIDC absent: refusing to post")
    sep="&" if "?" in endpoint else "?"
    response=requests.get(
        endpoint+sep+"audience="+quote(AUDIENCE),
        headers={"Authorization":"Bearer "+secret},
        timeout=14
    )
    response.raise_for_status()
    token=response.json().get("value")
    if not token:
        raise RuntimeError("GitHub OIDC token missing")
    return token

def ledger_call(path: str, ref_id: str, ref_date: str, token: str, message_id: int | None = None):
    payload={"kind":"live_neon_signal","ref_id":ref_id,"ref_date":ref_date}
    if message_id is not None: payload["telegram_message_id"]=message_id
    response=requests.post(
        LEDGER+path, json=payload,
        headers={"Authorization":"Bearer "+token,"Accept":"application/json"},
        timeout=18
    )
    if response.status_code != 200:
        raise RuntimeError("Ledger "+path+" HTTP "+str(response.status_code))
    data=response.json()
    if not isinstance(data,dict):
        raise RuntimeError("Invalid ledger response")
    return data

def telegram_call(method: str, bot: str, *, params=None, data=None, files=None):
    # Do not print request exceptions: Telegram URL contains the secret token.
    try:
        url="https://api.telegram.org/bot"+bot+"/"+method
        if files is not None or data is not None:
            res=requests.post(url,data=data,files=files,timeout=(10,30))
        else:
            res=requests.get(url,params=params,timeout=(8,18))
        try:
            out=res.json()
        except ValueError:
            raise RuntimeError("Telegram invalid JSON") from None
    except requests.RequestException as e:
        raise RuntimeError("Telegram transport failure: "+type(e).__name__) from None
    if not isinstance(out,dict) or out.get("ok") is not True:
        status=res.status_code
        desc=str(out.get("description") or "unknown").replace(bot,"[redacted]")[:150]
        raise TelegramRejection("Telegram "+method+" rejected "+str(status)+": "+desc)
    return out.get("result")

class TelegramRejection(Exception):
    """Definite API rejection: claim can be released for a subsequent retry."""

def destinations(bot: str, mode: str):
    if mode=="test":
        raw=[("test",os.environ.get("TELEGRAM_TEST_CHAT_ID") or "@predict_mrxp")]
    else:
        raw=[("primary",os.environ.get("TELEGRAM_CHAT_ID") or ""),
             ("secondary",os.environ.get("TELEGRAM_CHAT_ID_SECONDARY") or SECONDARY_FALLBACK)]
    me=telegram_call("getMe",bot)
    bot_id=me.get("id")
    if not isinstance(bot_id,int):
        raise RuntimeError("Invalid Telegram bot identity")
    valid=[];seen=set()
    for slot,chatid in raw:
        if not chatid:
            if slot=="primary": raise RuntimeError("TELEGRAM_CHAT_ID secret missing")
            continue
        try:
            chat=telegram_call("getChat",bot,params={"chat_id":chatid})
            channel_id=chat.get("id")
            if chat.get("type")!="channel" or not isinstance(channel_id,int):
                raise RuntimeError("Not a Telegram channel")
            member=telegram_call("getChatMember",bot,params={"chat_id":channel_id,"user_id":bot_id})
            status=member.get("status")
            authorized=(status=="creator" or
                        (status=="administrator" and member.get("can_post_messages") is True))
            if not authorized:
                raise RuntimeError("Bot cannot post to this channel")
            if mode=="test" and str(chat.get("username") or "").lower()!="predict_mrxp":
                raise RuntimeError("Wrong test channel")
            if channel_id in seen:
                print("Skipping duplicate destination alias: "+slot,flush=True)
                continue
            seen.add(channel_id)
            valid.append((slot,channel_id))
            print("TELEGRAM_ROUTE_READY "+slot+" yes",flush=True)
        except (TelegramRejection,RuntimeError) as e:
            # Primary must be configured. Secondary may be temporarily unavailable.
            if slot in ("primary","test"):
                raise RuntimeError("Required Telegram destination unavailable: "+type(e).__name__) from None
            print("TELEGRAM_SECONDARY_UNAVAILABLE "+type(e).__name__,flush=True)
    if not valid:raise RuntimeError("No verified Telegram destinations")
    return valid

def parsed_date(value: Any):
    try:
        v=dt.datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return v.replace(tzinfo=dt.timezone.utc) if v.tzinfo is None else v.astimezone(dt.timezone.utc)
    except (TypeError,ValueError):
        return None

def eligible_signals(history: list[dict], live_matches: list[dict]):
    live_ids={str(x.get("id")) for x in live_matches if x.get("is_live") is True and x.get("is_finished") is not True}
    now=dt.datetime.now(dt.timezone.utc)
    picks=[]
    for row in history:
        if not isinstance(row,dict) or row.get("model_version")!=MODEL:
            continue
        identity=str(row.get("id") or "")
        when=parsed_date(row.get("created_at"))
        if not UUID_RE.fullmatch(identity) or not when:continue
        age=(now-when).total_seconds()
        if not 0<=age<=MAX_AGE_SECONDS:continue
        if row.get("validated") is True:continue
        if str(row.get("match_id") or "") not in live_ids:continue
        if row.get("signal_tier") not in ("quality","value","high_value"):continue
        if row.get("type") not in ("total_shots","total_corners","total_fouls"):continue
        if row.get("pricing_mode")!="model_only":continue
        try:
            threshold=float(row.get("threshold"))
            current=float(row.get("signal_value"))
            reliability=float(row.get("reliability"))
            quality=float(row.get("data_quality_score"))
            chance=float(row.get("probability"))
        except (ValueError,TypeError):
            continue
        if threshold-current<2 or reliability<68 or quality<67 or not .3<=chance<=.95:
            continue
        picks.append(row)
    return sorted(picks,key=lambda x:str(x["created_at"]))[:SEND_LIMIT_PER_RUN]

def font(size, bold=False):
    path="/usr/share/fonts/truetype/dejavu/DejaVuSans"+("-Bold" if bold else "")+".ttf"
    return ImageFont.truetype(path,size)

def abbreviate(value: str, n=43):
    v=" ".join(str(value).split())
    return v if len(v)<=n else v[:n-1]+"…"

def image_coupon(pred: dict):
    img=Image.new("RGB",(1080,1080),(10,24,44))
    d=ImageDraw.Draw(img)
    navy=(10,24,44); muted=(156,181,202); white=(245,248,255)
    blue=(27,130,244); yellow=(255,192,66); green=(68,222,174)
    d.rounded_rectangle((34,32,1046,1048),radius=36,fill=(16,37,63))
    d.rounded_rectangle((48,48,1032,205),radius=24,fill=(20,57,94))
    d.text((82,76),"MR XPRONOS",font=font(53,True),fill=white)
    d.text((82,145),"NOUVEAU SIGNAL LIVE",font=font(28,True),fill=yellow)
    d.ellipse((937,90,974,127),fill=green)
    d.text((82,251),abbreviate(pred.get("league",{}).get("name") or "FOOTBALL",34).upper(),font=font(26,True),fill=muted)
    home=abbreviate(pred.get("home_team") or "Domicile",30)
    away=abbreviate(pred.get("away_team") or "Extérieur",30)
    d.text((82,320),home,font=font(41,True),fill=white)
    d.text((82,397),"VS",font=font(26,True),fill=yellow)
    d.text((82,450),away,font=font(41,True),fill=white)
    minute=int(float(pred.get("minute") or 0))
    d.rounded_rectangle((799,293,995,364),radius=22,fill=(30,88,139))
    d.text((833,310),f"{minute}' LIVE",font=font(27,True),fill=white)
    d.line((82,548,998,548),fill=(56,92,123),width=2)
    market={"total_shots":"TIRS","total_corners":"CORNERS","total_fouls":"FAUTES"}.get(pred.get("type"),"STATISTIQUES")
    d.text((82,583),f"PRONOSTIC · {market}",font=font(28,True),fill=muted)
    d.text((82,643),"OVER "+str(pred.get("threshold")),font=font(81,True),fill=white)
    d.rounded_rectangle((82,782,998,892),radius=20,fill=(23,56,85))
    d.text((103,804),"AU SIGNAL",font=font(23,True),fill=muted)
    d.text((103,842),str(pred.get("signal_value")),font=font(37,True),fill=white)
    d.text((440,804),"FIABILITÉ MODÈLE",font=font(23,True),fill=muted)
    d.text((440,842),str(round(float(pred.get("reliability") or 0)))+" / 100",font=font(37,True),fill=white)
    d.text((82,944),"Données LIVE · Estimation du modèle, pas une garantie.",font=font(21),fill=muted)
    d.text((82,992),"18+  •  Joue responsablement",font=font(22,True),fill=yellow)
    output=io.BytesIO();img.save(output,format="PNG",optimize=True);output.seek(0)
    return output

def publish(bot: str, slot: str, chatid: int, pred: dict):
    chance=round(float(pred["probability"])*100)
    label={"total_shots":"Tirs","total_corners":"Corners","total_fouls":"Fautes"}[pred["type"]]
    caption=(f"⚽ NOUVEAU PRONOSTIC LIVE\n"
             f"{pred.get('home_team') or ''} vs {pred.get('away_team') or ''}\n"
             f"⏱ {pred.get('minute')}′ | 🎯 {label} : Over {pred.get('threshold')}\n"
             f"📊 Au signal : {pred.get('signal_value')}\n"
             f"🧠 Probabilité estimée par le modèle : {chance}% (non garantie)\n"
             f"18+ · Joue responsablement.")
    content=image_coupon(pred)
    inline={"inline_keyboard":[[{"text":"⚽ Plus d’opportunités LIVE","url":SITE}]]}
    try:
        result=telegram_call("sendPhoto",bot,data={
           "chat_id":str(chatid),"caption":caption,"reply_markup":json.dumps(inline,ensure_ascii=False)
        },files={"photo":("mrx-live.png",content,"image/png")})
    finally:content.close()
    if not isinstance(result,dict) or not isinstance(result.get("message_id"),int):
        raise RuntimeError("Telegram did not confirm message id")
    print("TELEGRAM_SEND_OK slot="+slot+" prediction_id="+str(pred["id"]),flush=True)
    return int(result["message_id"])

def execute(mode: str):
    bot=os.environ.get("TELEGRAM_BOT_TOKEN","").strip()
    if not bot:raise RuntimeError("TELEGRAM_BOT_TOKEN secret missing")
    token=ledger_token()
    status=get_json(LEDGER+"/health")
    if status.get("ready") is not True:raise RuntimeError("Telegram ledger is not ready")
    channels=destinations(bot,mode)
    check=get_json(API+"/health")
    if check.get("ok") is not True:raise RuntimeError("Neon API not ready")
    data=get_json(API+"/predictions/history")
    matches=get_json(API+"/matches")
    history=data.get("history")
    live=matches.get("matches")
    if not isinstance(history,list) or not isinstance(live,list):
        raise RuntimeError("Neon response schema mismatch")
    filtered=eligible_signals(history,live)
    print("NEON_TELEGRAM_"+mode.upper()+" eligible_signals="+str(len(filtered))+" destinations="+str(len(channels)),flush=True)
    if mode=="probe":
        # exercise ledger auth/claim/release without posting any Telegram messages
        runid=os.environ.get("GITHUB_RUN_ID") or str(int(time.time()))
        testref="probe:"+runid
        for slot,_ in channels:
            key=testref+":"+slot
            obj=ledger_call("/claim",key,dt.datetime.now(dt.timezone.utc).date().isoformat(),token)
            if obj.get("claimed") is not True:raise RuntimeError("Test ledger claim failed")
            released=ledger_call("/release",key,dt.datetime.now(dt.timezone.utc).date().isoformat(),token)
            if released.get("released") is not True:raise RuntimeError("Test ledger release failed")
        print("TELEGRAM_PREFLIGHT_PASS no messages sent",flush=True)
        return 0
    failed=0;sent=0
    for p in filtered:
        created=parsed_date(p["created_at"])
        date=created.date().isoformat()
        for slot,channel in channels:
            key=str(p["id"])+":"+slot
            claim=ledger_call("/claim",key,date,token)
            if claim.get("claimed") is not True:
                print("TELEGRAM_DUPLICATE_SKIPPED "+slot+" "+str(p["id"]),flush=True)
                continue
            try:
                message_id=publish(bot,slot,channel,p)
                marked=ledger_call("/mark",key,date,token,message_id)
                if marked.get("marked") is not True:
                    raise RuntimeError("Telegram sent but D1 delivery acknowledgement failed")
                sent+=1
            except TelegramRejection as e:
                # Only definitive API rejections are safe to retry.
                ledger_call("/release",key,date,token)
                failed+=1
                print("TELEGRAM_REJECTED "+slot+" "+str(e),flush=True)
            except Exception as e:
                # Network uncertainty: retaining claim prevents a duplicate publication.
                failed+=1
                print("TELEGRAM_UNCERTAIN_SEND "+slot+" "+type(e).__name__,flush=True)
    print("TELEGRAM_DELIVERY_REPORT sent="+str(sent)+" errors="+str(failed),flush=True)
    return 1 if failed else 0

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("probe","live","test"),default="probe")
    args=parser.parse_args()
    try:
        return execute(args.mode)
    except Exception as e:
        # NEVER print exception representation from requests: secret may be in Telegram URL.
        print("TELEGRAM_DELIVERY_ERROR "+type(e).__name__+" "+(str(e) if isinstance(e,RuntimeError) else "")[:170],flush=True)
        return 1

if __name__=="__main__":sys.exit(main())
