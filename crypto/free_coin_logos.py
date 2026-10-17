"""Resolve real crypto logos from free CryptoCompare coin catalog for selected movers.

No API key, no third-party plugin. Logos are downloaded once per render, checked
as actual raster images, and embedded as data URIs in the JSON export.
"""
from __future__ import annotations
import base64
import io
import logging
from urllib.parse import urlparse
import requests
from PIL import Image

LOG=logging.getLogger(__name__)
CATALOG="https://min-api.cryptocompare.com/data/all/coinlist"
BASE="https://www.cryptocompare.com"
SESSION=requests.Session()
SESSION.headers.update({"User-Agent":"MrXPRONOS/1.0","Accept":"application/json,image/png,image/jpeg,image/webp"})

def enrich_with_logos(rows):
    try:
        response=SESSION.get(CATALOG,params={"summary":"true"},timeout=(8,25))
        response.raise_for_status()
        payload=response.json()
        catalog=payload.get("Data") or {}
        if not isinstance(catalog,dict):
            raise ValueError("Invalid CryptoCompare catalog")
    except (requests.RequestException,ValueError,TypeError) as exc:
        LOG.warning("CryptoCompare logo catalog unavailable: %s",type(exc).__name__)
        catalog={}
    for row in rows:
        symbol=str(row["symbol"]).upper()
        info=catalog.get(symbol) or {}
        # Symbols can collide: verify name when catalog provides one.
        source_name=str(info.get("CoinName") or "").strip().casefold()
        row_name=str(row.get("name") or "").strip().casefold()
        if source_name and row_name and source_name!=row_name and source_name not in row_name and row_name not in source_name:
            LOG.warning("Logo name mismatch %s: %s != %s",symbol,source_name,row_name)
            continue
        path=info.get("ImageUrl") or ""
        if not isinstance(path,str) or not path.startswith("/media/"):
            continue
        url=BASE+path
        try:
            response=SESSION.get(url,timeout=(8,20))
            response.raise_for_status()
            if len(response.content)>1_000_000:
                raise ValueError("Oversized logo")
            with Image.open(io.BytesIO(response.content)) as image:
                image.load()
                if image.width<24 or image.height<24:
                    raise ValueError("Tiny logo")
                image.thumbnail((256,256))
                output=io.BytesIO()
                image.convert("RGBA").save(output,format="PNG")
            row["logo_data_uri"]="data:image/png;base64,"+base64.b64encode(output.getvalue()).decode("ascii")
            row["logo_source"]="CryptoCompare"
            LOG.info("CRYPTO_LOGO_OK %s",symbol)
        except (requests.RequestException,OSError,ValueError) as exc:
            LOG.warning("CRYPTO_LOGO_UNAVAILABLE %s: %s",symbol,type(exc).__name__)
    return rows
