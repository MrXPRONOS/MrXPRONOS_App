#!/usr/bin/env python3
"""Audit READ-ONLY des canaux où @mrxpronos_canal_bot est administrateur.

Sources : canaux déjà configurés dans GitHub Secrets et canaux visibles par
la session Telegram personnelle, si elle est disponible.

IMPORTANT : Telegram Bot API ne fournit pas de méthode « list my channels ».
L'audit ne revendique donc jamais l'exhaustivité sur les canaux inconnus de ces
sources. Aucun jeton, session, invitation privée ou identifiant de canal privé
n'est imprimé dans les logs de ce dépôt GitHub public.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections import OrderedDict
from typing import Any

import requests

TARGET_USERNAME = "mrxpronos_canal_bot"
BOT_SECRET_NAMES = (
    "MRXPRONOS_CANAL_BOT_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "FOOTBALL_NEWS_BOT_TOKEN",
    "EDITORIAL_TELEGRAM_BOT_TOKEN",
    "PARTNERSHIP_BOT_TOKEN",
    "CINEX_BOT_TOKEN",
)
CHANNEL_SECRET_NAMES = (
    "TELEGRAM_TEST_CHAT_ID",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_CHAT_ID_SECONDARY",
    "TELEGRAM_LIVE_CHAT_ID",
    "TELEGRAM_COUPONS_CHAT_ID",
    "FOOTBALL_NEWS_CHAT_ID",
    "EDITORIAL_TELEGRAM_CHAT_ID",
    "PARTNERSHIP_CHAT_ID",
    "CINEX_CHANNEL_CHAT_ID",
    "CINEX_FILMS_CHAT_ID",
    "CINEX_SERIES_CHAT_ID",
)
PUBLIC_HANDLES = ("@predict_mrxp", "@mrxpronosfr", "@mr_xpronos")
REQUEST_TIMEOUT = (8, 20)


class Telegram:
    def __init__(self, token: str):
        self.token = token
        self.http = requests.Session()

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict:
        for attempt in range(2):
            try:
                response = self.http.get(
                    "https://api.telegram.org/bot" + self.token + "/" + method,
                    params=params or {},
                    timeout=REQUEST_TIMEOUT,
                )
                body = response.json()
            except (requests.RequestException, ValueError):
                # Le libellé de l'exception HTTP peut contenir le token !
                raise RuntimeError("telegram_network_error") from None
            if response.status_code == 429 and attempt == 0:
                delay = min(15, max(1, int((body.get("parameters") or {}).get("retry_after", 2))))
                time.sleep(delay)
                continue
            if not isinstance(body, dict) or body.get("ok") is not True:
                # Ne pas révéler un éventuel token dans la description renvoyée.
                raise RuntimeError("telegram_error_http_" + str(response.status_code))
            result = body.get("result")
            if not isinstance(result, dict):
                raise RuntimeError("telegram_invalid_result")
            return result
        raise RuntimeError("telegram_rate_limited")


def find_exact_bot() -> tuple[Telegram | None, dict, list[str]]:
    tested: set[str] = set()
    matches: list[tuple[str, Telegram, dict]] = []
    detected: list[str] = []
    for secret in BOT_SECRET_NAMES:
        token = os.getenv(secret, "").strip()
        if not token or token in tested:
            continue
        tested.add(token)
        api = Telegram(token)
        try:
            me = api.call("getMe")
        except RuntimeError as exc:
            print("TOKEN_CHECK_UNAVAILABLE", secret, str(exc))
            continue
        username = str(me.get("username") or "").casefold().lstrip("@")
        detected.append(secret + " -> @" + username)
        if me.get("is_bot") is True and username == TARGET_USERNAME:
            matches.append((secret, api, me))

    print("BOT_SECRETS_VERIFIED", len(tested))
    # Identités des autres bots = publiques mais sans nécessité de les afficher.
    print("MATCHING_BOT_TOKEN_VARIABLES", [x[0] for x in matches])
    if not matches:
        print("BOT_IDENTITY_NOT_FOUND: aucun jeton configuré ne correspond à @"
              + TARGET_USERNAME)
        return None, {}, detected
    return matches[0][1], matches[0][2], detected


def configured_candidates() -> tuple[OrderedDict, list[str]]:
    candidates: OrderedDict[str, dict] = OrderedDict()
    sources: list[str] = []

    def put(chat_id: str, source: str):
        key = chat_id.strip().casefold()
        if not key:
            return
        if key not in candidates:
            candidates[key] = {"chat_id": chat_id.strip(), "sources": [source]}
        elif source not in candidates[key]["sources"]:
            candidates[key]["sources"].append(source)

    for name in CHANNEL_SECRET_NAMES:
        value = os.getenv(name, "").strip()
        if not value:
            continue
        sources.append(name)
        put(value, name)
    for handle in PUBLIC_HANDLES:
        put(handle, "repo_public_handle")
    return candidates, sources


async def telethon_candidates() -> tuple[list[dict], str]:
    api_id = os.getenv("TG_API_ID", "").strip()
    api_hash = os.getenv("TG_API_HASH", "").strip()
    session = (
        os.getenv("TG_SESSION_STRING", "").strip()
        or os.getenv("TG_STRING_SESSION", "").strip()
        or os.getenv("TG_STREAM_SESSION", "").strip()
    )
    if not all((api_id, api_hash, session)):
        return [], "personal_session_unavailable"

    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        from telethon.tl.types import Channel
    except ImportError:
        return [], "telethon_not_installed"

    items = []
    client = TelegramClient(StringSession(session), int(api_id), api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return [], "personal_session_not_authorized"
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            # Pas de groupes / supergroupes (megagroup); seulement canaux de diffusion.
            if isinstance(entity, Channel) and bool(getattr(entity, "broadcast", False)):
                items.append({
                    "chat_id": "-100" + str(entity.id),
                    "title": str(getattr(entity, "title", "") or ""),
                    "username": str(getattr(entity, "username", "") or ""),
                })
        return items, "complete_personal_dialog_scan"
    except Exception as exc:
        # Ne pas faire fuiter de sessions ni de références privées.
        return items, "personal_session_scan_failed_" + type(exc).__name__
    finally:
        await client.disconnect()


def get_membership(api: Telegram, bot_id: int, chat_id: str) -> dict | None:
    try:
        return api.call("getChatMember", {"chat_id": chat_id, "user_id": bot_id})
    except RuntimeError:
        return None


def main():
    api, bot, _ = find_exact_bot()
    if api is None:
        print("AUDIT_INCOMPLETE_UNVERIFIED_BOT_IDENTITY")
        return 2
    bot_id = bot.get("id")
    if not isinstance(bot_id, int):
        print("AUDIT_INCOMPLETE_INVALID_BOT_ID")
        return 2
    print("EXACT_BOT_VERIFIED", "@" + TARGET_USERNAME, "id", bot_id)

    candidates, used_secrets = configured_candidates()
    dialogs, source_status = asyncio.run(telethon_candidates())
    print("PERSONAL_SCAN", source_status, "broadcast_channels", len(dialogs))
    for channel in dialogs:
        key = channel["chat_id"].lower()
        if key not in candidates:
            candidates[key] = {
                "chat_id": channel["chat_id"],
                "sources": ["personal_dialogs"],
                "title": channel["title"],
                "username": channel["username"],
            }
        elif "personal_dialogs" not in candidates[key]["sources"]:
            candidates[key]["sources"].append("personal_dialogs")

    # Possible que le même canal soit identifié par @username et -100id.
    # Dédoublonner les confirmations par ID réel Telegram.
    confirmed: dict[int, dict] = {}
    checked = 0
    unavailable = 0
    for entry in candidates.values():
        checked += 1
        membership = get_membership(api, bot_id, entry["chat_id"])
        if membership is None:
            unavailable += 1
            continue
        status = membership.get("status")
        if status not in ("administrator", "creator"):
            continue

        try:
            chat = api.call("getChat", {"chat_id": entry["chat_id"]})
        except RuntimeError:
            unavailable += 1
            continue
        if chat.get("type") != "channel" or not isinstance(chat.get("id"), int):
            continue
        channel_id = chat["id"]
        username = str(chat.get("username") or "").lstrip("@")
        is_public = bool(re.fullmatch(r"[a-zA-Z0-9_]{5,32}", username))
        can_post = status == "creator" or membership.get("can_post_messages") is True
        info = {
            "title": str(chat.get("title") or ""),
            "username": "@" + username if is_public else None,
            "url": "https://t.me/" + username if is_public else None,
            "bot_status": status,
            "can_post_messages": bool(can_post),
            "public": is_public,
        }
        confirmed[channel_id] = info

    public_channels = sorted((c for c in confirmed.values() if c["public"]),
                             key=lambda c: c["username"].casefold())
    private_count = sum(not c["public"] for c in confirmed.values())
    writable = sum(bool(c["can_post_messages"]) for c in confirmed.values())

    print("CHANNEL_AUDIT_JSON", json.dumps({
        "bot": "@" + TARGET_USERNAME,
        "candidate_channels_checked": checked,
        "candidate_checks_unavailable": unavailable,
        "telegram_session_status": source_status,
        "configured_secret_sources": used_secrets,
        "confirmed_admin_channels": len(confirmed),
        "confirmed_can_publish": writable,
        "confirmed_public_count": len(public_channels),
        "confirmed_private_count_not_disclosed": private_count,
        "public_channels": public_channels,
        "limitation": (
            "Only discovered/configured channels were checked. Telegram does not "
            "provide a Bot API endpoint to enumerate every channel the bot administers."
        ),
    }, ensure_ascii=False))

    with_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if with_summary:
        from pathlib import Path
        rows = [
            "## Audit administrateur @" + TARGET_USERNAME,
            "",
            "**Canaux confirmés dans le périmètre testé :** " + str(len(confirmed)),
            "",
            "**Canaux publics :** " + str(len(public_channels))
            + " | **Canaux privés :** " + str(private_count)
            + " (noms/liens non publiés dans les logs publics)",
            "",
            "| Canal public | Username | Lien | Peut publier ? |",
            "|---|---|---|---|",
        ]
        for item in public_channels:
            rows.append(
                "| " + item["title"].replace("|", "/")
                + " | " + item["username"]
                + " | " + item["url"]
                + " | " + ("Oui" if item["can_post_messages"] else "Non") + " |"
            )
        rows.extend([
            "",
            "Périmètre : canaux configurés et canaux visibles par la session Telegram.",
            "Cette liste ne prouve pas l'absence de canaux inconnus de ces sources.",
            "Aucune publication n'a été envoyée.",
        ])
        Path(with_summary).open("a", encoding="utf-8").write("\n".join(rows) + "\n")

    if source_status != "complete_personal_dialog_scan":
        print("WARNING_PARTIAL_ENUMERATION", source_status)
    print("AUDIT_COMPLETED_READ_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
