"""Recover seven already-checkpointed official Secours invitations into private D1.

Does not create channels or invitations, send messages, modify profiles, or
write any invite URL into Git. Fails closed on stale Telegram peer or invite.
"""
from __future__ import annotations

import asyncio
import json
import os
import re

from scripts.complete_remaining_manual_vaults import d1_query

HANDLE = re.compile(r"^@[a-z][a-z0-9_]{4,31}$")


def source_checkpoint_valid(username, row):
    if not isinstance(row, dict) or not HANDLE.fullmatch(str(username)):
        return False
    return bool(
        str(row.get("public_username") or "").lower() == username
        and isinstance(row.get("public_id"), int)
        and row["public_id"] < -1000000000000
        and isinstance(row.get("rescue_channel_id"), int)
        and row["rescue_channel_id"] < -1000000000000
        and row["rescue_channel_id"] != row["public_id"]
        and re.fullmatch(r"[0-9a-f]{64}",str(row.get("invite_sha256") or ""))
    )


def register_existing_rescue(username, entry, link):
    from film_relay.rescue_links_runtime import fingerprint
    from film_relay.rescue_channels import is_invite
    if (not source_checkpoint_valid(username, entry)
            or not is_invite(link)
            or fingerprint(link) != entry["invite_sha256"]):
        raise ValueError("rescue_mapping_unverified")
    previous = d1_query(
        "SELECT rescue_chat_id FROM cine_classic_rescue_config "
        "WHERE LOWER(public_handle)=LOWER(?)",
        [username]
    )
    if previous and (len(previous) != 1 or
                     str(previous[0]["rescue_chat_id"]) !=
                     str(entry["rescue_channel_id"])):
        raise RuntimeError("rescue_mapping_conflict")
    d1_query(
        "INSERT INTO cine_classic_rescue_config"
        "(public_handle,rescue_chat_id,invite_url,updated_at)"
        " VALUES(?,?,?,CURRENT_TIMESTAMP)"
        " ON CONFLICT(public_handle) DO UPDATE SET"
        " invite_url=excluded.invite_url,updated_at=CURRENT_TIMESTAMP"
        " WHERE cine_classic_rescue_config.rescue_chat_id=excluded.rescue_chat_id",
        [username,str(entry["rescue_channel_id"]),link]
    )
    confirmed = d1_query(
        "SELECT rescue_chat_id,invite_url FROM cine_classic_rescue_config "
        "WHERE LOWER(public_handle)=LOWER(?)", [username]
    )
    if (len(confirmed)!=1 or
            str(confirmed[0]["rescue_chat_id"]) != str(entry["rescue_channel_id"]) or
            confirmed[0]["invite_url"]!=link):
        raise RuntimeError("rescue_d1_receipt_missing")
    return True


async def sync():
    from telethon import TelegramClient, utils
    from telethon.sessions import StringSession
    from film_relay.rescue_channels import read_state
    from film_relay.rescue_links_runtime import (
        recover_checkpoint_peer,get_existing_invite
    )
    creds=[str(os.getenv(k) or "").strip() for k in
           ("TG_API_ID","TG_API_HASH","TG_STRING_SESSION")]
    if any(not x for x in creds) or not creds[0].isdecimal():
        raise RuntimeError("personal_session_required")
    checkpoints=read_state()["channels"]
    if not checkpoints:
        raise RuntimeError("rescue_checkpoints_missing")
    d1_query("SELECT public_handle FROM cine_classic_rescue_config LIMIT 1")
    client=TelegramClient(StringSession(creds[2]),int(creds[0]),creds[1],
                          flood_sleep_threshold=0,request_retries=0,
                          connection_retries=0)
    await client.connect()
    outcome={"checked":0,"registered":0,"unavailable":0,"conflicts":0}
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("personal_session_revoked")
        me=await client.get_me()
        if not me or getattr(me,"bot",False):
            raise RuntimeError("owner_session_invalid")
        dialogs=[d.entity async for d in client.iter_dialogs(limit=500)]
        by_id={utils.get_peer_id(d):d for d in dialogs}
        for username,row in sorted(checkpoints.items()):
            if not source_checkpoint_valid(username,row):
                outcome["conflicts"]+=1;continue
            outcome["checked"]+=1
            try:
                # Verify live public peer and the checkpoint identity.
                public=await client.get_entity(username)
                if (not getattr(public,"broadcast",False) or
                        utils.get_peer_id(public)!=int(row["public_id"])):
                    outcome["conflicts"]+=1;continue
                p=await client.get_permissions(public,me)
                if not (getattr(p,"is_creator",False) or (
                    getattr(p,"is_admin",False) and
                    getattr(p,"post_messages",False))):
                    outcome["conflicts"]+=1;continue
                rescue=await recover_checkpoint_peer(client,by_id,row)
                if rescue is None:
                    outcome["unavailable"]+=1;continue
                invite=await get_existing_invite(
                    client,rescue,expected_sha=row["invite_sha256"])
                if not invite:
                    outcome["unavailable"]+=1;continue
                register_existing_rescue(username,row,invite)
                outcome["registered"]+=1
            except Exception as exc:
                from telethon.errors import FloodWaitError,PeerFloodError
                if isinstance(exc,(FloodWaitError,PeerFloodError)):
                    raise
                # No private IDs or raw URLs logged.
                outcome["unavailable"]+=1
        return outcome
    finally:
        await client.disconnect()


def main():
    try:
        result=asyncio.run(sync())
        print("CINEX_RESCUE_D1_SYNC "+json.dumps(result,sort_keys=True))
        return 0 if result["registered"]==result["checked"] and \
                    result["checked"]>=6 else 2
    except Exception as exc:
        print("CINEX_RESCUE_SYNC_STOPPED",type(exc).__name__)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
