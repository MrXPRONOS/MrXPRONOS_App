#!/usr/bin/env python3
"""Génère localement une StringSession Telegram. Ne jamais commit la valeur."""
import asyncio
import getpass
from telethon import TelegramClient
from telethon.sessions import StringSession

async def main():
    api_id = int(input("Telegram API ID: ").strip())
    api_hash = getpass.getpass("Telegram API Hash: ").strip()
    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Connexion Telegram non autorisée")
        print("\nTG_SESSION_STRING (à garder secrète):\n")
        print(client.session.save())

if __name__ == "__main__":
    asyncio.run(main())
