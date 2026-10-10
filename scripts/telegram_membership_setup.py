#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import sys
from dataclasses import dataclass
from typing import Any

import requests

PROJECT_REF = "nhwafcpndlufzzxexikh"
DEFAULT_WEBHOOK_URL = (
    f"https://{PROJECT_REF}.supabase.co/functions/v1/telegram-membership"
)

LINK_PREFIX = "MX_ADHESION_"


@dataclass(frozen=True)
class Channel:
    key: str
    label: str
    chat_id: str
    description: str


def clean(value: str | None) -> str:
    return str(value or "").strip()


def bot_token() -> str:
    generic = clean(os.getenv("TELEGRAM_BOT_TOKEN"))
    football = clean(os.getenv("FOOTBALL_NEWS_BOT_TOKEN"))

    if generic and football and generic != football:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN et FOOTBALL_NEWS_BOT_TOKEN sont différents. "
            "Tu as indiqué que les trois canaux utilisent le même bot."
        )
    token = generic or football
    if not token:
        raise SystemExit(
            "Token absent: TELEGRAM_BOT_TOKEN ou FOOTBALL_NEWS_BOT_TOKEN"
        )
    return token


def configured_channels() -> list[Channel]:
    live = (
        clean(os.getenv("TELEGRAM_LIVE_CHAT_ID"))
        or clean(os.getenv("TELEGRAM_CHAT_ID_SECONDARY"))
    )
    coupons = (
        clean(os.getenv("TELEGRAM_COUPONS_CHAT_ID"))
        or clean(os.getenv("TELEGRAM_CHAT_ID"))
    )
    actu = clean(os.getenv("FOOTBALL_NEWS_CHAT_ID"))

    missing = []
    if not live:
        missing.append("TELEGRAM_LIVE_CHAT_ID (ou TELEGRAM_CHAT_ID_SECONDARY)")
    if not coupons:
        missing.append("TELEGRAM_COUPONS_CHAT_ID (ou TELEGRAM_CHAT_ID)")
    if not actu:
        missing.append("FOOTBALL_NEWS_CHAT_ID")
    if missing:
        raise SystemExit("Canaux manquants: " + ", ".join(missing))

    channels = [
        Channel(
            "LIVE",
            "Pronos Live",
            live,
            "signaux live, corners, tirs et autres opportunités en direct",
        ),
        Channel(
            "COUPONS",
            "Coupons du jour",
            coupons,
            "coupons et sélections Mr XPRONOS du jour",
        ),
        Channel(
            "ACTU_FOOT",
            "Actu Foot",
            actu,
            "flashs, résultats, statistiques et actualités football",
        ),
    ]

    raw = [c.chat_id.casefold() for c in channels]
    if len(set(raw)) != len(raw):
        raise SystemExit(
            "Les trois destinations Telegram doivent être trois canaux distincts."
        )
    return channels


class Telegram:
    def __init__(self, token: str):
        self.token = token
        self.base = f"https://api.telegram.org/bot{token}"
        self.session = requests.Session()

    def call(self, method: str, *, json_body: dict[str, Any] | None = None):
        response = self.session.post(
            f"{self.base}/{method}",
            json=json_body or {},
            timeout=(8, 45),
        )
        try:
            body = response.json()
        except ValueError:
            body = {"ok": False, "description": response.text[:500]}
        if not response.ok or body.get("ok") is not True:
            raise RuntimeError(
                f"Telegram {method}: HTTP {response.status_code} "
                f"{body.get('description') or body}"
            )
        return body.get("result")


