#!/usr/bin/env python3
"""One-shot Telegram CTA smoke in the exact private CineX stock registered in D1.

No personal MTProto login; no public channels; no films copied.
Safely fails closed if the verified bot or private channel is unavailable.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from urllib.parse import urlsplit

import requests

ACCOUNT_ID = "9c86118191b804d91b5f5b2c89114999"
DATABASE_ID = "fa8b5009-bc1a-4a6e-b143-7a487c7297a5"
EXPECTED_BOT = "cineradarfr_bot"
EXPECTED_TITLE = "CinéX — Stock privé"
BUTTON_URL = "https://t.me/CineRadarFr_Bot"
BUTTON_TEXT = "🎬 Ouvrir Ciné Radar"
TEXT = "🧪 TEST PRIVÉ MR XPRONOS — vérification du bouton Telegram. Ce message est temporaire."
KEYBOARD = {"inline_keyboard": [[{"text": BUTTON_TEXT, "url": BUTTON_URL}]]}


class SmokeFailure(RuntimeError):
    pass


def private_stock_record(session, cf_key):
    if not cf_key:
        raise SmokeFailure("CLOUDFLARE_API_TOKEN absent")
    url = (f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}"
           f"/d1/database/{DATABASE_ID}/query")
    try:
        response = session.post(url, headers={"Authorization": "Bearer " + cf_key},
            json={"sql": "SELECT stock_chat_id,radar_bot_id,ready "
                         "FROM cine_private_stock_config WHERE singleton=1"}, timeout=(8, 25))
        data = response.json()
    except (requests.RequestException, ValueError):
        raise SmokeFailure("Stock D1 inaccessible") from None
    if not response.ok or data.get("success") is not True:
        raise SmokeFailure("Stock D1 refusé") from None
    chunks = data.get("result") or []
    rows = chunks[0].get("results") or [] if len(chunks) == 1 else []
    if len(rows) != 1 or int(rows[0].get("ready") or 0) != 1:
        raise SmokeFailure("Stock D1 non prêt")
    chat = str(rows[0].get("stock_chat_id") or "")
    bot_id = int(rows[0].get("radar_bot_id") or 0)
    if not re.fullmatch(r"-100[0-9]{5,}", chat) or bot_id <= 0:
        raise SmokeFailure("Identifiants du stock D1 non valides")
    return chat, bot_id


def telegram(session, token, method, payload):
    if not token:
        raise SmokeFailure("Bot Cine Radar absent")
    try:
        response = session.post(
            "https://api.telegram.org/bot" + token + "/" + method,
            json=payload, timeout=(8, 30))
        data = response.json()
    except (requests.RequestException, ValueError):
        # A write may have reached Telegram; never retry.
        raise SmokeFailure("Requête Telegram incertaine: " + method) from None
    if not response.ok or data.get("ok") is not True:
        raise SmokeFailure("Telegram a refusé " + method)
    return data.get("result")


def validate_destination(session, token, stock_id, expected_bot_id):
    me = telegram(session, token, "getMe", {})
    if (not isinstance(me, dict) or me.get("is_bot") is not True
        or int(me.get("id") or 0) != expected_bot_id
        or str(me.get("username", "")).casefold() != EXPECTED_BOT):
        raise SmokeFailure("Identité du bot incorrecte")
    chat = telegram(session, token, "getChat", {"chat_id": stock_id})
    if (not isinstance(chat, dict) or str(chat.get("id")) != stock_id
        or chat.get("type") != "channel"
        or chat.get("username")
        or chat.get("title") != EXPECTED_TITLE):
        raise SmokeFailure("Le canal n'est pas le stock privé autorisé")
    member = telegram(session, token, "getChatMember",
        {"chat_id": stock_id, "user_id": expected_bot_id})
    if not isinstance(member, dict):
        raise SmokeFailure("Droits du bot introuvables")
    status = member.get("status")
    if not (status == "creator"
            or (status == "administrator" and member.get("can_post_messages") is True
                and member.get("can_delete_messages") is True)):
        raise SmokeFailure("Le bot doit pouvoir publier ET supprimer le test")
    return True


def verify_receipt(result, stock_id):
    if not isinstance(result, dict):
        raise SmokeFailure("Reçu de publication manquant")
    message_id = int(result.get("message_id") or 0)
    if message_id <= 0 or str((result.get("chat") or {}).get("id")) != stock_id:
        raise SmokeFailure("Message envoyé vers une destination inattendue")
    keyboard = result.get("reply_markup") or {}
    rows = keyboard.get("inline_keyboard") or []
    if not any(isinstance(b, dict) and b.get("url") == BUTTON_URL
               and b.get("text") == BUTTON_TEXT for row in rows for b in row):
        raise SmokeFailure("Telegram n'a pas confirmé le bouton URL attendu")
    if result.get("text") != TEXT:
        raise SmokeFailure("Contenu Telegram inattendu")
    return message_id


def run(session, cf_key, bot_token, execute=False):
    if not execute:
        print("DRY_RUN: exact private stock and Telegram are not contacted")
        return {"sent": False, "verified": False, "deleted": False}
    stock_id, bot_id = private_stock_record(session, cf_key)
    validate_destination(session, bot_token, stock_id, bot_id)
    message_id = None
    verified = False
    try:
        receipt = telegram(session, bot_token, "sendMessage", {
            "chat_id": stock_id, "text": TEXT,
            "reply_markup": KEYBOARD, "disable_notification": True,
            "protect_content": True
        })
        if isinstance(receipt, dict) and isinstance(receipt.get("message_id"), int):
            message_id = receipt["message_id"]
        verify_receipt(receipt, stock_id)
        verified = True
    finally:
        if message_id is not None:
            # Delete only the exact message created by this single test.
            telegram(session, bot_token, "deleteMessage",
                     {"chat_id": stock_id, "message_id": message_id})
            print("TEST_PRIVATE_MESSAGE_DELETED")
    if verified:
        print("CINEX_PRIVATE_BUTTON_SMOKE_SUCCESS: destination private, button verified, deleted")
    return {"sent": True, "verified": verified, "deleted": True}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--execute", action="store_true")
    opts = p.parse_args()
    if opts.execute and os.getenv("CINEX_PRIVATE_BUTTON_TEST_ONCE") != "1":
        raise SmokeFailure("Test activation guard missing")
    with requests.Session() as sess:
        run(sess, os.getenv("CLOUDFLARE_API_TOKEN", ""),
            os.getenv("CINEX_RADAR_BOT_TOKEN", ""), execute=opts.execute)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SmokeFailure as exc:
        print("CINEX_PRIVATE_BUTTON_SMOKE_FAILED:", str(exc), file=sys.stderr)
        sys.exit(1)
