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
    """Real 48h hourly charts; try independent public providers."""
    def valid(values):
        import math
        try:
            values=[float(v) for v in values]
            return values if len(values)>=12 and all(math.isfinite(v) and v>0 for v in values) and max(values)>min(values) else None
        except (ValueError,TypeError):
            return None
    errors=[]
    try:
        response=requests.get("https://min-api.cryptocompare.com/data/v2/histohour",
            params={"fsym":symbol,"tsym":"USD","limit":48},timeout=(8,25))
        response.raise_for_status()
        payload=response.json()
        if payload.get("Response")=="Success":
            candles=(payload.get("Data") or {}).get("Data") or []
            values=valid([c["close"] for c in candles if c.get("close")])
            if values:
                print("CHART_SOURCE",symbol,"CryptoCompare",len(values))
                return values
        errors.append("CryptoCompare empty")
    except (requests.RequestException,ValueError,TypeError,KeyError) as exc:
        errors.append("CryptoCompare "+type(exc).__name__)
    try:
        product=symbol+"-USD"
        response=requests.get("https://api.exchange.coinbase.com/products/"+product+"/candles",
            params={"granularity":3600},timeout=(8,25),
            headers={"User-Agent":"MrXPRONOS/1.0","Accept":"application/json"})
        response.raise_for_status()
        candles=response.json()
        if isinstance(candles,list):
            candles=sorted((c for c in candles if isinstance(c,list) and len(c)>4),key=lambda c:c[0])
            values=valid([c[4] for c in candles[-49:]])
            if values:
                print("CHART_SOURCE",symbol,"Coinbase",len(values))
                return values
        errors.append("Coinbase empty")
    except (requests.RequestException,ValueError,TypeError,KeyError) as exc:
        errors.append("Coinbase "+type(exc).__name__)
    key=(os.getenv("COINGECKO_DEMO_API_KEY") or "").strip()
    if key:
        try:
            coin={"BTC":"bitcoin","ETH":"ethereum","SOL":"solana","BNB":"binancecoin","XRP":"ripple"}[symbol]
            response=requests.get("https://api.coingecko.com/api/v3/coins/"+coin+"/market_chart",
                params={"vs_currency":"usd","days":"2"},
                headers={"x-cg-demo-api-key":key},timeout=(8,25))
            response.raise_for_status()
            prices=response.json().get("prices") or []
            values=valid([p[1] for p in prices if isinstance(p,list) and len(p)>1])
            if values:
                print("CHART_SOURCE",symbol,"CoinGecko",len(values))
                return values
        except (requests.RequestException,ValueError,TypeError,KeyError) as exc:
            errors.append("CoinGecko "+type(exc).__name__)
    print("CHART_UNAVAILABLE",symbol,"; ".join(errors))
    return None

def get_global_metrics():
    """CoinLore global market summary: public, no API key, no paid subscription."""
    response=requests.get("https://api.coinlore.net/api/global/",timeout=(8,25),
        headers={"User-Agent":"MrXPRONOS/1.0","Accept":"application/json"})
    response.raise_for_status()
    raw=response.json()
    if isinstance(raw,list):
        if not raw:raise RuntimeError("CoinLore global: empty response")
        raw=raw[0]
    if not isinstance(raw,dict):
        raise RuntimeError("CoinLore global: invalid format")
    import math
    cap=float(raw["total_mcap"])
    volume=float(raw["total_volume"])
    change=float(raw["mcap_change"])
    if not all(math.isfinite(v) for v in (cap,volume,change)) or cap<=0 or volume<=0 or abs(change)>50:
        raise RuntimeError("CoinLore global: invalid metrics")
    # CoinLore /api/global/ already reports total_mcap and total_volume in USD.
    # Never multiply by 1e9; that silently inflated the Oct 18 posters.
    # Reject impossible orders of magnitude before ANY poster can be published.
    if not (1e11 <= cap <= 1e14 and 1e9 <= volume <= 1e13):
        raise RuntimeError("CoinLore global: USD order of magnitude invalid")
    return {"market_cap_total":cap,"market_cap_change_24h":change,
            "global_volume_24h":volume,"global_metrics_source":"CoinLore"}

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
    if count!=len(chosen):
        raise RuntimeError(f"Publication annulée : seulement {count}/5 graphiques réels disponibles")
    metrics=get_global_metrics()
    chosen[0].update(metrics)
    print("GLOBAL_MARKET_SOURCE",metrics["global_metrics_source"])
    print("GLOBAL_MARKET_CAP_USD",metrics["market_cap_total"])
    print("GLOBAL_MARKET_VOLUME_USD",metrics["global_volume_24h"])
    try:
        fear,observed=fear_index()
        chosen[0]["fear_greed"]=fear
        print("FEAR_GREED_REAL",fear,observed.isoformat())
    except (RuntimeError,ValueError,TypeError):
        print("FEAR_GREED_UNAVAILABLE")
    if "--export-design-json" in sys.argv[1:]:
        import json
        output=Path("crypto/generated/test/market_design_data.json")
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps({"timestamp":now.isoformat(),"provider":provider,"rows":chosen},ensure_ascii=False),encoding="utf-8")
        print("DESIGN_DATA_EXPORT",output)
        return
    path=render_prices_card(chosen,provider,now,Path("crypto/generated/test/prices_real.png"))
    print("REAL_MARKET_PROVIDER",provider)
    print("REAL_CHARTS",count,"of",len(chosen))
    print("REAL_MARKET_IMAGE",path)
    if "--preview-only" in sys.argv[1:]:
        return
    token=(os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    target=(os.getenv("TELEGRAM_TEST_CHAT_ID") or "@predict_mrxp").strip()
    verified=validate_test_channel(target,token)
    trends=", ".join(
        "{}: {} {:.1f}% sur 48h".format(
            r["symbol"],"hausse" if r["sparkline"][-1]>r["sparkline"][0] else "baisse",
            abs((r["sparkline"][-1]/r["sparkline"][0]-1)*100))
        for r in chosen)
    caption=(
        "🧪 TEST RÉEL — COURS DU MARCHÉ CRYPTO\n"
        "📅 "+now.strftime("%d/%m/%Y %H:%M UTC")+"\n"
        "Source cours : "+provider+"\n"
        "Graphiques réels : 5/5 (48 h)\n"
        "Tendances observées : "+trends+"\n"
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
