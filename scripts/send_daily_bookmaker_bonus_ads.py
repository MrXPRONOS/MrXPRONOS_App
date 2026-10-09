#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from telegram_promo_channels import promo_channels, deliver_to_both
from PIL import Image, ImageOps

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SECONDARY_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID_SECONDARY")
FORCE_KEY = os.environ.get("BOOKMAKER_FORCE_KEY", "").strip().lower()

TOGO_TZ = timezone(timedelta(hours=0))
PROMO_CODE = "XPVIP"
ASSETS_DIR = Path("assets/images/telegram-bonus-ads")

BOOKMAKERS = {
    "melbet": {
        "name": "MelBet",
        "day": 0,
        "image": ASSETS_DIR / "melbet-bonus.png",
        "signup_url": "https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041",
        "offer_title": "Bonus sport boosté",
        "offer_value": "150%",
        "offer_limit": "jusqu’à 150% sur ton premier dépôt",
        "pitch": "Une offre renforcée pour bien lancer ton compte dès le premier dépôt.",
    },
    "betwinner": {
        "name": "BetWinner",
        "day": 1,
        "image": ASSETS_DIR / "betwinner-bonus.png",
        "signup_url": "https://bwredir.com/299Y",
        "offer_title": "Bonus sport",
        "offer_value": "100%",
        "offer_limit": "jusqu’à 70 000 XOF sur ton premier dépôt",
        "pitch": "Un bonus simple et direct pour démarrer avec plus de marge.",
    },
    "1xbet": {
        "name": "1xBet",
        "day": 2,
        "image": ASSETS_DIR / "1xbet-bonus.png",
        "signup_url": "https://tinyurl.com/VEXIA7",
        "offer_title": "Bonus de bienvenue",
        "offer_value": "100%",
        "offer_limit": "jusqu’à 100 $ sur ton premier dépôt",
        "pitch": "Parfait pour ouvrir un nouveau compte et profiter d’un bonus de départ.",
    },
    "linebet": {
        "name": "LineBet",
        "day": 3,
        "image": ASSETS_DIR / "linebet-bonus.png",
        "signup_url": "https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3072389&ad=22611",
        "offer_title": "Bonus premier dépôt",
        "offer_value": "100%",
        "offer_limit": "jusqu’à 85 000 XOF sur ton premier dépôt",
        "pitch": "Une offre sport claire pour les nouveaux joueurs qui veulent commencer fort.",
    },
    "1win": {
        "name": "1Win",
        "day": 4,
        "image": ASSETS_DIR / "1win-bonus.png",
        "signup_url": "https://1wrbgb.com/?open=register&p=qqcw",
        "offer_title": "Bonus de bienvenue",
        "offer_value": "100%",
        "offer_limit": "jusqu’à 500 $ sur ton premier dépôt",
        "pitch": "Un des bonus de bienvenue les plus généreux pour démarrer immédiatement.",
    },
    "betclic": {
        "name": "Betclic",
        "day": 5,
        "image": ASSETS_DIR / "betclic-bonus.png",
        "signup_url": "https://betpari-click.com/2vY0?extid=USD",
        "offer_title": "1er pari remboursé",
        "offer_value": "Freebet",
        "offer_limit": "jusqu’à 5 000 FCFA en freebet si ton premier pari est perdant",
        "pitch": "Idéal pour tester Betclic avec un risque réduit sur ton premier ticket.",
    },
}

# Dimanche : on remet 1xBet en mise en avant par défaut.
WEEK_ROTATION = {
    0: "melbet",
    1: "betwinner",
    2: "1xbet",
    3: "linebet",
    4: "1win",
    5: "betclic",
    6: "1xbet",
}


def get_today_key():
    if FORCE_KEY and FORCE_KEY in BOOKMAKERS:
        return FORCE_KEY
    now = datetime.now(TOGO_TZ)
    return WEEK_ROTATION[now.weekday()]


