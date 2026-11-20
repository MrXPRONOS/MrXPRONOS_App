#!/usr/bin/env python3
"""Campagne quotidienne Ciné Radar dans les canaux publics vérifiés.

Origine : inventaire Telegram double administrateur du 17/11/2026, stocké
dans Supabase Vault. Cette liste *publique et sélectionnée* n'autorise pas
la diffusion vers les canaux privés ou les canaux foot/pronostics.

Seul @mrxpronos_canal_bot est autorisé. Chaque jour, on confirme à nouveau
ses droits via Telegram, puis l'on réserve une livraison par jour/canal dans
l'anti-doublon Supabase AVANT de copier l'affiche approuvée n°373.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timezone

import requests

BOT_USERNAME = "mrxpronos_canal_bot"
SOURCE_CHAT = "@CineXFilms_vf"
SOURCE_MESSAGE_ID = 373
CAMPAIGN = "cineradar-discovery-daily-v1"
FIRST_DAY = date(2026, 11, 21)
BOT_SECRETS = (
    "MRXPRONOS_CANAL_BOT_TOKEN", "TELEGRAM_BOT_TOKEN",
    "FOOTBALL_NEWS_BOT_TOKEN", "EDITORIAL_TELEGRAM_BOT_TOKEN",
    "PARTNERSHIP_BOT_TOKEN", "CINEX_BOT_TOKEN",
)
# Public channels confirmed by the 2026-11-17 verified shared admin inventory.
# Intentionally no private channels, predictions, sports, or test channels.
TARGETS = (
    ("actucrypto_mrxp", "crypto"),
    ("ActuCrypto24H", "crypto"),
    ("ActuCryptoNewsFR", "crypto"),
    ("CryptoActuLive", "crypto"),
    ("bleachvffr", "anime"),
    ("CineXAnimeFR", "anime"),
    ("CineXComediefr", "films"),
    ("CineXDesirfr", "films"),
    ("CineXFilms_vf", "films"),
    ("fichiers_cloud", "films_series"),
    ("filmsaction2026vf", "films"),
    ("lecarnetdelapovf", "anime"),
    ("lupin4saisonsvf", "series"),
    ("seriesvf_cinex", "series"),
)
CAPTION = "\n".join((
    "🎬 <b>CINÉ RADAR — Ton NETFLIX sur Telegram !</b>",
    "",
    "<blockquote>🔎 Trouve facilement les <b>bons canaux</b> de films, séries et animés.</blockquote>",
    "🔥 Découvre les <b>contenus</b> et les <i>chaînes tendance du moment</i>.",
    "🍿 <i>Tout ton univers cinéma, réuni au même endroit !</i>",
    "",
    "👇 <b>Plus besoin de chercher partout !</b>",
))
BUTTON = {
    "inline_keyboard": [[{
        "text": "🎬 Ouvrir le bot",
        "url": "https://t.me/CineRadarFr_Bot",
        "style": "primary",
    }]],
}
assert len(CAPTION) <= 1024
assert len(set(x[0].casefold() for x in TARGETS)) == len(TARGETS)


def api(token: str, method: str, payload: dict) -> dict:
    """Do not log request URLs or exceptions: URLs contain the bot token."""
    try:
        response = requests.post(
            "https://api.telegram.org/bot" + token + "/" + method,
            json=payload, timeout=(8, 28),
        )
        data = response.json()
    except (requests.RequestException, ValueError):
        raise RuntimeError("telegram_request_unavailable") from None
    if not isinstance(data, dict) or data.get("ok") is not True:
        code = data.get("error_code", response.status_code) if isinstance(data, dict) else response.status_code
        raise RuntimeError("telegram_http_" + str(code))
    return data["result"]


def find_publisher() -> tuple[str, int]:
    used = set()
    for secret in BOT_SECRETS:
        token = os.getenv(secret, "").strip()
        if not token or token in used:
            continue
        used.add(token)
        try:
            me = api(token, "getMe", {})
        except RuntimeError:
            continue
        if me.get("is_bot") and str(me.get("username", "")).casefold() == BOT_USERNAME:
            return token, int(me["id"])
    raise RuntimeError("verified_publishing_bot_missing")


def eligible_channel(token: str, bot_id: int, username: str) -> tuple[str, str]:
    """Recheck exact channel identity and can_post_messages, each run."""
    handle = "@" + username
    chat = api(token, "getChat", {"chat_id": handle})
    if chat.get("type") != "channel" or str(chat.get("username", "")).casefold() != username.casefold():
        raise RuntimeError("unexpected_channel_identity")
    member = api(token, "getChatMember", {"chat_id": chat["id"], "user_id": bot_id})
    status = member.get("status")
    can_post = status == "creator" or (status == "administrator" and member.get("can_post_messages") is True)
    if not can_post:
        raise RuntimeError("publisher_not_authorized")
    return str(chat["id"]), handle


def ledger_session() -> tuple[str, requests.Session]:
    base = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not base.startswith("https://") or not base.endswith(".supabase.co") or not key:
        raise RuntimeError("supabase_antiduplicate_unavailable")
    session = requests.Session()
    session.headers.update({
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    })
    return base + "/rest/v1/telegram_promo_deliveries", session


def reserve(session: requests.Session, endpoint: str, day: str, channel_id: str) -> bool:
    """Atomic conflict-ignore insert; no retries on uncertain delivery."""
    try:
        response = session.post(
            endpoint,
            params={"on_conflict": "campaign,delivery_day,chat_id"},
            headers={"Prefer": "resolution=ignore-duplicates,return=representation"},
            json={"campaign": CAMPAIGN, "delivery_day": day, "chat_id": channel_id},
            timeout=(8, 25),
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            raise RuntimeError("ledger_unexpected_response")
        return bool(rows)
    except (requests.RequestException, ValueError):
        raise RuntimeError("ledger_reservation_unavailable") from None


def mark_sent(session: requests.Session, endpoint: str, day: str, channel_id: str) -> None:
    try:
        r = session.patch(
            endpoint,
            params={"campaign": "eq." + CAMPAIGN, "delivery_day": "eq." + day, "chat_id": "eq." + channel_id},
            headers={"Prefer": "return=minimal"},
            json={"status": "sent", "sent_at": datetime.now(timezone.utc).isoformat()},
            timeout=(8, 25),
        )
        r.raise_for_status()
    except requests.RequestException:
        raise RuntimeError("ledger_sent_status_unavailable") from None


def run(*, dry_run: bool) -> int:
    day = datetime.now(timezone.utc).date()
    if not dry_run and day < FIRST_DAY:
        print("Campaign begins 2026-11-21 UTC; no sends today.")
        return 0
    token, bot_id = find_publisher()
    print("Publisher verified: @" + BOT_USERNAME)
    if len(TARGETS) != 14:
        raise RuntimeError("target_list_incomplete")
    endpoint, session = ("", None) if dry_run else ledger_session()
    counts = {"verified": 0, "sent": 0, "already_reserved": 0, "skipped": 0, "errors": 0}
    try:
        for username, kind in TARGETS:
            try:
                channel_id, handle = eligible_channel(token, bot_id, username)
                counts["verified"] += 1
            except RuntimeError as exc:
                print("SKIP", "@" + username, kind, str(exc))
                counts["skipped"] += 1
                continue
            if dry_run:
                print("ELIGIBLE", handle, kind, "NO_MESSAGE_SENT")
                continue
            try:
                if not reserve(session, endpoint, day.isoformat(), channel_id):
                    print("ALREADY_RESERVED", handle)
                    counts["already_reserved"] += 1
                    continue
            except RuntimeError as exc:
                counts["errors"] += 1
                print("ERROR", handle, str(exc), "NOT_SENT")
                continue
            try:
                result = api(token, "copyMessage", {
                    "chat_id": channel_id,
                    "from_chat_id": SOURCE_CHAT,
                    "message_id": SOURCE_MESSAGE_ID,
                    "caption": CAPTION,
                    "parse_mode": "HTML",
                    "reply_markup": BUTTON,
                    "disable_notification": True,
                })
                counts["sent"] += 1
                new_message_id = int(result["message_id"])
                print("SENT", handle, "https://t.me/" + username + "/" + str(new_message_id))
                try:
                    mark_sent(session, endpoint, day.isoformat(), channel_id)
                except RuntimeError as exc:
                    print("WARNING", handle, str(exc), "DELIVERY_WAS_ACCEPTED")
            except (RuntimeError, ValueError, KeyError) as exc:
                counts["errors"] += 1
                print("UNCERTAIN", handle, str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__,
                      "RESERVATION_KEPT_TO_AVOID_DUPLICATE")
            time.sleep(1.2)
    finally:
        if session is not None:
            session.close()
    mode = "DRY_RUN" if dry_run else "PUBLISH"
    print("CINERADAR_CAMPAIGN_SUMMARY", mode, json.dumps(counts, sort_keys=True))
    with open(os.getenv("GITHUB_STEP_SUMMARY", os.devnull), "a", encoding="utf-8") as output:
        output.write(
            "## Ciné Radar — " + mode + " (" + day.isoformat() + " UTC)\n\n" +
            "| Vérifiés | Publiés | Déjà réservés | Ignorés | Erreurs |\n|---:|---:|---:|---:|---:|\n" +
            "| {verified} | {sent} | {already_reserved} | {skipped} | {errors} |\n".format(**counts)
        )
    if dry_run:
        return 0 if counts["verified"] == len(TARGETS) else 1
    return 1 if counts["errors"] or counts["skipped"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Ciné Radar: diffusion quotidienne sécurisée")
    parser.add_argument("--dry-run", action="store_true", help="Vérifie les droits sans publier et sans écrire en base.")
    args = parser.parse_args()
    try:
        return run(dry_run=args.dry_run)
    except RuntimeError as exc:
        print("ERROR", str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
