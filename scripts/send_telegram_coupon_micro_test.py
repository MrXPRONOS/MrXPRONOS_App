#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""5 micro-légendes Telegram (3-5 lignes), même photo, bouton CTA bleu.

Test-only : canal @predict_mrxp validé par telegram_test_guard.
Réutilisable depuis GitHub Actions (all ou une seule variante).
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
CHANNEL_URL = "https://t.me/mrxpronosfr"
BUTTON = {
    "inline_keyboard": [[{
        "text": "📲 REJOINDRE LE CANAL GRATUIT",
        "url": CHANNEL_URL,
        "style": "primary",
    }]]
}

# Cinq lignes utiles maximum, aucune ligne vide.
# Un seul ticket passé ne prédit pas les résultats futurs.
VARIANTS = (
    ("11-direct", """🚨 <b>STOP AUX COUPONS PAYANTS !</b>
💸 <i>Payant ne veut pas dire gagnant.</i>
✅ <b>Nos pronostics : GRATUITS.</b>
📲 <b>REJOINS LE CANAL TELEGRAM 👇</b>
🔞 <i>18+ • Risque de perte.</i>"""),

    ("12-provocateur", """😏 <b>ENCORE UN COUPON « 100 % SÛR » ?</b>
<blockquote><b><i>Pourquoi payer pour une promesse ?</i></b></blockquote>
⚽ <b>Ici, les coupons sont GRATUITS.</b>
📲 <b>REJOINS NOTRE TELEGRAM 👇</b>
🔞 <i>18+ • Aucun pari garanti.</i>"""),

    ("13-ultra-court", """💸 <b>COUPONS PAYANTS ? STOP !</b>
✅ <b>COUPONS GRATUITS ICI.</b>
📲 <b>REJOINS LE CANAL TELEGRAM 👇</b>
🔞 <i>18+ • Risque de perte.</i>"""),

    ("14-humour", """😂 <b>TON PORTEFEUILLE : « PITIÉ, PAS ENCORE ! »</b>
💀 <i>Quand le coupon payant perd aussi...</i>
🎯 <b>Nos coupons ? GRATUITS.</b>
📲 <b>REJOINS NOTRE TELEGRAM 👇</b>
🔞 <i>18+ • Aucun gain garanti.</i>"""),

    ("15-ticket-preuve", """📸 <b>CE TICKET : COTE 4,18 ✅</b>
<blockquote><i>Un gain passé ≠ un gain garanti.</i></blockquote>
⚽ <b>Découvre nos coupons GRATUITS.</b>
📲 <b>REJOINS LE CANAL TELEGRAM 👇</b>
🔞 <i>18+ • Joue responsablement.</i>"""),
)


