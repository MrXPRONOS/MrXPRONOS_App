#!/usr/bin/env python3
"""Safety guard for Telegram's MAIN production channel @mrxpronosfr.

Uses the existing production video bot, never the test-channel bot.
Never prints credentials or Telegram API URLs containing a bot token.
"""
from __future__ import annotations

import requests

EXPECTED_USERNAME = "mrxpronosfr"


class ProductionChannelGuardError(RuntimeError):
    pass


def validate_production_channel(chat_id: str, bot_token: str,
                                request_get=requests.get) -> dict:
    chat_id = (chat_id or "").strip()
    bot_token = (bot_token or "").strip()
    if not chat_id or not bot_token:
        raise ProductionChannelGuardError("Canal ou bot de production manquant")

    def call(method: str, params: dict) -> dict:
        try:
            response = request_get(
                "https://api.telegram.org/bot" + bot_token + "/" + method,
                params=params, timeout=(8, 20))
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            raise ProductionChannelGuardError(
                "Impossible de vérifier la destination Telegram de production") from None
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise ProductionChannelGuardError("Vérification Telegram rejetée: " + method)
        result = payload.get("result")
        if not isinstance(result, dict):
            raise ProductionChannelGuardError("Réponse Telegram invalide")
        return result

    chat = call("getChat", {"chat_id": chat_id})
    username = str(chat.get("username") or "").lstrip("@").casefold()
    if chat.get("type") != "channel" or username != EXPECTED_USERNAME:
        raise ProductionChannelGuardError(
            "Destination interdite: canal principal @mrxpronosfr uniquement")

    me = call("getMe", {})
    if not isinstance(me.get("id"), int):
        raise ProductionChannelGuardError("Identité du bot de production inconnue")
    member = call("getChatMember", {
        "chat_id": chat["id"], "user_id": me["id"]})
    allowed = member.get("status") == "creator" or (
        member.get("status") == "administrator"
        and member.get("can_post_messages") is True)
    if not allowed:
        raise ProductionChannelGuardError(
            "Le bot de production ne peut pas publier sur @mrxpronosfr")
    return {"chat_id": chat["id"], "username": username, "can_post": True}
