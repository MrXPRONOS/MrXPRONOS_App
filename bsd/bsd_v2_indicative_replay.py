"""Counterfactual BSD V2 publication gates with *model-indicative* odds.

Reuse actual site pricing, publication tier and V2.1 acceptance. Never identify
model-derived prices as bookmaker evidence. No change to production output.
"""
from __future__ import annotations
from datetime import datetime
from bsd_v2_estimated_odds import price_selected_market, valid_standalone_prediction, ESTIMATED_SOURCE
from bsd_v2_publication_policy import eligible_model_choice
from bsd_v2_guardrails import v21_accept_priced,post_price_value_guard,v21_signal_tier
from bsd_v2_core import classify_quality_category

def model_only_publication(model_prediction, *, now, tracker=None, league_market=None):
    """Check the original production pipeline after a football market was chosen.

    Returns (result, reason). This does not select another market when pricing
    rejects the chosen one: production locks a chosen market before pricing.
    """
    if not eligible_model_choice(model_prediction):
        return None,"category_or_confidence_below_79"
    football=model_prediction["prediction"]
    quote=price_selected_market(football, {}, now=now)
    if quote is None:
        return None,"chosen_market_unpriceable"
    if quote.get("odds_source")!=ESTIMATED_SOURCE:
        return None,"not_model_indicative"
    ok,reason=v21_accept_priced(quote,tracker,league_market)
    if not ok:return None,reason
    guard=post_price_value_guard(quote)
    if not guard["passed"]:
        return None,guard["reason"]
    if float(quote["bookmaker_odds"])<1.20:
        return None,"quote_below_120"
    pick={**quote,"selection_key":quote["key"]}
    if not valid_standalone_prediction(pick,False):
        return None,"invalid_standalone_prediction"
    return {
        "key":quote["key"],"market_code":quote.get("internal_market_code") or quote.get("market_code"),
        "probability":quote["probability"],"conservative_probability":quote["conservative_probability"],
        "odds":quote["odds"],"odds_source":quote["odds_source"],
        "estimated_odds":quote["estimated_odds"],
        "tier":v21_signal_tier(quote),"category":model_prediction["category"],
        "odds_method":quote.get("odds_method"),
        "overround_assumption":quote.get("overround_assumption"),
        "post_price_value_guard":guard["reason"],
    },"published_model_indicative"

def experimental_model_prediction(c, calibrated, conservative, features):
    """Adapt a validated new binary selection to the site's publication shape.

    Conservative adjustment is research-calibrated, and MUST remain tagged
    experimental rather than claiming exact equivalence to legacy V2 policies.
    """
    category=classify_quality_category(conservative,features)
    return {"category":category,
            "prediction":{"key":c.key,
                          "internal_market_code":c.market_code,
                          "market_code":c.market_code,
                          "probability":round(float(calibrated),6),
                          "conservative_probability":round(float(conservative),6)}}
