"""Test volontaire #07 : envoi exclusivement vers @predict_mrxp, données réelles."""
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import requests
from crypto.export_weekly_v2 import validate_real
from scripts.telegram_test_guard import validate_test_channel

DATA=Path("crypto/generated/test/weekly_v2_data.json")
IMAGE=Path("crypto/generated/test/weekly_v2.png")

def main():
    if not DATA.is_file() or not IMAGE.is_file() or IMAGE.stat().st_size < 10000:
        raise RuntimeError("Affiche réelle absente : pas d'envoi")
    d=json.loads(DATA.read_text(encoding="utf-8"))
    validate_real(d)
    token=(os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    target=validate_test_channel("@predict_mrxp",token)
    collected=datetime.fromisoformat(d["collected_at"]).astimezone(timezone.utc)
    fmt=lambda n:("+" if n>0 else "")+f"{n:.2f} %"
    caption=(
        "🧪 TEST #07 — BILAN CRYPTO DE LA SEMAINE\n"
        f"📆 7 jours glissants • {collected:%d/%m/%Y %H:%M} UTC\n"
        f"₿ Bitcoin : {fmt(d['btc']['change_7d'])} sur 7 j\n"
        f"Ξ Ethereum : {fmt(d['eth']['change_7d'])} sur 7 j\n"
        f"🌍 Capitalisation actuelle : {d['market_cap_usd']/1e12:.2f} billions USD\n"
        f"📊 Dominance BTC actuelle : {d['btc_dominance_pct']:.2f} %\n"
        f"🧠 Sentiment : {d['fear']['score']}/100 ({d['fear']['delta_7d']:+d} points en 7 j)\n"
        f"Sources : {d['provider']} et Alternative.me.\n"
        "⚠️ Données indicatives, aucun conseil en investissement."
    )
    with IMAGE.open("rb") as img:
        try:
            response=requests.post("https://api.telegram.org/bot"+token+"/sendPhoto",
                data={"chat_id":target["chat_id"],"caption":caption},
                files={"photo":(IMAGE.name,img,"image/png")},timeout=(10,90))
            response.raise_for_status()
        except requests.RequestException:
            raise RuntimeError("Envoi Telegram incertain : ne pas relancer automatiquement") from None
    try: answer=response.json()
    except ValueError: raise RuntimeError("Réponse Telegram invalide") from None
    if answer.get("ok") is not True:raise RuntimeError("Telegram a refusé le n°07")
    print("WEEKLY_07_TEST_SENT",answer.get("result",{}).get("message_id"),target["username"])

if __name__=="__main__":main()
