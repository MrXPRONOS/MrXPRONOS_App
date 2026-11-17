#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mr XPRONOS : second lot de 5 légendes (06-10) avec photo + bouton Telegram.

Exemples :
  python scripts/send_telegram_coupon_variants_v2_test.py --check
  python scripts/send_telegram_coupon_variants_v2_test.py --send --variant all
  python scripts/send_telegram_coupon_variants_v2_test.py --send --variant 8

Fail-closed : le bot est contrôlé via telegram_test_guard avant tout envoi.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

import requests

from telegram_test_guard import TestChannelGuardError, validate_test_channel

ROOT = Path(__file__).resolve().parents[1]
PHOTO = ROOT / "assets/telegram/promo_coupon_2026-10-25.jpg"
TEST_USERNAME = "predict_mrxp"
TARGET_URL = "https://t.me/mrxpronosfr"
BUTTON = {
    "inline_keyboard": [[{
        "text": "📲 REJOINDRE LE CANAL GRATUIT",
        "url": TARGET_URL,
        "style": "primary",  # bleu selon l’API Telegram
    }]]
}

# Tous les messages se basent sur l'idée de ne pas payer pour des tickets
# aléatoires, et rappellent qu'un résultat passé ne garantit pas un gain.
# Le texte est une légende directement attachée à l'image via sendPhoto.
VARIANTS = (
    ("06-provocateur", """🚨 <b>ARRÊTE D’ACHETER DES COUPONS… POUR ACHETER DES REGRETS !</b> 💸

Tu paies le coupon. Tu risques ta mise. <i>Et quand ça perd, on te vend le « prochain sûr » ?</i> 😅

<blockquote><b><i>Si quelqu’un dit gagner à tous les coups, pourquoi insiste-t-il pour vendre ses tickets ?</i></b></blockquote>

⚽ Chez <b>Mr XPRONOS</b>, découvre les coupons <b>GRATUITEMENT</b>.

📲 <b>REJOINS LE CANAL TELEGRAM GRATUIT</b> 👇

🔞 <i>18+ • Aucun gain garanti. Les paris comportent des risques.</i>"""),

    ("07-humour", """😂 <b>« COUPON VIP 100 % SÛR » : TON PORTEFEUILLE A DES SUEURS FROIDES.</b> 💀

Le vendeur : <i>« Cette fois, c’est du béton. »</i>
Le résultat : ❌
Ton portefeuille : <i>« On déménage. »</i> 🧳

<blockquote><b><i>Un ticket payant ne devient pas gagnant par magie.</i></b></blockquote>

✅ <b>STOP aux coupons payants !</b> Nos pronostics sont partagés <b>GRATUITEMENT</b>.

📲 <b>REJOINS MR XPRONOS SUR TELEGRAM</b> 👇

🔞 <i>18+ • Les pronostics peuvent perdre.</i>"""),

    ("08-direct", """💸 <b>POURQUOI PAYER UN COUPON… QUI PEUT PERDRE ?</b>

<blockquote><b><i>Le prix d’un pronostic ne garantit jamais son résultat.</i></b></blockquote>

❌ Arrête de payer pour des promesses.
✅ <b>Récupère nos coupons GRATUITEMENT.</b>

📲 <b>REJOINS LE CANAL TELEGRAM</b> et découvre nos analyses 👇

🔞 <i>18+ • Joue responsablement.</i>"""),

    ("09-humour-court", """💀 <b>COUPON PAYANT + PARI PERDANT = DOUBLE DOULEUR.</b> 😂

<blockquote><b><i>Ton portefeuille mérite mieux qu’un « c’était presque gagné ».</i></b></blockquote>

✋ <b>ARRÊTE D’ACHETER DES COUPONS.</b>
⚽ Les nôtres ? <b>GRATUITS.</b>

📲 <b>REJOINS NOTRE CANAL TELEGRAM</b> 👇

🔞 <i>18+ • Aucun pari garanti.</i>"""),

    ("10-ticket-gratuit", """🏆 <b>CE TICKET A GAGNÉ À 4,18. MAIS VOICI LA VRAIE BONNE NOUVELLE…</b> 👀

📸 La photo montre un ticket passé, <i>pas une promesse de gain pour demain.</i>

<blockquote><b><i>Pourquoi acheter des « coupons sûrs » quand tu peux consulter nos pronostics gratuitement ?</i></b></blockquote>

💸 <b>STOP AUX COUPONS PAYANTS.</b>
📲 <b>REJOINS MR XPRONOS SUR TELEGRAM — C’EST GRATUIT !</b> 👇

🔞 <i>18+ • Risque de perte. Joue responsablement.</i>"""),
)


