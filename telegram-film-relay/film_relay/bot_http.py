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
        url = "https://api.telegram.org/bot" + self._token + "/" + method
        try:
            response = requests.post(url, data=data or {}, files=files, timeout=(10, self._timeout))
            payload = response.json()
        except (requests.exceptions.RequestException, ValueError) as exc:
            raise TelegramBotHTTPError("Réseau Telegram indisponible (envoi incertain : pas de réessai automatique).") from exc
        if response.status_code == 429 or not payload.get("ok", False):
            info = payload.get("description", "Réponse Bot API rejetée")
            wait = (payload.get("parameters") or {}).get("retry_after")
            if wait is not None:
                raise TelegramBotHTTPError("Telegram demande une pause de " + str(wait) + " secondes pour " + method)
            raise TelegramBotHTTPError(method + " : " + str(info))
        return payload["result"]

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

    async def disconnect(self):
        # Aucun état d'authentification MTProto à libérer.
        return None
