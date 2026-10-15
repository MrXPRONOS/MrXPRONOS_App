"""List visible channels and numeric -100 IDs from your Telegram account."""
import asyncio
import os

from telethon import TelegramClient, utils
from telethon.sessions import StringSession


async def main():
    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")
    session = os.getenv("TG_STRING_SESSION")
    if not all((api_id, api_hash, session)):
        raise SystemExit("Variables requises : TG_API_ID, TG_API_HASH, TG_STRING_SESSION")
    async with TelegramClient(StringSession(session), int(api_id), api_hash) as client:
        async for d in client.iter_dialogs():
            if getattr(d, "is_channel", False):
                print(f"{utils.get_peer_id(d.entity)}  |  {d.name}")


if __name__ == "__main__":
    asyncio.run(main())
