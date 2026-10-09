"""Prix indicatifs Mr XPRONOS, jamais des cotes proposées par un bookmaker.

Probabilités calibrées BSD V2 -> cote équitable -> ajustement d'overround.
Lorsque BSD propose des marchés complets 1X2 / BTTS / over-under,
leur overround sert de référence locale; sinon hypothèse prudente de 6 %.
Ce module NE prétend ni reproduire les prix réels, ni garantir une mise.
"""
from __future__ import annotations

from math import isfinite
from statistics import median

ESTIMATED_SOURCE = "mrxpronos_model"
VERIFIED_SOURCES = frozenset(("bsd_consensus", "bsd_bookmaker"))
DEFAULT_OVERROUND = 0.06
MIN_STANDALONE_ODDS = 1.20


def _real_quote(entry):
    if not isinstance(entry, dict) or entry.get("origin") not in VERIFIED_SOURCES:
        return None
    val = entry.get("odds")
    if type(val) not in (int, float) or not isfinite(val):
        return None
    return float(val) if 1.01 <= val <= 100 else None


def reference_overround(quotes):
    """Ne calcule l'overround que sur des issues mutuellement exclusives complètes."""
    if not isinstance(quotes, dict):
        return DEFAULT_OVERROUND, "hypothese_6pct"
    groups = [
        ("1X2_HOME_FT", "1X2_DRAW_FT", "1X2_AWAY_FT"),
        ("BTTS_YES_FT", "BTTS_NO_FT"),
        *(("OU_%.1f_OVER_FT" % n, "OU_%.1f_UNDER_FT" % n)
          for n in (1.5, 2.5, 3.5, 4.5)),
    ]
    margins = []
    for group in groups:
        prices = [_real_quote(quotes.get(code)) for code in group]
        if any(price is None for price in prices):
            continue
        overround = sum(1.0 / x for x in prices) - 1
        if isfinite(overround) and 0.01 <= overround <= 0.20:
            margins.append(overround)
    if margins:
        # Exclure les valeurs marginales aberrantes et limiter l'ajustement.
        return max(0.02, min(0.12, median(margins))), "bsd_marches_complets"
    return DEFAULT_OVERROUND, "hypothese_6pct"


def estimated_quote(candidate_row, quotes, *, now=None):
    """Renvoie None si les données probabilistes ne permettent pas de prix sûr."""
    if not isinstance(candidate_row, dict):
        return None
    p = candidate_row.get("probability")
    conservative = candidate_row.get("conservative_probability")
    if type(p) not in (int, float) or type(conservative) not in (int, float):
        return None
    if not (isfinite(p) and isfinite(conservative) and
            0.70 <= p <= 0.99 and 0.50 <= conservative <= p):
        return None
    if candidate_row.get("key") in ("UNDER_45", None, ""):
        return None
    code = candidate_row.get("market_code")
    # Ne jamais inventer une meilleure cote pour un marché déjà coté par BSD,
    # même si sa cote réelle a été refusée comme trop basse.
    if code in (quotes or {}) and _real_quote(quotes[code]) is not None:
        return None
    margin, origin = reference_overround(quotes)
    fair = 1.0 / p
    # Cote calculée pour le marché CHOISI, sans sélectionner un autre pari.
    # Réduire la marge si 6 % ferait tomber une issue très probable sous 1.01.
    # Ne jamais relever artificiellement un prix au-dessus de sa cote équitable.
    margin = min(margin, max(0.0, (1.0 / (1.20 * p)) - 1.0))
    price = round(1.0 / (p * (1.0 + margin)), 3)
    if not (MIN_STANDALONE_ODDS <= price <= 100 and price <= fair):
        return None
    return {
        "odds": price,
        "origin": ESTIMATED_SOURCE,
        "updated_at": now.isoformat() if now is not None else None,
        "fair_odds": round(fair, 4),
        "overround_assumption": round(margin, 5),
        "overround_reference": origin,
        "estimated": True,
    }


def valid_standalone_prediction(pick, combo_only=False):
    """Source et prix explicites, jamais de cote théorique baptisée BSD."""
    if not isinstance(pick, dict):
        return False
    val = pick.get("odds")
    source = pick.get("odds_source")
    if type(val) not in (int, float) or not isfinite(val):
        return False
    if pick.get("selection_key") in ("UNDER_45", None, ""):
        return False
    if source == ESTIMATED_SOURCE:
        return MIN_STANDALONE_ODDS <= val <= 100 and not combo_only and pick.get("estimated_odds") is True
    if source in VERIFIED_SOURCES:
        return 1.20 <= val <= 100
    return False


def price_selected_market(selection, quotes, *, now=None):
    """Ajoute un prix à l'option DEJA sélectionnée, sans changer son identité.

    Le moteur probabiliste et les contrôles qualité doivent être appliqués AVANT
    cet appel. Une cote BSD réelle est conservée, même sous 1.20 (combo-only).
    Une cote absente est une estimation explicitement identifiée, jamais BSD.
    """
    if not isinstance(selection, dict):
        return None
    key = selection.get("key")
    code = selection.get("internal_market_code") or selection.get("market_code")
    if not code or key in ("UNDER_45", None, ""):
        return None
    source_quote=(quotes or {}).get(code)
    price=_real_quote(source_quote)
    result=dict(selection)
    if price is not None:
        result.update({
            "bookmaker_odds":price,"odds":price,
            "odds_source":source_quote["origin"],
            "odds_updated_at":source_quote.get("updated_at"),
            "estimated_odds":False,
            "odds_method":None,"overround_assumption":None,
        })
    else:
        estimate=estimated_quote({
            "key":key,"market_code":code,
            "probability":selection.get("probability"),
            "conservative_probability":selection.get("conservative_probability"),
        },quotes,now=now)
        if estimate is None:
            return None
        result.update({
            "bookmaker_odds":estimate["odds"],"odds":estimate["odds"],
            "odds_source":ESTIMATED_SOURCE,
            "odds_updated_at":estimate["updated_at"],
            "estimated_odds":True,
            "odds_method":estimate["overround_reference"],
            "overround_assumption":estimate["overround_assumption"],
            "estimated_value":None,
        })
    return result
