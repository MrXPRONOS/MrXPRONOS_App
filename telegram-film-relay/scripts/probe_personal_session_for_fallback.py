"""Classify personal Telegram availability without broadcasting or bypassing FloodWait.

Outputs exactly one safe status line. Telegram credentials and peer IDs never
reach CI logs. Unknown errors must NOT authorize bot failover.
"""
from __future__ import annotations
import asyncio
import os
import sys
from datetime import datetime, timezone

def classify_credentials(env):
    # Cooldown always takes precedence even when a secret was removed.
    # A missing session must never become an excuse to evade FloodWait.
    until=str(env.get("TG_PERSONAL_COOLDOWN_UNTIL_UTC") or "").strip()
    if until:
        try:
            delta=datetime.fromisoformat(until.replace("Z","+00:00")).astimezone(timezone.utc)
            if delta > datetime.now(timezone.utc):
                return "flood_wait"
        except ValueError:
            return "unknown"
    if not env.get("TG_STRING_SESSION") or not env.get("TG_API_ID") or not env.get("TG_API_HASH"):
        return "session_missing"
    return None

async def probe():
    local=classify_credentials(os.environ)
    if local:
        return local
    from telethon import TelegramClient,errors
    from telethon.sessions import StringSession
    try:
        client=TelegramClient(
            StringSession(os.environ["TG_STRING_SESSION"]),
            int(os.environ["TG_API_ID"]),os.environ["TG_API_HASH"],
            flood_sleep_threshold=0,request_retries=0,
            connection_retries=0,timeout=12)
        try:
            await asyncio.wait_for(client.connect(),timeout=16)
            authorized=await asyncio.wait_for(client.is_user_authorized(),timeout=16)
            return "available" if authorized else "session_revoked"
        finally:
            await client.disconnect()
    except (errors.SessionRevokedError,errors.AuthKeyUnregisteredError,
            errors.AuthKeyInvalidError):
        return "session_revoked"
    except errors.FloodWaitError:
        return "flood_wait"
    except errors.PeerFloodError:
        return "peer_flood"
    except (Exception,):
        return "unknown"

def main():
    try:
        status=asyncio.run(probe())
    except Exception:
        status="unknown"
    allowed={"session_missing","session_revoked","flood_wait","peer_flood","available","unknown"}
    status=status if status in allowed else "unknown"
    print("PERSONAL_TELEGRAM_STATUS="+status)
    github_output=os.getenv("GITHUB_OUTPUT","")
    if github_output:
        with open(github_output,"a",encoding="utf-8") as f:
            f.write("status="+status+"\n")
    return 0

if __name__=="__main__":
    sys.exit(main())
