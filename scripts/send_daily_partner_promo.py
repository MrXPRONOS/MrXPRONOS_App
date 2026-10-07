#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json, requests
from pathlib import Path

TOKEN=os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID=os.environ.get("TELEGRAM_CHAT_ID")
SECONDARY_CHAT_ID=os.environ.get("TELEGRAM_CHAT_ID_SECONDARY","@mrxpronosfr")
IMAGE_PATH=os.environ.get("PROMO_IMAGE","assets/images/xpvip-partners-daily.jpg")
CAPTION=os.environ.get(
    "PROMO_CAPTION",
    "🔥 Crée ton compte avec le code promo XPVIP et profite des offres disponibles chez nos bookmakers partenaires.\n\n"
    "Utilise toujours le lien officiel du partenaire et vérifie que le code XPVIP est bien appliqué à l'inscription.\n\n"
    "⚠️ 18+ · Joue de façon responsable. Les bonus et conditions peuvent varier selon le pays et le compte."
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
    vals=[CHAT_ID,SECONDARY_CHAT_ID]
    return list(dict.fromkeys(v.strip() for v in vals if v and v.strip()))

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
    errors=[]
    for cid in chat_ids():
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
            print(f"Promo XPVIP envoyée vers {cid}")
        except Exception as e:
            errors.append(f"{cid}: {e}")
    if errors:
        raise SystemExit(" | ".join(errors))

if __name__=="__main__":
    main()
