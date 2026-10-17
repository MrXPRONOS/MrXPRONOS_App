"""Free crypto logo resolution by exact asset identity, not ambiguous symbol alone.

Use CoinPaprika coin metadata and CoinGecko market images as fallbacks.
Only verified real raster images are embedded; incomplete batches cannot publish.
"""
from __future__ import annotations
import base64
import io
import logging
import os
import re
import requests
from PIL import Image

LOG=logging.getLogger(__name__)
SESSION=requests.Session()
SESSION.headers.update({"User-Agent":"MrXPRONOS/1.0","Accept":"application/json,image/png,image/jpeg,image/webp"})
TIMEOUT=(8,22)

def _normalize(s):
    return re.sub(r"[^a-z0-9]+","",str(s or "").casefold())

def _image(uri):
    if not isinstance(uri,str) or not uri.startswith("https://"):
        return None
    response=SESSION.get(uri,timeout=TIMEOUT)
    response.raise_for_status()
    if len(response.content)>1_000_000 or not response.content:
        raise ValueError("Logo too large or empty")
    with Image.open(io.BytesIO(response.content)) as im:
        im.load()
        if min(im.size)<24:
            raise ValueError("Logo too small")
        im.thumbnail((256,256))
        out=io.BytesIO()
        im.convert("RGBA").save(out,format="PNG")
    return "data:image/png;base64,"+base64.b64encode(out.getvalue()).decode("ascii")

def enrich_with_logos(rows):
    # CoinPaprika has stable IDs and free per-coin metadata with logo URLs.
    try:
        res=SESSION.get("https://api.coinpaprika.com/v1/coins",timeout=TIMEOUT)
        res.raise_for_status()
        catalog=res.json()
        if not isinstance(catalog,list):
            raise ValueError("Invalid CoinPaprika catalog")
    except (requests.RequestException,ValueError) as exc:
        LOG.warning("CoinPaprika logo catalog unavailable: %s",type(exc).__name__)
        catalog=[]
    candidates={}
    for item in catalog:
        if not isinstance(item,dict) or not item.get("is_active",True):
            continue
        key=(_normalize(item.get("symbol")),_normalize(item.get("name")))
        candidates.setdefault(key,[]).append(item)
    for row in rows:
        key=(_normalize(row.get("symbol")),_normalize(row.get("name")))
        options=candidates.get(key,[])
        # Exact symbol AND exact name, no guessing for ticker collisions.
        if len(options)==1:
            coin_id=options[0]["id"]
            try:
                response=SESSION.get("https://api.coinpaprika.com/v1/coins/"+coin_id,timeout=TIMEOUT)
                response.raise_for_status()
                detail=response.json()
                if _normalize(detail.get("symbol"))!=key[0] or _normalize(detail.get("name"))!=key[1]:
                    raise ValueError("Identity mismatch")
                uri=detail.get("logo") or detail.get("logo_url")
                if uri:
                    row["logo_data_uri"]=_image(uri)
                    row["logo_source"]="CoinPaprika"
                    LOG.info("CRYPTO_LOGO_OK %s CoinPaprika",row["symbol"])
                    continue
            except (requests.RequestException,ValueError,OSError) as exc:
                LOG.warning("CoinPaprika logo unavailable for %s: %s",row["symbol"],type(exc).__name__)
    # CoinGecko provides image URLs directly in its /coins/markets response.
    missing=[r for r in rows if not r.get("logo_data_uri")]
    if missing:
        try:
            key=(os.getenv("COINGECKO_DEMO_API_KEY") or "").strip()
            headers={"x-cg-demo-api-key":key} if key else {}
            res=SESSION.get("https://api.coingecko.com/api/v3/coins/markets",
                params={"vs_currency":"usd","order":"market_cap_desc","per_page":250,"page":1,"sparkline":"false"},
                headers=headers,timeout=TIMEOUT)
            res.raise_for_status()
            coins=res.json()
            if not isinstance(coins,list):
                raise ValueError("Invalid CoinGecko response")
            by_key={}
            for coin in coins:
                by_key.setdefault((_normalize(coin.get("symbol")),_normalize(coin.get("name"))),[]).append(coin)
            for row in missing:
                matches=by_key.get((_normalize(row.get("symbol")),_normalize(row.get("name"))),[])
                if len(matches)!=1 or not matches[0].get("image"):
                    continue
                try:
                    row["logo_data_uri"]=_image(matches[0]["image"])
                    row["logo_source"]="CoinGecko"
                    LOG.info("CRYPTO_LOGO_OK %s CoinGecko",row["symbol"])
                except (requests.RequestException,ValueError,OSError) as exc:
                    LOG.warning("CoinGecko image unavailable %s: %s",row["symbol"],type(exc).__name__)
        except (requests.RequestException,ValueError) as exc:
            LOG.warning("CoinGecko logo fallback unavailable: %s",type(exc).__name__)
    missing=[r["symbol"] for r in rows if not r.get("logo_data_uri")]
    if missing:
        raise RuntimeError("Publication V2 annulée : logos réels introuvables pour "+", ".join(missing))
    return rows
