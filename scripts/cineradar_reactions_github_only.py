#!/usr/bin/env python3
"""CineRadar GitHub-only reaction dispatcher.

Persistent state: isolated AES-GCM encrypted GitHub file. No Cloudflare calls.
Telegram channel_post updates: getUpdates of an independent administrator bot.
The legacy SQL reaction planner operates on a local SQLite adapter only.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from scripts import telegram_reactions_github as reactions
from scripts.cineradar_reaction_store import (
    ReactionVault, LocalReactionDB, load, save,
)
from scripts.actu_foot_github_vault import VaultError


def allowed_channels(db, env):
    """Only explicitly configured or previously observed channel IDs."""
    ids = {str(row["chat_id"]) for row in db.query(
        "SELECT DISTINCT chat_id FROM channel_reaction_posts"
    )["results"]}
    configured = str(env.get("CINERADAR_REACTION_CHANNEL_IDS", "")).strip()
    if configured:
        ids.update(x.strip() for x in configured.split(",") if x.strip())
    return ids


def observe(db, env, cursor, transport=reactions._request_json):
    token = str(env.get("CINERADAR_REACTION_OBSERVER_TOKEN", "") or env.get("TELEGRAM_REACTION_BOT_03_TOKEN", "")).strip()
    if not token:
        raise RuntimeError("No dedicated GitHub reaction observer token configured")
    code, identity = reactions.telegram_call(token, "getMe", {}, transport)
    if code != 200 or not identity.get("ok") or not (identity.get("result") or {}).get("is_bot"):
        raise RuntimeError("GitHub reaction observer identity not verified")
    code, webhook = reactions.telegram_call(token, "getWebhookInfo", {}, transport)
    if code != 200 or not webhook.get("ok") or (webhook.get("result") or {}).get("url"):
        raise RuntimeError("Observer has an active webhook, cannot safely poll Telegram")
    allowed = allowed_channels(db, env)
    if not allowed:
        raise RuntimeError("No approved channel IDs present in imported snapshot")
    observer_id = (identity.get("result") or {}).get("id")
    for channel in sorted(allowed):
        code, result = reactions.telegram_call(token, "getChatMember", {
            "chat_id": channel, "user_id": observer_id,
        }, transport)
        role = (result.get("result") or {}).get("status")
        if code != 200 or result.get("ok") is not True or role not in ("administrator", "creator"):
            raise RuntimeError("GitHub observer lacks administrator access to a configured channel")
    params = {"limit": 100, "timeout": 0, "allowed_updates": ["channel_post"]}
    if cursor is not None:
        params["offset"] = int(cursor)
    code, payload = reactions.telegram_call(token, "getUpdates", params, transport)
    if code != 200 or payload.get("ok") is not True:
        raise RuntimeError("Telegram observer polling failed")
    new_cursor, inserted = cursor, 0
    for update in payload.get("result") or []:
        update_id = update.get("update_id")
        if not isinstance(update_id, int):
            continue
        post = update.get("channel_post") or {}
        chat = post.get("chat") or {}
        mid = post.get("message_id")
        chat_id = str(chat.get("id") or "")
        if (chat.get("type") == "channel" and chat_id in allowed
                and isinstance(mid, int) and mid > 0 and not post.get("is_automatic_forward")):
            album = str(post["media_group_id"]) if post.get("media_group_id") else None
            db.query("INSERT OR IGNORE INTO channel_reaction_posts"
                     "(chat_id,message_id,media_group_id) VALUES(?,?,?)",
                     (chat_id, mid, album))
            inserted += 1
        new_cursor = max(new_cursor or 0, update_id + 1)
    return new_cursor, inserted


def dispatch(db, env, transport=reactions._request_json):
    candidates = reactions.configured_tokens(env)
    extras = reactions.verify_bots(candidates, transport) if candidates else {}
    primaries = reactions.verify_primary_bots(env, transport) if (
        env.get("REACTIONS_GITHUB_PRIMARY", "").lower() == "true"
    ) else {}
    if not extras and not primaries:
        raise RuntimeError("No verified Telegram reaction bots")
    total = 0
    if primaries:
        reactions.prepare_primary_jobs(db)
        sent, _, _ = reactions.process_primary_jobs(db, primaries, transport)
        total += sent
    if extras:
        reactions.prepare_jobs(db, tuple(sorted(extras)))
        rows = reactions.due_jobs(db, tuple(sorted(extras)))
        updates = []
        for row in rows:
            slot = int(row["bot_slot"])
            emoji = reactions.reaction_for(int(row["post_seq"]), slot)
            if emoji != row["emoji"]:
                raise RuntimeError("Reaction parity mismatch")
            try:
                status, response = reactions.telegram_call(
                    extras[slot], "setMessageReaction", {
                        "chat_id": row["chat_id"], "message_id": int(row["message_id"]),
                        "reaction": [{"type": "emoji", "emoji": emoji}], "is_big": False,
                    }, transport,
                )
                failed = False
            except reactions.APIError:
                status, response, failed = 0, {}, True
            updates.append(reactions.make_update(row, status, response, failed))
        db.batch(updates)
        total += sum(1 for sql, _ in updates if "state='sent'" in sql)
    return total


def main(env=None):
    env = dict(os.environ if env is None else env)
    vault = ReactionVault()
    try:
        db, cursor, sha = load(vault)
    except Exception as exc:
        # Never create a blank state or replay historical posts after a failed import.
        print("REACTIONS_STATE_NOT_READY:", type(exc).__name__, file=sys.stderr)
        return 2
    before = db.connection.total_changes
    try:
        new_cursor, observed = observe(db, env, cursor)
        if new_cursor != cursor or db.connection.total_changes != before:
            sha = save(vault, db, new_cursor, sha)
            # The first commit must precede Telegram side effects. The GitHub
            # snapshot remains the sole source of truth on a later retry.
        after_observe = db.connection.total_changes
        delivered = dispatch(db, env)
        if db.connection.total_changes != after_observe:
            save(vault, db, new_cursor, sha)
        print(f"reaction_observed={observed} delivered={delivered} cursor_advanced={new_cursor != cursor}")
        return 0
    except Exception as exc:
        # Persisted observations remain recoverable; Telegram reactions are idempotent.
        print("REACTIONS_GITHUB_ONLY_ERROR:", type(exc).__name__, file=sys.stderr)
        return 1
    finally:
        db.connection.close()


if __name__ == "__main__":
    sys.exit(main())
