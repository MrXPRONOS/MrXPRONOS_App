"""Independent Telegram Bot API transport for CinéX Anime V2.

No user session or MTProto dependency. Publishing is gated by verified bot
permissions, an explicit user-authorized source allowlist and rights attestation.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import requests


class BotOperationError(RuntimeError):
    """Includes ambiguous network results: caller must not blindly retry."""


@dataclass(frozen=True)
class BotIdentity:
    id: int
    username: str


class AnimeBotTransport:
    def __init__(self, token: str, *, timeout: int = 45):
        if not token or ":" not in token:
            raise ValueError("Dedicated source bot token is required.")
        self._token = token
        self.timeout = timeout
        self._identity = None

    def _request(self, method: str, data=None):
        # Do not log token, remote URLs or message captions.
        try:
            response = requests.post(
                "https://api.telegram.org/bot" + self._token + "/" + method,
                data=data or {}, timeout=(10, self.timeout))
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise BotOperationError(
                "Bot API response uncertain: stop without retrying publication"
            ) from exc
        if not response.ok or payload.get("ok") is not True:
            extra = payload.get("parameters") or {}
            retry = extra.get("retry_after")
            if retry is not None:
                raise BotOperationError(f"Bot API rate limit: retry_after={int(retry)}")
            raise BotOperationError(
                f"Telegram rejected {method}: "
                + str(payload.get("description") or "unspecified error")[:180])
        return payload["result"]

    async def call(self, method: str, data=None):
        return await asyncio.to_thread(self._request, method, data)

    async def identity(self):
        if not self._identity:
            me = await self.call("getMe")
            self._identity = BotIdentity(int(me["id"]), me.get("username", ""))
        return self._identity

    async def assert_permissions(self, source_ids, private_id: str, public_id: str):
        me = await self.identity()
        for chat in [*source_ids, private_id, public_id]:
            status = await self.call(
                "getChatMember", {"chat_id": str(chat), "user_id": str(me.id)})
            role = status.get("status")
            if role not in ("creator", "administrator"):
                raise RuntimeError(
                    "Bot without channel administrator access: " + str(chat))
            if chat in (private_id, public_id) and not status.get(
                    "can_post_messages", role == "creator"):
                raise RuntimeError("Bot cannot post to destination: " + str(chat))
        return me

    async def assert_polling_available(self):
        response = await self.call("getWebhookInfo")
        if response.get("url"):
            raise RuntimeError(
                "Dedicated bot has an active webhook; getUpdates must not consume "
                "another system's channel messages.")
        return True

    async def get_updates(self, *, offset: int, limit: int = 100):
        return await self.call("getUpdates", {
            "offset": str(int(offset)), "limit": str(max(1, min(100, limit))),
            "timeout": "0", "allowed_updates": '["channel_post","edited_channel_post"]',
        })

    async def copy_message(self, destination: str, source: str, message_id: int,
                           *, caption: str = "", reply_markup=None):
        import json
        data = {
            "chat_id": str(destination), "from_chat_id": str(source),
            "message_id": str(int(message_id)),
        }
        if caption:
            data.update({"caption": caption, "parse_mode": "HTML"})
        if reply_markup:
            data["reply_markup"] = json.dumps(
                reply_markup, ensure_ascii=False)
        result = await self.call("copyMessage", data)
        return int(result["message_id"])

    async def send_message(self, destination: str, text: str, *, keyboard=None):
        import json
        data = {"chat_id": str(destination), "text": text,
                "parse_mode": "HTML", "disable_web_page_preview": "true"}
        if keyboard:
            data["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)
        result = await self.call("sendMessage", data)
        return int(result["message_id"])

    async def edit_message(self, destination: str, message_id: int, text: str):
        return await self.call("editMessageText", {
            "chat_id": str(destination), "message_id": str(int(message_id)),
            "text": text, "parse_mode": "HTML", "disable_web_page_preview": "true",
        })

    async def edit_buttons(self, destination: str, message_id: int, keyboard: dict):
        import json
        return await self.call("editMessageReplyMarkup", {
            "chat_id": str(destination), "message_id": str(int(message_id)),
            "reply_markup": json.dumps(keyboard, ensure_ascii=False),
        })

    async def send_animation(self, destination: str, file_id: str, *, caption: str):
        if not file_id:
            raise ValueError("No verified animation file ID supplied.")
        return await self.call("sendAnimation", {
            "chat_id": str(destination), "animation": file_id,
            "caption": caption[:900],
        })


def verify_anime_bot_guard(env=None):
    env = os.environ if env is None else env
    if env.get("CINEX_ANIME_BOT_ENABLE", "").casefold() != "true":
        raise RuntimeError("CINEX_ANIME_BOT_ENABLE=true required.")
    if env.get("ANIME_RIGHTS_ATTESTED", "").casefold() != "true":
        raise RuntimeError("ANIME_RIGHTS_ATTESTED=true required.")
    token = env.get("CINEX_ANIME_SOURCE_BOT_TOKEN", "").strip()
    if not token or ":" not in token:
        raise RuntimeError("A dedicated CINEX_ANIME_SOURCE_BOT_TOKEN is required.")
    return token