def webhook_secret(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return "mx_" + digest[:48]


def public_channel_url(chat: dict[str, Any]) -> str:
    username = clean(chat.get("username"))
    return f"https://t.me/{username}" if username else ""


def validate_admin(tg: Telegram, bot_id: int, channel: Channel) -> dict[str, Any]:
    chat = tg.call("getChat", json_body={"chat_id": channel.chat_id})
    actual_id = chat.get("id")
    member = tg.call(
        "getChatMember",
        json_body={"chat_id": actual_id, "user_id": bot_id},
    )
    status = clean(member.get("status"))
    if status not in ("administrator", "creator"):
        raise RuntimeError(
            f"{channel.label}: le bot n'est pas administrateur (status={status!r})."
        )

    if status == "administrator":
        if member.get("can_invite_users") is not True:
            raise RuntimeError(
                f"{channel.label}: donne au bot le droit d'inviter/approuver des membres."
            )
        # Pour un canal, l'envoi et l'épinglage nécessitent des droits admin.
        if chat.get("type") == "channel" and member.get("can_post_messages") is not True:
            raise RuntimeError(
                f"{channel.label}: donne au bot le droit de publier des messages."
            )

    title = clean(chat.get("title")) or channel.label
    username = clean(chat.get("username"))
    print(
        "CHANNEL_OK",
        json.dumps(
            {
                "key": channel.key,
                "label": channel.label,
                "title": title,
                "chat_id": actual_id,
                "username": username,
                "bot_status": status,
            },
            ensure_ascii=False,
        ),
    )
    return chat


def create_request_link(
    tg: Telegram,
    channel: Channel,
    actual_chat_id: int | str,
) -> str:
    result = tg.call(
        "createChatInviteLink",
        json_body={
            "chat_id": actual_chat_id,
            "name": LINK_PREFIX + channel.key,
            "creates_join_request": True,
        },
    )
    link = clean(result.get("invite_link"))
    if not link:
        raise RuntimeError(f"{channel.label}: Telegram n'a pas retourné de lien.")
    print("MEMBERSHIP_LINK", channel.key, link)
    return link


def public_message(channel: Channel, request_link: str) -> str:
    label = html.escape(channel.label)
    description = html.escape(channel.description)
    return (
        f"👑 <b>{label.upper()} • MR XPRONOS</b>\n\n"
        "<i>Rejoins la communauté et reste connecté aux publications importantes.</i>\n\n"
        f"<blockquote>⚡ Retrouve nos {description}.</blockquote>\n\n"
        "<b>👉 Comment rejoindre ?</b>\n\n"
        "1️⃣ Appuie sur le bouton ci-dessous.\n"
        "2️⃣ Envoie ta demande d’adhésion.\n"
        "3️⃣ Après validation, <b>active la cloche 🔔</b>.\n\n"
        "<blockquote>🔥 Ne rate aucune nouvelle publication Mr XPRONOS.</blockquote>\n\n"
        "<i>18+ • Joue responsablement.</i>"
    )


def publish_and_pin(
    tg: Telegram,
    channel: Channel,
    actual_chat_id: int | str,
    request_link: str,
) -> int:
    message = tg.call(
        "sendMessage",
        json_body={
            "chat_id": actual_chat_id,
            "text": public_message(channel, request_link),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "disable_notification": True,
            "reply_markup": {
                "inline_keyboard": [[
                    {
                        "text": "✅ DEMANDER À REJOINDRE",
                        "url": request_link,
                    }
                ]]
            },
        },
    )
    message_id = int(message["message_id"])

    try:
        tg.call(
            "pinChatMessage",
            json_body={
                "chat_id": actual_chat_id,
                "message_id": message_id,
                "disable_notification": True,
            },
        )
        print("PIN_OK", channel.key, message_id)
    except RuntimeError as exc:
        # Le message reste publié et le diagnostic est explicite.
        print("PIN_WARNING", channel.key, str(exc))
    return message_id


def refresh_pinned_message(
    tg: Telegram,
    channel: Channel,
    actual_chat_id: int | str,
) -> int:
    chat = tg.call("getChat", json_body={"chat_id": actual_chat_id})
    pinned = chat.get("pinned_message") if isinstance(chat, dict) else None
    if not isinstance(pinned, dict):
        raise RuntimeError(f"{channel.label}: aucun message épinglé trouvé.")

    message_id = int(pinned["message_id"])
    markup = pinned.get("reply_markup") or {}
    buttons = markup.get("inline_keyboard") or []

    request_link = ""
    for row in buttons:
        if not isinstance(row, list):
            continue
        for button in row:
            if isinstance(button, dict) and clean(button.get("url")).startswith("https://t.me/"):
                request_link = clean(button.get("url"))
                break
        if request_link:
            break

    if not request_link:
        raise RuntimeError(
            f"{channel.label}: le message épinglé ne contient pas le lien d’adhésion."
        )

    tg.call(
        "editMessageText",
        json_body={
            "chat_id": actual_chat_id,
            "message_id": message_id,
            "text": public_message(channel, request_link),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": {
                "inline_keyboard": [[
                    {
                        "text": "✅ DEMANDER À REJOINDRE",
                        "url": request_link,
                    }
                ]]
            },
        },
    )
    print("PIN_REFRESH_OK", channel.key, message_id)
    return message_id


