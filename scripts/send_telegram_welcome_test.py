#!/usr/bin/env python3
"""Publie le message d'accueil avec mise en forme Telegram, UNIQUEMENT vers @predict_mrxp.

Utilisation :
  python scripts/send_telegram_welcome_test.py --check  # Validation locale sans envoi
  python scripts/send_telegram_welcome_test.py --send   # Publication dans le canal de test
"""
from __future__ import annotations

import argparse
import os
import sys
from html.parser import HTMLParser
from pathlib import Path

import requests

from telegram_test_guard import TestChannelGuardError, validate_test_channel

TEST_CHANNEL = "predict_mrxp"
WELCOME_HTML = """👋 <b><i>Bienvenue chez Mr XPRONOS !</i></b> ⚽👑

🎯 <b>Reçois nos pronostics et coupons chaque jour !</b>

📲 <b>Sur Telegram :</b>
<i>Rejoins notre canal en cliquant sur le bouton ci-dessous.</i>

📱 <b>Garde Mr XPRONOS à portée de main !</b>
<i>Installe notre application sur ton téléphone pour retrouver facilement les pronostics et suivre nos nouveautés, en un seul geste.</i>

✅ <b>Enregistre mon numéro</b> pour suivre mes statuts WhatsApp !

🔞 <i>18+ • Joue responsablement.</i>"""

# Ces boutons sont attachés au même message via reply_markup (inline_keyboard).
# Ils s'affichent directement sous le texte, pas comme de simples URL.
WELCOME_BUTTONS = {
    "inline_keyboard": [
        [{"text": "📲 Rejoindre le canal Telegram", "url": "https://t.me/mrxpronosfr"}],
        [{"text": "📱 Installer l’application", "url": "https://mrxpronos.github.io/MrXPRONOS_App/installer.html"}],
    ],
}


class WelcomeHTMLValidator(HTMLParser):
    """Contrôle les balises supportées et les imbrications bien formées."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in {"b", "i"} or attrs:
            raise ValueError("Balise de mise en forme non autorisée")
        self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack.pop() != tag:
            raise ValueError("Balises de mise en forme mal imbriquées")


def check_message() -> None:
    validator = WelcomeHTMLValidator()
    validator.feed(WELCOME_HTML)
    validator.close()
    if validator.stack:
        raise ValueError("Balises de mise en forme non fermées")
    if len(WELCOME_HTML) > 4096:
        raise ValueError("Message Telegram trop long")
    for required in (
        "<b><i>Bienvenue chez Mr XPRONOS !</i></b>",
        "Enregistre mon numéro",
        "18+ • Joue responsablement.",
    ):
        if required not in WELCOME_HTML:
            raise ValueError("Élément du message d'accueil manquant")
    expected = [
        ("📲 Rejoindre le canal Telegram", "https://t.me/mrxpronosfr"),
        ("📱 Installer l’application", "https://mrxpronos.github.io/MrXPRONOS_App/installer.html"),
    ]
    rows = WELCOME_BUTTONS.get("inline_keyboard")
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("Les deux boutons Telegram sont requis")
    for row, (label, url) in zip(rows, expected):
        if not isinstance(row, list) or row != [{"text": label, "url": url}]:
            raise ValueError("Bouton Telegram invalide")
        if url in WELCOME_HTML:
            raise ValueError("Les URL doivent être des boutons, pas du texte visible")


def send() -> int:
    token = (os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_TEST_CHAT_ID") or "@predict_mrxp").strip()
    try:
        # Refuse systématiquement un autre canal, même si le secret CHAT_ID est erroné.
        verified = validate_test_channel(chat_id, token)
        if verified.get("username") != TEST_CHANNEL or not verified.get("can_post"):
            raise TestChannelGuardError("Destination Telegram non autorisée")
    except TestChannelGuardError as exc:
        print(f"::error::Canal de test non validé : {exc}")
        return 1

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": verified["chat_id"],
                "text": WELCOME_HTML,
                "parse_mode": "HTML",
                "reply_markup": WELCOME_BUTTONS,
                "disable_web_page_preview": True,
                "protect_content": False,  # autorise le transfert du message à un nouvel abonné
            },
            timeout=(8, 25),
        )
        payload = response.json()
    except (requests.RequestException, ValueError):
        # Important : jamais de trace réseau ni d'URL contenant le jeton du bot.
        print("::error::Échec du contact avec l'API Telegram")
        return 1

    message_id = (payload.get("result") or {}).get("message_id") if isinstance(payload, dict) else None
    if response.status_code != 200 or payload.get("ok") is not True or not isinstance(message_id, int):
        print(f"::error::Telegram n'a pas confirmé l'envoi (HTTP {response.status_code})")
        return 1

    url = f"https://t.me/{TEST_CHANNEL}/{message_id}"
    print(f"Message d'accueil publié dans @{TEST_CHANNEL} : {url}")
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        Path(summary_path).open("a", encoding="utf-8").write(
            f"### Message d'accueil Telegram publié\n\n"
            f"[Ouvrir le message de test]({url})\n\n"
            "Le message utilise le format HTML et deux boutons Telegram natifs. "
            "Attention : le transfert manuel peut retirer les boutons.\n"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Valider le contenu sans publier")
    group.add_argument("--send", action="store_true", help="Publier UNIQUEMENT vers @predict_mrxp")
    args = parser.parse_args()
    try:
        check_message()
    except ValueError as exc:
        print(f"::error::Message d'accueil invalide : {exc}")
        return 1
    if args.check:
        print("Message d'accueil OK : HTML, 2 boutons URL natifs et mention 18+ vérifiés. Aucun envoi.")
        return 0
    return send()


if __name__ == "__main__":
    sys.exit(main())
