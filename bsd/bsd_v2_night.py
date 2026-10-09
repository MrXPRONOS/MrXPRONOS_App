"""Calendrier des coupons nuit MR XPRONOS (heures locales du Togo = UTC).

Un soir D, les matchs compris dans [D 21:00, D+1 05:00] constituent
la campagne 'Coupons nuit' diffusée entre D 20:00 et D 20:59.
Les horaires sont comparés en UTC : aucun déplacement à la date de KO.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from bsd_h2h import _utc

NIGHT_START=21
NIGHT_END=5
NIGHT_BATCH_HOUR=20

def _dt(value):
    if isinstance(value,datetime):
        if value.tzinfo is None:
            raise ValueError("Naive datetime forbidden for night coupons")
        return value.astimezone(timezone.utc)
    return _utc(value)

def night_date(value):
    """Date du soir de rattachement ; 05:00 inclus, 05:00:01 exclu."""
    dt=_dt(value)
    if dt.hour>=NIGHT_START:
        return dt.date()
    if dt.hour<NIGHT_END or (dt.hour==NIGHT_END and
                               dt.minute==0 and dt.second==0 and dt.microsecond==0):
        return (dt-timedelta(days=1)).date()
    return None

def batch_date(now):
    """Autorise 20h00–20h59 pour rattraper un runner GitHub en retard."""
    dt=_dt(now)
    return dt.date() if dt.hour==NIGHT_BATCH_HOUR else None

def is_night_match(match):
    try:
        return night_date(match["event_date"]) is not None
    except (KeyError,TypeError,ValueError):
        return False

def matches_for_night(matches,now):
    evening=batch_date(now)
    if evening is None:
        return []
    selected=[]
    for match in matches:
        if not isinstance(match,dict) or match.get("source")!="bsd":
            continue
        if match.get("status") not in ("notstarted","upcoming"):
            continue
        try:
            ko=_dt(match["event_date"])
        except (KeyError,TypeError,ValueError):
            continue
        if night_date(ko)==evening and ko>_dt(now):
            selected.append(match)
    return sorted(selected,key=lambda m:(_dt(m["event_date"]),str(m.get("id",""))))
