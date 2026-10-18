"""Telegram #09: PNG + caption, test channel only, demo never impersonates news."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import requests

from scripts.telegram_test_guard import validate_test_channel
from crypto.export_exchanges_v2 import validate_real, load_state, fingerprint

BASE = Path("crypto/generated/test")
STATE = Path("crypto/exchanges_09_state.json")
CHANNEL = "@predict_mrxp"


def deliver(demo: bool, requester=requests.post) -> int:
    stem = "exchanges_v2_demo" if demo else "exchanges_v2"
    datafile, png = BASE / (stem + ".json" if demo else "exchanges_v2_data.json"), BASE / (stem + ".png")
    if not datafile.is_file() or not png.is_file() or png.stat().st_size < 10_000:
        raise RuntimeError("Expected JSON and PNG missing; Telegram send forbidden")
    d = json.loads(datafile.read_text(encoding="utf-8"))
    if demo:
        if d.get("is_demo") is not True or d.get("status") != "demo" or d.get("publication") != 9:
            raise RuntimeError("Refusing to mislabel demo as real")
    else:
        validate_real(d)
        state = load_state(STATE)
        if any(x in state["sent_urls"] for x in d["fingerprints"]):
            print("EXCHANGE_09_DUPLICATE — skip Telegram")
            return 0
    token = (os.environ.get("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    dest = validate_test_channel(CHANNEL, token)
    article, conf = d["main"], d["confirmation"]
    if demo:
        caption = (
            "🧪 MR XPRONOS · ACTU CRYPTO #09 — APERÇU PREMIUM\n\n"
            "⚠️ SIMULATION — TITRE FICTIF, PAS UNE ACTUALITÉ.\n"
            "Contrôle du design, de l'image PNG et du canal test @predict_mrxp."
        )
    else:
        caption = (
            "🏦 ACTU CRYPTO #09 · PLATEFORMES\n"
            f"📌 {d['exchange']} — {d['category']}\n\n"
            f"📰 {article['title']}\n\n"
            f"🗞 Selon {article['source']} : {article['url']}\n"
            + (f"🔎 Deuxième média : {conf['source']} : {conf['url']}\n" if conf else
               "ℹ️ Information rapportée par une source journalistique.\n")
            + "\n🕒 Événement daté dans la source. Lisez l'article complet.\n"
            "🌍 Disponibilité régionale à vérifier. Ce n'est pas un conseil financier."
        )
    if len(caption) > 1024:
        raise RuntimeError("Telegram caption exceeds 1024 characters")
    with png.open("rb") as img:
        try:
            response = requester(
                "https://api.telegram.org/bot" + token + "/sendPhoto",
                data={"chat_id": dest["chat_id"], "caption": caption,
                      "disable_notification": demo},
                files={"photo": (png.name, img, "image/png")},
                timeout=(10, 90))
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError("Telegram outcome unknown — do not auto-retry") from None
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RuntimeError("Telegram refused image")
    result = payload.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
        raise RuntimeError("Telegram did not return a reliable message ID")
    if (not isinstance(result.get("chat"), dict)
            or result["chat"].get("id") != dest["chat_id"]
            or not isinstance(result.get("photo"), list) or not result["photo"]):
        raise RuntimeError("Telegram photo or destination unverified")
    if not demo:
        state = load_state(STATE)
        state["sent_urls"] = list(dict.fromkeys(state["sent_urls"] + d["fingerprints"]))[-600:]
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("EXCHANGE_09_TELEGRAM_PHOTO_CONFIRMED",
          "mode=DEMO" if demo else "mode=REAL",
          "chat=@" + dest["username"],
          "message_id=" + str(result["message_id"]),
          "photo_sizes=" + str(len(result["photo"])))
    return result["message_id"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    exclusive = ap.add_mutually_exclusive_group(required=True)
    exclusive.add_argument("--demo", action="store_true")
    exclusive.add_argument("--real", action="store_true")
    args = ap.parse_args()
    deliver(args.demo)