def setup_webhook(tg: Telegram, token: str, *, replace: bool = False) -> None:
    target = clean(os.getenv("TELEGRAM_MEMBERSHIP_WEBHOOK_URL")) or DEFAULT_WEBHOOK_URL
    current = tg.call("getWebhookInfo") or {}
    current_url = clean(current.get("url"))

    if current_url and current_url != target and not replace:
        raise RuntimeError(
            "Le bot possède déjà un webhook différent: "
            f"{current_url}. Relance avec --replace-webhook seulement après vérification."
        )

    tg.call(
        "setWebhook",
        json_body={
            "url": target,
            "secret_token": webhook_secret(token),
            "allowed_updates": ["chat_join_request"],
            "drop_pending_updates": False,
            "max_connections": 20,
        },
    )
    after = tg.call("getWebhookInfo") or {}
    if clean(after.get("url")) != target:
        raise RuntimeError("Le webhook Telegram n'a pas été installé correctement.")
    print(
        "WEBHOOK_OK",
        json.dumps(
            {
                "url": target,
                "pending_update_count": after.get("pending_update_count"),
                "allowed_updates": after.get("allowed_updates"),
            },
            ensure_ascii=False,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Configure les demandes d'adhésion des 3 canaux Mr XPRONOS"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Vérifie bot/canaux sans créer de lien, message ou webhook.",
    )
    parser.add_argument(
        "--replace-webhook",
        action="store_true",
        help="Autorise le remplacement d'un webhook existant différent.",
    )
    parser.add_argument(
        "--refresh-pinned-messages",
        action="store_true",
        help="Met à jour les messages déjà épinglés sans recréer de liens.",
    )
    args = parser.parse_args()

    token = bot_token()
    channels = configured_channels()
    tg = Telegram(token)
    me = tg.call("getMe") or {}
    bot_id = int(me["id"])
    print(
        "BOT_OK",
        json.dumps(
            {
                "id": bot_id,
                "username": me.get("username"),
            },
            ensure_ascii=False,
        ),
    )

    resolved: list[tuple[Channel, dict[str, Any]]] = []
    for channel in channels:
        resolved.append((channel, validate_admin(tg, bot_id, channel)))

    if args.check_only:
        print("MEMBERSHIP_CHECK_OK", len(resolved))
        return

    if args.refresh_pinned_messages:
        refreshed = []
        for channel, chat in resolved:
            refreshed.append({
                "key": channel.key,
                "message_id": refresh_pinned_message(
                    tg, channel, chat["id"]
                ),
            })
        print("MEMBERSHIP_PINNED_REFRESH_OK", json.dumps(refreshed, ensure_ascii=False))
        return

    report = []
    for channel, chat in resolved:
        actual_id = chat["id"]
        request_link = create_request_link(tg, channel, actual_id)
        message_id = publish_and_pin(
            tg,
            channel,
            actual_id,
            request_link,
        )
        report.append(
            {
                "key": channel.key,
                "label": channel.label,
                "chat_id": actual_id,
                "username": chat.get("username"),
                "public_url": public_channel_url(chat),
                "request_link": request_link,
                "pinned_message_id": message_id,
            }
        )

    setup_webhook(tg, token, replace=args.replace_webhook)
    print("MEMBERSHIP_SETUP_OK", json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
