"""Only publish crypto #02 V2 to the approved test Telegram channel."""
import os
from pathlib import Path
import requests
from scripts.telegram_test_guard import validate_test_channel

def main():
    token=(os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    verified=validate_test_channel("@predict_mrxp",token)
    path=Path("crypto/generated/test/gainers_v2.png")
    if not path.is_file() or path.stat().st_size<10000:
        raise RuntimeError("Missing valid gainers V2 PNG")
    caption=("🧪 TEST PUBLICATION 02 — TOP 5 DES HAUSSES CRYPTO\n"
             "Classement réel des hausses sur 24 h parmi les 100 premières cryptos.\n"
             "Nouveau design V2 — ancien visuel conservé.\n"
             "⚠️ Canal de test uniquement, données indicatives.")
    with path.open("rb") as image:
        try:
            response=requests.post("https://api.telegram.org/bot"+token+"/sendPhoto",
                data={"chat_id":verified["chat_id"],"caption":caption},
                files={"photo":(path.name,image,"image/png")},timeout=(10,90))
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError("Telegram delivery uncertain; no automatic retry") from exc
    payload=response.json()
    if not payload.get("ok"):raise RuntimeError("Telegram rejected gainers V2")
    print("GAINERS_V2_TEST_PUBLISHED",payload.get("result",{}).get("message_id"))

if __name__=="__main__":main()
