#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publish MR XPRONOS F Telegram folder poster ONLY to verified @predict_mrxp.

Usage:
  python scripts/send_telegram_folder_promo_test.py --check
  python scripts/send_telegram_folder_promo_test.py --send

Does not change membership, schedule or other Telegram channels.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

from telegram_test_guard import TestChannelGuardError, validate_test_channel

ROOT = Path(__file__).resolve().parents[1]
PHOTO = ROOT / "assets/telegram/mrxpronos_f_folder_promo.jpg"
TEST_CHAT = "predict_mrxp"
TARGET_URL = "https://t.me/addlist/ZmW4vfwcrMAwNzJk"
CAPTION = (
    "🎬 <b>FILMS • SÉRIES • ANIMÉS 🍿</b>\n"
    "🔥 <b>TOUT DANS UN SEUL DOSSIER TELEGRAM !</b>\n"
    "📂 <i>Tes chaînes de divertissement réunies au même endroit.</i>\n"
    "👇 <b>AJOUTE MR XPRONOS F GRATUITEMENT !</b>"
)
BUTTON = {
    "inline_keyboard": [[{
        "text": "📥 AJOUTER LE DOSSIER",
        "url": TARGET_URL,
        "style": "primary",
    }]]
}


def check():
    if not PHOTO.is_file() or PHOTO.stat().st_size < 1024:
        raise ValueError("L'affiche n'est pas présente dans GitHub")
    with PHOTO.open("rb") as img:
        if img.read(3) != b"\xff\xd8\xff":
            raise ValueError("Le fichier doit être au format JPEG")
    if len(CAPTION) > 1024 or CAPTION.count("\n") != 3:
        raise ValueError("La légende doit être courte et compatible avec sendPhoto")
    if (BUTTON["inline_keyboard"][0][0]["style"] != "primary"
            or BUTTON["inline_keyboard"][0][0]["url"] != TARGET_URL):
        raise ValueError("Bouton bleu ou lien du dossier incorrect")
    print("FOLDER_PROMO_CHECK_OK image_bytes=", PHOTO.stat().st_size,
          "caption_lines=4", "blue_button=primary", "folder_link=", TARGET_URL)


def send():
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or
             os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    destination = (os.getenv("TELEGRAM_TEST_CHAT_ID") or "@predict_mrxp").strip()
    if not token:
        print("::error::Telegram bot token manquant")
        return 1
    try:
        chat = validate_test_channel(destination, token)
        if (chat.get("username") != TEST_CHAT
                or chat.get("can_post") is not True
                or str(chat.get("bot_username", "")).casefold() != "mrxpronos_canal_bot"):
            raise TestChannelGuardError("Bot ou canal de test inattendu")
    except TestChannelGuardError as e:
        print("::error::Vérification du canal de test refusée :", str(e))
        return 1

    try:
        with PHOTO.open("rb") as img:
            response = requests.post(
                "https://api.telegram.org/bot" + token + "/sendPhoto",
                data={
                    "chat_id": chat["chat_id"],
                    "caption": CAPTION,
                    "parse_mode": "HTML",
                    "reply_markup": json.dumps(BUTTON, ensure_ascii=False),
                    "protect_content": "false",
                },
                files={"photo": (PHOTO.name, img, "image/jpeg")},
                timeout=(10, 45),
            )
        payload = response.json()
    except (requests.RequestException, ValueError):
        # Never print the token-containing request URL, including in exceptions.
        print("::error::Erreur de connexion ou réponse Telegram invalide")
        return 1

    result = payload.get("result") if isinstance(payload, dict) else None
    msg_id = result.get("message_id") if isinstance(result, dict) else None
    if response.status_code != 200 or payload.get("ok") is not True or not isinstance(msg_id, int):
        print("::error::Envoi refusé (HTTP", response.status_code, ")")
        return 1

    link = "https://t.me/" + TEST_CHAT + "/" + str(msg_id)
    print("FOLDER_PROMO_SENT", link)
    markup = result.get("reply_markup") or {}
    keyboard = markup.get("inline_keyboard") or []
    returned_style = keyboard[0][0].get("style") if keyboard and keyboard[0] else None
    print("BLUE_BUTTON",
          "confirmed" if returned_style == "primary" else "requested_unverified")
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as f:
            f.write("## MR XPRONOS F — Dossier Telegram\n\n")
            f.write("- [Ouvrir la publication test](" + link + ")\n")
            f.write("- [Lien dossier](" + TARGET_URL + ")\n")
            f.write("- Bouton : 📥 AJOUTER LE DOSSIER (primary/bleu)\n")
            f.write("- Destination : @predict_mrxp uniquement\n")
    return 0


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--send", action="store_true")
    args = parser.parse_args()
    try:
        check()
    except ValueError as e:
        print("::error::", str(e))
        return 1
    return send() if args.send else 0


if __name__ == "__main__":
    sys.exit(main())
