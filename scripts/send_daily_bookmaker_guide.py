#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from telegram_rich import post_photo
from telegram_promo_channels import promo_channels, deliver_to_both
from telegram_promo_colors import colorized_button

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SECONDARY_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID_SECONDARY")
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
            [colorized_button(f"✅ S'inscrire sur {partner['name']}",partner["url"],partner["image"])]
        ]
    }


def common_keyboard():
    order = ["1xbet", "1win", "melbet", "linebet", "betclic", "betwinner"]
    buttons = [
        colorized_button(f"S'inscrire sur {PARTNERS[key]['name']}",PARTNERS[key]["url"],COMMON_IMAGE)
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
        "Suis les étapes affichées sur l’image puis utilise le bouton ci-dessous pour accéder "
        "au lien partenaire MrXPRONOS.\n\n"
        "<blockquote>🎁 <b>CODE PROMO : XPVIP</b>\n"
        "<i>Avant de valider ton inscription, vérifie que XPVIP apparaît bien dans le champ "
        "« Code promo » lorsqu’il est proposé.</i></blockquote>\n\n"
        "👇 <b>Inscription :</b> clique sur le bouton juste en dessous.\n\n"
        "⚠️ <b>18+</b> · <i>Offres et conditions variables selon le pays et le compte. "
        "Joue de façon responsable.</i>"
    )


def common_caption():
    return (
        "🔥 <b>XPVIP — PARTENAIRES MrXPRONOS</b>\n\n"
        "Choisis le bookmaker qui te convient avec les boutons ci-dessous.\n\n"
        "<blockquote>🎁 <b>CODE PROMO : XPVIP</b>\n"
        "<i>Vérifie que le code est bien renseigné lorsque le champ promo est proposé "
        "avant de terminer ton inscription.</i></blockquote>\n\n"
        "👇 <b>Sélectionne ton bookmaker :</b>\n\n"
        "⚠️ <b>18+</b> · <i>Les offres et conditions peuvent varier selon le pays. "
        "Joue de façon responsable.</i>"
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
    image = Path(image_path)
    if not image.exists():
        raise FileNotFoundError(f"Image introuvable: {image}")
    post_photo(requests,TOKEN,chat_id,image,caption,keyboard,
               timeout=120,mime="image/jpeg")


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

    deliver_to_both(
        promo_channels(CHAT_ID,SECONDARY_CHAT_ID),
        lambda cid: send_photo(cid,image,caption,keyboard),
        label=label,
    )


if __name__ == "__main__":
    main()
