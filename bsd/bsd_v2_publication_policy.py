"""Mandatory BSD V2 distribution eligibility (no historical ledger rewrites).

Only PRO or VIP with an announced calibrated confidence >= 79.0% may be
published on the website or distributed as a single/secondary/combo leg.
This is an additional gate; existing V2.1, price, quality, and value
guards remain in force. Historical results remain in the immutable audit.
"""
from __future__ import annotations
from math import isfinite

ALLOWED_CATEGORIES = frozenset(("pro", "vip"))
MIN_CONFIDENCE_PERCENT = 79.0


def confidence_percent(value):
    """Accept the calibrated 0..1 representation or public 0..100 scale."""
    if type(value) not in (int, float) or not isfinite(value) or value < 0:
        return None
    p = value * 100 if value <= 1 else value
    return p if p <= 100 else None


def qualifying_confidence(value):
    p = confidence_percent(value)
    return p is not None and p >= MIN_CONFIDENCE_PERCENT


def eligible_category(category):
    return isinstance(category, str) and category.strip().lower() in ALLOWED_CATEGORIES


def eligible_model_choice(prediction):
    """Raw, unrounded calibrated confidence as displayed by BSD V2."""
    return (isinstance(prediction, dict)
            and eligible_category(prediction.get("category"))
            and isinstance(prediction.get("prediction"), dict)
            and qualifying_confidence(prediction["prediction"].get("probability")))


def eligible_feed_match(match):
    """Never trust an old/stale website JSON for publication or Telegram."""
    return (isinstance(match, dict)
            and eligible_category(match.get("category"))
            and isinstance(match.get("prediction"), dict)
            and qualifying_confidence(match["prediction"].get("confidence")))


def eligible_feed_selection(match, selection):
    return (eligible_feed_match(match) and isinstance(selection, dict)
            and qualifying_confidence(selection.get("confidence")))
