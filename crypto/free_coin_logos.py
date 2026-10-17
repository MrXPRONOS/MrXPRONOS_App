"""Free logo resolver: seven independent catalog/CDN routes, verified identities.

Sources: CoinPaprika, CoinGecko, CryptoCompare, CoinCap, DefiLlama,
Trust Wallet assets, and spothq/cryptocurrency-icons.
Never assign logos by ticker alone when names collide. Fail closed if missing.
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
S=requests.Session()
S.headers.update({"User-Agent":"MrXPRONOS/1.0","Accept":"application/json,image/png,image/jpeg,image/webp"})
TIMEOUT=(7,16)

def norm(value):
    return re.sub(r"[^a-z0-9]+","",str(value or "").casefold())

def fetch_json(url,params=None,headers=None):
    response=S.get(url,params=params,headers=headers,timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()

def image(uri):
    if not isinstance(uri,str) or not uri.startswith("https://"):
        raise ValueError("Invalid image URL")
    response=S.get(uri,timeout=TIMEOUT)
    response.raise_for_status()
    if not response.content or len(response.content)>1_000_000:
        raise ValueError("Invalid image size")
    with Image.open(io.BytesIO(response.content)) as im:
        im.load()
        if min(im.size)<24:
            raise ValueError("Image too small")
        im.thumbnail((256,256))
        out=io.BytesIO()
        im.convert("RGBA").save(out,format="PNG")
    return "data:image/png;base64,"+base64.b64encode(out.getvalue()).decode("ascii")

def assign(row,uri,source):
    try:
        row["logo_data_uri"]=image(uri)
        row["logo_source"]=source
        LOG.info("CRYPTO_LOGO_OK %s %s",row["symbol"],source)
        return True
    except (requests.RequestException,ValueError,OSError) as exc:
        LOG.warning("CRYPTO_LOGO_FAILED %s %s %s",row["symbol"],source,type(exc).__name__)
        return False

def pending(rows):
    return [r for r in rows if not r.get("logo_data_uri")]

def index(items):
    result={}
    for item in items:
        if isinstance(item,dict):
            key=(norm(item.get("symbol")),norm(item.get("name") or item.get("CoinName")))
            if all(key):
                result.setdefault(key,[]).append(item)
    return result

def match(row,catalog):
    matches=catalog.get((norm(row["symbol"]),norm(row["name"])),[])
    return matches[0] if len(matches)==1 else None

def catalog_paprika(rows):
    coins=fetch_json("https://api.coinpaprika.com/v1/coins")
    catalog=index([c for c in coins if c.get("is_active",True)])
    for row in pending(rows):
        item=match(row,catalog)
        if not item:continue
        try:
            detail=fetch_json("https://api.coinpaprika.com/v1/coins/"+item["id"])
            if norm(detail.get("symbol"))!=norm(row["symbol"]) or norm(detail.get("name"))!=norm(row["name"]):
                continue
            uri=detail.get("logo") or detail.get("logo_url")
            if uri:assign(row,uri,"CoinPaprika")
        except (requests.RequestException,ValueError,KeyError) as exc:
            LOG.warning("CoinPaprika detail %s %s",row["symbol"],type(exc).__name__)

def catalog_gecko(rows):
    headers={"x-cg-demo-api-key":os.getenv("COINGECKO_DEMO_API_KEY")} if os.getenv("COINGECKO_DEMO_API_KEY") else {}
    coins=fetch_json("https://api.coingecko.com/api/v3/coins/markets",
        {"vs_currency":"usd","order":"market_cap_desc","per_page":250,"page":1,"sparkline":"false"},headers)
    catalog=index(coins)
    for row in pending(rows):
        item=match(row,catalog)
        if item:
            row["_coingecko_id"]=item.get("id")
            if item.get("image"):assign(row,item["image"],"CoinGecko")

def catalog_cryptocompare(rows):
    coins=fetch_json("https://min-api.cryptocompare.com/data/all/coinlist",{"summary":"true"}).get("Data") or {}
    catalog=index([dict(c,name=c.get("CoinName")) for c in coins.values() if isinstance(c,dict)])
    for row in pending(rows):
        item=match(row,catalog)
        if item and str(item.get("ImageUrl","")).startswith("/media/"):
            assign(row,"https://www.cryptocompare.com"+item["ImageUrl"],"CryptoCompare")

def catalog_coincap(rows):
    coins=fetch_json("https://api.coincap.io/v2/assets",{"limit":2000}).get("data") or []
    catalog=index(coins)
    for row in pending(rows):
        item=match(row,catalog)
        if item:
            # CoinCap CDN uses the verified asset symbol.
            assign(row,"https://assets.coincap.io/assets/icons/"+item["symbol"].lower()+"@2x.png","CoinCap")

def catalog_defillama(rows):
    # CoinGecko stable IDs from a full free coin list, matched by name + ticker.
    coins=fetch_json("https://api.coingecko.com/api/v3/coins/list")
    catalog=index(coins)
    for row in pending(rows):
        item=match(row,catalog)
        if item:
            row["_coingecko_id"]=item["id"]
            assign(row,"https://coins.llama.fi/icons/coingecko:"+item["id"],"DefiLlama")

def catalog_trustwallet(rows):
    # TrustWallet images require an actual chain and contract, not a guessed ticker.
    coins=fetch_json("https://api.coingecko.com/api/v3/coins/list",{"include_platform":"true"})
    catalog=index(coins)
    for row in pending(rows):
        item=match(row,catalog)
        if not item:continue
        platforms=item.get("platforms") or {}
        eth=platforms.get("ethereum")
        if eth and re.fullmatch(r"0x[a-fA-F0-9]{40}",str(eth)):
            assign(row,"https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/assets/"+eth+"/logo.png","TrustWallet")

def catalog_spothq(rows):
    # Public repository is ticker-indexed. Require independent exact-name
    # verification against CoinGecko catalog before using any symbol icon.
    coins=fetch_json("https://api.coingecko.com/api/v3/coins/list")
    catalog=index(coins)
    for row in pending(rows):
        if match(row,catalog):
            assign(row,"https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/"+str(row["symbol"]).lower()+".png","spothq")

SOURCES=(("CoinPaprika",catalog_paprika),("CoinGecko",catalog_gecko),
         ("CryptoCompare",catalog_cryptocompare),("CoinCap",catalog_coincap),
         ("DefiLlama",catalog_defillama),("TrustWallet",catalog_trustwallet),
         ("spothq",catalog_spothq))

def enrich_with_logos(rows):
    for name,fn in SOURCES:
        if not pending(rows):break
        try:
            fn(rows)
        except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
            LOG.warning("LOGO_SOURCE_UNAVAILABLE %s %s",name,type(exc).__name__)
    missing=[r["symbol"] for r in pending(rows)]
    if missing:
        raise RuntimeError("Publication V2 annulée : logos réels introuvables pour "+", ".join(missing))
    LOG.info("CRYPTO_LOGOS_COMPLETE %s",[(r["symbol"],r["logo_source"]) for r in rows])
    return rows
