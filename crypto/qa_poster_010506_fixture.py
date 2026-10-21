"""QA-only fixture for visual comparisons #01: deliberately opposite 24h/48h signs.

Never a production source: QA_SIMULATION triggers a visible red warning ribbon.
"""
import json
import math
from pathlib import Path
from datetime import datetime,timezone

PATH=Path("crypto/generated/test/market_design_data.json")
base={
 "BTC":("Bitcoin",81827.52,.97,1.014,"CryptoCompare"),
 "ETH":("Ethereum",2389.05,.53,.968,"Coinbase"),
 "SOL":("Solana",103.64,1.54,.955,"Coinbase"),
 "BNB":("BNB",725.01,1.68,1.019,"Coinbase"),
 "XRP":("XRP",1.294,1.77,.963,"CryptoCompare"),
}
rows=[]
for symbol,(name,price,change,ratio,source) in base.items():
    # Exactly 49 historical samples: 48 one-hour intervals.
    # Smooth deterministic undulations, never to be marked as actual market data.
    points=[round(price*(1+(ratio-1)*i/48)*(1+0.003*math.sin(i*.34)),8)
            for i in range(49)]
    rows.append({"symbol":symbol,"name":name,"price":price,"change":change,
                 "sparkline":points,"sparkline_source":source})
rows[0].update(market_cap_total=2_738_100_000_000,
               global_volume_24h=103_810_000_000,
               market_cap_change_24h=2.48,
               global_metrics_source="CoinLore",
               fear_greed=59)
payload={"provider":"QA_SIMULATION","timestamp":datetime.now(timezone.utc).isoformat(),
         "rows":rows}
PATH.parent.mkdir(parents=True,exist_ok=True)
PATH.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("MARKET_QA_FAKE_CHARTS_UNAMBIGUOUSLY_WATERMARKED",PATH)
