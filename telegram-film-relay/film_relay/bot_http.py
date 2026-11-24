"""Transport Telegram Bot API pour les affiches publiques CineX.

Evite les authentifications MTProto répétées de bots (ImportBotAuthorizationRequest).
Les séances utilisateur Telethon restent utilisées pour la lecture et le transfert
natifs vers Torrent9.
"""
from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
from types import SimpleNamespace

import requests


def url_button(text: str, url: str, *, style: str = "primary"):
    """Bouton URL natif Bot API, indépendant des objets TL de Telethon."""
    if style not in {"primary", "success", "danger"}:
        raise ValueError("Style Telegram inconnu.")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Texte du bouton vide.")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise ValueError("Lien Telegram invalide.")
    return SimpleNamespace(text=text, url=url, style=style)


class TelegramBotHTTPError(RuntimeError):
    pass


class BotHTTPClient:
    """Adaptateur des seules méthodes de bot utilisées par les relais CineX."""

    def __init__(self, token: str, user_client, *, timeout: int = 90):
        if not token or ":" not in token:
            raise ValueError("Token du bot Telegram absent ou invalide.")
        self._token = token
        self._user = user_client
        self._timeout = timeout
        self._identity = None

    def _call_sync(self, method: str, data: dict | None = None, files: dict | None = None):
        """Retry transient *reads* once. Never retry a write with an uncertain receipt.

        getMe/getChatMember are idempotent Bot API queries. A sendPhoto,
        copyMessage, edit or delete timeout may have succeeded server-side,
        so repeating one would create duplicate or destructive operations.
        """
        import time

        url = "https://api.telegram.org/bot" + self._token + "/" + method
        readonly = method in {"getMe", "getChatMember"} and files is None
        attempts = 2 if readonly else 1
        for attempt in range(attempts):
            try:
                response = requests.post(
                    url, data=data or {}, files=files,
                    timeout=(10, min(self._timeout, 30) if readonly else self._timeout),
                )
                payload = response.json()
            except (requests.exceptions.RequestException, ValueError) as exc:
                if readonly and attempt == 0:
                    time.sleep(1)
                    continue
                detail = ("lecture en échec après deux tentatives sûres"
                          if readonly else
                          "envoi incertain : pas de réessai automatique")
                raise TelegramBotHTTPError(
                    "Réseau Telegram indisponible (" + detail + ").") from exc
            # Retry a transient gateway error only for reads. Never retry 429:
            # Telegram's retry_after must be respected by the owner cooldown.
            if readonly and attempt == 0 and response.status_code in (500, 502, 503, 504):
                time.sleep(1)
                continue
            if response.status_code == 429 or not payload.get("ok", False):
                info = payload.get("description", "Réponse Bot API rejetée")
                wait = (payload.get("parameters") or {}).get("retry_after")
                if wait is not None:
                    raise TelegramBotHTTPError(
                        "Telegram demande une pause de " + str(wait) +
                        " secondes pour " + method)
                raise TelegramBotHTTPError(method + " : " + str(info))
            return payload["result"]
        raise TelegramBotHTTPError(method + " : aucune réponse de lecture vérifiée")

    async def _call(self, method, data=None, files=None):
        return await asyncio.to_thread(self._call_sync, method, data, files)

    async def get_me(self):
        if self._identity is None:
            data = await self._call("getMe")
            self._identity = SimpleNamespace(id=data["id"], username=data.get("username", ""))
        return self._identity

    async def get_entity(self, entity):
        # L'identité Telegram exacte du canal reste celle de la session utilisateur.
        return await self._user.get_entity(entity)

    async def get_permissions(self, channel, identity):
        from telethon import utils
        cid = utils.get_peer_id(channel)
        data = await self._call("getChatMember", {
            "chat_id": str(cid), "user_id": str(identity.id)
        })
        status = data.get("status")
        return SimpleNamespace(
            is_creator=(status == "creator"),
            is_admin=(status == "administrator"),
            post_messages=bool(data.get("can_post_messages", False)),
            edit_messages=bool(data.get("can_edit_messages", False)),
        )

    @staticmethod
    def _keyboard(buttons):
        rows = []
        for row in buttons or []:
            built = []
            for button in row:
                # Telethon Button.url(...) enveloppe un KeyboardButtonUrl dans .button
                underlying = getattr(button, "button", button)
                url = getattr(underlying, "url", None)
                text = getattr(underlying, "text", None)
                if not url or not text:
                    raise ValueError("Un bouton de publication doit avoir un texte et une URL.")
                payload = {"text": str(text), "url": str(url)}
                style = getattr(underlying, "style", getattr(button, "style", None))
                if style in ("primary", "success", "danger"):
                    payload["style"] = style
                built.append(payload)
            if built:
                rows.append(built)
        return {"inline_keyboard": rows} if rows else None

    async def send_file(self, channel, file, *, caption="", buttons=None,
                        parse_mode=None, force_document=False, **kwargs):
        from telethon import utils
        if force_document:
            raise ValueError("Ce transport n'autorise que les affiches photo.")
        if isinstance(file, (str, Path)):
            path = Path(file)
            raw, name = path.read_bytes(), path.name
        elif isinstance(file, io.BytesIO):
            raw, name = file.getvalue(), (getattr(file, "name", None) or "cinex.jpg")
        elif isinstance(file, bytes):
            raw, name = file, "cinex.jpg"
        else:
            raise TypeError("Format de photo non pris en charge : " + type(file).__name__)
        if not raw:
            raise ValueError("Image vide : publication interdite.")
        mime = "image/png" if raw[:8] == bytes.fromhex("89504e470d0a1a0a") else "image/jpeg"
        data = {"chat_id": str(utils.get_peer_id(channel)), "caption": str(caption)}
        if parse_mode and str(parse_mode).lower() == "html":
            data["parse_mode"] = "HTML"
        keyboard = self._keyboard(buttons)
        if keyboard:
            data["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)
        result = await self._call("sendPhoto", data, {"photo": (str(name), raw, mime)})
        return SimpleNamespace(id=int(result["message_id"]))

    async def send_message(self, channel, message, *, buttons=None, parse_mode=None, **kwargs):
        from telethon import utils
        data = {"chat_id": str(utils.get_peer_id(channel)), "text": str(message)}
        if parse_mode and str(parse_mode).lower() == "html":
            data["parse_mode"] = "HTML"
        keyboard = self._keyboard(buttons)
        if keyboard:
            data["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)
        result = await self._call("sendMessage", data)
        return SimpleNamespace(id=int(result["message_id"]))

    async def copy_message(self, destination, source, message_id: int,
                           *, caption: str = "", parse_mode=None, buttons=None):
        """Bot API server-side copy from an authorized source channel.

        The bot must be a member/admin with sufficient access to both chats.
        It cannot copy protected messages or read arbitrary channel histories.
        """
        from telethon import utils
        data = {
            "chat_id": str(utils.get_peer_id(destination)),
            "from_chat_id": str(utils.get_peer_id(source)),
            "message_id": str(int(message_id)),
        }
        if caption:
            data["caption"] = str(caption)
        if parse_mode and str(parse_mode).lower() == "html":
            data["parse_mode"] = "HTML"
        keyboard = self._keyboard(buttons)
        if keyboard:
            data["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)
        result = await self._call("copyMessage", data)
        return SimpleNamespace(id=int(result["message_id"]))

    async def edit_photo_caption(self, channel, message_id: int, *,
                                 caption: str, buttons, parse_mode=None):
        """Edit an EXISTING channel photo and its buttons, without reposting.

        If Telegram refuses to edit a message published by a different bot or
        channel administrator, propagate the error. The caller must NOT clone
        the photo or delete the associated video in that case.
        """
        from telethon import utils
        if not isinstance(caption, str):
            raise TypeError("Description d'affiche invalide")
        data = {"chat_id": str(utils.get_peer_id(channel)),
                "message_id": str(int(message_id)),
                "caption": caption}
        if parse_mode and str(parse_mode).lower() == "html":
            data["parse_mode"] = "HTML"
        markup = self._keyboard(buttons)
        data["reply_markup"] = json.dumps(markup or {"inline_keyboard": []},
                                           ensure_ascii=False)
        try:
            return await self._call("editMessageCaption", data)
        except TelegramBotHTTPError as exc:
            if "message is not modified" in str(exc).casefold():
                return False
            raise

    async def edit_reply_markup(self, channel, message_id: int, *, buttons):
        """Mettre à jour les saisons sans publier une nouvelle affiche publique."""
        from telethon import utils
        data = {"chat_id": str(utils.get_peer_id(channel)),
                "message_id": str(int(message_id))}
        keyboard = self._keyboard(buttons)
        data["reply_markup"] = json.dumps(keyboard or {"inline_keyboard": []},
                                          ensure_ascii=False)
        try:
            return await self._call("editMessageReplyMarkup", data)
        except TelegramBotHTTPError as exc:
            if "message is not modified" in str(exc).casefold():
                return False  # Catalogue already carries these exact buttons.
            raise

    async def delete_message(self, channel, message_id: int):
        """Delete a channel message via Bot API when permitted (<48h rule)."""
        from telethon import utils
        return await self._call("deleteMessage", {
            "chat_id": str(utils.get_peer_id(channel)),
            "message_id": str(int(message_id)),
        })

    async def pin_message(self, channel, message_id: int, *, silent: bool = True):
        """Pin a verified channel post, without notifying subscribers."""
        from telethon import utils
        return await self._call("pinChatMessage", {
            "chat_id": str(utils.get_peer_id(channel)),
            "message_id": str(int(message_id)),
            "disable_notification": "true" if silent else "false",
        })

    async def unpin_message(self, channel, message_id: int):
        """Unpin only the exact previously curated public message."""
        from telethon import utils
        return await self._call("unpinChatMessage", {
            "chat_id": str(utils.get_peer_id(channel)),
            "message_id": str(int(message_id)),
        })

    async def disconnect(self):
        # Aucun état d'authentification MTProto à libérer.
        return None
