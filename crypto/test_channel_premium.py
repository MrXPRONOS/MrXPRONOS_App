"""Test premium envoyé UNIQUEMENT au canal Telegram @predict_mrxp.
Jeu de données fictives explicitement marqué SIMULATION.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import requests
from crypto.render_premium_cards import render_prices_card

def main():
    preview_only = "--preview-only" in sys.argv[1:]
    now = datetime.now(timezone.utc)
    rows = [
        dict(symbol="BTC", name="Bitcoin", rank=1, price=72000, change=2.4, volume=5e9),
        dict(symbol="ETH", name="Ethereum", rank=2, price=3800, change=-3.2, volume=5e9),
        dict(symbol="SOL", name="Solana", rank=3, price=185.25, change=8.4, volume=5e9),
        dict(symbol="BNB", name="BNB", rank=4, price=1020, change=-2.1, volume=5e9),
        dict(symbol="XRP", name="XRP", rank=5, price=2.48, change=4.72, volume=5e9),
    ]
    output=Path("crypto/generated/test")
    tests = [
        ("COURS DU MARCHE", render_prices_card(rows, "SIMULATION", now, output/"prices.png")),
    ]
    print("PREVIEW_PRICES_READY:", str(tests[0][1]))
    if preview_only:
        return
    token = (os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    target = (os.getenv("TELEGRAM_TEST_CHAT_ID") or "@predict_mrxp").strip()
    if not token or not target:
        raise SystemExit("Secret FOOTBALL_NEWS_BOT_TOKEN ou canal test absent")
    from scripts.telegram_test_guard import validate_test_channel
    verified = validate_test_channel(target, token)
    verified_chat = verified["chat_id"]
    print("ROUTE TEST CONFIRMEE:", verified["username"], "bot", verified["bot_username"])
    for title, path in tests:
        caption = "🧪 TEST ACTU CRYPTO — " + title + "\n⚠️ DONNEES FICTIVES — DEMONSTRATION, PAS DES COURS REELS."
        with path.open("rb") as fp:
            try:
                result = requests.post(
                    f"https://api.telegram.org/bot{token}/sendPhoto",
                    data={"chat_id":verified_chat, "caption":caption},
                    files={"photo":(path.name, fp, "image/png")},
                    timeout=(10,90))
                result.raise_for_status()
                if not result.json().get("ok"):
                    raise RuntimeError("Telegram refused photo")
            except requests.RequestException:
                raise RuntimeError("Envoi incertain, pas de nouvelle tentative") from None
        print("TEST_IMAGE_PUBLISHED", title)

if __name__ == "__main__":
    main()