class CaptionValidator(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag not in {"b", "i", "blockquote"} or attrs:
            raise ValueError("Balise non autorisée : " + tag)
        if tag == "blockquote" and "blockquote" in self.stack:
            raise ValueError("Citation imbriquée")
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            raise ValueError("Mauvais emboîtement HTML : " + tag)
        self.stack.pop()

    def handle_data(self, text):
        self.text.append(text)


def check():
    if not PHOTO.is_file() or PHOTO.stat().st_size < 1024:
        raise ValueError("Image du coupon absente ou vide")
    with PHOTO.open("rb") as fh:
        if fh.read(3) != b"\xff\xd8\xff":
            raise ValueError("Fichier JPEG attendu")
    if len(VARIANTS) != 5:
        raise ValueError("Cinq variantes attendues")
    btn = BUTTON["inline_keyboard"][0][0]
    if btn.get("url") != CHANNEL_URL or btn.get("style") != "primary":
        raise ValueError("Lien du canal et style bleu du bouton obligatoires")

    seen = set()
    for name, caption in VARIANTS:
        if name in seen:
            raise ValueError("Nom de variante dupliqué")
        seen.add(name)
        lines = caption.splitlines()
        if not (3 <= len(lines) <= 5) or any(not x.strip() for x in lines):
            raise ValueError(name + " : maximum 5 lignes sans lignes vides")
        parser = CaptionValidator()
        parser.feed(caption)
        parser.close()
        if parser.stack:
            raise ValueError(name + " : balises non fermées")
        visible_chars = len("".join(parser.text))
        if visible_chars > 1024:
            raise ValueError(name + " : légende Telegram trop longue")
        if "<b>" not in caption or "REJOINS" not in caption or "GRATUIT" not in caption or "18+" not in caption:
            raise ValueError(name + " : élément essentiel absent")
        print("MICRO_CAPTION_OK", name, "lines", len(lines), "chars", visible_chars)
    print("IMAGE_AND_BLUE_BUTTON_OK", PHOTO.stat().st_size, CHANNEL_URL)


def publish(selected: str) -> int:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or
             os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_TEST_CHAT_ID") or "@predict_mrxp").strip()
    if not token:
        print("::error::Bot token absent (TELEGRAM_BOT_TOKEN/FOOTBALL_NEWS_BOT_TOKEN)")
        return 1
    try:
        verified = validate_test_channel(chat_id, token)
        if verified.get("username") != TEST_USERNAME or not verified.get("can_post"):
            raise TestChannelGuardError("Seul le canal test est autorisé")
        # L'audit du projet a identifié ce bot précisément.
        if str(verified.get("bot_username", "")).casefold() != "mrxpronos_canal_bot":
            raise TestChannelGuardError("L'identité @mrxpronos_canal_bot n'est pas confirmée")
    except TestChannelGuardError as exc:
        print("::error::Vérification Telegram refusée :", str(exc))
        return 1

    chosen = [(name, caption) for name, caption in VARIANTS
              if selected == "all" or name.startswith(selected + "-")]
    if not chosen:
        print("::error::Variante inconnue")
        return 1

    links = []
    for index, (name, caption) in enumerate(chosen):
        try:
            with PHOTO.open("rb") as image:
                response = requests.post(
                    "https://api.telegram.org/bot" + token + "/sendPhoto",
                    data={
                        "chat_id": verified["chat_id"],
                        "caption": caption,
                        "parse_mode": "HTML",
                        "reply_markup": json.dumps(BUTTON, ensure_ascii=False),
                        "protect_content": "false",
                    },
                    files={"photo": (PHOTO.name, image, "image/jpeg")},
                    timeout=(10, 45),
                )
            payload = response.json()
        except (requests.RequestException, ValueError):
            # Ne pas exposer l'exception requests: son URL peut contenir le token.
            print("::error::Erreur transport ou réponse Telegram pour", name)
            return 1

        message = payload.get("result") if isinstance(payload, dict) else None
        mid = message.get("message_id") if isinstance(message, dict) else None
        if (response.status_code != 200 or payload.get("ok") is not True
                or not isinstance(mid, int)):
            print("::error::Envoi non confirmé pour", name, "HTTP", response.status_code)
            return 1

        link = "https://t.me/" + TEST_USERNAME + "/" + str(mid)
        print("MICRO_CAPTION_SENT", name, link)
        markup = message.get("reply_markup") or {}
        rows = markup.get("inline_keyboard") or []
        returned_style = rows[0][0].get("style") if rows and rows[0] else None
        print("BLUE_BUTTON", name,
              "confirmed" if returned_style == "primary" else "requested_unverified")
        links.append((name, link))
        if index != len(chosen) - 1:
            time.sleep(1)

    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as f:
            f.write("## Publications micro-légendes (canal de test uniquement)\n\n")
            for name, link in links:
                f.write("- [" + name + "](" + link + ")\n")
            f.write("\nBouton : " + CHANNEL_URL + "\n")
    return 0


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--send", action="store_true")
    parser.add_argument("--variant", choices=["all", "11", "12", "13", "14", "15"],
                        default="all")
    args = parser.parse_args()
    try:
        check()
    except ValueError as exc:
        print("::error::", str(exc))
        return 1
    return publish(args.variant) if args.send else 0


if __name__ == "__main__":
    sys.exit(main())
