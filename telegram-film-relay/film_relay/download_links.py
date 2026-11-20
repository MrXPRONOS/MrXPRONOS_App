"""Resolve GitHub-controlled CinéX links from Cloudflare D1.

The GitHub toggle is synchronized to bot_settings; no Cine Radar owner-screen
approval is required. Technical library/rights/bot/scan checks remain mandatory.
"""
from __future__ import annotations
import hashlib
import logging
import os
import re
from functools import lru_cache

from .episode_identity import canonical_title, series_title

LOG=logging.getLogger("cinex.download_links")
TOKEN=re.compile(r"^[a-zA-Z0-9_-]{24}$")
ID=re.compile(r"^[a-z0-9]{32}$")


def title_key(category: str, title: str) -> str | None:
    if category not in {"series","action"}:
        return None
    value=canonical_title(series_title(title) if category == "series" else title)
    if not value or len(value)<3:
        return None
    return hashlib.sha256((category+"\0"+value).encode()).hexdigest()[:32]


@lru_cache(maxsize=256)
def approved_download_url(category: str, title: str, season: int = 0) -> str | None:
    key=title_key(category,title)
    if not key or not isinstance(season,int) or not 0<=season<=50:
        return None
    token=os.getenv("CLOUDFLARE_API_TOKEN") or os.getenv("CF_API_TOKEN")
    account=os.getenv("CLOUDFLARE_ACCOUNT_ID")
    db=os.getenv("CINERADAR_D1_DATABASE_ID")
    if not token or not account or not db:
        return None
    try:
        import requests
        sql=("""
        SELECT l.token FROM cine_delivery_links l
        JOIN cine_delivery_titles t ON t.title_key=l.title_key
        JOIN cine_delivery_libraries b ON b.category=l.category
        WHERE l.title_key=? AND l.category=? AND l.season_key=?
          AND l.enabled=1 AND t.rights_attested=1
          AND b.rights_attested=1 AND b.bot_access='verified'
          AND b.owner_access='verified'
          AND EXISTS (SELECT 1 FROM cine_delivery_media m WHERE m.category=l.category AND m.title_key=l.title_key AND m.observed_at=b.last_scanned_at AND m.availability IN ('pending_review','approved') AND COALESCE(m.season_number,0)=l.season_key)
          AND EXISTS (SELECT 1 FROM bot_settings WHERE setting_key='cine_delivery_enabled' AND value='1')
        LIMIT 1
        """)
        r=requests.post(
            f"https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{db}/query",
            headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"},
            json={"sql":sql,"params":[key,category,season]},
            timeout=8,
        )
        if not r.ok:
            return None
        obj=r.json()
        if not obj.get("success",False):
            return None
        data=(obj.get("result") or [{}])[0].get("results") or []
        candidate=str(data[0].get("token","")) if data else ""
        if not TOKEN.fullmatch(candidate):
            return None
        return "https://t.me/CineRadarFr_Bot?start=d_"+candidate
    except Exception as exc:
        LOG.warning("Lien de téléchargement non disponible (%s)",type(exc).__name__)
        return None
