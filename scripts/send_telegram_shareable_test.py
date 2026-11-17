#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Message partageable avec bouton URL, publié UNIQUEMENT sur @predict_mrxp.

--check : valider sans publier
--send  : publier après vérification du bot et du canal de test
Personnalisation (optionnelle) : SHARE_MESSAGE, SHARE_BUTTON_TEXT, SHARE_BUTTON_URL.
"""
from __future__ import annotations

import argparse
import os
import sys
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

import requests

from telegram_test_guard import TestChannelGuardError, validate_test_channel

DEFAULT_HTML = """🚨 <b>ARRÊTEZ D'ACHETER DES COUPONS QUI PERDENT !</b>

💸 Pourquoi continuer à payer pour des pronostics qui vous font perdre votre argent ?

🎯 Un bon pronostiqueur n'a pas besoin de vendre ses coupons pour prouver sa valeur.

✅ <b>Venez récupérer nos coupons GRATUITEMENT !</b>

⚽ Pronostics football • Analyses • Coupons gratuits

🔞 18+ • Aucun pronostic n'est garanti. Jouez responsablement."""

DEFAULT_BUTTON_TEXT = "🎁 Recevoir les coupons gratuits"
DEFAULT_BUTTON_URL = "https://t.me/mr_xpronos"
TEST_CHANNEL = "predict_mrxp"


def build_message() -> tuple[str, dict]:
    custom = (os.getenv("SHARE_MESSAGE") or "").strip()
    # Saisie libre = texte brut, échappé afin de ne pas casser le HTML Telegram.
    text = escape(custom, quote=False) if custom else DEFAULT_HTML
    label = (os.getenv("SHARE_BUTTON_TEXT") or DEFAULT_BUTTON_TEXT).strip()
    url = (os.getenv("SHARE_BUTTON_URL") or DEFAULT_BUTTON_URL).strip()
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {"t.me", "telegram.me"}:
        raise ValueError("Le bouton doit contenir un lien Telegram HTTPS.")
    if not parsed.path.strip("/"):
        raise ValueError("Lien Telegram incomplet.")
    if not 1 <= len(label) <= 64:
        raise ValueError("Libellé du bouton invalide.")
    if not 1 <= len(text) <= 4096:
        raise ValueError("Longueur du message Telegram invalide.")
    keyboard = {
        "inline_keyboard": [[{"text": label, "url": url, "style": "primary"}]]
    }
    return text, keyboard


def publish() -> int:
    token = (os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    destination = (os.getenv("TELEGRAM_TEST_CHAT_ID") or "@predict_mrxp").strip()
    if not token:
        print("::error::FOOTBALL_NEWS_BOT_TOKEN manquant")
        return 1

    try:
        chat = validate_test_channel(destination, token)
        if chat.get("username") != TEST_CHANNEL or not chat.get("can_post"):
            raise TestChannelGuardError("Canal de test non autorisé")
    except TestChannelGuardError as exc:
        print("::error::Vérification du canal de test refusée : " + str(exc))
        return 1

    text, keyboard = build_message()
    try:
        response = requests.post(
            "https://api.telegram.org/bot" + token + "/sendMessage",
            json={
                "chat_id": chat["chat_id"],
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": keyboard,
                "disable_web_page_preview": True,
                "protect_content": False,
            },
            timeout=(8, 25),
        )
        payload = response.json()
    except (requests.RequestException, ValueError):
        # Ne jamais exposer l'URL de requête contenant le jeton du bot.
        print("::error::Envoi Telegram échoué (réseau ou réponse invalide)")
        return 1

    result = payload.get("result") if isinstance(payload, dict) else None
    message_id = result.get("message_id") if isinstance(result, dict) else None
    if response.status_code != 200 or payload.get("ok") is not True or not isinstance(message_id, int):
        print("::error::Telegram a refusé le message (HTTP %s)" % response.status_code)
        return 1

    message_url = "https://t.me/" + TEST_CHANNEL + "/" + str(message_id)
    print("MESSAGE_PARTAGEABLE_ENVOYE " + message_url)
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        Path(summary).open("a", encoding="utf-8").write(
            "### Publication Telegram de test\n\n"
            f"[Ouvrir le message avec bouton]({message_url})\n\n"
            "Canal de test vérifié : @predict_mrxp. Aucun envoi vers la production.\n"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--send", action="store_true")
    args = parser.parse_args()
    try:
        text, keyboard = build_message()
    except ValueError as exc:
        print("::error::" + str(exc))
        return 1
    if args.check:
        print("MESSAGE_CHECK_OK text_chars=%s buttons=%s url=%s" %
              (len(text), len(keyboard["inline_keyboard"]), keyboard["inline_keyboard"][0][0]["url"]))
        return 0
    return publish()


if __name__ == "__main__":
    sys.exit(main())
