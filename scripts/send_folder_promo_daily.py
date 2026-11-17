#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MR XPRONOS F: one image/caption/blue button per eligible Telegram channel/day.

The bot is verified before posting; channels are loaded from the secured
Supabase registry. Four explicitly excluded Mr XPRONOS channels are blocked
by BOTH immutable channel ID and username. Includes private channels.

Each (day, bot, channel) is reserved in Supabase before publishing so a retry
will not deliberately send the same ad twice to that destination. If transport
is ambiguous, delivery remains marked 'uncertain', never automatically retried.
No private channel titles, IDs or links are written to public GitHub logs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[1]
PHOTO = BASE / "assets/telegram/mrxpronos_f_folder_promo.jpg"
BOT_ID = 8586885516
BOT_USERNAME = "mrxpronos_canal_bot"
URL = "https://t.me/addlist/ZmW4vfwcrMAwNzJk"
CAPTION = (
    "🎬 <b>FILMS • SÉRIES • ANIMÉS 🍿</b>\n"
    "🔥 <b>TOUT DANS UN SEUL DOSSIER TELEGRAM !</b>\n"
    "📂 <i>Tes chaînes de divertissement réunies au même endroit.</i>\n"
    "👇 <b>AJOUTE MR XPRONOS F GRATUITEMENT !</b>"
)
KEYBOARD = {"inline_keyboard": [[{
    "text": "📥 AJOUTER LE DOSSIER",
    "url": URL,
    "style": "primary",
}]]}
# Identifiants publics confirmés via le registre Telegram au 17 novembre 2026.
EXCLUDED_ID_TO_HANDLE = {
    -1003919448551: "actufoot_mrxp",
    -1003902962214: "actucrypto_mrxp",
    -1001733080826: "mrxpronosfr",
    -1003741349066: "mr_xpronos_vip",
}
EXCLUDED_HANDLES = set(EXCLUDED_ID_TO_HANDLE.values())
REGISTERED_TOTAL = 28
EXPECTED_EXCLUDED = 4
EXPECTED_TARGETS = REGISTERED_TOTAL - EXPECTED_EXCLUDED
CAMPAIGN_PREFIX = "mrxp_folder_f_daily_v1_"
REGISTRY = "telegram_channel_registry"
RECEIPTS = "telegram_channel_broadcast_receipts"


def validate_static():
    if not PHOTO.is_file() or PHOTO.stat().st_size < 1024:
        raise RuntimeError("Affiche MR XPRONOS F absente.")
    with PHOTO.open("rb") as f:
        if f.read(3) != b"\xff\xd8\xff":
            raise RuntimeError("Image JPEG attendue.")
    if CAPTION.count("\n") != 3 or len(CAPTION) > 1024:
        raise RuntimeError("Légende Telegram invalide.")
    if len(EXCLUDED_ID_TO_HANDLE) != 4:
        raise RuntimeError("Quatre exclusions sont nécessaires.")
    button = KEYBOARD["inline_keyboard"][0][0]
    if button["style"] != "primary" or button["url"] != URL:
        raise RuntimeError("Bouton bleu/lien de dossier invalide.")
    print("DAILY_PROMO_STATIC_OK", "four_lines", "blue_button",
          "file_size", PHOTO.stat().st_size, "exclusions", EXPECTED_EXCLUDED)