def html_caption(bm: dict) -> str:
    if bm["name"] == "Betclic":
        bonus_block = (
            f"<blockquote>🎁 <b>OFFRE :</b> {bm['offer_limit']}\n"
            f"🎟 <b>CODE PROMO :</b> <b>{PROMO_CODE}</b></blockquote>"
        )
    else:
        bonus_block = (
            f"<blockquote>🎁 <b>OFFRE :</b> {bm['offer_value']} — {bm['offer_limit']}\n"
            f"🎟 <b>CODE PROMO :</b> <b>{PROMO_CODE}</b></blockquote>"
        )

    return (
        f"🔥 <b>{bm['name'].upper()} — {bm['offer_title'].upper()}</b>\n\n"
        f"Crée un <b>nouveau compte</b> avec le code promo <b>{PROMO_CODE}</b>, "
        f"effectue ton premier dépôt et profite de l’offre de bienvenue du moment.\n\n"
        f"{bonus_block}\n\n"
        f"<i>{bm['pitch']}</i>\n\n"
        f"✨ <b>Étapes rapides :</b>\n"
        f"• ouvre le lien officiel ci-dessous\n"
        f"• crée un nouveau compte\n"
        f"• saisis <b>{PROMO_CODE}</b> si le champ promo apparaît\n"
        f"• fais ton premier dépôt pour activer l’offre\n\n"
        f"👇 <b>Lien d’inscription :</b> clique sur le bouton juste en dessous.\n\n"
        f"⚠️ <b>Important :</b> <i>vérifie toujours que le code promo <b>{PROMO_CODE}</b> est bien appliqué avant de valider ton inscription.</i>\n\n"
        f"⚠️ <b>18+</b> · <i>Les bonus, montants et conditions peuvent varier selon le pays, la devise et le compte. Joue de façon responsable.</i>"
    )


def keyboard(bm: dict):
    return {
        "inline_keyboard": [
            [{"text": f"🎯 S’inscrire sur {bm['name']}", "url": bm["signup_url"]}],
        ]
    }


def prepare_telegram_image(src: Path) -> Path:
    if not src.exists():
        raise SystemExit(f"Image introuvable: {src}")
    out = Path(".tmp_daily_bonus_ad.jpg")
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        max_side = 2000
        if max(im.size) > max_side:
            ratio = max_side / max(im.size)
            im = im.resize((max(1, int(im.width * ratio)), max(1, int(im.height * ratio))))
        im.save(out, "JPEG", quality=92, optimize=True, progressive=False)
    return out


def chat_ids():
    vals = [("primary", CHAT_ID)]
    if SECONDARY_CHAT_ID and SECONDARY_CHAT_ID.strip():
        vals.append(("secondary", SECONDARY_CHAT_ID.strip()))
    out, seen = [], set()
    for role, cid in vals:
        if cid and cid.strip() and cid.strip() not in seen:
            seen.add(cid.strip())
            out.append((role, cid.strip()))
    return out


def send():
    if not BOT_TOKEN or not CHAT_ID:
        raise SystemExit("Secrets manquants: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")

    key = get_today_key()
    bm = BOOKMAKERS[key]
    img = prepare_telegram_image(Path(bm["image"]))
    caption = html_caption(bm)
    markup = json.dumps(keyboard(bm), ensure_ascii=False)
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

    channels=promo_channels(CHAT_ID,SECONDARY_CHAT_ID)
    def send_to(cid):
        with img.open("rb") as f:
            resp=requests.post(api,data={
                "chat_id":cid,"caption":caption,"parse_mode":"HTML",
                "reply_markup":markup,
            },files={"photo":(img.name,f,"image/jpeg")},timeout=120)
        resp.raise_for_status()
        if not resp.json().get("ok",False):
            raise RuntimeError(f"Telegram rejected image for {cid}")
    deliver_to_both(channels,send_to,label=bm["name"])


if __name__ == "__main__":
    send()
