"""Safe fallback when a qualified primary selection has no publishable quote.

The ranking is calculated BEFORE any odds. When a primary *indicative*
quote is unavailable (typically below 1.20), walk ONLY previously ranked
and quality-approved alternatives. Every alternative must pass the very same
Pro/VIP 79%, V2.1, quote and value gates. No real quote is replaced by a
model quote for the same market. Immutable published picks are not touched.
"""
from __future__ import annotations

from bsd_v2_core import classify_quality_category
from bsd_v2_estimated_odds import price_selected_market,ESTIMATED_SOURCE
from bsd_v2_publication_policy import eligible_model_choice
from bsd_v2_guardrails import v21_accept_priced,post_price_value_guard

def try_next_qualified_market(prediction,quotes,*,now,tracker=None,league_market=None):
    """Return (priced_choice, category, attempts) or (None,None,attempts).

    A candidate's published market is not inferred from its price. It is
    taken exclusively from the football-ranked options already validated
    by predict_v2() before any quote is supplied.
    """
    diagnostics=[]
    selected=(prediction.get('prediction') or {}).get('key')
    features=prediction.get('estimated_goals') or {}
    options=prediction.get('ranked_candidates') or []
    for item in options:
        if not isinstance(item,dict) or item.get('key')==selected:
            continue
        key=item.get('key')
        if item.get('passes_quality_policy') is not True:
            diagnostics.append({'key':key,'reason':'football_quality_rejected'})
            continue
        conservative=item.get('conservative_probability')
        probability=item.get('probability')
        if type(conservative) not in (int,float) or type(probability) not in (int,float):
            diagnostics.append({'key':key,'reason':'missing_calibrated_probability'})
            continue
        category=classify_quality_category(float(conservative),features)
        candidate={'key':key,'name':item.get('name') or key,
                   'market':item.get('market'),'outcome':item.get('outcome'),
                   'line':item.get('line'),'internal_market_code':item.get('market_code'),
                   'probability':probability,
                   'conservative_probability':conservative,
                   'calibration_samples':item.get('calibration_samples'),
                   'fair_odds':item.get('fair_odds')}
        if not eligible_model_choice({'category':category,'prediction':candidate}):
            diagnostics.append({'key':key,'reason':'category_or_confidence_below_79'})
            continue
        chosen=price_selected_market(candidate,quotes,now=now)
        if chosen is None:
            diagnostics.append({'key':key,'reason':'no_publishable_quote'})
            continue
        if chosen.get('odds',0)<1.20:
            diagnostics.append({'key':key,'reason':'below_120'})
            continue
        group=(league_market or {}).get(str(key))
        ok,reason=v21_accept_priced(chosen,tracker,group)
        if not ok:
            diagnostics.append({'key':key,'reason':reason})
            continue
        guard=post_price_value_guard(chosen)
        if not guard['passed']:
            diagnostics.append({'key':key,'reason':guard['reason']})
            continue
        diagnostics.append({'key':key,'reason':'passed_fallback_all_guards',
                            'price_source':chosen['odds_source']})
        return chosen,category,diagnostics
    return None,None,diagnostics
