"""Offline-only plausible layout inputs for posters #01/#02/#03.

NEVER used by a production workflow; all dataset providers = QA_SIMULATION.
A fake data producer is separated from every real production exporter.
"""
import json
from pathlib import Path
from datetime import datetime,timezone
from math import sin

DEST=Path("crypto/generated/test")
NOW=datetime.now(timezone.utc).isoformat()
CAP=2_718_295_617_920
VOL=84_134_511_488

def series(base, pct, count=49):
    return [round(base * (1 + pct * i/(count-1)/100 + .002*sin(i)),10) for i in range(count)]

def basic(symbol,name,price,change,rank,volume=30_000_000,extra=False):
    out={"symbol":symbol,"name":name,"rank":rank,
         "price":price,"change":change,"volume":volume,"sparkline":series(price,change)}
    if extra:
        out.update(market_cap_total=CAP,global_volume_24h=VOL,
                   market_cap_change_24h=1.37,fear_greed=53)
    return out

DEST.mkdir(parents=True,exist_ok=True)
fixtures={
 "market_design_data.json":[
    basic("BTC","Bitcoin",81881.70,.59,1,extra=True),
    basic("ETH","Ethereum",2403.93,.12,2),
    basic("SOL","Solana",103.95,.59,5),
    basic("BNB","BNB",721.33,.53,4),
    basic("XRP","XRP",1.30,.66,3)],
 "gainers_v2_data.json":[
    basic("PEPE","Pepe",.000004123456,4.10,43),
    basic("NEAR","Near Protocol",5.0,3.14,37),
    basic("RAIN","Rain Protocol",.009281,3.02,48),
    basic("ARB","Arbitrum",.186249,2.92,51),
    basic("AKE","Akedo",.030872,2.81,85)],
 "losers_v2_data.json":[
    basic("AERO","Aerodrome Finance",.80025,-4.84,75,extra=True),
    basic("PUMP","Pump.fun",.00415,-4.23,64),
    basic("RENDER","Render",1.81,-2.59,65),
    basic("FIL","Filecoin",1.04,-1.86,54),
    basic("LIT","Lighter",3.06,-1.79,86)],
}
for path, rows in fixtures.items():
    (DEST/path).write_text(json.dumps({"timestamp":NOW,"provider":"QA_SIMULATION",
        "status":"offline_fixture","is_demo":True,"rows":rows},indent=2)+"\n",encoding="utf-8")
    print("OFFLINE_LAYOUT_FIXTURE_CREATED_NOT_PUBLISHABLE",path,len(rows))
