"""Test premium envoyé UNIQUEMENT au canal Telegram @predict_mrxp.
Jeu de données fictives explicitement marqué SIMULATION.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone
from pathlib import Path
import requests
from crypto.render_premium_cards import (
    render_prices_card, render_movers_card, render_fear_card, render_alert_card
)

def main():
    token = (os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    target = (os.getenv("TELEGRAM_TEST_CHAT_ID") or "@predict_mrxp").strip()
    if not token or not target:
        raise SystemExit("Secret FOOTBALL_NEWS_BOT_TOKEN ou canal test absent")
    from scripts.telegram_test_guard import validate_test_channel
    verified = validate_test_channel(target, token)
    verified_chat = verified["chat_id"]
    print("ROUTE TEST CONFIRMEE:", verified["username"], "bot", verified["bot_username"])
    now = datetime.now(timezone.utc)
    rows = [
        dict(symbol="BTC", name="Bitcoin", rank=1, price=72000, change=2.4, volume=5e9),
        dict(symbol="ETH", name="Ethereum", rank=2, price=3800, change=-3.2, volume=5e9),
        dict(symbol="SOL", name="Solana", rank=3, price=185.25, change=8.4, volume=5e9),
        dict(symbol="BNB", name="BNB", rank=4, price=1020, change=-2.1, volume=5e9),
        dict(symbol="XRP", name="XRP", rank=5, price=2.48, change=4.72, volume=5e9),
    ]
    gains = [
        dict(symbol="SOL", name="Solana", price=185.25, change=8.4),
        dict(symbol="LINK", name="Chainlink", price=18.5, change=7.15),
        dict(symbol="AVAX", name="Avalanche", price=32.4, change=6.03),
        dict(symbol="ADA", name="Cardano", price=.85, change=5.2),
        dict(symbol="XRP", name="XRP", price=2.48, change=4.72),
    ]
    losses = [
        dict(symbol="DOGE", name="Dogecoin", price=.145, change=-6.8),
        dict(symbol="DOT", name="Polkadot", price=4.75, change=-5.4),
        dict(symbol="UNI", name="Uniswap", price=7.3, change=-4.8),
        dict(symbol="ETH", name="Ethereum", price=3800, change=-3.2),
        dict(symbol="BNB", name="BNB", price=1020, change=-2.1),
    ]
    output=Path("crypto/generated/test")
    tests = [
        ("COURS DU MARCHE", render_prices_card(rows, "SIMULATION", now, output/"prices.png")),
        ("TOP 5 HAUSSES", render_movers_card(gains, "SIMULATION", now, "up", output/"gainers.png")),
        ("TOP 5 BAISSES", render_movers_card(losses, "SIMULATION", now, "down", output/"losers.png")),
        ("ALERTE SOL", render_alert_card(rows[2], "SIMULATION", now, 5, output/"alert.png", demo=True)),
        ("FEAR & GREED", render_fear_card(32, now, now, output/"fear.png")),
    ]
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
