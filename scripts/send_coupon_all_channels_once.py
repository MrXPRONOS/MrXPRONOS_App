#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ONE-TIME approved campaign to all 28 verified @mrxpronos_canal_bot channels.

Runs only with explicit --send. Uses a private Supabase registry and one-shot
delivery claims. A claim is reserved BEFORE contacting Telegram, so rerunning
the workflow never deliberately republishes the same campaign to a channel.
It does NOT permanently enable broadcasting and does NOT expose private
channel IDs, titles, or invite links in public GitHub logs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from html import escape
from pathlib import Path

import requests

BOT_USERNAME = "mrxpronos_canal_bot"
BOT_ID = 8586885516
CAMPAIGN_ID = "mrxp_coupon_free_proof_20261117_v1"
EXPECTED_CHANNELS = 28
ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "assets/telegram/promo_coupon_2026-10-25.jpg"
CHANNEL_URL = "https://t.me/mrxpronosfr"
MESSAGE_LINES = (
    "💸 COUPONS PAYANTS ? STOP !",
    "✅ COUPONS GRATUITS ICI.",
    "📲 REJOINS LE CANAL TELEGRAM 👇",
    "🔞 18+ • Risque de perte.",
)
MESSAGE = "\n".join(MESSAGE_LINES)
HTML_MESSAGE = "\n".join((
    "<b>" + escape(MESSAGE_LINES[0]) + "</b>",
    "<b>" + escape(MESSAGE_LINES[1]) + "</b>",
    "<b>" + escape(MESSAGE_LINES[2]) + "</b>",
    "<i>" + escape(MESSAGE_LINES[3]) + "</i>",
))
KEYBOARD = {"inline_keyboard": [[{
    "text": "📲 REJOINDRE LE CANAL GRATUIT",
    "url": CHANNEL_URL,
    "style": "primary",
}]]}
REGISTRY = "telegram_channel_registry"
RECEIPTS = "telegram_channel_broadcast_receipts"


def validate_static():
    if len(MESSAGE_LINES) != 4:
        raise RuntimeError("La légende doit comporter exactement quatre lignes.")
    if "\n" in MESSAGE_LINES[0]:
        raise RuntimeError("Ligne de légende invalide.")
    if not IMAGE.is_file() or IMAGE.stat().st_size < 1024:
        raise RuntimeError("Image du coupon introuvable.")
    with IMAGE.open("rb") as f:
        if f.read(3) != b"\xff\xd8\xff":
            raise RuntimeError("Image attendue au format JPEG.")
    assert KEYBOARD["inline_keyboard"][0][0]["url"] == CHANNEL_URL
    assert KEYBOARD["inline_keyboard"][0][0]["style"] == "primary"
    print("CAMPAIGN_VALIDATION_OK", CAMPAIGN_ID, "4_lignes", "image_ok", "bouton_primary")


class Supabase:
    def __init__(self):
        base = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
        key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not base.startswith("https://") or not base.endswith(".supabase.co") or not key:
            raise RuntimeError("Supabase serveur non configuré")
        self.endpoint = base + "/rest/v1/"
        self.session = requests.Session()
        self.session.headers.update({
            "apikey": key,
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        })

    def load_channels(self):
        try:
            r = self.session.get(
                self.endpoint + REGISTRY,
                params={
                    "select": "bot_id,channel_id,title,username,bot_status,can_post_messages,is_private",
                    "bot_id": "eq." + str(BOT_ID),
                    "order": "channel_id.asc",
                    "limit": "100",
                },
                timeout=(10, 25),
            )
        except requests.RequestException:
            raise RuntimeError("Lecture du registre indisponible") from None
        if r.status_code != 200:
            raise RuntimeError("Lecture registre refusée HTTP " + str(r.status_code))
        rows = r.json()
        if not isinstance(rows, list):
            raise RuntimeError("Registre invalide")
        if len(rows) != EXPECTED_CHANNELS:
            raise RuntimeError("Registre incomplet: " + str(len(rows))
                               + "/" + str(EXPECTED_CHANNELS))
        ids = [row["channel_id"] for row in rows]
        if len(set(ids)) != len(ids) or not all(isinstance(x, int) for x in ids):
            raise RuntimeError("IDs de canaux invalides ou dupliqués")
        for row in rows:
            if (row.get("bot_id") != BOT_ID or row.get("bot_status") not in
                ("administrator", "creator") or row.get("can_post_messages") is not True):
                raise RuntimeError("Le registre comporte un canal non autorisé")
        return rows

    def reserve(self, channel_id):
        row = {
            "campaign_id": CAMPAIGN_ID,
            "bot_id": BOT_ID,
            "channel_id": channel_id,
            "delivery_status": "reserved",
        }
        try:
            response = self.session.post(
                self.endpoint + RECEIPTS,
                headers={"Prefer": "return=representation"},
                json=row,
                timeout=(10, 25),
            )
        except requests.RequestException:
            raise RuntimeError("Réservation Supabase incertaine") from None
        if response.status_code == 409:
            # Unique campaign/bot/channel receipt; even previously failed or
            # uncertain sends must not be repeated automatically.
            return False
        if response.status_code != 201:
            raise RuntimeError("Réservation refusée HTTP " + str(response.status_code))
        body = response.json()
        if not isinstance(body, list) or len(body) != 1:
            raise RuntimeError("Réservation Supabase non confirmée")
        return True

    def finish(self, channel_id, status, message_id=None, reason=None):
        payload = {"delivery_status": status}
        if message_id is not None:
            payload["message_id"] = message_id
            payload["sent_at"] = __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).isoformat()
        if reason is not None:
            payload["error_kind"] = reason[:80]
        try:
            response = self.session.patch(
                self.endpoint + RECEIPTS,
                params={
                    "campaign_id": "eq." + CAMPAIGN_ID,
                    "bot_id": "eq." + str(BOT_ID),
                    "channel_id": "eq." + str(channel_id),
                },
                json=payload,
                headers={"Prefer": "return=minimal"},
                timeout=(10, 25),
            )
        except requests.RequestException:
            print("RECEIPT_UPDATE_UNCERTAIN", status)
            return False
        if response.status_code not in (200, 204):
            print("RECEIPT_UPDATE_FAILED_HTTP", response.status_code)
            return False
        return True


