#!/usr/bin/env python3
"""Inventaire CinéX Séries : accès bot UNIQUEMENT.

Source des canaux : GitHub Actions variable CINEX_SERIES_CHANNEL_IDS.
N'utilise jamais Telethon, TG_SESSION_STRING, getUpdates ou une session utilisateur.
La Bot API ne peut PAS parcourir rétrospectivement l'historique des messages.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CHANNEL_ID = re.compile(r"^-100[0-9]{6,}$")
SEPARATORS = re.compile(r"[\s,;]+")
MAX_CHANNELS = 50
REPORT = Path("cinex-series-bot-inventory.json")
RADAR_HEALTH_URL = "https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/health?telegram=1"


def validated_radar_identity(data: dict) -> int:
    """Accept only the ID actually verified by the deployed CineRadar Worker."""
    if data.get("service") != "cine-radar":
        raise ValueError("Le diagnostic ne vient pas de Ciné Radar")
    identity = data.get("botIdentity")
    if not isinstance(identity, dict) or identity.get("connected") is not True or identity.get("matchesExpected") is not True:
        raise ValueError("Le Worker n'a pas confirmé le bot officiel")
    if str(identity.get("username") or "").lower() != "cineradarfr_bot":
        raise ValueError("Nom du bot Ciné Radar incohérent")
    user_id = identity.get("id")
    if type(user_id) is not int or user_id <= 0 or user_id >= 2**53:
        raise ValueError("Identifiant public du bot Ciné Radar indisponible")
    return user_id


def identify_radar_bot(configured_token: str = "") -> int:
    """Use the real Radar bot only; never substitute GitHub's unrelated bot token.

    Optional dedicated token via CINEX_RADAR_BOT_TOKEN, otherwise get the
    *public bot user ID*, never its token, from Radar's existing Worker health.
    """
    if configured_token:
        try:
            identity = BotAPI(configured_token).call("getMe", {})
            if str(identity.get("username") or "").lower() == "cineradarfr_bot":
                user_id = identity.get("id")
                if type(user_id) is int and 0 < user_id < 2**53:
                    return user_id
            print("CINEX_RADAR_TOKEN_MISMATCH: jeton non officiel ignore; diagnostic public utilise")
        except (RuntimeError, ValueError):
            print("CINEX_RADAR_TOKEN_UNAVAILABLE: recours au diagnostic public")
    try:
        req = urllib.request.Request(
            RADAR_HEALTH_URL,
            headers={"Accept": "application/json", "Cache-Control": "no-cache"},
            method="GET")
        with urllib.request.urlopen(req, timeout=14) as response:
            payload = json.load(response)
        return validated_radar_identity(payload)
    except (urllib.error.URLError, TimeoutError, ValueError, TypeError) as error:
        raise RuntimeError(
            "Identité officielle Ciné Radar non vérifiable depuis le Worker. "
            "Vérifier /health?telegram=1 ou fournir le secret GitHub dédié "
            "CINEX_RADAR_BOT_TOKEN (ne pas utiliser TELEGRAM_BOT_TOKEN)."
        ) from None



def parse_channel_ids(raw: str) -> list[str]:
    """Espaces, retours ligne, virgules et points-virgules acceptés ; ordre conservé."""
    parts = [p for p in SEPARATORS.split((raw or "").strip()) if p]
    if len(parts) > MAX_CHANNELS:
        raise ValueError(f"Trop de canaux ({len(parts)}) : limite {MAX_CHANNELS}")
    unique = []
    for part in parts:
        if not CHANNEL_ID.fullmatch(part):
            raise ValueError(f"Identifiant de canal non valide : {part[:32]}")
        if part not in unique:
            unique.append(part)
    return unique


class BotAPI:
    def __init__(self, token: str):
        if not token or ":" not in token:
            raise ValueError("Jeton du bot de publication manquant")
        self._token = token

    def call(self, method: str, data: dict) -> dict:
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        request = urllib.request.Request(
            url, json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=17) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            # Ne jamais inclure l'URL d'appel : elle contient le jeton du bot.
            raise RuntimeError(f"{method}: HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError):
            raise RuntimeError(f"{method}: erreur réseau") from None
        if not payload.get("ok"):
            raise RuntimeError(f"{method}: Telegram {payload.get('error_code', 'error')}")
        return payload["result"]


def is_admin(member: dict) -> bool:
    return member.get("status") in ("creator", "administrator")


def identify_pinned_poster(chat: dict) -> int | None:
    pinned = chat.get("pinned_message") or {}
    if pinned.get("photo") and isinstance(pinned.get("message_id"), int):
        return pinned["message_id"]
    return None


def audit(ids: list[str], publication_bot: BotAPI, radar_bot: BotAPI | None, *, verified_radar_id: int | None = None) -> dict:
    publisher = publication_bot.call("getMe", {})
    radar_id = verified_radar_id
    if radar_bot and radar_id is None:
        identity = radar_bot.call("getMe", {})
        if str(identity.get("username", "")).lower() != "cineradarfr_bot":
            raise RuntimeError("Le bot Radar configuré ne correspond pas à @CineRadarFr_Bot")
        radar_id = identity.get("id")
    elif radar_id is None:
        # Compatibilité avec l'ancien audit hors connexion. En production,
        # verified_radar_id est fourni par le Worker officiel.
        try:
            radar_id = publication_bot.call("getChat", {"chat_id": "@CineRadarFr_Bot"}).get("id")
        except RuntimeError:
            pass

    entries = []
    for chat_id in ids:
        item = {
            "chat_id": chat_id, "title": None, "status": "error",
            "publisher_admin": False, "radar_admin": None,
            "pinned_poster_message_id": None,
            "message_history_readable": False,
        }
        try:
            chat = publication_bot.call("getChat", {"chat_id": chat_id})
            if str(chat.get("id")) != chat_id or chat.get("type") != "channel":
                raise RuntimeError("chat_id différent ou chat non-canal")
            item["title"] = str(chat.get("title") or "")[:140]
            item["pinned_poster_message_id"] = identify_pinned_poster(chat)
            role = publication_bot.call("getChatMember", {
                "chat_id": chat_id, "user_id": publisher["id"]})
            item["publisher_admin"] = is_admin(role)
            if radar_id:
                try:
                    radar_role = publication_bot.call("getChatMember", {
                        "chat_id": chat_id, "user_id": radar_id})
                    item["radar_admin"] = is_admin(radar_role)
                except RuntimeError:
                    item["radar_admin"] = None
            item["status"] = ("verified" if item["publisher_admin"]
                              and item["radar_admin"] is True
                              else "publisher_not_admin" if not item["publisher_admin"]
                              else "radar_not_admin" if item["radar_admin"] is False
                              else "radar_unverified")
        except RuntimeError as error:
            item["error"] = str(error)[:100]
        entries.append(item)
        print(f"SERIE_CANAL {chat_id}: {item['status']} | {item['title'] or '(inconnu)'}")

    counts = {name: sum(i["status"] == name for i in entries)
              for name in ("verified", "publisher_not_admin", "radar_not_admin",
                           "radar_unverified", "error")}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "GitHub variable CINEX_SERIES_CHANNEL_IDS",
        "mode": "bot_api_read_only",
        "total": len(entries), "counts": counts,
        "channels": entries,
        "notice": ("Les bots vérifient les canaux listés, mais ne peuvent pas feuilleter "
                   "les anciens messages. Seule une affiche épinglée renvoyée par getChat "
                   "peut être identifiée sans nouvel événement ou message_id fourni."),
    }


def main() -> int:
    try:
        ids = parse_channel_ids(os.getenv("CINEX_SERIES_CHANNEL_IDS", ""))
        if not ids:
            print("CONFIGURATION_REQUIRED: créer la variable GitHub CINEX_SERIES_CHANNEL_IDS")
            REPORT.write_text(json.dumps({
                "status": "configuration_required",
                "variable": "CINEX_SERIES_CHANNEL_IDS",
                "example": "-1001234567890 -1009876543210",
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return 0
        bot = BotAPI(os.getenv("CINEX_PUBLISH_BOT_TOKEN", "").strip())
        radar_id = identify_radar_bot(os.getenv("CINEX_RADAR_BOT_TOKEN", "").strip())
        report = audit(ids, bot, None, verified_radar_id=radar_id)
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
        print("INVENTORY_SUMMARY", json.dumps({
            "total": report["total"], "counts": report["counts"]}, ensure_ascii=False))
        return 0 if not report["counts"]["error"] else 1
    except (ValueError, RuntimeError) as error:
        print("CINEX_SERIES_AUDIT_ERROR:", str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
