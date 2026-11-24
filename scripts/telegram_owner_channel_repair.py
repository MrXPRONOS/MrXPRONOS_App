"""Owner-authorized Telegram channel repair. No public messages, no unsafe replay.

Only the existing personal Telegram account can create channels or promote bots.
Reuses an existing private Formation stage before considering creation.
Never creates a replacement for the historical Actu Crypto public channel.
Never prints private chat IDs, access hashes, tokens, invites or full exceptions.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

STAGE_TITLE = "MRX Formation - Transit Technique"
STAGE_MARKER = "MRX_FORMATION_STAGE_V1"
BOT_USERNAME = "mrxpronos_canal_bot"
REPO = "MrXPRONOS/MrXPRONOS_App"
PRIVATE_ID = re.compile(r"-100[0-9]{6,}$")
PUBLIC_NAME = re.compile(r"@[a-zA-Z][a-zA-Z0-9_]{3,31}$")


@dataclass
class Status:
    stage: str = "unchecked"
    legacy: str = "unchecked"
    bot: str = "unchecked"


def valid_stage_id(value):
    """Treat a private channel ID as a *reference*, not proof of its existence."""
    return isinstance(value, str) and bool(PRIVATE_ID.fullmatch(value.strip()))


def legacy_handle(value):
    """Do not silently redirect a historical publication route."""
    value = str(value or "").strip()
    return value if PUBLIC_NAME.fullmatch(value) else ""


def check_bot(token):
    import requests
    if not token or ":" not in token:
        raise RuntimeError("bot_token_missing")
    try:
        reply = requests.get("https://api.telegram.org/bot" + token + "/getMe",
                             timeout=(8, 15)).json()
    except (requests.RequestException, ValueError):
        raise RuntimeError("bot_metadata_unavailable") from None
    me = reply.get("result") if isinstance(reply, dict) and reply.get("ok") is True else None
    if (not isinstance(me, dict) or me.get("username", "").lower() != BOT_USERNAME
            or me.get("is_bot") is not True or not isinstance(me.get("id"), int)):
        raise RuntimeError("unexpected_bot_identity")
    return me


def secret_key_credentials(env):
    """Validate ability to store a new stage ID BEFORE attempting creation."""
    import requests
    pat = (env.get("GH_PAT_SECRETS") or "").strip()
    if not pat:
        raise RuntimeError("github_secret_update_unavailable")
    endpoint = "https://api.github.com/repos/" + REPO + "/actions/secrets/public-key"
    try:
        response = requests.get(endpoint, headers={
            "Authorization": "Bearer " + pat, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }, timeout=(8, 15))
        if response.status_code != 200:
            raise RuntimeError("github_secret_update_unavailable")
        data = response.json()
    except (requests.RequestException, ValueError):
        raise RuntimeError("github_secret_update_unavailable") from None
    if not isinstance(data, dict) or not isinstance(data.get("key_id"), str) or not isinstance(data.get("key"), str):
        raise RuntimeError("github_secret_update_unavailable")
    return pat, data["key_id"], data["key"]


def persist_stage_secret(stage_id, prepared):
    """Encrypt a private chat ID for GitHub Actions; NEVER log the value."""
    import requests
    from nacl.public import PublicKey, SealedBox
    if not valid_stage_id(stage_id):
        raise RuntimeError("invalid_stage_id")
    pat, key_id, public_key = prepared
    try:
        cipher = SealedBox(PublicKey(base64.b64decode(public_key))).encrypt(stage_id.encode())
        encoded = base64.b64encode(cipher).decode("ascii")
        response = requests.put(
            "https://api.github.com/repos/" + REPO +
            "/actions/secrets/FORMATION_STAGE_CHAT",
            headers={"Authorization": "Bearer " + pat,
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28"},
            json={"encrypted_value": encoded, "key_id": key_id},
            timeout=(8, 15),
        )
    except (requests.RequestException, ValueError):
        raise RuntimeError("github_stage_secret_write_failed") from None
    if response.status_code not in (201, 204):
        raise RuntimeError("github_stage_secret_write_failed")
    return True


def select_stage(dialogs, configured):
    """Reuse the exactly configured stage or a uniquely marked recovery stage."""
    from telethon import utils
    exact = [d for d in dialogs
             if getattr(d, "broadcast", False) and not getattr(d, "username", None)
             and configured and str(utils.get_peer_id(d)) == configured]
    if len(exact) == 1:
        return exact[0], "configured"
    matched = [
        d for d in dialogs
        if getattr(d, "broadcast", False) and not getattr(d, "username", None)
        and getattr(d, "title", "") == STAGE_TITLE
    ]
    if len(matched) > 1:
        raise RuntimeError("ambiguous_stage_titles")
    if matched:
        return matched[0], "candidate"
    return None, "missing"


async def validate_stage_candidate(client, entity, mode):
    from telethon import functions
    if mode == "candidate":
        full = await client(functions.channels.GetFullChannelRequest(entity))
        if STAGE_MARKER not in str(getattr(full.full_chat, "about", "") or ""):
            raise RuntimeError("stage_candidate_marker_mismatch")
    if getattr(entity, "username", None) or not getattr(entity, "broadcast", False):
        raise RuntimeError("stage_not_private_broadcast")
    return entity


async def ensure_minimum_admin(client, entity, me, bot_entity):
    from telethon import functions, errors
    from telethon.tl.types import ChatAdminRights
    own = await client.get_permissions(entity, me)
    if not (getattr(own, "is_creator", False) or
            (getattr(own, "is_admin", False) and getattr(own, "add_admins", False))):
        return "insufficient_owner_rights"
    not_a_member = False
    try:
        access = await client.get_permissions(entity, bot_entity)
        if getattr(access, "is_creator", False) or (
                getattr(access, "is_admin", False) and
                getattr(access, "post_messages", False)):
            return "already_admin"
    except (errors.UserNotParticipantError, ValueError, TypeError):
        not_a_member = True
    if not_a_member:
        # Invite only the exact verified service bot. Never invite a guessed
        # username, retry an unknown result, or add unrelated subscribers.
        await client(functions.channels.InviteToChannelRequest(
            channel=entity, users=[bot_entity]))
    # Promote with no permission to manage users or other admins.
    rights = ChatAdminRights(
        change_info=False, post_messages=True, edit_messages=False,
        delete_messages=False, ban_users=False, invite_users=False,
        pin_messages=False, add_admins=False, anonymous=False,
        manage_call=False, other=False, manage_topics=False,
        post_stories=False, edit_stories=False, delete_stories=False,
    )
    # Telegram's editAdmin can promote a bot directly. If Telegram requires
    # an invitation first, the operation fails closed (no blind invite retry).
    await client(functions.channels.EditAdminRequest(
        channel=entity, user_id=bot_entity, admin_rights=rights,
        rank="MRX Service"))
    verified = await client.get_permissions(entity, bot_entity)
    if not (getattr(verified, "is_creator", False) or (
            getattr(verified, "is_admin", False) and getattr(verified, "post_messages", False))):
        raise RuntimeError("bot_admin_not_verified")
    return "repaired"


async def repair(env):
    from telethon import TelegramClient, errors, functions, utils
    from telethon.sessions import StringSession
    state = Status()
    expected = (env.get("FORMATION_STAGE_CHAT") or "").strip()
    if expected and not valid_stage_id(expected):
        raise RuntimeError("formation_stage_invalid_reference")
    legacy = legacy_handle(env.get("ACTU_CRYPTO_CHAT_ID", ""))
    if not legacy:
        raise RuntimeError("historical_crypto_channel_not_public_handle")
    identity = check_bot(env.get("FORMATION_BOT_TOKEN", ""))
    creds = [str(env.get(k) or "").strip() for k in ("TG_STRING_SESSION", "TG_API_ID", "TG_API_HASH")]
    if not all(creds):
        raise RuntimeError("personal_session_credentials_missing")
    client = TelegramClient(StringSession(creds[0]), int(creds[1]), creds[2],
                            flood_sleep_threshold=0, request_retries=0,
                            connection_retries=0, timeout=15)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("personal_session_revoked")
        me = await client.get_me()
        bot = await client.get_entity("@" + BOT_USERNAME)
        if not getattr(bot, "bot", False) or bot.id != identity["id"]:
            raise RuntimeError("bot_identity_mismatch")
        state.bot = "verified"
        dialogs = [d.entity async for d in client.iter_dialogs(limit=600)]
        stage, mode = select_stage(dialogs, expected)
        prepared_secret = None
        if stage is None or (stage is not None and mode != "configured"):
            # Never create/repoint a private channel if we cannot persist the
            # reference to the actual secret consumed by production.
            try:
                prepared_secret = secret_key_credentials(env)
            except RuntimeError:
                state.stage = "blocked_secret_update"
        if state.stage != "blocked_secret_update":
            try:
                created = False
                if stage is None:
                    # Exactly one new private stage, deliberately not public.
                    # Telegram errors (incl. FloodWait) are NEVER retried here.
                    updates = await client(functions.channels.CreateChannelRequest(
                        title=STAGE_TITLE, about=STAGE_MARKER + ": internal-only",
                        broadcast=True, megagroup=False))
                    found = [c for c in updates.chats
                             if getattr(c, "broadcast", False)
                             and getattr(c, "title", "") == STAGE_TITLE]
                    if len(found) != 1:
                        raise RuntimeError("stage_create_result_uncertain")
                    stage, created = found[0], True
                    mode = "candidate"
                stage = await validate_stage_candidate(client, stage, mode)
                outcome = await ensure_minimum_admin(client, stage, me, bot)
                if outcome == "insufficient_owner_rights":
                    state.stage = "blocked_owner_permissions"
                else:
                    new_id = str(utils.get_peer_id(stage))
                    if new_id != expected:
                        persist_stage_secret(new_id, prepared_secret)
                        state.stage = "created_configured" if created else "relinked_configured"
                    else:
                        state.stage = outcome
            except errors.FloodWaitError:
                raise
            except Exception:
                state.stage = "blocked_stage_operation"

        # Legacy crypto channel MUST retain its identity and history.
        try:
            old_channel = await client.get_entity(legacy)
            if not getattr(old_channel, "broadcast", False):
                state.legacy = "blocked_wrong_channel_type"
            else:
                # Only the channel creator is allowed to perform this auto-repair.
                outcome = await ensure_minimum_admin(client, old_channel, me, bot)
                state.legacy = outcome
        except errors.FloodWaitError:
            raise
        except Exception:
            state.legacy = "blocked_channel_inaccessible"
    finally:
        await client.disconnect()
    return state


async def run():
    env = os.environ
    if env.get("TELEGRAM_OWNER_REPAIR_AUTHORIZED") != "true":
        raise RuntimeError("explicit_authorization_missing")
    result = await repair(env)
    print("OWNER_TELEGRAM_REPAIR",
          "bot=" + result.bot,
          "stage=" + result.stage,
          "legacy=" + result.legacy, flush=True)
    return 0 if (result.stage in ("already_admin", "repaired", "created_configured", "relinked_configured")
                 and result.legacy in ("already_admin", "repaired")) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(run()))
    except Exception as exc:
        # Telegram may include private IDs, titles or access hashes in errors.
        # No exception strings, tokens or raw response bodies in public logs.
        print("OWNER_TELEGRAM_REPAIR_ABORTED", type(exc).__name__, flush=True)
        raise SystemExit(1)
