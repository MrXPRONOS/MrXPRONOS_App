#!/usr/bin/env python3
"""Campagne e-book Telegram quotidienne, canaux cinema administres et autorises.

Utilise le meme bot, le meme registre protege et le ledger anti-doublons
que le dossier MR XPRONOS F. Jamais de session Telegram personnelle pour
publier, ni d'identifiants de canaux prives dans les journaux GitHub.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from send_folder_promo_daily import (
    BOT_ID, EXCLUDED_HANDLES, EXCLUDED_ID_TO_HANDLE,
    REGISTRY, Storage, Telegram,
)
from telegram_admin_cinema_catalog import classify_channel

ROOT = Path(__file__).resolve().parents[1]
PHOTO = ROOT / "assets/marketing/telegram-ebook-2026-11/affiche-promo-1938-fcfa.jpg"
PREVIEW_URL = "https://mr-xpronos.myficsell.com/njtp54yjw"
GUIDE_URL = "https://mr-xpronos.myficsell.com/favxph7ge"
CAPTION = (
    "💰 <b>Et si Telegram devenait une nouvelle source de revenus ?</b>\n"
    "<blockquote>📘 <i>Découvre 10 méthodes concrètes pour le monétiser.</i></blockquote>\n"
    "📈 Apprends à <b>attirer des abonnés</b> et à développer ton activité.\n"
    "🎁 <i>Inclus : plan de 30 jours + bonus Canal Manager X.</i>\n"
    "👇 Clique sur le bouton ci-dessous pour obtenir ton guide à <b>1 938 FCFA</b> !"
)
BUTTONS = {"inline_keyboard": [
    [{"text": "Voir l’extrait du PDF", "url": PREVIEW_URL, "style": "primary"}],
    [{"text": "Télécharger mon guide", "url": GUIDE_URL, "style": "primary"}],
]}
CAMPAIGN = "mrxp_ebook_cinema_v1_"
MAX_AGE_DAYS = 14
EXCLUDED_OTHER_HANDLES = {"predict_mrxp"}


def is_movie_channel(row: dict) -> bool:
    """Ne pas detourner des chaines de pronostics, foot ou crypto."""
    cid = row.get("channel_id")
    handle = str(row.get("username") or "").lstrip("@").casefold()
    if cid in EXCLUDED_ID_TO_HANDLE or handle in EXCLUDED_HANDLES | EXCLUDED_OTHER_HANDLES:
        return False
    meta = classify_channel(row.get("title") or "", row.get("username"), "")
    return bool(meta and set(meta.get("categories") or ()) & {"films", "series", "animes"})


def validate_static() -> None:
    if not PHOTO.is_file() or PHOTO.stat().st_size < 15000 or PHOTO.read_bytes()[:3] != b"\xff\xd8\xff":
        raise RuntimeError("Affiche JPEG e-book introuvable ou incorrecte.")
    if len(CAPTION) > 1024:
        raise RuntimeError("Legende trop longue pour une photo Telegram")
    for row in BUTTONS["inline_keyboard"]:
        if len(row) != 1 or row[0]["style"] != "primary":
            raise RuntimeError("Bouton non bleu ou structure incorrecte")
        parsed = urlparse(row[0]["url"])
        if parsed.scheme != "https" or parsed.hostname != "mr-xpronos.myficsell.com":
            raise RuntimeError("Destination commerciale inattendue")
    print("EBOOK_CINEMA_STATIC_OK", "image_kb", PHOTO.stat().st_size // 1024, "buttons", 2)


def get_targets(storage: Storage) -> list[dict]:
    response = storage.http.get(storage.base + REGISTRY, params={
        "select": "bot_id,channel_id,title,username,is_private,bot_status,can_post_messages,broadcast_enabled,last_verified_at",
        "bot_id": "eq." + str(BOT_ID),
        "broadcast_enabled": "eq.true",
        "order": "channel_id.asc",
        "limit": "1000",
    }, timeout=(10, 30))
    if response.status_code != 200:
        raise RuntimeError("Lecture du registre autorise impossible")
    rows = response.json()
    if not isinstance(rows, list) or len(rows) == 1000:
        raise RuntimeError("Registre anormal ou tronque")
    now = dt.datetime.now(dt.timezone.utc)
    out, seen = [], set()
    for row in rows:
        cid = row.get("channel_id")
        if not isinstance(cid, int) or cid in seen or row.get("bot_id") != BOT_ID:
            raise RuntimeError("Identifiant invalide ou duplique dans le registre")
        seen.add(cid)
        if not is_movie_channel(row):
            continue
        if row.get("bot_status") not in ("administrator", "creator") or row.get("can_post_messages") is not True:
            continue
        checked = str(row.get("last_verified_at") or "").replace("Z", "+00:00")
        try:
            stamp = dt.datetime.fromisoformat(checked)
            if stamp.tzinfo is None:
                raise ValueError("timezone missing")
        except ValueError:
            continue
        if stamp > now + dt.timedelta(minutes=5) or now - stamp > dt.timedelta(days=MAX_AGE_DAYS):
            continue
        out.append(row)
    print("EBOOK_CINEMA_TARGETS", len(out), "private", sum(bool(r["is_private"]) for r in out))
    return out


def send_photo(bot: Telegram, channel_id: int) -> int:
    try:
        with PHOTO.open("rb") as fp:
            response = bot.http.post(bot.root + "sendPhoto", data={
                "chat_id": str(channel_id),
                "caption": CAPTION,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(BUTTONS, ensure_ascii=False),
            }, files={"photo": (PHOTO.name, fp, "image/jpeg")}, timeout=(10, 45))
        payload = response.json()
    except (requests.RequestException, ValueError):
        raise RuntimeError("telegram_transport_uncertain") from None
    if response.status_code == 429:
        raise RuntimeError("telegram_rate_limited")
    if response.status_code != 200 or not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RuntimeError("telegram_refused_http_" + str(response.status_code))
    result = payload.get("result") or {}
    if result.get("chat", {}).get("id") != channel_id or not isinstance(result.get("message_id"), int):
        raise RuntimeError("telegram_missing_message_id")
    return result["message_id"]


def run() -> int:
    validate_static()
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("Bot de diffusion absent")
    storage = Storage()
    targets = get_targets(storage)
    if not targets:
        print("EBOOK_CINEMA_NO_ELIGIBLE_CHANNELS")
        return 0
    bot = Telegram(token)
    bot.verify_bot()
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    campaign = CAMPAIGN + today
    stats = {"sent": 0, "recorded": 0, "failed": 0, "uncertain": 0, "permission_missing": 0}
    public_links = []
    for index, row in enumerate(targets, 1):
        cid = row["channel_id"]
        try:
            authorized = bot.verify_access(cid)
        except RuntimeError:
            authorized = False
        if not authorized:
            stats["permission_missing"] += 1
            print("EBOOK_PERMISSION_UNAVAILABLE", index)
            continue
        try:
            reserved = storage.reserve(campaign, cid)
        except RuntimeError:
            stats["uncertain"] += 1
            print("EBOOK_RESERVATION_UNCERTAIN", index)
            continue
        if not reserved:
            stats["recorded"] += 1
            continue
        try:
            message_id = send_photo(bot, cid)
        except RuntimeError as exc:
            status = "uncertain" if str(exc) in ("telegram_transport_uncertain", "telegram_missing_message_id") else "failed"
            storage.mark(campaign, cid, status, error_kind=str(exc))
            stats[status] += 1
            print("EBOOK_DELIVERY_FAILED", index, status)
            continue
        marked = storage.mark(campaign, cid, "sent", message_id=message_id)
        stats["sent"] += 1
        print("EBOOK_DELIVERY_CONFIRMED", index, "private" if row["is_private"] else "public", "receipt_ok", marked)
        if row.get("username"):
            public_links.append("https://t.me/" + row["username"] + "/" + str(message_id))
        if index < len(targets):
            time.sleep(1.5)
    print("EBOOK_CINEMA_RESULTS", json.dumps(stats))
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("\n## Campagne e-book — chaînes cinéma\n\n")
            f.write("Candidats : " + str(len(targets)) + "; privés : " + str(sum(bool(r["is_private"]) for r in targets)) + "\n\n")
            for key, count in stats.items():
                f.write("- " + key + " : " + str(count) + "\n")
            for url in public_links:
                f.write("- " + url + "\n")
            f.write("\nAucun identifiant de chaîne privée dans ce journal.\n")
    return 0 if not (stats["failed"] or stats["uncertain"] or stats["permission_missing"]) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--send", action="store_true")
    args = ap.parse_args()
    try:
        if args.check:
            validate_static()
            return 0
        return run()
    except RuntimeError as exc:
        print("::error::EBOOK_CINEMA_ABORTED", str(exc))
        return 1

if __name__ == "__main__":
    sys.exit(main())