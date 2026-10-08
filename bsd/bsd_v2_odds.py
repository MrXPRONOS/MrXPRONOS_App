"""Cotes BSD pré-match : consensus gratuit, bookmaker nommé si abonnement.

Le flux /api/v2/odds/ est un flux instantané, PAS un historique de ticks.
On ne prétend jamais reconstituer une cote de 2024/25/26 rétroactivement.
"""
from __future__ import annotations
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Dict, Optional, Tuple

from bsd_api import BSDAPIError, BSDClient
from bsd_h2h import _utc
from bsd_markets import candidates_from_goals

# Codes internes -> filtre BSD officiel (uniquement FT).
MARKETS = {c.market_code: (c.market, c.outcome)
           for c in candidates_from_goals(1.4, 1.2)}
# Le paramètre de filtrage legacy ne nomme pas toutes les lignes. Les réponses
# non filtrées peuvent contenir d'autres lignes, y compris 4,5 buts.
ALLOWED_MARKETS = frozenset(("1x2", "double_chance", "btts",
                            "over_under_15", "over_under_25", "over_under_35",
                            "over_under_45"))


def _odds_number(v):
    if isinstance(v, bool) or v is None:
        return None
    try:
        p = float(v)
        return p if isfinite(p) and 1.01 <= p <= 100.0 else None
    except (ValueError, TypeError):
        return None


def _event_id(row):
    v = row.get("event_id", row.get("event"))
    if isinstance(v, dict):
        v = v.get("id")
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _canonical_market(row):
    """Normalize only unambiguous full-time goal totals from unfiltered odds.

    Never conflate total corners, half-time totals and goal lines.
    """
    raw = str(row.get("market") or "").strip().lower()
    if raw not in ("over_under", "total_goals", "goals_over_under", "over_under_05",
                   "over_under_15", "over_under_25", "over_under_35", "over_under_45"):
        return raw
    if raw.startswith("over_under_") and raw not in ("over_under",):
        implied = {"05": .5, "15": 1.5, "25": 2.5, "35": 3.5, "45": 4.5}.get(raw[-2:])
        if implied is None:
            return ""
        value = row.get("line")
        if value is not None:
            try:
                if float(value) != implied:
                    return ""
            except (TypeError, ValueError):
                return ""
        return raw
    try:
        line = float(row["line"])
    except (KeyError, TypeError, ValueError):
        return ""
    return {1.5: "over_under_15", 2.5: "over_under_25",
            3.5: "over_under_35", 4.5: "over_under_45"}.get(line, "")


def parse_odds(rows, event_id: int, *, kickoff: datetime, fetched_at: datetime,
               bookmaker_slug: str = "consensus", max_age_hours: int = 48):
    """Rejette toute cote ambiguë, d'un autre match, hors FT ou non pré-match.

    book=consensus correspond à la moyenne du flux gratuit et NE signifie
    PAS 1xBet. Les identifiants de tickets ne sont pas fournis par BSD.
    """
    if not isinstance(rows, list):
        raise ValueError("Liste de cotes BSD invalide")
    if fetched_at >= kickoff:
        raise ValueError("Cotes BSD après le coup d’envoi refusées")
    result = {}
    reject = {}
    mapping = {(market, outcome): code for code, (market, outcome) in MARKETS.items()
               if market in ALLOWED_MARKETS}
    for row in rows:
        if not isinstance(row, dict) or _event_id(row) != int(event_id):
            continue
        kind = _canonical_market(row)
        outcome = str(row.get("outcome") or "").strip()
        code = mapping.get((kind, outcome))
        if not code:
            reject["unsupported_market"] = reject.get("unsupported_market", 0) + 1
            continue
        period = row.get("period", row.get("market_period", "FT"))
        if period is not None and str(period).upper() not in ("FT", "FULL_TIME", "FULL-TIME", "FULLTIME"):
            reject["non_full_time"] = reject.get("non_full_time", 0) + 1
            continue
        bookmaker = str(row.get("bookmaker_slug") or row.get("bookmaker_code") or "").lower()
        if bookmaker != bookmaker_slug.lower():
            reject["wrong_bookmaker"] = reject.get("wrong_bookmaker", 0) + 1
            continue
        quote = _odds_number(row.get("decimal_odds"))
        if quote is None:
            reject["invalid_quote"] = reject.get("invalid_quote", 0) + 1
            continue
        try:
            updated = _utc(str(row["updated_at"]))
        except (KeyError, ValueError, TypeError):
            reject["missing_timestamp"] = reject.get("missing_timestamp", 0) + 1
            continue
        if not updated <= fetched_at < kickoff or (fetched_at-updated).total_seconds() > max_age_hours*3600:
            reject["stale_or_post_kickoff"] = reject.get("stale_or_post_kickoff", 0) + 1
            continue
        prev = result.get(code)
        if prev is None or updated > _utc(prev["updated_at"]):
            result[code] = {
                "odds": quote, "bookmaker": bookmaker,
                "updated_at": updated.isoformat(),
                "captured_at": fetched_at.isoformat(),
                "origin": "bsd_consensus" if bookmaker == "consensus" else "bsd_bookmaker",
                "bookmaker_selection_code": None,
            }
    return result, reject


def fetch_event_odds(client: BSDClient, event_id: int, *, kickoff: datetime,
                     captured_at: datetime, bookmaker_slug="consensus",
                     max_pages=5, max_age_hours=48):
    if captured_at >= kickoff:
        raise ValueError("Aucune collecte de cotes après le début du match")
    if not 1 <= max_pages <= 10:
        raise ValueError("Pagination odds invalide")
    all_rows = []
    total = None
    for page in range(max_pages):
        payload = client.get_json("/odds/", {
            "event_id": int(event_id), "limit": 200, "offset": page*200,
            **({"bookmaker_slug": bookmaker_slug} if bookmaker_slug != "consensus" else {}),
        }, ttl=0)
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ValueError("Schéma cotes BSD inattendu")
        if not isinstance(payload.get("count"), int):
            raise ValueError("Pagination cotes BSD sans count")
        total = payload["count"]
        all_rows.extend(payload["results"])
        if len(all_rows) >= total:
            break
        if not payload["results"]:
            break
    if total is None or len(all_rows) < total:
        raise RuntimeError("Pagination BSD incomplète; cotes ignorées")
    quotes, errors = parse_odds(all_rows, event_id, kickoff=kickoff,
                                fetched_at=captured_at, bookmaker_slug=bookmaker_slug,
                                max_age_hours=max_age_hours)
    return quotes, {"rows_read":len(all_rows), "usable":len(quotes),
                    "rejected":errors, "bookmaker_slug":bookmaker_slug}
