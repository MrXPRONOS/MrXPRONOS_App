"""Test UNIQUE de la publication #06 sur @predict_mrxp, uniquement en données réelles."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from crypto.export_dominance_v2 import validate_real
from scripts.telegram_test_guard import validate_test_channel

DATA = Path("crypto/generated/test/dominance_v2_data.json")
IMAGE = Path("crypto/generated/test/dominance_v2.png")


def main() -> None:
    if not DATA.is_file() or not IMAGE.is_file() or IMAGE.stat().st_size < 10_000:
        raise RuntimeError("Données et affiche réelles absentes : pas de publication")
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    validate_real(payload)
    token = (os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    channel = validate_test_channel("@predict_mrxp", token)
    observed = datetime.fromisoformat(payload["source_updated_at"] or payload["collected_at"])
    when = observed.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    cap = payload["market_cap_usd"]
    dominance = payload["btc_dominance_pct"]
    change = payload["market_cap_change_24h_pct"]
    vol = payload["volume_24h_usd"]
    caption = (
        "🧪 PUBLICATION TEST #06 — DOMINANCE BITCOIN\n"
        f"₿ BTC.D : {dominance:.2f} %\n"
        f"🌍 Capitalisation totale : {cap / 1e12:.3f} billions USD\n"
        f"📊 Variation sur 24 h : {change:+.2f} %\n"
        f"🔄 Volume 24 h : {vol / 1e9:.1f} milliards USD\n"
        f"{'Mesuré' if payload['source_updated_at'] else 'Consulté'} le {when}\n"
        f"Source : {payload['provider']}\n"
        "⚠️ Données indicatives — pas un conseil en investissement."
    )
    with IMAGE.open("rb") as image:
        try:
            response = requests.post(
                "https://api.telegram.org/bot" + token + "/sendPhoto",
                data={"chat_id": channel["chat_id"], "caption": caption},
                files={"photo": (IMAGE.name, image, "image/png")},
                timeout=(10, 90),
            )
            response.raise_for_status()
        except requests.RequestException:
            raise RuntimeError("Envoi Telegram incertain : ne pas réessayer automatiquement") from None
    try:
        result = response.json()
    except ValueError:
        raise RuntimeError("Réponse Telegram non JSON") from None
    if result.get("ok") is not True:
        raise RuntimeError("Telegram a refusé la publication #06")
    print("DOMINANCE_V2_TEST_PUBLISHED", result.get("result", {}).get("message_id"),
          "channel", channel["username"])


if __name__ == "__main__":
    main()
