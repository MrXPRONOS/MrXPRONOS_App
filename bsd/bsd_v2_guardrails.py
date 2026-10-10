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

POLICY_VERSION = "bsd-v2-policy-2026-10-10-r1"
PERFORMANCE_FORMAT = "bsd-v2-performance-v1"

VERIFIED_ODDS_SOURCES = frozenset(("bsd_consensus", "bsd_bookmaker"))

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
        }
    settled_ids = [str(x) for x in tracker.get("settled_ids", []) if x]
    seen = set(settled_ids)
    by_selection = {str(k): _sanitize_bucket(v)
                    for k, v in (tracker.get("by_selection") or {}).items()}
    by_family = {str(k): _sanitize_bucket(v)
                 for k, v in (tracker.get("by_family") or {}).items()}
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
        for mapping, bucket_key in ((by_selection, key), (by_family, family)):
            row = mapping.setdefault(bucket_key, _empty_bucket())
            row["n"] += 1
            row["wins"] += win
            row["sum_pred"] = float(row.get("sum_pred") or 0.0) + probability
        seen.add(ref)
        settled_ids.append(ref)
        added += 1

    for mapping in (by_selection, by_family):
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
