#!/usr/bin/env python3
"""Transfère le message d'accueil Telegram à « Messages enregistrés ».

La destination est impérativement InputPeerSelf (le compte Telegram connecté).
L'authentification est une session UTILISATEUR MTProto, jamais un jeton de bot.
Le workflow ne publie aucun nouveau message dans @predict_mrxp.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

from send_telegram_welcome_test import WELCOME_BUTTONS, WELCOME_HTML, check_message

SOURCE_CHANNEL = "predict_mrxp"
DEFAULT_MESSAGE_ID = 1675


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)


def expected_message_text() -> str:
    parser = _PlainText()
    parser.feed(WELCOME_HTML)
    parser.close()
    return "".join(parser.text_parts).strip()


def expected_buttons() -> list[tuple[str, str]]:
    return [
        (item["text"], item["url"])
        for row in WELCOME_BUTTONS["inline_keyboard"]
        for item in row
    ]


def message_buttons(message: object) -> list[tuple[str, str]]:
    markup = getattr(message, "reply_markup", None)
    rows = getattr(markup, "rows", None) or []
    return [
        (str(getattr(button, "text", "")), str(getattr(button, "url", "")))
        for row in rows
        for button in (getattr(row, "buttons", None) or [])
    ]


def validate_source_message(message: object) -> None:
    if not message:
        raise ValueError("Message source introuvable dans le canal de test")
    if str(getattr(message, "raw_text", "")).strip() != expected_message_text():
        raise ValueError("Le message source ne correspond pas au texte d'accueil actuel")
    buttons = message_buttons(message)
    if buttons != expected_buttons():
        raise ValueError("Les deux boutons URL attendus sont absents ou différents")
    # Telegram préserve les inline keyboards à boutons URL lors des transferts.
    # Aucun autre type de bouton n'est autorisé ici.


def validate_message_id(message_id: int) -> None:
    if message_id <= 0:
        raise ValueError("L'identifiant du message doit être positif")
    check_message()
    expected = expected_buttons()
    if len(expected) != 2 or any(not url.startswith("https://") for _, url in expected):
        raise ValueError("Deux boutons HTTPS sont nécessaires")


async def save_message(source_message_id: int) -> int:
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    required = (
        "TELEGRAM_USER_API_ID",
        "TELEGRAM_USER_API_HASH",
        "TELEGRAM_USER_SESSION",
        "TELEGRAM_USER_ID",
    )
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        raise ValueError("Secrets GitHub manquants : " + ", ".join(missing))

    try:
        api_id = int(os.environ["TELEGRAM_USER_API_ID"])
        account_id = int(os.environ["TELEGRAM_USER_ID"])
    except ValueError as exc:
        raise ValueError("API_ID ou USER_ID incorrect (entiers requis)") from exc
    if api_id <= 0 or account_id <= 0:
        raise ValueError("API_ID et USER_ID doivent être positifs")

    async with TelegramClient(
        StringSession(os.environ["TELEGRAM_USER_SESSION"].strip()),
        api_id,
        os.environ["TELEGRAM_USER_API_HASH"].strip(),
    ) as client:
        self_user = await client.get_me()
        if not self_user or self_user.bot or int(self_user.id) != account_id:
            raise ValueError(
                "Session Telegram refusée : elle ne correspond pas au compte personnel attendu"
            )

        source = await client.get_entity("@" + SOURCE_CHANNEL)
        if str(getattr(source, "username", "")).casefold() != SOURCE_CHANNEL:
            raise ValueError("Le canal source n'est pas @predict_mrxp")

        message = await client.get_messages(source, ids=source_message_id)
        validate_source_message(message)

        # « me » désigne exclusivement les Messages enregistrés du compte connecté.
        sent = await client.forward_messages("me", message)
        if isinstance(sent, list):
            sent = sent[0] if sent else None
        if not sent:
            raise RuntimeError("Telegram n'a pas retourné de message transféré")

        saved = await client.get_messages("me", ids=sent.id)
        if not saved or saved.raw_text.strip() != expected_message_text():
            raise RuntimeError("Contenu non retrouvé dans Messages enregistrés après transfert")
        if message_buttons(saved) != expected_buttons():
            raise RuntimeError(
                "Les boutons ne sont pas conservés dans Messages enregistrés : "
                "contrôle manuel du message requis"
            )

        print(
            "SUCCESS: message d'accueil transféré dans Messages enregistrés ; "
            f"compte vérifié, ID du message enregistré : {sent.id} ; "
            "2 boutons URL conservés."
        )
        path = os.getenv("GITHUB_STEP_SUMMARY")
        if path:
            with Path(path).open("a", encoding="utf-8") as summary:
                summary.write(
                    "### Message d'accueil dans « Messages enregistrés »\n\n"
                    f"- Source : https://t.me/{SOURCE_CHANNEL}/{source_message_id}\n"
                    "- Destination : Messages enregistrés du compte Telegram vérifié\n"
                    "- Vérification : texte et 2 boutons URL conservés\n"
                    f"- Identifiant du message enregistré : {sent.id}\n"
                )
        return int(sent.id)


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Contrôle sans réseau")
    group.add_argument("--send", action="store_true", help="Transfert vers Messages enregistrés")
    parser.add_argument(
        "--source-message-id",
        type=int,
        default=DEFAULT_MESSAGE_ID,
        help="ID du message validé dans @predict_mrxp (défaut : 1675)",
    )
    args = parser.parse_args()
    try:
        validate_message_id(args.source_message_id)
        if args.check:
            print("OK : source autorisée, deux liens et formatage validés. Aucun envoi.")
            return 0
        asyncio.run(save_message(args.source_message_id))
        return 0
    except Exception as exc:
        # Ne jamais afficher d'informations de connexion ni de trace contenant une session.
        if isinstance(exc, (ValueError, RuntimeError)):
            print("::error::" + str(exc))
        else:
            print("::error::Échec de la session ou de l'API Telegram (détails masqués)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
