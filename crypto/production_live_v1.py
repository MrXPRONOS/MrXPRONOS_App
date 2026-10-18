"""Controlled recurring production of verified Actu Crypto posters.

Uses the same source validation and premium renderers as the tested one-time
history seeder. Only trusted real data, never DEMO. #10: review archive only.
The registry is tracked and committed by GitHub Actions with concurrency lock.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from crypto import production_seed_v1 as seed

UTC = timezone.utc
TODAY = datetime.now(UTC)
MODES = {
    "morning": (1, 5, 6),
    "midday": (2, 3),
    "evening": (1,),
    "alerts": (4,),
    "news": (8, 9),
    "weekly": (7,),
}
REG = Path("crypto/generated/test/regulation_v2_candidate.json")


def key_for(number: int, data: dict, mode: str) -> str:
    day = TODAY.strftime("%Y-%m-%d")
    if number in (8, 9):
        # Stable URL fingerprints prevent reposting the same published article.
        ids = data.get("fingerprints")
        if not isinstance(ids, list) or not ids:
            raise ValueError("News article fingerprints missing")
        joined = "|".join(sorted(set(ids)))
        return f"news:{number:02d}:" + hashlib.sha256(joined.encode()).hexdigest()[:24]
    if number == 7:
        iso = TODAY.isocalendar()
        return f"weekly:07:{iso.year}-W{iso.week:02d}"
    if number == 4:
        row = data.get("row") or {}
        symbol = row.get("symbol")
        variation = float(row["change"])
        direction = "up" if variation > 0 else "down"
        level = int(row["level"])
        return f"alert:04:{day}:{symbol}:{direction}:{level}"
    return f"daily:{number:02d}:{day}:{mode if number == 1 else 'default'}"


def blocked_by_initial_history(state: dict, number: int) -> bool:
    # Do not repeat initial-history posts as same-day daily messages.
    initial = state["sent"].get(f"initial_history_{number:02d}")
    if number in (4, 8, 9) or not isinstance(initial, dict):
        return False
    try:
        date = seed.datetime_from(initial["sent_at"]).date()
    except (KeyError, ValueError):
        raise RuntimeError("Invalid recorded initial-history timestamp") from None
    if number == 7:
        return date.isocalendar()[:2] == TODAY.date().isocalendar()[:2]
    return date == TODAY.date()


def record_send(chat: dict, caption: str, image: Path) -> int:
    seed.validate_image(image)
    with image.open("rb") as fp:
        try:
            resp = requests.post(
                "https://api.telegram.org/bot" + seed.TOKEN + "/sendPhoto",
                data={"chat_id": chat["id"], "caption": caption},
                files={"photo": (image.name, fp, "image/png")},
                timeout=(10, 90))
            resp.raise_for_status()
            result = resp.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError("Unknown Telegram send result — do not automatically retry") from None
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Telegram rejected photo")
    m = result.get("result")
    if (not isinstance(m, dict) or not isinstance(m.get("message_id"), int)
            or not isinstance(m.get("chat"), dict) or m["chat"].get("id") != chat["id"]
            or not isinstance(m.get("photo"), list) or not m["photo"]):
        raise RuntimeError("No confirmed production photo; manual audit required")
    return m["message_id"]


def execute(mode: str):
    if mode == "legal":
        # Regulatory articles are review candidates, never public assertions.
        seed.run("python", "-m", "crypto.export_regulation_v2")
        if REG.is_file():
            seed.run("node", "scripts/render_crypto_regulation_v2.mjs")
            print("CRYPTO_LIVE_REVIEW_CANDIDATE_ONLY", "number=10",
                  "no_telegram_send=1", "check archived artifact")
        else:
            print("CRYPTO_LIVE_NO_LEGAL_CANDIDATE", "number=10")
        return

    chat = seed.verify_production_route()
    state = seed.read_state()
    for number in MODES[mode]:
        if blocked_by_initial_history(state, number):
            print("CRYPTO_LIVE_SKIP_INITIAL_ALREADY_POSTED", number)
            continue
        # Skip known timed posts before expensive API calls.
        if number not in (4, 8, 9):
            prekey = f"daily:{number:02d}:{TODAY:%Y-%m-%d}:{mode if number == 1 else 'default'}"
            if number == 7:
                iso = TODAY.isocalendar()
                prekey = f"weekly:07:{iso.year}-W{iso.week:02d}"
            if prekey in state["sent"]:
                print("CRYPTO_LIVE_SKIP_ALREADY_POSTED", number)
                continue
        try:
            output = seed.prepared(number)
            if output is None:
                print("CRYPTO_LIVE_SKIP_NO_REAL_EVENT", number)
                continue
            data, image = output
            key = key_for(number, data, mode)
            if key in state["sent"]:
                print("CRYPTO_LIVE_SKIP_DUPLICATE", number, key)
                continue
            caption = seed.caption_for(number, data)
            message_id = record_send(chat, caption, image)
            state["sent"][key] = {
                "number": number,
                "message_id": message_id,
                "sent_at": datetime.now(UTC).isoformat(),
                "source": data.get("provider") or data.get("main", {}).get("source") or "Alternative.me",
            }
            seed.write_state(state)
            print("CRYPTO_LIVE_PUBLISHED", "number="+str(number),
                  "message_id="+str(message_id), "photo_confirmed=1")
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
            # A one-off upstream source failure should not suppress unrelated news.
            # Do not auto-retry uncertain send calls on same iteration.
            print("CRYPTO_LIVE_FAILED", number, type(exc).__name__, str(exc)[:250])
            continue


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=tuple(MODES) + ("legal",), required=True)
    args = parser.parse_args()
    execute(args.mode)


if __name__ == "__main__":
    main()
