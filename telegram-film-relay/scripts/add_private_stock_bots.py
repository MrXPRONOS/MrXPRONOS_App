"""Add every *verified* user-configured CinéX bot to EXISTING private stock.

Never creates a channel, copies media, issues an invitation or exposes bot tokens.
Secrets come exclusively from GitHub Actions; no tokens committed to GitHub.
Personal account session is only opened after cooldown and Bot API identity checks.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys

from scripts.provision_private_stock import (
    TITLE, MARKER, bot_identity, d1_query, verify_members,
)

# Explicit allowlist of GitHub secrets already used by CineX or its publishing
# workflows; an arbitrary secret cannot become a stock administrator.
BOT_SECRETS = (
    ("radar", "CINEX_RADAR_BOT_TOKEN"),
    ("radar_fallback", "TELEGRAM_BOT_TOKEN"),
    ("publisher", "CINEX_PUBLISH_BOT_TOKEN"),
    ("cinex_legacy", "CINEX_BOT_TOKEN"),
    ("film_publisher", "FOOTBALL_NEWS_BOT_TOKEN"),
    ("series", "SERIES_BOT_TOKEN"),
    ("anime", "ANIME_BOT_TOKEN"),
    ("action", "ACTION_BOT_TOKEN"),
    ("desir", "DESIR_BOT_TOKEN"),
    ("comedie", "COMEDIE_BOT_TOKEN"),
)
USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")
CREATE = """CREATE TABLE IF NOT EXISTS cine_private_stock_bots(
  bot_id INTEGER PRIMARY KEY CHECK(bot_id>0),
  username TEXT NOT NULL,
  secret_label TEXT NOT NULL,
  can_post INTEGER NOT NULL CHECK(can_post IN(0,1)),
  verified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)"""
RIGHT_KEYS = (
    "change_info", "edit_messages", "delete_messages", "ban_users",
    "invite_users", "pin_messages", "add_admins", "anonymous",
    "manage_call", "other", "manage_topics", "post_stories",
    "edit_stories", "delete_stories",
)


def discover_bot_candidates(env=None, identify=None):
    """Return (valid, unavailable, invalid); duplicates share ONE bot identity.

    No token, chat ID or private identifiers are returned or logged.
    An S03 publisher is accepted ONLY when its expected identity matches.
    """
    env = os.environ if env is None else env
    identify = bot_identity if identify is None else identify
    candidates, invalid, unavailable = [], [], []
    seen = set()
    publisher_expected = str(env.get("CINEX_PUBLISH_BOT_USERNAME") or "").lstrip("@").lower()
    for label, key in BOT_SECRETS:
        token = (env.get(key) or "").strip()
        if not token:
            unavailable.append(label)
            continue
        try:
            item = identify(token)
            username = str(item.get("username") or "")
            botid = item.get("id")
            if (item.get("is_bot") is not True or not isinstance(botid, int)
                or botid <= 0 or not USERNAME.fullmatch(username)):
                raise ValueError("invalid_bot_identity")
            if label == "publisher" and (
                not publisher_expected or username.lower() != publisher_expected
            ):
                invalid.append(label)
                continue
            if label == "radar" and username.lower() != "cineradarfr_bot":
                invalid.append(label)
                continue
            # Telegram usernames are public, but never print any message IDs.
            if botid not in seen:
                candidates.append({"id": botid, "username": username, "label": label})
                seen.add(botid)
        except Exception:
            # Invalid secrets/Telegram identity are explicitly reported and
            # never granted access to the stock.
            invalid.append(label)
    if not any(x["username"].lower() == "cineradarfr_bot" for x in candidates):
        raise RuntimeError("radar_identity_missing_or_unverified")
    return candidates, unavailable, invalid


def _exact_stock_record():
    rows = d1_query(
        "SELECT stock_chat_id,owner_id,radar_bot_id,ready "
        "FROM cine_private_stock_config WHERE singleton=1"
    )
    if len(rows) != 1 or int(rows[0]["ready"]) != 1:
        raise RuntimeError("existing_stock_not_ready")
    return rows[0]


def _minimal_rights(rights):
    if rights is None or not getattr(rights, "post_messages", False):
        return False
    return not any(bool(getattr(rights, name, False)) for name in RIGHT_KEYS)


def _record_bot(bot):
    d1_query(CREATE)
    d1_query(
        "INSERT INTO cine_private_stock_bots(bot_id,username,secret_label,can_post) "
        "VALUES(?,?,?,1) ON CONFLICT(bot_id) DO UPDATE SET "
        "username=excluded.username,secret_label=excluded.secret_label,"
        "can_post=1,verified_at=CURRENT_TIMESTAMP",
        [int(bot["id"]), bot["username"], bot["label"]],
    )


async def attach(*, apply=False, pause=13):
    candidates, absent, invalid = discover_bot_candidates()
    # Never disclose the actual stock channel ID, bot tokens or invitations.
    print("CINEX_STOCK_BOT_INVENTORY", "verified_distinct", len(candidates),
          "missing_secrets", len(absent), "invalid_or_unverified", len(invalid))
    if not apply:
        return {"mode": "dry_run", "verified": len(candidates),
                "missing": len(absent), "invalid": len(invalid)}
    if not 12 <= pause <= 120:
        raise RuntimeError("invalid_pacing")
    config = _exact_stock_record()
    expected_owner = int(config["owner_id"])
    expected_stock = str(config["stock_chat_id"])
    expected_radar = int(config["radar_bot_id"])
    if not expected_stock.startswith("-100") or expected_owner <= 0 or expected_radar <= 0:
        raise RuntimeError("invalid_d1_stock_identity")
    if not any(bot["id"] == expected_radar for bot in candidates):
        raise RuntimeError("d1_radar_identity_mismatch")
    # Ensure we can write verification receipts before modifying Telegram.
    d1_query(CREATE)

    from telethon import TelegramClient, functions, utils
    from telethon.errors import FloodWaitError, PeerFloodError, UserNotParticipantError
    from telethon.sessions import StringSession
    from telethon.tl.functions.channels import GetParticipantRequest
    from telethon.tl.types import ChatAdminRights

    api_id, api_hash, session = (
        (os.getenv("TG_API_ID") or "").strip(),
        (os.getenv("TG_API_HASH") or "").strip(),
        (os.getenv("TG_STRING_SESSION") or "").strip(),
    )
    if not api_id.isdecimal() or not api_hash or not session:
        raise RuntimeError("personal_telegram_session_not_configured")
    client = TelegramClient(StringSession(session), int(api_id), api_hash,
                            flood_sleep_threshold=0, request_retries=1,
                            connection_retries=2)
    await client.connect()
    added = verified = failed = 0
    failed_labels = []
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("personal_telegram_session_invalid")
        owner = await client.get_me()
        if not owner or getattr(owner, "bot", False) or owner.id != expected_owner:
            raise RuntimeError("connected_owner_mismatch")
        dialogs = [d.entity async for d in client.iter_dialogs(limit=500)]
        matches = [
            item for item in dialogs
            if getattr(item, "broadcast", False)
            and utils.get_peer_id(item) == int(expected_stock)
            and getattr(item, "title", "") == TITLE
            and not getattr(item, "username", None)
        ]
        if len(matches) != 1:
            raise RuntimeError("registered_private_stock_channel_not_found")
        stock = matches[0]
        details = await client(functions.channels.GetFullChannelRequest(stock))
        if MARKER not in str(getattr(details.full_chat, "about", "") or ""):
            raise RuntimeError("private_stock_marker_mismatch")
        if not getattr(await client.get_permissions(stock, owner), "is_creator", False):
            raise RuntimeError("private_stock_owner_not_creator")
        # Any unknown human or bot already present stops the operation.
        await verify_members(client, stock, expected_owner, candidates)
        for bot in candidates:
            try:
                user = await client.get_entity("@" + bot["username"])
                if not getattr(user, "bot", False) or int(user.id) != int(bot["id"]):
                    raise RuntimeError("bot_identity_changed")
                rights = None
                try:
                    member = await client(GetParticipantRequest(
                        channel=stock, participant=user
                    ))
                    rights = getattr(member.participant, "admin_rights", None)
                except UserNotParticipantError:
                    pass
                if not _minimal_rights(rights):
                    minimal = ChatAdminRights(
                        change_info=False, post_messages=True,
                        edit_messages=False, delete_messages=False,
                        ban_users=False, invite_users=False, pin_messages=False,
                        add_admins=False, anonymous=False, manage_call=False,
                        other=False, manage_topics=False,
                        post_stories=False, edit_stories=False,
                        delete_stories=False,
                    )
                    await client(functions.channels.EditAdminRequest(
                        channel=stock, user_id=user, admin_rights=minimal,
                        rank="CinéX Stock"
                    ))
                    added += 1
                    await asyncio.sleep(pause)
                receipt = await client(GetParticipantRequest(
                    channel=stock, participant=user
                ))
                confirmed = getattr(receipt.participant, "admin_rights", None)
                if not _minimal_rights(confirmed):
                    raise RuntimeError("minimal_post_only_permission_not_confirmed")
                _record_bot(bot)
                verified += 1
                if bot["label"] == "publisher":
                    d1_query(
                        "UPDATE cine_private_stock_config SET publisher_bot_id=? "
                        "WHERE singleton=1 AND stock_chat_id=? AND owner_id=?",
                        [bot["id"], expected_stock, expected_owner],
                    )
            except (FloodWaitError, PeerFloodError):
                # Account safety: never work around Telegram's restriction.
                raise
            except Exception:
                failed += 1
                failed_labels.append(bot["label"])
        # Confirm that NO unexpected human or bot was granted membership.
        await verify_members(client, stock, expected_owner, candidates)
        print("CINEX_STOCK_BOTS_VERIFIED", "total", verified,
              "new_or_permissions_corrected", added,
              "failed", failed,
              "unknown_members", 0)
        if failed or invalid:
            print("CINEX_STOCK_BOTS_REQUIRING_REVIEW",
                  "invalid_labels", ",".join(invalid) or "none",
                  "failed_labels", ",".join(failed_labels) or "none")
            # Partial result is not silently presented as complete.
            raise RuntimeError("stock_bot_integration_partial")
        return {"verified": verified, "updated": added,
                "missing": len(absent), "failed": 0}
    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--pause", type=int, default=13)
    args = parser.parse_args()
    from scripts.check_personal_cooldown import seconds_remaining
    if seconds_remaining():
        print("CINEX_STOCK_BOTS_STOPPED_FOR_FLOODWAIT")
        return 75
    asyncio.run(attach(apply=args.apply, pause=args.pause))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # No tokens / private Telegram chat IDs in stdout or stderr.
        print("CINEX_STOCK_BOTS_ERROR", type(exc).__name__, file=sys.stderr)
        sys.exit(1)
