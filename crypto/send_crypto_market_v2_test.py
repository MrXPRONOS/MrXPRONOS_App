"""Send only V2 crypto design to verified Telegram test channel."""
import os
from pathlib import Path
import requests
from scripts.telegram_test_guard import validate_test_channel

def main():
    token=(os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    target=(os.getenv("TELEGRAM_TEST_CHAT_ID") or "@predict_mrxp").strip()
    verified=validate_test_channel(target,token)
    path=Path("crypto/generated/test/prices_v2.png")
    if not path.is_file() or path.stat().st_size<10000:
        raise RuntimeError("V2 PNG absent or incomplete; no publication")
    caption=("🧪 TEST DESIGN V2 — COURS DU MARCHÉ CRYPTO\n"
             "Nouvelle conception HTML/CSS/SVG + Playwright.\n"
             "Données de marché réelles, 5 courbes historiques, capitalisation et volume mondiaux.\n"
             "Comparaison avec la version V1 (conservée).\n"
             "⚠️ TEST UNIQUEMENT — aucune publication en production.")
    with path.open("rb") as fp:
        try:
            r=requests.post("https://api.telegram.org/bot"+token+"/sendPhoto",
                data={"chat_id":verified["chat_id"],"caption":caption},
                files={"photo":(path.name,fp,"image/png")},timeout=(10,90))
            r.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError("Envoi Telegram incertain, ne pas retenter automatiquement") from exc
    payload=r.json()
    if not payload.get("ok"):raise RuntimeError("Telegram refused V2 photo")
    print("V2_TEST_ONLY_PUBLISHED",payload.get("result",{}).get("message_id"))

if __name__=="__main__":main()
