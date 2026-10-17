"""Test réel unique du visuel marché vers @predict_mrxp (aucune publication de production)."""
from __future__ import annotations
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import requests
from crypto.publish_crypto_1_5 import market, selected_watch, fear_index
from crypto.render_premium_cards import render_prices_card
from scripts.telegram_test_guard import validate_test_channel

def get_sparkline(symbol):
    """48 heures réelles via CryptoCompare; aucune courbe inventée en cas d'échec."""
    try:
        response = requests.get(
            "https://min-api.cryptocompare.com/data/v2/histohour",
            params={"fsym":symbol,"tsym":"USD","limit":48},
            timeout=(8,25),
        )
        response.raise_for_status()
        payload=response.json()
        if payload.get("Response") != "Success":
            return None
        candles=(payload.get("Data") or {}).get("Data") or []
        points=[float(c["close"]) for c in candles if c.get("close") is not None]
        return points if len(points)>=12 else None
    except (requests.RequestException,ValueError,TypeError,KeyError):
        return None

def main():
    now=datetime.now(timezone.utc)
    rows,provider=market()
    chosen=selected_watch(rows)
    count=0
    for row in chosen:
        points=get_sparkline(row["symbol"])
        if points:
            row["sparkline"]=points
            count+=1
    try:
        fear,observed=fear_index()
        chosen[0]["fear_greed"]=fear
        print("FEAR_GREED_REAL",fear,observed.isoformat())
    except (RuntimeError,ValueError,TypeError):
        print("FEAR_GREED_UNAVAILABLE")
    path=render_prices_card(chosen,provider,now,Path("crypto/generated/test/prices_real.png"))
    print("REAL_MARKET_PROVIDER",provider)
    print("REAL_CHARTS",count,"of",len(chosen))
    print("REAL_MARKET_IMAGE",path)
    if "--preview-only" in sys.argv[1:]:
        return
    token=(os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    target=(os.getenv("TELEGRAM_TEST_CHAT_ID") or "@predict_mrxp").strip()
    verified=validate_test_channel(target,token)
    caption=(
        "🧪 TEST RÉEL — COURS DU MARCHÉ CRYPTO\n"
        "📅 "+now.strftime("%d/%m/%Y %H:%M UTC")+"\n"
        "Source cours : "+provider+"\n"
        "Courbes réelles disponibles : "+str(count)+"/5 (CryptoCompare, 48 h)\n"
        "⚠️ Canal de test uniquement. Données indicatives, pas un conseil d'investissement."
    )
    with path.open("rb") as fp:
        try:
            response=requests.post(
                "https://api.telegram.org/bot"+token+"/sendPhoto",
                data={"chat_id":verified["chat_id"],"caption":caption},
                files={"photo":(path.name,fp,"image/png")},
                timeout=(10,90),
            )
            response.raise_for_status()
            data=response.json()
            if not data.get("ok"):
                raise RuntimeError("Telegram refused photo")
        except requests.RequestException:
            raise RuntimeError("Envoi Telegram incertain, ne pas retenter automatiquement") from None
    print("REAL_TEST_TELEGRAM_PUBLISHED",data.get("result",{}).get("message_id"))

if __name__=="__main__":
    main()
