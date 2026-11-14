#!/usr/bin/env python3
"""Initialiser EN LOCAL une session utilisateur Telegram pour GitHub Actions.

Ne jamais publier la session obtenue, ni la coller dans un chat.
Pre-requis : pip install 'telethon>=1.38,<2'
Identifiants API : https://my.telegram.org/apps
"""
from __future__ import annotations

import asyncio
import getpass

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    api_id = int(input("TELEGRAM_USER_API_ID (my.telegram.org/apps) : ").strip())
    api_hash = getpass.getpass("TELEGRAM_USER_API_HASH : ").strip()

    print("\nConnexion au compte TELEGRAM PERSONNEL dont tu veux remplir Messages enregistrés.")
    print("N'entre tes codes de connexion et ton mot de passe 2FA que dans ce terminal local.")
    client = TelegramClient(StringSession(), api_id, api_hash)
    try:
        await client.start(
            phone=lambda: input("Numéro Telegram (+indicatif) : ").strip(),
            code_callback=lambda: input("Code Telegram reçu : ").strip(),
            password=lambda: getpass.getpass("Mot de passe 2FA (si demandé) : "),
        )
        me = await client.get_me()
        if not me or me.bot:
            raise ValueError("Un compte personnel Telegram est requis, pas un bot.")
        session = client.session.save()
        print("\nCompte connecté et autorisé.")
        print("Copie les valeurs ci-dessous UNIQUEMENT dans les secrets GitHub Actions :")
        print(f"TELEGRAM_USER_ID = {me.id}")
        print(f"TELEGRAM_USER_API_ID = {api_id}")
        print("TELEGRAM_USER_API_HASH = (la valeur my.telegram.org/apps)")
        print("TELEGRAM_USER_SESSION = " + session)
        print("\nATTENTION : la session est un accès à ton compte Telegram.")
        print("Ne la communique à personne et ne la stocke pas dans le dépôt ni dans un journal public.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
