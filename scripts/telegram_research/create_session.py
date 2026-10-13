import asyncio
import getpass
from telethon import TelegramClient
from telethon.sessions import StringSession

async def main():
    api_id = int(input("Telegram API ID: ").strip())
    api_hash = getpass.getpass("Telegram API Hash: ").strip()
    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram login failed")
        print("Store this value ONLY in the GitHub secret TG_SESSION_STRING:")
        print(client.session.save())
        print("Never commit or share this session string.")

if __name__ == "__main__":
    asyncio.run(main())
