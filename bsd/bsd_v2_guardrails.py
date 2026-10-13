"""Guardrails prospectifs BSD V2.

Ce module regroupe uniquement des règles de sécurité mesurables :
- version de politique publiée avec chaque pronostic ;
- seuil conservateur spécifique à certaines familles ;
- contrôle final d'une cote BSD réelle sans laisser la cote choisir le marché ;
- suivi prospectif de dérive par sélection et famille.

Aucune statistique 2026 n'est utilisée pour réentraîner rétroactivement le modèle.
Les résultats réellement publiés ne servent qu'à une pénalité progressive après
un minimum d'observations.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from math import isfinite

POLICY_VERSION = "bsd-v2-policy-2026-10-11-v21-vip81-model775-verified76"
PERFORMANCE_FORMAT = "bsd-v2-performance-v1"

VERIFIED_ODDS_SOURCES = frozenset(("bsd_consensus", "bsd_bookmaker", "pinnwire", "oddslink", "moviodds", "oddsharvester"))

# Même marge de prix que celle utilisée par le classement conservateur du moteur.
FAMILY_PRICE_EDGE = {
    "double_chance": .018,
    "btts": .022,
    "goals": .022,
    "result": .025,
}

# Pas de changement du système simple/pro demandé ici. On renforce uniquement
# la double chance : en-dessous de 75 % de probabilité conservatrice, elle ne
# peut pas être publiée comme sélection principale.
MIN_CONSERVATIVE_BY_FAMILY = {
    "double_chance": .75,
    "goals": .00,
}

MIN_DRIFT_SAMPLES = 100
DRIFT_PRIOR = 200
MAX_DRIFT_PENALTY = .08
MAX_TRACKED_SETTLED_IDS = 5000


def market_family(value):
    """Normalise le nom public/interne du marché vers une famille de risque."""
    if isinstance(value, dict):
        market = str(value.get("market") or "")
        key = str(value.get("selection_key") or value.get("key") or "")
    else:
        market = str(value or "")
        key = ""
    low = market.casefold()
    if low == "double_chance" or key in ("1X", "X2", "12"):
        return "double_chance"
    if low == "btts" or key.startswith("BTTS_"):
        return "btts"
    if low.startswith("over_under") or key.startswith(("OVER_", "UNDER_")):
        return "goals"
    if low in ("result", "1x2") or key in ("1", "X", "2"):
        return "result"
    return "result"


def family_price_edge(family):
    return FAMILY_PRICE_EDGE.get(str(family), FAMILY_PRICE_EDGE["result"])


def post_price_value_guard(selection):
    """Vérifie une cote réelle APRES la sélection probabiliste.

    Une cote estimée par Mr XPRONOS n'est pas une observation indépendante du
    marché et ne peut donc ni confirmer ni invalider la value. Elle reste
    explicitement marquée comme non vérifiable par ce garde-fou.
    """
    if not isinstance(selection, dict):
        return {"checked": True, "passed": False, "reason": "invalid_selection"}
    source = selection.get("odds_source")
    odds = selection.get("bookmaker_odds", selection.get("odds"))
    p = selection.get("conservative_probability")
    if p is None:
        p = selection.get("probability")
    if source not in VERIFIED_ODDS_SOURCES:
        return {
            "checked": False,
            "passed": True,
            "reason": "estimated_price_not_independent",
            "source": source,
        }
    if type(odds) not in (int, float) or not isfinite(float(odds)) or float(odds) <= 1:
        return {"checked": True, "passed": False, "reason": "invalid_verified_odds", "source": source}
    if type(p) not in (int, float) or not isfinite(float(p)) or not 0 < float(p) < 1:
        return {"checked": True, "passed": False, "reason": "missing_conservative_probability", "source": source}
    family = market_family(selection)
    edge = family_price_edge(family)
    implied = 1.0 / float(odds)
    required = min(.995, implied + edge)
    passed = float(p) >= required
    return {
        "checked": True,
        "passed": passed,
        "reason": "ok" if passed else "conservative_probability_below_real_price_edge",
        "source": source,
        "family": family,
        "odds": round(float(odds), 5),
        "implied_probability": round(implied, 6),
        "safety_edge": edge,
        "required_probability": round(required, 6),
        "conservative_probability": round(float(p), 6),
    }


def _empty_bucket():
    return {"n": 0, "wins": 0, "sum_pred": 0.0, "penalty": 0.0}


def _sanitize_bucket(value):
    if not isinstance(value, dict):
        return _empty_bucket()
    try:
        n = max(0, int(value.get("n", 0)))
        wins = max(0, min(n, int(value.get("wins", 0))))
        total = max(0.0, float(value.get("sum_pred", 0.0)))
    except (TypeError, ValueError):
        return _empty_bucket()
    return {"n": n, "wins": wins, "sum_pred": total, "penalty": 0.0}


def _penalty(bucket):
    n = int(bucket.get("n") or 0)
    if n < MIN_DRIFT_SAMPLES:
        return 0.0
    expected = float(bucket.get("sum_pred") or 0.0) / n
    observed = float(bucket.get("wins") or 0.0) / n
    optimism = max(0.0, expected - observed)
    # Shrinkage progressif : à 100 observations, seulement 1/3 de l'écart est
    # appliqué ; la correction augmente ensuite sans dépasser 8 points.
    return round(min(MAX_DRIFT_PENALTY, optimism * n / (n + DRIFT_PRIOR)), 6)


def _prediction_probability(match):
    pred = match.get("prediction") or {}
    value = pred.get("conservative_probability")
    if type(value) in (int, float) and isfinite(float(value)) and 0 < float(value) < 1:
        return float(value)
    value = pred.get("confidence")
    if type(value) in (int, float) and isfinite(float(value)):
        value = float(value) / 100.0
        if 0 < value < 1:
            return value
    return None


def _won(match):
    if "verified_prediction" in match:
        return bool(match.get("verified_prediction"))
    return bool(match.get("verified_double"))


def update_performance_tracker(existing, matches, *, now=None):
    """Ajoute chaque résultat publié une seule fois et recalcule les pénalités."""
    tracker = deepcopy(existing) if isinstance(existing, dict) else {}
    if tracker.get("format") != PERFORMANCE_FORMAT:
        tracker = {
            "format": PERFORMANCE_FORMAT,
            "settled_ids": [],
            "by_selection": {},
            "by_family": {},
            "by_league_market": {},
        }
    settled_ids = [str(x) for x in tracker.get("settled_ids", []) if x]
    seen = set(settled_ids)
    by_selection = {str(k): _sanitize_bucket(v)
                    for k, v in (tracker.get("by_selection") or {}).items()}
    by_family = {str(k): _sanitize_bucket(v)
                 for k, v in (tracker.get("by_family") or {}).items()}
    by_league_market = {str(k): _sanitize_bucket(v) for k,v in
                        (tracker.get("by_league_market") or {}).items()}
    added = 0
    for match in matches or []:
        if not isinstance(match, dict) or not match.get("is_finished"):
            continue
        pred = match.get("prediction") or {}
        key = str(pred.get("selection_key") or "")
        if not key:
            continue
        probability = _prediction_probability(match)
        if probability is None:
            continue
        ref = "%s:%s:%s" % (
            str(match.get("id") or match.get("source_event_id") or ""),
            key,
            str(match.get("event_date") or match.get("date") or ""),
        )
        if ref in seen:
            continue
        win = int(_won(match))
        family = market_family(pred)
        league = str(match.get("league") or "").strip()
        buckets = [(by_selection, key), (by_family, family)]
        if league:
            buckets.append((by_league_market, league + "|" + key))
        for mapping, bucket_key in buckets:
            row = mapping.setdefault(bucket_key, _empty_bucket())
            row["n"] += 1
            row["wins"] += win
            row["sum_pred"] = float(row.get("sum_pred") or 0.0) + probability
        seen.add(ref)
        settled_ids.append(ref)
        added += 1

    for mapping in (by_selection, by_family, by_league_market):
        for row in mapping.values():
            row["penalty"] = _penalty(row)
            n = row["n"]
            row["hit_rate"] = round(row["wins"] / n, 6) if n else None
            row["average_predicted"] = round(row["sum_pred"] / n, 6) if n else None

    tracker.update({
        "format": PERFORMANCE_FORMAT,
        "settled_ids": settled_ids[-MAX_TRACKED_SETTLED_IDS:],
        "by_selection": by_selection,
        "by_family": by_family,
        "by_league_market": by_league_market,
        "last_added": added,
        "updated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "min_samples_for_penalty": MIN_DRIFT_SAMPLES,
        "drift_prior": DRIFT_PRIOR,
        "max_penalty": MAX_DRIFT_PENALTY,
    })
    return tracker


def tracker_penalties(tracker):
    if not isinstance(tracker, dict) or tracker.get("format") != PERFORMANCE_FORMAT:
        return {}, {}
    by_key = {
        str(k): max(0.0, min(MAX_DRIFT_PENALTY, float(v.get("penalty") or 0.0)))
        for k, v in (tracker.get("by_selection") or {}).items()
        if isinstance(v, dict)
    }
    by_family = {
        str(k): max(0.0, min(MAX_DRIFT_PENALTY, float(v.get("penalty") or 0.0)))
        for k, v in (tracker.get("by_family") or {}).items()
        if isinstance(v, dict)
    }
    return by_key, by_family

# V2.1 prospective publication controls. No revision of probability training.
V21_EXCLUDED_KEYS = frozenset(("12",))
V21_MIN_OVER15_CONSERVATIVE = .85
V21_MIN_VALUE_EDGE = .022
V21_MODEL_MIN_CONSERVATIVE = .775  # Carefully broaden model Pro; VIP remains >= .81
V21_SHADOW_MIN_SAMPLES = 50
V21_SHADOW_MAX_OVERCONFIDENCE = .06
V21_SHADOW_MIN_LEAGUE_MARKET_SAMPLES = 50
V21_DAILY_NEW_PICKS = 10
V21_POLICY_ID = "bsd-v21-2026-10-11"

def v21_bucket_gap(bucket):
    if not isinstance(bucket, dict) or int(bucket.get("n") or 0) < V21_SHADOW_MIN_SAMPLES:
        return 0.0
    n = int(bucket["n"])
    return float(bucket.get("sum_pred") or 0.0)/n - float(bucket.get("wins") or 0.0)/n

def v21_market_shadow(tracker, selection_key):
    bucket = (tracker or {}).get("by_selection", {}).get(str(selection_key), {})
    return v21_bucket_gap(bucket) > V21_SHADOW_MAX_OVERCONFIDENCE

def v21_signal_tier(choice):
    p = float(choice.get("conservative_probability", choice.get("probability") or 0))
    price = float(choice.get("bookmaker_odds") or 0)
    if price <= 1:
        return "OBSERVATION"
    # A model price is derived from its own probability, not a bookmaker quote.
    # Do not describe that self-referential comparison as a verified edge.
    if choice.get("odds_source") == "mrxpronos_model":
        return "INDICATIF" if p >= V21_MODEL_MIN_CONSERVATIVE and price >= 1.20 else "OBSERVATION"
    edge = p - 1.0/price
    if p >= .80 and edge >= .025:
        return "PREMIUM"
    if p >= .76 and edge >= V21_MIN_VALUE_EDGE:
        return "QUALIFIE"
    return "OBSERVATION"

def v21_accept_priced(choice, tracker=None, league_market=None):
    """Check observed BSD value or confidence-only model quotes, without claiming independent edge."""
    if not isinstance(choice, dict):
        return False, "invalid_choice"
    key = str(choice.get("key") or choice.get("selection_key") or "")
    if key in V21_EXCLUDED_KEYS:
        return False, "v21_excluded_12"
    if choice.get("odds_source") not in VERIFIED_ODDS_SOURCES | frozenset(("mrxpronos_model",)):
        return False, "v21_unknown_quote_source"
    if v21_market_shadow(tracker, key):
        return False, "v21_market_circuit_breaker"
    if isinstance(league_market, dict) and v21_bucket_gap(league_market) > V21_SHADOW_MAX_OVERCONFIDENCE:
        return False, "v21_league_market_circuit_breaker"
    p = choice.get("conservative_probability", choice.get("probability"))
    price = choice.get("bookmaker_odds", choice.get("odds"))
    if not isinstance(p, (float, int)) or not isinstance(price, (float, int)) or price <= 1:
        return False, "v21_missing_probability_or_price"
    p = float(p)
    price = float(price)
    if not isfinite(p) or not isfinite(price) or not 0 < p < 1 or not 1 < price <= 100:
        return False, "v21_invalid_probability_or_price"
    if choice.get("odds_source") == "mrxpronos_model":
        # This price is calculated FROM the probability, so comparing it to
        # the same probability with a positive bookmaker edge is circular
        # and always fails for correctly priced conservative estimates.
        # Retain the minimum odds, strong model confidence, drift protection
        # and extra safeguards for Over 1.5. Never claim bookmaker value.
        if key == "OVER_15" and p < V21_MIN_OVER15_CONSERVATIVE:
            return False, "v21_over15_conservative_too_low"
        if price < 1.20 or p < V21_MODEL_MIN_CONSERVATIVE:
            return False, "v21_model_confidence_or_price_below_floor"
        if price > 1.0 / p + 0.001:
            return False, "v21_model_quote_above_conservative_fair_odds"
        return True, "ok_model_indicative"
    if key == "OVER_15" and p < max(V21_MIN_OVER15_CONSERVATIVE, 1/price + V21_MIN_VALUE_EDGE):
        return False, "v21_over15_conservative_too_low"
    if p < 1/price + V21_MIN_VALUE_EDGE:
        return False, "v21_insufficient_indicative_price_edge" if choice.get("odds_source") == "mrxpronos_model" else "v21_insufficient_real_price_edge"
    if v21_signal_tier(choice) == "OBSERVATION":
        return False, "v21_observation_not_recommended"
    return True, "ok"

def v21_league_market_performance(matches):
    """Retrospective settled groups for monitoring; protect tiny samples."""
    groups = {}
    for match in matches or ():
        if not isinstance(match, dict) or not match.get("is_finished"):
            continue
        pred = match.get("prediction") or {}
        league = str(match.get("league") or "").strip()
        key = str(pred.get("selection_key") or "")
        if not league or not key or "verified_prediction" not in match:
            continue
        p = pred.get("conservative_probability", pred.get("confidence"))
        if not isinstance(p, (int, float)):
            continue
        prob = float(p)
        if prob > 1:
            prob /= 100
        group = groups.setdefault(league + "|" + key, {"n": 0, "wins": 0, "sum_pred": 0.0})
        group["n"] += 1
        group["wins"] += int(bool(match["verified_prediction"]))
        group["sum_pred"] += prob
    return groups
