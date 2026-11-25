#!/usr/bin/env python3
"""Read-only personal-admin channel discovery, saved in encrypted GitHub Vault.

No Supabase or Cloudflare calls. No Telegram writes, joins, reactions or posts.
Must run only with the existing personal-session safety cooldown and
mrx-telegram-personal-account concurrency lock.
"""
from __future__ import annotations

import asyncio
import base64
import os
import re
import sys
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from scripts.actu_foot_github_vault import GitHubVault, VaultError

OWNER_PATH = "assets/data/private/cineradar/owner_channels.aes.json"
OWNER_CONTEXT = b"MrXPRONOS/CineRadar/OwnerAdminChannels/GitHubVault/v1"
ID_PATTERN = re.compile(r"^-100[0-9]{5,20}$")
MAX_ADMIN_CHANNELS = 1200


class OwnerChannelVault(GitHubVault):
    def __init__(self, **kwargs):
        super().__init__(path=OWNER_PATH, **kwargs)
        self.key = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None, info=OWNER_CONTEXT
        ).derive(self.key)


def validate(document):
    if not isinstance(document, dict) or document.get("version") != 1:
        raise VaultError("Invalid owner-channel vault version")
    if document.get("source") != "personal_admin_dialogs" or document.get("complete") is not True:
        raise VaultError("Owner-channel audit was not complete")
    raw = document.get("channels")
    excluded = document.get("excluded")
    if not isinstance(raw, list) or not isinstance(excluded, list):
        raise VaultError("Invalid owner-channel data")
    if len(raw) > MAX_ADMIN_CHANNELS or len(excluded) > MAX_ADMIN_CHANNELS:
        raise VaultError("Owner-channel size cap exceeded")
    if any(not isinstance(x,str) or not ID_PATTERN.fullmatch(x)
           for x in [*raw,*excluded]):
        raise VaultError("Owner-channel identifier invalid")
    channels, banned = set(raw), set(excluded)
    if channels & banned or len(channels) != len(raw) or len(banned) != len(excluded):
        raise VaultError("Duplicate or ambiguous owner channel")
    if not document.get("verified_at"):
        raise VaultError("Missing owner verification timestamp")
    return channels,banned


def read_owner_channels():
    vault = OwnerChannelVault(branch="main")
    snapshot = vault.read(allow_new=True)
    if snapshot.sha is None:
        return None
    included, excluded = validate(snapshot.data)
    return included,excluded


async def discover():
    # Deferred dependency: the normal 5-minute GitHub-only reaction runner
    # needs no Telegram personal session or Telethon installation.
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.types import Channel
    from telethon.errors import FloodWaitError, PeerFloodError

    raw_id = (os.getenv("TG_API_ID") or "").strip()
    api_hash = (os.getenv("TG_API_HASH") or "").strip()
    session = (os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
               or os.getenv("TG_STREAM_SESSION") or "").strip()
    if not raw_id.isdecimal() or not api_hash or not session:
        raise VaultError("Telegram personal admin inventory credentials unavailable")

    client = TelegramClient(
        StringSession(session),int(raw_id),api_hash,
        flood_sleep_threshold=0,request_retries=0,connection_retries=1,
        receive_updates=False,
    )
    seen, owned, excluded = 0, set(), set()
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise VaultError("Telegram personal session not authorized")
        me = await client.get_me()
        if me is None or getattr(me,"bot",False):
            raise VaultError("Personal session does not belong to a user")
        async for dialog in client.iter_dialogs():
            channel = dialog.entity
            if not isinstance(channel, Channel) or not channel.broadcast:
                continue
            seen += 1
            if seen > MAX_ADMIN_CHANNELS:
                raise VaultError("Admin discovery reached channel safety limit")
            # Server-returned creator and admin_rights flags are necessary;
            # being subscribed to a channel is never sufficient.
            if not (getattr(channel,"creator",False)
                    or getattr(channel,"admin_rights",None)):
                continue
            cid = "-100"+str(channel.id)
            if not ID_PATTERN.fullmatch(cid):
                raise VaultError("Invalid Telegram channel ID")
            from scripts.cineradar_reaction_multichannel import is_torrent9
            chat = {"username":getattr(channel,"username",None),
                    "title":getattr(channel,"title",None)}
            if is_torrent9(chat):
                excluded.add(cid)
            else:
                owned.add(cid)
    finally:
        await client.disconnect()
    if not owned:
        raise VaultError("No verified personal admin channels; previous snapshot preserved")
    return {
        "version":1,"source":"personal_admin_dialogs","complete":True,
        "verified_at":datetime.now(timezone.utc).isoformat(),
        "channels":sorted(owned),"excluded":sorted(excluded),
    }


if __name__ == "__main__":
    try:
        # GitHub Actions checks cooldown before invoking this script.
        document = asyncio.run(discover())
        included,excluded = validate(document)
        vault = OwnerChannelVault(branch="main")
        prior = vault.read(allow_new=True)
        vault.write(document,expected_sha=prior.sha,
                    message="data(cineradar): encrypted verified owner-admin channels")
        print("CINERADAR_OWNER_CHANNELS_ENCRYPTED",
              "verified_admin_channels="+str(len(included)),
              "torrent9_exclusions="+str(len(excluded)),
              "storage=github_aes_gcm")
    except Exception as exc:
        print("CINERADAR_OWNER_CHANNEL_DISCOVERY_FAILED",
              type(exc).__name__,file=sys.stderr)
        sys.exit(1)
