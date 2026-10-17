"""Publish ONLY crypto publication 03 V2 to approved @predict_mrxp test channel."""
from __future__ import annotations
import json
import os
from pathlib import Path
import requests
from scripts.telegram_test_guard import validate_test_channel

def main():
    token = (os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    verified = validate_test_channel("@predict_mrxp", token)
    path = Path("crypto/generated/test/losers_v2.png")
    info = Path("crypto/generated/test/losers_v2_data.json")
    if not path.is_file() or path.stat().st_size < 10_000 or not info.is_file():
        raise RuntimeError("Valid V2 losses PNG/data are required before publishing")
    market_data = json.loads(info.read_text(encoding="utf-8"))
    rows = market_data["rows"]
    if len(rows) != 5 or any(float(r["change"]) >= 0 or len(r.get("sparkline") or []) < 12 for r in rows):
        raise RuntimeError("Invalid real losses or missing 48h historical data")
    caption = (
        "🧪 TEST PUBLICATION 03 — TOP 5 DES BAISSES CRYPTO\n"
        "Les 5 plus fortes baisses sur 24 h (top 100, volume ≥ 1 M USD).\n"
        "Cours : " + market_data["provider"] + " • 5/5 courbes réelles (48 h).\n"
        "Classement : " + ", ".join(r["symbol"] for r in rows) + "\n"
        "⚠️ Canal de test uniquement. Données indicatives, aucun conseil d'investissement."
    )
    with path.open("rb") as image:
        try:
            response = requests.post(
                "https://api.telegram.org/bot" + token + "/sendPhoto",
                data={"chat_id": verified["chat_id"], "caption": caption},
                files={"photo": (path.name, image, "image/png")}, timeout=(10, 90),
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError("Telegram result uncertain; do not retry automatically") from exc
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError("Telegram refused losers V2 poster")
    print("LOSERS_V2_TEST_PUBLISHED", data.get("result", {}).get("message_id"))

if __name__ == "__main__":
    main()
