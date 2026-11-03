"""User-facing Mr XPRONOS tier names; never imply mathematical certainty.

Ultra Safe: existing verified publication policy Pro/VIP (>=79%).
Safe: distinct model-only market analysis with 1.30 < indicated odds <=1.50.
Cotes 1,50+: distinct model-only analysis with indicated odds >1.50.
The latter two are analyses, not Pro/VIP recommended tickets.
"""
from __future__ import annotations
from math import isfinite

ULTRA="ultra"
SAFE="safe"
COTES15="cotes15"
MIN_SAFE_ODDS=1.30
MAX_SAFE_ODDS=1.50
MAX_ANALYSIS_ODDS=2.00

LABELS={ULTRA:"ULTRA SAFE",SAFE:"SAFE",COTES15:"COTES 1,50+"}
HEADLINES={ULTRA:"ULTRA SAFE DU JOUR",SAFE:"SAFE DU JOUR",COTES15:"COTES 1,50+ DU JOUR"}

def tier_for_price(price):
    if type(price) not in (float,int) or not isfinite(float(price)):
        return None
    if MIN_SAFE_ODDS<float(price)<=MAX_SAFE_ODDS:return SAFE
    if MAX_SAFE_ODDS<float(price)<=MAX_ANALYSIS_ODDS:return COTES15
    return None

def tier_for_record(row):
    if not isinstance(row,dict):return None
    if row.get("analysis_only") is True:
        if row.get("recommendation_eligible") is not False:
            return None
        return tier_for_price(row.get("odds"))
    if (row.get("category") in ("pro","vip") and
        row.get("recommendation_eligible") is True and
        (row.get("prediction") or {}).get("recommendation_eligible") is True):
        return ULTRA
    return None

def public_category_title(tier,*,night=False):
    if tier not in HEADLINES:raise ValueError("Unknown visitor tier")
    if night:return "🌙 "+HEADLINES[tier].replace("DU JOUR","DE LA NUIT")
    return HEADLINES[tier]
