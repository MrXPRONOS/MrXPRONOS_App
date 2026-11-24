"""Read-only diagnostics for Telegram routes. NEVER send/copy/forward messages.

This command checks existing credentials and admin membership using getMe,
getChat and getChatMember; no Telegram user session, Supabase write RPC,
Git state mutation, or publication API is reachable from this script.
All private identifiers and tokens are omitted from output.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "formation-relay"))

from relay import Bot, CATS, channel_ref, read_config_json
from crypto import news_multichannel_v1 as multi
from crypto import production_seed_v1 as premium


def safe_reason(exc):
    """Only the formation Bot wrapper supplies sanitized Telegram descriptions."""
    msg = str(exc)
    if isinstance(exc, RuntimeError) and msg.startswith("Bot API "):
        return msg
    return type(exc).__name__


def public_bot_alias(value):
    """Only print syntactically valid public bot handles; never raw API text."""
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", value):
        return "@" + value
    return "unknown"


def audit_formation():
    print("FORMATION_ROUTE_AUDIT_START", flush=True)
    try:
        destinations = read_config_json("FORMATION_DESTINATIONS_JSON", dict)
        if set(destinations) != set(CATS) | {"general"}:
            raise ValueError("unexpected destinations")
        stage = channel_ref(os.environ["FORMATION_STAGE_CHAT"])
        if not isinstance(stage, int):
            raise ValueError("stage must be numeric")
        bot = Bot(os.environ.get("FORMATION_BOT_TOKEN", ""))
        bot_user = bot.call("getMe", context="bot identity")
        bot_id = bot_user["id"]
        if not isinstance(bot_id, int):
            raise ValueError("invalid bot identity")
        # The bot username is public; private channel references stay hidden.
        print("FORMATION_BOT_AUTH_OK", "bot=" + public_bot_alias(bot_user.get("username")), flush=True)
    except (ValueError, KeyError, TypeError, RuntimeError) as exc:
        print("FORMATION_ROUTE_AUDIT_CONFIG_FAIL", safe_reason(exc), flush=True)
        return False

    checks = [(cat, destinations[cat]) for cat in ("general", *CATS)]
    checks.append(("stage", stage))
    ok = True
    for category, raw_chat in checks:
        operation = "config"
        try:
            chat = channel_ref(raw_chat)
            operation = "getChat"
            info = bot.call("getChat", context=category, chat_id=chat)
            is_public = bool(info.get("username") or info.get("active_usernames"))
            if info.get("type") != "channel" or is_public != (category == "general"):
                raise ValueError("unexpected channel visibility")
            if category == "stage" and (info.get("has_protected_content") or info.get("id") != stage):
                raise ValueError("unexpected staging channel identity/settings")
            operation = "getChatMember"
            member = bot.call("getChatMember", context=category, chat_id=info["id"], user_id=bot_id)
            if member.get("status") not in ("creator", "administrator"):
                raise ValueError("bot is not a channel administrator")
            if (category != "stage" and member.get("status") != "creator"
                    and member.get("can_post_messages") is not True):
                raise ValueError("bot cannot post")
            print("FORMATION_ROUTE_OK", "category=" + category, flush=True)
        except (ValueError, KeyError, TypeError, RuntimeError) as exc:
            ok = False
            print("FORMATION_ROUTE_FAIL", "category=" + category,
                  "operation=" + operation, "reason=" + safe_reason(exc), flush=True)
    return ok


def audit_premium():
    print("CRYPTO_PREMIUM_ROUTE_AUDIT_START", flush=True)
    # Use read-only getMe; publish methods are intentionally absent.
    for index, token in enumerate(premium.TOKEN_CANDIDATES, start=1):
        try:
            bot = multi.Telegram(token=token).get("getMe")
            alias = public_bot_alias(bot.get("username"))
        except (RuntimeError, ValueError, TypeError, KeyError):
            alias = "unknown"
        print("CRYPTO_PREMIUM_BOT_CANDIDATE",
              "index=" + str(index), "bot=" + alias, flush=True)
    try:
        premium.verify_production_route()
    except (RuntimeError, KeyError, TypeError, ValueError) as exc:
        print("CRYPTO_PREMIUM_ROUTE_AUDIT_FAIL", "reason=" + type(exc).__name__, flush=True)
        return False
    print("CRYPTO_PREMIUM_ROUTE_AUDIT_OK", flush=True)
    return True


def audit_multichannel():
    print("CRYPTO_MULTICHANNEL_ROUTE_AUDIT_START", flush=True)
    try:
        targets = multi.Supabase().targets()
        targets = [t for t in targets
                   if str(t.get("chat_id", "")).lower() != multi.FASTDEAL_USERNAME]
        if not targets:
            print("CRYPTO_MULTICHANNEL_NO_ACTIVE_TARGETS", flush=True)
            return True
        client = multi.Telegram()
        bot_id = client.assert_correct_bot(targets)
    except (RuntimeError, KeyError, TypeError, ValueError) as exc:
        print("CRYPTO_MULTICHANNEL_ROUTE_AUDIT_SETUP_FAIL",
              "reason=" + type(exc).__name__, flush=True)
        return False

    print("CRYPTO_MULTICHANNEL_BOT_AUTH_OK", "target_count=" + str(len(targets)), flush=True)
    ok = True
    # Each target is checked independently. Never print its ID/username.
    for i, target in enumerate(targets, start=1):
        try:
            client.verify_destination(target, bot_id)
            print("CRYPTO_MULTICHANNEL_TARGET_OK", "index=" + str(i), flush=True)
        except (RuntimeError, KeyError, TypeError, ValueError) as exc:
            ok = False
            print("CRYPTO_MULTICHANNEL_TARGET_FAIL", "index=" + str(i),
                  "reason=" + type(exc).__name__, flush=True)

    legacy_chat = (os.environ.get("ACTU_CRYPTO_CHAT_ID") or "").strip()
    if legacy_chat:
        try:
            info = client.get("getChat", {"chat_id": legacy_chat})
            if info.get("type") != "channel" or not isinstance(info.get("id"), int):
                raise ValueError("not a channel")
            print("CRYPTO_LEGACY_ROUTE_OK", flush=True)
        except (RuntimeError, KeyError, TypeError, ValueError) as exc:
            ok = False
            print("CRYPTO_LEGACY_ROUTE_FAIL",
                  "operation=getChat", "reason=" + type(exc).__name__, flush=True)
    else:
        print("CRYPTO_LEGACY_ROUTE_NOT_CONFIGURED", flush=True)

    return ok


def main():
    results = {
        "formation": audit_formation(),
        "premium": audit_premium(),
        "multichannel": audit_multichannel(),
    }
    print("TELEGRAM_READONLY_ROUTE_AUDIT",
          " ".join(k + "=" + ("OK" if v else "FAILED") for k, v in results.items()),
          flush=True)
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
