#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json, requests
from pathlib import Path

TOKEN=os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID=os.environ.get("TELEGRAM_CHAT_ID")
SECONDARY_CHAT_ID=os.environ.get("TELEGRAM_CHAT_ID_SECONDARY")
IMAGE_PATH=os.environ.get("PROMO_IMAGE","assets/images/xpvip-partners-daily.jpg")
CAPTION=os.environ.get(
    "PROMO_CAPTION",
    "🔥 <b>XPVIP — PARTENAIRES MrXPRONOS</b>\n\n"
    "Retrouve ci-dessous les liens d’inscription de nos bookmakers partenaires.\n\n"
    "<blockquote>🎁 <b>CODE PROMO : XPVIP</b>\n"
    "<i>Avant de terminer ton inscription, vérifie que XPVIP est bien renseigné "
    "lorsque le champ « Code promo » est proposé.</i></blockquote>\n\n"
    "👇 <b>Choisis ton bookmaker avec les boutons ci-dessous.</b>\n\n"
    "⚠️ <b>18+</b> · <i>Les offres et conditions peuvent varier selon le pays et le compte. "
    "Joue de façon responsable.</i>"
)

PARTNERS=[
    ("1xBet","https://reffpa.com/L?tag=d_2054511m_1573c_&site=2054511&ad=1573"),
    ("1Win","https://1wrbgb.com/?open=register&p=qqcw"),
    ("MelBet","https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041"),
    ("LineBet","https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3072389&ad=22611"),
    ("Betclic","https://betpari-click.com/2vY0?extid=USD"),
    ("BetWinner","https://bwredir.com/299Y"),
]

def chat_ids():
    vals=[("primary", CHAT_ID)]
    if SECONDARY_CHAT_ID and SECONDARY_CHAT_ID.strip():
        vals.append(("secondary", SECONDARY_CHAT_ID.strip()))
    seen=set()
    out=[]
    for role, value in vals:
        if value and value.strip() and value.strip() not in seen:
            seen.add(value.strip())
            out.append((role, value.strip()))
    return out

def keyboard():
    rows=[]
    for i in range(0,len(PARTNERS),2):
        row=[]
        for name,url in PARTNERS[i:i+2]:
            row.append({"text":f"S’inscrire sur {name}","url":url})
        rows.append(row)
    return {"inline_keyboard":rows}

def main():
    if not TOKEN or not CHAT_ID:
        raise SystemExit("Secrets manquants: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
    p=Path(IMAGE_PATH)
    if not p.exists():
        raise SystemExit(f"Image introuvable: {p}")
    api=f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    markup=json.dumps(keyboard(),ensure_ascii=False)
    primary_error=None
    for role, cid in chat_ids():
        try:
            with p.open("rb") as f:
                r=requests.post(
                    api,
                    data={
                        "chat_id":cid,
                        "caption":CAPTION,
                        "parse_mode":"HTML",
                        "reply_markup":markup,
                    },
                    files={"photo":f},
                    timeout=120,
                )
            if not r.ok:
                raise RuntimeError(f"{r.status_code} {r.text}")
            print(f"✅ Promo XPVIP envoyée vers {cid} ({role})")
        except Exception as e:
            if role == "primary":
                primary_error=f"{cid}: {e}"
            else:
                print(f"⚠️ Canal secondaire ignoré après erreur: {cid}: {e}")
    if primary_error:
        raise SystemExit(primary_error)

if __name__=="__main__":
    main()