class Telegram:
    def __init__(self, token):
        self.token = token
        self.http = requests.Session()
        self.url = "https://api.telegram.org/bot" + token + "/"

    def call(self, method, *, json_body=None, photo=None):
        try:
            if photo is None:
                r = self.http.post(self.url + method, json=json_body, timeout=(10, 30))
            else:
                with IMAGE.open("rb") as f:
                    r = self.http.post(
                        self.url + method,
                        data={
                            "chat_id": photo,
                            "caption": HTML_MESSAGE,
                            "parse_mode": "HTML",
                            "reply_markup": json.dumps(KEYBOARD, ensure_ascii=False),
                            "protect_content": "false",
                        },
                        files={"photo": (IMAGE.name, f, "image/jpeg")},
                        timeout=(10, 45),
                    )
            data = r.json()
        except (requests.RequestException, ValueError):
            # Never print requests exception: URL includes the token.
            raise RuntimeError("transport_ambiguous") from None
        if not isinstance(data, dict) or data.get("ok") is not True:
            if r.status_code == 429:
                raise RuntimeError("telegram_rate_limited")
            raise RuntimeError("telegram_rejected_" + str(r.status_code))
        return data["result"]

    def identity(self):
        me = self.call("getMe", json_body={})
        if (me.get("username", "").casefold() != BOT_USERNAME
                or me.get("id") != BOT_ID):
            raise RuntimeError("Identité du bot non conforme")
        return me

    def verify_channel(self, channel_id):
        chat = self.call("getChat", json_body={"chat_id": channel_id})
        if chat.get("type") != "channel" or chat.get("id") != channel_id:
            return False
        member = self.call("getChatMember",
                           json_body={"chat_id": channel_id, "user_id": BOT_ID})
        return (member.get("status") == "creator" or
                (member.get("status") == "administrator" and
                 member.get("can_post_messages") is True))


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--send", action="store_true")
    args = parser.parse_args()
    validate_static()
    if args.check:
        return 0

    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN manquant")

    db = Supabase()
    channels = db.load_channels()
    tg = Telegram(token)
    tg.identity()
    print("BOT_CONFIRMED", "@" + BOT_USERNAME)
    print("CAMPAIGN_SCOPE", len(channels), "canaux dont",
          sum(bool(row["is_private"]) for row in channels), "privés")

    # Scope must be exactly what the user authorized, once.
    results = {"sent": 0, "skipped_existing": 0, "permission_unavailable": 0,
               "failed": 0, "uncertain": 0}
    public_links = []
    for index, channel in enumerate(channels, 1):
        cid = channel["channel_id"]
        try:
            allowed = tg.verify_channel(cid)
        except RuntimeError:
            allowed = False
        if not allowed:
            results["permission_unavailable"] += 1
            print("CHANNEL_PERMISSION_UNAVAILABLE", index, "of", len(channels))
            continue
        try:
            reserved = db.reserve(cid)
        except RuntimeError:
            results["uncertain"] += 1
            print("CHANNEL_RESERVATION_UNCERTAIN", index, "of", len(channels))
            continue
        if not reserved:
            results["skipped_existing"] += 1
            print("CAMPAIGN_ALREADY_RESERVED", index, "of", len(channels))
            continue
        try:
            message = tg.call("sendPhoto", photo=cid)
            mid = message.get("message_id")
            if not isinstance(mid, int):
                raise RuntimeError("telegram_missing_message_id")
        except RuntimeError as exc:
            reason = str(exc)
            status = "uncertain" if reason in ("transport_ambiguous", "telegram_missing_message_id") else "failed"
            results[status] += 1
            db.finish(cid, status, reason=reason)
            print("CHANNEL_SEND", status, index, "of", len(channels))
            continue

        if not db.finish(cid, "sent", message_id=mid):
            print("WARNING_RECEIPT_UPDATE_UNCERTAIN", index)
        results["sent"] += 1
        username = channel.get("username")
        if username:
            public_links.append("https://t.me/" + username + "/" + str(mid))
        print("CHANNEL_SENT", index, "of", len(channels),
              "visibility", "private" if channel["is_private"] else "public")
        if index < len(channels):
            time.sleep(1.3)

    print("CAMPAIGN_SUMMARY", json.dumps(results, ensure_ascii=False))
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as f:
            f.write("## Campagne Telegram : coupons gratuits (28 canaux)\n\n")
            f.write("**Campagne :** " + CAMPAIGN_ID + "\n\n")
            f.write("| Résultat | Nombre |\n|---|---:|\n")
            for label, count in results.items():
                f.write("| " + label + " | " + str(count) + " |\n")
            f.write("\nAucun titre, identifiant ou lien privé n'a été journalisé.\n\n")
            f.write("### Liens publics des envois\n\n")
            for url in public_links:
                f.write("- " + url + "\n")
    return 0 if results["failed"] == results["uncertain"] == results["permission_unavailable"] == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        # Our own strings never contain bot tokens or private chat IDs.
        print("::error::CAMPAIGN_ABORTED", str(exc))
        sys.exit(1)
