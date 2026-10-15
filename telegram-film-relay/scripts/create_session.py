"""Generate a user-session string on your OWN computer; never commit it."""
import getpass
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("Telegram API ID : ").strip())
api_hash = getpass.getpass("Telegram API HASH : ").strip()
with TelegramClient(StringSession(), api_id, api_hash) as client:
    client.start()
    print("\nSESSION SECRET (paste ONLY into GitHub Actions secret TG_STRING_SESSION):")
    print(client.session.save())
    print("\nDo not publish this string or send it in chat.")