class TelegramHTMLValidator(HTMLParser):
    """Vérifie l'imbrication des balises de mise en forme autorisées."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.visible = []

    def handle_starttag(self, tag, attrs):
        if tag not in {"b", "i", "blockquote"} or attrs:
            raise ValueError("Balise HTML non autorisée : " + tag)
        if tag == "blockquote" and "blockquote" in self.stack:
            raise ValueError("Citations imbriquées interdites")
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            raise ValueError("Balises HTML mal imbriquées : " + tag)
        self.stack.pop()

    def handle_data(self, data):
        self.visible.append(data)


def validate_content():
    if not PHOTO.is_file() or PHOTO.stat().st_size < 1024:
        raise ValueError("Photo source du coupon absente ou vide")
    with PHOTO.open("rb") as file:
        if file.read(3) != b"\xff\xd8\xff":
            raise ValueError("La photo utilisée doit être un vrai JPEG")
    if len(VARIANTS) != 5:
        raise ValueError("Cinq variantes sont obligatoires")
    if BUTTON["inline_keyboard"][0][0]["url"] != TARGET_URL:
        raise ValueError("Destination du bouton incorrecte")
    if BUTTON["inline_keyboard"][0][0].get("style") != "primary":
        raise ValueError("Le bouton doit utiliser le style bleu primary")

    names = set()
    for name, caption in VARIANTS:
        if name in names:
            raise ValueError("Variante en double : " + name)
        names.add(name)
        parser = TelegramHTMLValidator()
        parser.feed(caption)
        parser.close()
        if parser.stack:
            raise ValueError(name + ": balises non fermées")
        if "<blockquote>" not in caption or "<b>" not in caption or "<i>" not in caption:
            raise ValueError(name + ": manque gras, italique ou citation")
        length = len("".join(parser.visible))
        if not 1 <= length <= 1024:
            raise ValueError(name + ": légende hors limites Telegram")
        if "REJOINS" not in caption or "18+" not in caption:
            raise ValueError(name + ": appel à l'action ou avertissement manquant")
        print("VALIDATION_OK", name, "caption_chars", length)
    print("IMAGE_OK bytes", PHOTO.stat().st_size, "DESTINATION_BUTTON_OK", TARGET_URL)


def deliver(variant: str) -> int:
    token = (os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    destination = (os.getenv("TELEGRAM_TEST_CHAT_ID") or "@predict_mrxp").strip()
    if not token:
        print("::error::FOOTBALL_NEWS_BOT_TOKEN manquant")
        return 1

    try:
        verified = validate_test_channel(destination, token)
        if verified.get("username") != TEST_USERNAME or not verified.get("can_post"):
            raise TestChannelGuardError("Canal non autorisé")
    except TestChannelGuardError as exc:
        print("::error::Vérification du canal de test refusée :", str(exc))
        return 1

    selected = [
        (name, caption) for name, caption in VARIANTS
        if variant == "all" or name.startswith(variant + "-")
    ]
    if not selected:
        print("::error::Variante introuvable")
        return 1

    published = []
    for index, (name, caption) in enumerate(selected):
        try:
            with PHOTO.open("rb") as photo:
                response = requests.post(
                    "https://api.telegram.org/bot" + token + "/sendPhoto",
                    data={
                        "chat_id": verified["chat_id"],
                        "caption": caption,
                        "parse_mode": "HTML",
                        "reply_markup": json.dumps(BUTTON, ensure_ascii=False),
                        "protect_content": "false",
                    },
                    files={"photo": (PHOTO.name, photo, "image/jpeg")},
                    timeout=(10, 45),
                )
            payload = response.json()
        except (requests.RequestException, ValueError):
            # Ne jamais journaliser l'URL d'appel contenant le secret Telegram.
            print("::error::Erreur réseau / API Telegram pour", name)
            return 1
        message = payload.get("result") if isinstance(payload, dict) else None
        message_id = message.get("message_id") if isinstance(message, dict) else None
        if (
            response.status_code != 200
            or not isinstance(payload, dict)
            or payload.get("ok") is not True
            or not isinstance(message_id, int)
        ):
            print("::error::Telegram a refusé", name, "HTTP", response.status_code)
            return 1
        # La réponse Telegram confirme le message, et parfois le style de son bouton.
        returned_keyboard = (message.get("reply_markup") or {}).get("inline_keyboard", [])
        returned_button = returned_keyboard[0][0] if returned_keyboard and returned_keyboard[0] else {}
        returned_style = returned_button.get("style")
        if returned_style == "primary":
            print("BUTTON_BLUE_CONFIRMED", name)
        else:
            print("BUTTON_BLUE_REQUESTED_UNVERIFIED", name, "Telegram style retour:", returned_style)
        link = "https://t.me/" + TEST_USERNAME + "/" + str(message_id)
        print("COUPON_V2_SENT", name, link)
        published.append((name, link))
        if index < len(selected) - 1:
            time.sleep(1)

    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as fh:
            fh.write("### 5 nouvelles publications : image + citation HTML + CTA\n\n")
            for name, link in published:
                fh.write("- [" + name + "](" + link + ")\n")
            fh.write("\nDestination test uniquement : @predict_mrxp\n")
            fh.write("Bouton vers : " + TARGET_URL + "\n")
    return 0


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--send", action="store_true")
    parser.add_argument("--variant", choices=["all", "6", "7", "8", "9", "10"], default="all")
    args = parser.parse_args()
    try:
        validate_content()
    except (ValueError, AssertionError) as exc:
        print("::error::Échec de validation :", str(exc))
        return 1
    return deliver(args.variant) if args.send else 0


if __name__ == "__main__":
    sys.exit(main())
