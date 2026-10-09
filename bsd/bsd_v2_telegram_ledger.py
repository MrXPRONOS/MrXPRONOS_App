"""Immutable Telegram publication snapshots and ledger update helpers."""
from __future__ import annotations
import json
from datetime import datetime, timezone

SINGLE="bsd_v2_hourly"
COMBO="bsd_v2_combo_hourly"

def snapshot(match, *, combo=False):
    if combo:
        legs=match.get("legs") or []
        if len(legs)!=2:raise ValueError("Exactly two combo legs")
        return {"version":1,"type":"combo","combined_odds":match.get("combined_odds"),
                "legs":[snapshot(leg) for leg in legs],"id":match.get("id")}
    pick=match.get("prediction") or {}
    if not pick.get("selection_key"):raise ValueError("Missing original market")
    return {"version":1,"type":"single","id":str(match["id"]),
            "event_date":match["event_date"],"date":match["date"],
            "home_team":match.get("home_team"),"away_team":match.get("away_team"),
            "home_logo":match.get("home_logo"),"away_logo":match.get("away_logo"),
            "league":match.get("league"),"league_logo":match.get("league_logo"),
            "source":"bsd","prediction":dict(pick)}

def selection_for_result(original):
    if not isinstance(original,dict):return None
    if original.get("type")=="single" and original.get("prediction",{}).get("selection_key"):
        return dict(original)
    return None

def normalized_ref(row):
    ref=str(row.get("ref_id") or "")
    chat,sep,suffix=ref.rpartition(":bsd:")
    ident,separator,market=suffix.partition(":")
    if sep and chat and ident.isdigit():
        return chat,ident,market if separator else ""
    return None

def pending_records(session,base,key,kind,*,limit=500,max_pages=30):
    """Read all unresolved entries; no expiring 10-day cutoff."""
    rows=[]
    for page in range(max_pages):
        response=session.get(base.rstrip("/")+"/rest/v1/telegram_sent",
            headers={"apikey":key,"Authorization":"Bearer "+key},
            params={"select":"*","kind":"eq."+kind,"validation_sent":"eq.false",
                    "order":"ref_date.asc,id.asc","limit":limit,"offset":page*limit},
            timeout=30)
        response.raise_for_status()
        page_rows=response.json()
        if not isinstance(page_rows,list):raise RuntimeError("Invalid Supabase settlement page")
        rows.extend(page_rows)
        if len(page_rows)<limit:return rows
    raise RuntimeError("Pending ledger pagination exceeded: review old entries")
