#!/usr/bin/env python3
"""Fail-closed preflight for manual Telegram test sends to @predict_mrxp.

This script never posts content and never displays bot tokens.
"""
from __future__ import annotations

import json
import os
import sys

import requests

EXPECTED_USERNAME = "predict_mrxp"


class TestChannelGuardError(RuntimeError):
    """The requested destination is not the approved public test channel."""


def validate_test_channel(chat_id: str, bot_token: str, request_get=requests.get) -> dict:
    chat_id = (chat_id or "").strip()
    bot_token = (bot_token or "").strip()
    if not chat_id or not bot_token:
        raise TestChannelGuardError("Destination de test ou bot Telegram manquant")

    def call(method: str, params: dict) -> dict:
        try:
            response = request_get(
                "https://api.telegram.org/bot" + bot_token + "/" + method,
                params=params,
                timeout=(8, 20),
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            # Never include the request URL: it contains the Telegram bot token.
            raise TestChannelGuardError("Échec vérification Telegram: réseau/API") from None
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise TestChannelGuardError("Telegram n'a pas validé " + method)
        result = payload.get("result")
        if not isinstance(result, dict):
            raise TestChannelGuardError("Réponse Telegram invalide pour " + method)
        return result

    chat = call("getChat", {"chat_id": chat_id})
    username = str(chat.get("username") or "").lstrip("@").casefold()
    if chat.get("type") != "channel" or username != EXPECTED_USERNAME:
        raise TestChannelGuardError(
            "Destination interdite: seuls les tests vers @predict_mrxp sont autorisés"
        )

    me = call("getMe", {})
    bot_id = me.get("id")
    if not isinstance(bot_id, int):
        raise TestChannelGuardError("Identité du bot Telegram non vérifiable")

    member = call("getChatMember", {"chat_id": chat["id"], "user_id": bot_id})
    status = member.get("status")
    can_post = (status == "creator" or
                (status == "administrator" and member.get("can_post_messages") is True))
    if not can_post:
        raise TestChannelGuardError("Le bot n'a pas le droit de publier sur @predict_mrxp")

    return {
        "chat_id": chat["id"],
        "username": username,
        "bot_username": str(me.get("username") or ""),
        "can_post": True,
    }


def main() -> int:
    try:
        result = validate_test_channel(
            os.getenv("TELEGRAM_TEST_CHAT_ID", ""),
            os.getenv("TELEGRAM_TEST_GUARD_BOT_TOKEN", ""),
        )
    except TestChannelGuardError as exc:
        print("::error::TELEGRAM_TEST_GUARD_REJECTED " + str(exc))
        return 1

    print("TELEGRAM_TEST_ROUTE_VERIFIED " + json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
