#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SECONDARY_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID_SECONDARY", "@mrxpronosfr")
OVERRIDE = (os.environ.get("BOOKMAKER_OVERRIDE") or "").strip().lower()

PARTNERS = {
    "melbet": {
        "name": "MelBet",
        "image": "assets/images/telegram-guides/melbet-xpvip.jpg",
        "url": "https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041",
    },
    "betwinner": {
        "name": "BetWinner",
        "image": "assets/images/telegram-guides/betwinner-xpvip.jpg",
        "url": "https://bwredir.com/299Y",
    },
    "1xbet": {
        "name": "1xBet",
        "image": "assets/images/telegram-guides/1xbet-xpvip.jpg",
        "url": "https://reffpa.com/L?tag=d_2054511m_1573c_&site=2054511&ad=1573",
    },
    "linebet": {
        "name": "LineBet",
        "image": "assets/images/telegram-guides/linebet-xpvip.jpg",
        "url": "https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3072389&ad=22611",
    },
    "1win": {
        "name": "1Win",
        "image": "assets/images/telegram-guides/1win-xpvip.jpg",
        "url": "https://1wrbgb.com/?open=register&p=qqcw",
    },
    "betclic": {
        "name": "Betclic",
        "image": "assets/images/telegram-guides/betclic-xpvip.jpg",
        "url": "https://betpari-click.com/2vY0?extid=USD",
    },
}

# Lundi=0 ... Dimanche=6 (heure du Togo = UTC)
WEEK_ROTATION = {
    0: "melbet",
    1: "betwinner",
    2: "1xbet",
    3: "linebet",
    4: "1win",
    5: "betclic",
    6: "common",
}

COMMON_IMAGE = "assets/images/xpvip-partners-daily.jpg"


def chat_ids():
    values = [CHAT_ID, SECONDARY_CHAT_ID]
    return list(dict.fromkeys(v.strip() for v in values if v and v.strip()))


def single_keyboard(partner):
    return {
        "inline_keyboard": [
            [{"text": f"✅ S'inscrire sur {partner['name']}", "url": partner["url"]}]
        ]
    }


def common_keyboard():
    order = ["1xbet", "1win", "melbet", "linebet", "betclic", "betwinner"]
    buttons = [
        {"text": f"S'inscrire sur {PARTNERS[key]['name']}", "url": PARTNERS[key]["url"]}
        for key in order
    ]
    return {
        "inline_keyboard": [
            buttons[0:2],
            buttons[2:4],
            buttons[4:6],
        ]
    }


def caption_for(partner):
    return (
        f"📲 <b>COMMENT CRÉER TON COMPTE {partner['name'].upper()} ?</b>\n\n"
        "Suis simplement les étapes indiquées sur l'image puis utilise le bouton ci-dessous "
        "pour passer par le lien partenaire MrXPRONOS.\n\n"
        "🎁 <b>Code promo : XPVIP</b>\n"
        "Avant de valider ton inscription, vérifie que <b>XPVIP</b> apparaît bien dans le champ "
        "« Code promo » lorsque ce champ est proposé.\n\n"
        "⚠️ <b>18+</b> · Les bonus, montants et conditions peuvent varier selon le pays et le compte. "
        "Joue de façon responsable."
    )


def common_caption():
    return (
        "🔥 <b>CODE PROMO XPVIP — PARTENAIRES MrXPRONOS</b>\n\n"
        "Choisis ton bookmaker avec les boutons ci-dessous et vérifie que le code "
        "<b>XPVIP</b> est bien renseigné lorsque le champ promo est proposé.\n\n"
        "⚠️ <b>18+</b> · Les offres et conditions peuvent varier selon le pays. "
        "Joue de façon responsable."
    )


def choose_today():
    if OVERRIDE and OVERRIDE not in ("auto", ""):
        if OVERRIDE == "common":
            return "common"
        if OVERRIDE not in PARTNERS:
            raise SystemExit(
                f"BOOKMAKER_OVERRIDE invalide: {OVERRIDE}. "
                f"Valeurs: auto, common, {', '.join(PARTNERS)}"
            )
        return OVERRIDE
    return WEEK_ROTATION[datetime.now(timezone.utc).weekday()]


def send_photo(chat_id, image_path, caption, keyboard):
    api = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    image = Path(image_path)
    if not image.exists():
        raise FileNotFoundError(f"Image introuvable: {image}")

    with image.open("rb") as fh:
        response = requests.post(
            api,
            data={
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(keyboard, ensure_ascii=False),
            },
            files={"photo": fh},
            timeout=120,
        )

    if not response.ok:
        raise RuntimeError(f"Telegram {response.status_code}: {response.text}")
    return response.json()


def main():
    if not TOKEN or not CHAT_ID:
        raise SystemExit("Secrets manquants: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")

    today = choose_today()

    if today == "common":
        image = COMMON_IMAGE
        caption = common_caption()
        keyboard = common_keyboard()
        label = "XPVIP partenaires"
    else:
        partner = PARTNERS[today]
        image = partner["image"]
        if not Path(image).exists():
            raise SystemExit(f"Affiche XPVIP introuvable pour {partner['name']}: {image}")
        print(f"🖼️ Affiche XPVIP sélectionnée: {image}")
        caption = caption_for(partner)
        keyboard = single_keyboard(partner)
        label = partner["name"]

    errors = []
    for cid in chat_ids():
        try:
            send_photo(cid, image, caption, keyboard)
            print(f"✅ {label} envoyé vers {cid}")
        except Exception as exc:
            errors.append(f"{cid}: {exc}")

    if errors:
        raise SystemExit(" | ".join(errors))


if __name__ == "__main__":
    main()