class Storage:
    def __init__(self):
        base = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
        key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not base.startswith("https://") or not base.endswith(".supabase.co") or not key:
            raise RuntimeError("Configuration Supabase serveur indisponible.")
        self.base = base + "/rest/v1/"
        self.http = requests.Session()
        self.http.headers.update({
            "apikey": key,
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        })

    def select_targets(self):
        try:
            resp = self.http.get(
                self.base + REGISTRY,
                params={
                    "select": "bot_id,channel_id,title,username,is_private,bot_status,can_post_messages",
                    "bot_id": "eq." + str(BOT_ID),
                    "limit": "100",
                    "order": "channel_id.asc",
                },
                timeout=(10, 30),
            )
            if resp.status_code != 200:
                raise RuntimeError("Erreur lecture registre HTTP " + str(resp.status_code))
            rows = resp.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError("Lecture du registre impossible.") from None
        if not isinstance(rows, list) or len(rows) != REGISTERED_TOTAL:
            raise RuntimeError("Nombre de canaux enregistrés différent de 28 : envoi annulé.")
        all_ids = [r.get("channel_id") for r in rows]
        if len(set(all_ids)) != REGISTERED_TOTAL:
            raise RuntimeError("Doublons dans le registre : envoi annulé.")
        excluded_found = set()
        targets = []
        for row in rows:
            cid = row.get("channel_id")
            username = str(row.get("username") or "").lstrip("@").casefold()
            if row.get("bot_id") != BOT_ID or not isinstance(cid, int):
                raise RuntimeError("Registre invalide.")
            # Fail closed on mismatched excluded ID or username: no chance of
            # accidentally publishing into a renamed/reassigned excluded channel.
            if cid in EXCLUDED_ID_TO_HANDLE:
                if username != EXCLUDED_ID_TO_HANDLE[cid]:
                    raise RuntimeError("Identité d'un canal exclu modifiée : envoi annulé.")
                excluded_found.add(cid)
                continue
            if username in EXCLUDED_HANDLES:
                raise RuntimeError("Un canal exclu a changé d'identifiant.")
            if (row.get("bot_status") not in ("administrator", "creator")
                    or row.get("can_post_messages") is not True):
                raise RuntimeError("Registre avec droits de publication insuffisants.")
            targets.append(row)
        if excluded_found != set(EXCLUDED_ID_TO_HANDLE):
            raise RuntimeError("Exclusions incomplètes : envoi annulé.")
        if len(targets) != EXPECTED_TARGETS:
            raise RuntimeError("Nombre de destinataires inattendu : envoi annulé.")
        print("DESTINATIONS_SELECTED", len(targets), "EXCLUDED", len(excluded_found),
              "PRIVATE", sum(bool(x["is_private"]) for x in targets))
        return targets

    def reserve(self, campaign, chat_id):
        try:
            r = self.http.post(
                self.base + RECEIPTS,
                headers={"Prefer": "return=representation"},
                json={
                    "campaign_id": campaign,
                    "bot_id": BOT_ID,
                    "channel_id": chat_id,
                    "delivery_status": "reserved",
                },
                timeout=(10, 30),
            )
        except requests.RequestException:
            raise RuntimeError("Réservation Supabase incertaine.") from None
        if r.status_code == 409:
            return False
        if r.status_code != 201:
            raise RuntimeError("Réservation refusée HTTP " + str(r.status_code))
        try:
            entry = r.json()
        except ValueError:
            raise RuntimeError("Réservation non vérifiable.") from None
        if not isinstance(entry, list) or len(entry) != 1:
            raise RuntimeError("Réservation non vérifiable.")
        return True

    def mark(self, campaign, chat_id, status, message_id=None, error_kind=None):
        data = {"delivery_status": status}
        if message_id is not None:
            data["message_id"] = message_id
            data["sent_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        if error_kind:
            data["error_kind"] = error_kind[:80]
        try:
            r = self.http.patch(
                self.base + RECEIPTS,
                params={
                    "campaign_id": "eq." + campaign,
                    "bot_id": "eq." + str(BOT_ID),
                    "channel_id": "eq." + str(chat_id),
                },
                json=data,
                headers={"Prefer": "return=minimal"},
                timeout=(10, 30),
            )
        except requests.RequestException:
            return False
        return r.status_code in (200, 204)


class Telegram:
    def __init__(self, token):
        self.http = requests.Session()
        self.root = "https://api.telegram.org/bot" + token + "/"

    def call(self, method, *, payload=None, photo_chat_id=None):
        try:
            if photo_chat_id is None:
                resp = self.http.post(self.root + method, json=payload or {},
                                      timeout=(10, 25))
            else:
                with PHOTO.open("rb") as img:
                    resp = self.http.post(
                        self.root + method,
                        data={
                            "chat_id": str(photo_chat_id),
                            "caption": CAPTION,
                            "parse_mode": "HTML",
                            "reply_markup": json.dumps(KEYBOARD, ensure_ascii=False),
                            "protect_content": "false",
                        },
                        files={"photo": (PHOTO.name, img, "image/jpeg")},
                        timeout=(10, 45),
                    )
            result = resp.json()
        except (requests.RequestException, ValueError):
            # requests exceptions contain the secret in the bot URL.
            raise RuntimeError("telegram_transport_uncertain") from None
        if resp.status_code == 429:
            raise RuntimeError("telegram_rate_limited")
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise RuntimeError("telegram_refused_http_" + str(resp.status_code))
        return result.get("result")

    def verify_bot(self):
        me = self.call("getMe")
        if not isinstance(me, dict) or me.get("id") != BOT_ID or (
                str(me.get("username") or "").casefold() != BOT_USERNAME):
            raise RuntimeError("Le jeton ne correspond pas à @mrxpronos_canal_bot")
        print("BOT_IDENTITY_OK", "@" + BOT_USERNAME)

    def verify_access(self, chat_id):
        chat = self.call("getChat", payload={"chat_id": chat_id})
        member = self.call("getChatMember",
                           payload={"chat_id": chat_id, "user_id": BOT_ID})
        if not isinstance(chat, dict) or chat.get("type") != "channel" or chat.get("id") != chat_id:
            return False
        if not isinstance(member, dict):
            return False
        return (member.get("status") == "creator" or
                (member.get("status") == "administrator"
                 and member.get("can_post_messages") is True))


def run():
    validate_static()
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN manquant.")
    db = Storage()
    targets = db.select_targets()
    telegram = Telegram(token)
    telegram.verify_bot()

    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    campaign = CAMPAIGN_PREFIX + today
    print("DAILY_CAMPAIGN", campaign)
    results = {"sent": 0, "already_recorded": 0, "failed": 0,
               "uncertain": 0, "permission_missing": 0}
    # Neither private chat names nor private IDs are exposed in logs or summary.
    public_links = []

    for index, row in enumerate(targets, 1):
        chat_id = row["channel_id"]
        try:
            verified = telegram.verify_access(chat_id)
        except RuntimeError:
            verified = False
        if not verified:
            results["permission_missing"] += 1
            print("DESTINATION_PERMISSION_UNAVAILABLE", index)
            continue

        try:
            claimed = db.reserve(campaign, chat_id)
        except RuntimeError:
            results["uncertain"] += 1
            print("RESERVATION_UNCERTAIN", index)
            continue
        if not claimed:
            results["already_recorded"] += 1
            print("ALREADY_PUBLISHED_OR_RESERVED", index)
            continue
        try:
            msg = telegram.call("sendPhoto", photo_chat_id=chat_id)
            msg_id = msg.get("message_id") if isinstance(msg, dict) else None
            if not isinstance(msg_id, int):
                raise RuntimeError("telegram_missing_message_id")
        except RuntimeError as exc:
            reason = str(exc)
            status = "uncertain" if reason in (
                "telegram_transport_uncertain",
                "telegram_missing_message_id",
            ) else "failed"
            db.mark(campaign, chat_id, status, error_kind=reason)
            results[status] += 1
            print("DELIVERY_ERROR", index, status)
            continue

        confirmed = db.mark(campaign, chat_id, "sent", message_id=msg_id)
        results["sent"] += 1
        print("DELIVERY_CONFIRMED", index, "of", len(targets),
              "private" if row["is_private"] else "public",
              "receipt" if confirmed else "receipt_update_unconfirmed")
        if row.get("username"):
            public_links.append("https://t.me/" + row["username"] + "/" + str(msg_id))
        if index < len(targets):
            time.sleep(1.5)

    print("DAILY_CAMPAIGN_RESULT", json.dumps(results, ensure_ascii=False))
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as f:
            f.write("## Promotion quotidienne — dossier MR XPRONOS F\n\n")
            f.write("Date (Lomé, UTC) : " + today + "\n\n")
            f.write("Cibles : 24 | Exclues : 4\n\n")
            for key, value in results.items():
                f.write("- " + key + " : " + str(value) + "\n")
            f.write("\nLiens publics publiés :\n\n")
            for link in public_links:
                f.write("- " + link + "\n")
            f.write("\nAucun lien ni nom de canal privé n'a été exposé.\n")

    return 0 if results["failed"] == results["uncertain"] == results["permission_missing"] == 0 else 1


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--send", action="store_true")
    args = parser.parse_args()
    try:
        if args.check:
            validate_static()
            return 0
        return run()
    except RuntimeError as exc:
        print("::error::DAILY_CAMPAIGN_ABORTED", str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
