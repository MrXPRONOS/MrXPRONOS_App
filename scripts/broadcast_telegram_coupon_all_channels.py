#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-time user-approved broadcast to 28 Telegram channels, including private.

Only the campaign specified by CAMPAIGN_ID is authorized. Does not change
telegram_channel_registry.broadcast_enabled (persistent permission remains off).
A service-role-only Supabase ledger reserves each destination BEFORE send.
Ambiguous failures stay reserved (prevent accidental duplicate sends).
Never print private channel IDs/titles/tokens in GitHub's public logs.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

CAMPAIGN_ID = "mrx-coupon-gratuit-20261117-all28-v1"
EXPECTED_BOT_USERNAME = "mrxpronos_canal_bot"
EXPECTED_BOT_ID = 8586885516
EXPECTED_DESTINATIONS = 28
CHANNEL_URL = "https://t.me/mrxpronosfr"
PHOTO = Path(__file__).resolve().parents[1] / "assets/telegram/promo_coupon_2026-10-25.jpg"
# Visible message is EXACTLY the four lines approved by the user.
TEXT = (
    "💸 COUPONS PAYANTS ? STOP !\n"
    "✅ COUPONS GRATUITS ICI.\n"
    "📲 REJOINS LE CANAL TELEGRAM 👇\n"
    "🔞 18+ • Risque de perte."
)
BUTTON = {
    "inline_keyboard": [[{
        "text": "📲 REJOINDRE LE CANAL GRATUIT",
        "url": CHANNEL_URL,
        "style": "primary",
    }]]
}
SESSION = requests.Session()


class BroadcastError(Exception):
    pass


def api_token() -> str:
    a = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    b = os.environ.get("FOOTBALL_NEWS_BOT_TOKEN", "").strip()
    token = a or b
    if not token:
        raise BroadcastError("telegram_token_not_configured")
    return token


def supabase_setup() -> tuple[str, dict[str, str]]:
    base = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not base.startswith("https://") or not base.endswith(".supabase.co") or not key:
        raise BroadcastError("supabase_service_role_missing_or_invalid")
    return base + "/rest/v1", {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    }


def db_request(method: str, table: str, *, params: dict | None = None,
               json_data: Any = None, prefer: str | None = None) -> Any:
    url, headers = supabase_setup()
    if prefer:
        headers["Prefer"] = prefer
    try:
        response = SESSION.request(
            method, url + "/" + table, params=params, json=json_data,
            headers=headers, timeout=(8, 35),
        )
    except requests.RequestException:
        raise BroadcastError("database_transport_failed") from None
    if not response.ok:
        # Never print private channel details or Supabase response bodies.
        raise BroadcastError("database_http_" + str(response.status_code))
    try:
        return response.json() if response.content else []
    except ValueError:
        raise BroadcastError("invalid_database_response") from None


def bot_call(token: str, method: str, data: dict) -> dict:
    # Never print underlying URL or exception (it includes Telegram bot token).
    try:
        response = SESSION.post(
            "https://api.telegram.org/bot" + token + "/" + method,
            json=data, timeout=(8, 25),
        )
        payload = response.json()
    except (requests.RequestException, ValueError):
        raise BroadcastError("telegram_transport_error") from None
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise BroadcastError("telegram_http_" + str(response.status_code))
    obj = payload.get("result")
    if not isinstance(obj, dict):
        raise BroadcastError("telegram_invalid_result")
    return obj


def check_preconditions(token: str) -> list[dict]:
    if not PHOTO.is_file() or PHOTO.stat().st_size < 1024:
        raise BroadcastError("coupon_image_missing")
    with PHOTO.open("rb") as image:
        if image.read(3) != b"\xff\xd8\xff":
            raise BroadcastError("coupon_image_not_jpeg")
    if os.getenv("CAMPAIGN_ID", "").strip() != CAMPAIGN_ID:
        raise BroadcastError("wrong_or_missing_campaign_id")
    if os.getenv("CAMPAIGN_SEND_APPROVED", "").strip() != "true":
        raise BroadcastError("explicit_campaign_authorization_missing")

    me = bot_call(token, "getMe", {})
    if (str(me.get("username") or "").lower() != EXPECTED_BOT_USERNAME
            or me.get("id") != EXPECTED_BOT_ID):
        raise BroadcastError("unexpected_bot_identity")

    rows = db_request(
        "GET", "telegram_channel_registry",
        params={
            "select": "bot_id,channel_id,username,is_private,can_post_messages",
            "bot_id": "eq." + str(EXPECTED_BOT_ID),
            "order": "channel_id.asc",
        },
    )
    if not isinstance(rows, list):
        raise BroadcastError("registry_invalid")
    if len(rows) != EXPECTED_DESTINATIONS:
        raise BroadcastError("unexpected_registry_total_" + str(len(rows)))
    if len({row["channel_id"] for row in rows}) != len(rows):
        raise BroadcastError("duplicate_registry_destinations")
    if any(row.get("can_post_messages") is not True for row in rows):
        raise BroadcastError("registry_contains_non_postable_channels")
    private_count = sum(row.get("is_private") is True for row in rows)
    if private_count != 15:
        raise BroadcastError("unexpected_private_channel_count_" + str(private_count))
    print("PRECHECK_OK exact_bot 28 destinations 15 private 13 public")
    return rows


