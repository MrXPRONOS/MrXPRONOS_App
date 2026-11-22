#!/usr/bin/env python3
"""Envoi unique et sécurisé de l'affiche e-book vers @predict_mrxp.

Jamais de destination de production, jamais de secrets en journal.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests

from telegram_test_guard import TestChannelGuardError, validate_test_channel

EXPECTED_CHANNEL = "@predict_mrxp"
POSTER = Path("assets/marketing/telegram-ebook-2026-11/affiche-promo-1938-fcfa.jpg")
URL_EXTRACT = "https://mr-xpronos.myficsell.com/njtp54yjw"
URL_GUIDE = "https://mr-xpronos.myficsell.com/favxph7ge"

# HTML Telegram: les balises <b>, <i>, <blockquote> restent de la mise en forme.
CAPTION = (
    "💰 <b>Et si Telegram devenait une nouvelle source de revenus ?</b>\n"
    "<blockquote>📘 <i>Découvre 10 méthodes concrètes pour le monétiser.</i></blockquote>\n"
    "📈 Apprends à <b>attirer des abonnés</b> et à développer ton activité.\n"
    "🎁 <i>Inclus : plan de 30 jours + bonus Canal Manager X.</i>\n"
    "👇 Clique sur le bouton ci-dessous pour obtenir ton guide à <b>1 938 FCFA</b> !"
)

BUTTONS = {"inline_keyboard": [
    [{"text": "Voir l’extrait du PDF", "url": URL_EXTRACT, "style": "primary"}],
    [{"text": "Télécharger mon guide", "url": URL_GUIDE, "style": "primary"}],
]}


def check_payload():
    if not POSTER.is_file() or POSTER.stat().st_size < 15000:
        raise ValueError("Affiche JPEG introuvable ou vide")
    if len(CAPTION) > 1024:
        raise ValueError("Légende Telegram trop longue")
    for row in BUTTONS["inline_keyboard"]:
        assert len(row) == 1
        btn = row[0]
        parsed = urlsplit(btn["url"])
        if parsed.scheme != "https" or parsed.netloc != "mr-xpronos.myficsell.com":
            raise ValueError("URL de vente/extrait inattendue")
        if btn["style"] != "primary":
            raise ValueError("Le bouton n'est pas bleu")


def post_test_photo(token: str, chat_id: int) -> int:
    form = {
        "chat_id": str(chat_id),
        "caption": CAPTION,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(BUTTONS, ensure_ascii=False),
    }
    with POSTER.open("rb") as image:
        try:
            response = requests.post(
                "https://api.telegram.org/bot" + token + "/sendPhoto",
                data=form,
                files={"photo": (POSTER.name, image, "image/jpeg")},
                timeout=(10, 50),
            )
            result = response.json()
        except (requests.RequestException, ValueError):
            # Ne jamais journaliser l'URL de requête contenant le token.
            raise RuntimeError("Envoi Telegram non confirmé (réseau ou réponse invalide); ne pas relancer sans contrôle") from None
    if not result.get("ok") or not response.ok:
        detail = str(result.get("description", "Erreur Telegram"))[:220]
        raise RuntimeError("Telegram a refusé le message : " + detail)
    msg = result.get("result") or {}
    if msg.get("chat", {}).get("id") != chat_id or not isinstance(msg.get("message_id"), int):
        raise RuntimeError("Réponse Telegram inattendue : destination non confirmée")
    return msg["message_id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    check_payload()
    if args.dry_run:
        print("DRY_RUN_OK: photo=", POSTER, "buttons=2", "caption_chars=", len(CAPTION))
        print("Bouton 1:", BUTTONS["inline_keyboard"][0][0]["text"], URL_EXTRACT)
        print("Bouton 2:", BUTTONS["inline_keyboard"][1][0]["text"], URL_GUIDE)
        return 0

    if os.getenv("GITHUB_EVENT_NAME") != "push" or os.getenv("GITHUB_RUN_ATTEMPT") != "1":
        raise RuntimeError("Blocage anti-doublons : envoi seulement lors du premier push de test")
    if os.getenv("GITHUB_REF") != "refs/heads/campaign/telegram-ebook-test-20261122":
        raise RuntimeError("Ref GitHub non autorisée pour ce test")
    channel = os.getenv("TELEGRAM_TEST_CHAT_ID", EXPECTED_CHANNEL).strip()
    if channel not in (EXPECTED_CHANNEL, "-1004366833281"):
        raise RuntimeError("Canal de test interdit : seuls @predict_mrxp et son chat_id officiel sont admis")
    token = os.getenv("TELEGRAM_TEST_GUARD_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Token du bot de test absent (aucun basculement vers la production)")
    try:
        verified = validate_test_channel(channel, token)
    except TestChannelGuardError as exc:
        raise RuntimeError("Accès au canal de test refusé : " + str(exc)) from None
    chat_id = verified["chat_id"]
    if int(chat_id) != -1004366833281:
        raise RuntimeError("L'identifiant retourné par Telegram ne correspond pas au canal de test")
    print("DESTINATION_VERIFIED @predict_mrxp; image et 2 boutons bleus")
    message_id = post_test_photo(token, chat_id)
    link = f"https://t.me/predict_mrxp/{message_id}"
    print("TELEGRAM_TEST_SENT", link)
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as s:
            s.write("## Publication e-book dans le canal de test\n\n")
            s.write(f"✅ Publication envoyée : {link}\n\n")
            s.write("Boutons bleus : Voir l’extrait du PDF / Télécharger mon guide\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError) as exc:
        print("::error::" + str(exc))
        sys.exit(1)