def reserve(channel_id: int) -> bool:
    record = {
        "campaign_id": CAMPAIGN_ID,
        "bot_id": EXPECTED_BOT_ID,
        "channel_id": channel_id,
        "delivery_status": "reserved",
    }
    rows = db_request(
        "POST", "telegram_channel_broadcast_receipts",
        params={"on_conflict": "campaign_id,bot_id,channel_id"},
        json_data=record,
        prefer="resolution=ignore-duplicates,return=representation",
    )
    if not isinstance(rows, list):
        raise BroadcastError("reservation_response_invalid")
    return len(rows) == 1


def mark(channel_id: int, status: str, *,
         message_id: int | None = None, error_kind: str | None = None):
    patch = {"delivery_status": status}
    if message_id is not None:
        patch["message_id"] = message_id
        patch["sent_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if error_kind:
        patch["error_kind"] = error_kind
    db_request(
        "PATCH", "telegram_channel_broadcast_receipts",
        params={
            "campaign_id": "eq." + CAMPAIGN_ID,
            "bot_id": "eq." + str(EXPECTED_BOT_ID),
            "channel_id": "eq." + str(channel_id),
        },
        json_data=patch,
        prefer="return=minimal",
    )


def can_post_now(token: str, chat_id: int) -> bool:
    try:
        chat = bot_call(token, "getChat", {"chat_id": chat_id})
        if chat.get("id") != chat_id or chat.get("type") != "channel":
            return False
        member = bot_call(
            token, "getChatMember",
            {"chat_id": chat_id, "user_id": EXPECTED_BOT_ID},
        )
        return (member.get("status") == "creator"
                or (member.get("status") == "administrator"
                    and member.get("can_post_messages") is True))
    except BroadcastError:
        return False


def publish(token: str, channel_id: int) -> int:
    # A POST network timeout is *uncertain*; never repeat automatically.
    try:
        with PHOTO.open("rb") as photo:
            response = SESSION.post(
                "https://api.telegram.org/bot" + token + "/sendPhoto",
                data={
                    "chat_id": str(channel_id),
                    "caption": TEXT,
                    "reply_markup": json.dumps(BUTTON, ensure_ascii=False),
                    "protect_content": "false",
                },
                files={"photo": (PHOTO.name, photo, "image/jpeg")},
                timeout=(10, 35),
            )
            payload = response.json()
    except (requests.RequestException, ValueError):
        raise BroadcastError("uncertain_telegram_send") from None
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise BroadcastError("telegram_rejected_http_" + str(response.status_code))
    result = payload.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
        raise BroadcastError("uncertain_telegram_message_id")
    return result["message_id"]


def report():
    rows = db_request(
        "GET", "telegram_channel_broadcast_receipts",
        params={
            "select": "channel_id,delivery_status",
            "campaign_id": "eq." + CAMPAIGN_ID,
            "bot_id": "eq." + str(EXPECTED_BOT_ID),
        },
    )
    statuses = {key: sum(r.get("delivery_status") == key for r in rows) for key in
                ("sent", "blocked", "failed", "uncertain", "reserved")}
    print("CAMPAIGN_TOTALS", json.dumps(statuses, sort_keys=True))
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as f:
            f.write(
                "## Diffusion Telegram — campagne unique\n\n"
                "Message : 4 lignes approuvées, photo du coupon et bouton bleu.\n\n"
                "Canaux prévus : **28**, dont **15 privés**. "
                "Noms et IDs privés non publiés ici.\n\n"
                + "\n".join("- " + k + " : **" + str(v) + "**"
                            for k, v in statuses.items()) + "\n"
                "\nAucun doublon automatique sur une requête incertaine.\n"
            )
    return statuses


def main() -> int:
    token = api_token()
    rows = check_preconditions(token)
    sent = skipped = blocked = failed = uncertain = 0
    for index, row in enumerate(rows, start=1):
        cid = row["channel_id"]
        # Reserve before checking or posting, so any concurrent/re-run cannot duplicate.
        if not reserve(cid):
            skipped += 1
            print("DESTINATION", index, "already_reserved_or_sent")
            continue
        if not can_post_now(token, cid):
            mark(cid, "blocked", error_kind="rights_or_visibility_unavailable")
            blocked += 1
            print("DESTINATION", index, "blocked_permissions")
            continue

        try:
            message_id = publish(token, cid)
        except BroadcastError as exc:
            kind = str(exc)
            # Telegram refused definitively, distinct from a network ambiguity.
            if kind.startswith("telegram_rejected_"):
                mark(cid, "failed", error_kind=kind)
                failed += 1
                print("DESTINATION", index, "definitive_failure")
            else:
                mark(cid, "uncertain", error_kind=kind)
                uncertain += 1
                print("DESTINATION", index, "uncertain_no_retry")
        else:
            mark(cid, "sent", message_id=message_id)
            sent += 1
            print("DESTINATION", index, "sent")
        time.sleep(1.25)

    totals = report()
    print("RUN_COMPLETED sent", sent, "skipped_existing", skipped,
          "blocked", blocked, "failed", failed, "uncertain", uncertain)
    return 0 if totals["sent"] == EXPECTED_DESTINATIONS else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BroadcastError as exc:
        print("::error::BROADCAST_ABORTED", str(exc))
        sys.exit(1)
