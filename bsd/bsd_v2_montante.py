#!/usr/bin/env python3
"""Sélecteur journalier de montante BSD V2, lecture seule des pronostics.

Ne passe aucun pari et n'invente aucune cote. Un seul choix figé par jour UTC;
l'absence de choix est un résultat valide. Les consensus doivent être vérifiés
chez le bookmaker avant toute mise réelle.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from math import isfinite, sqrt
from pathlib import Path

from bsd.bsd_v2_guardrails import (
    VERIFIED_ODDS_SOURCES, market_family, post_price_value_guard,
    v21_accept_priced, v21_bucket_gap,
)
from bsd.bsd_v2_publication_policy import eligible_feed_match, eligible_feed_selection

POLICY = "bsd-v2-montante-daily-1"
MIN_ODDS = 1.20                  # Strictement supérieur : 1,20 refusé
MIN_CONSERVATIVE_PROB = 0.82     # Ne remplace pas les politiques du moteur
MIN_PRICE_EDGE = 0.025          # Surplus conservateur en points de probabilité
MIN_LEAD_MINUTES = 60           # Évite les rencontres imminentes
MAX_QUOTE_AGE_HOURS = 6         # Cote horodatée avant le coup d'envoi
MAX_FEED_AGE_HOURS = 12
MIN_CALIBRATION_SAMPLES = 30
MAX_OVERCONFIDENCE = 0.05
BANNED_KEYS = frozenset(("12", "UNDER_45"))


def utc(value):
    if not isinstance(value, str):
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return d.astimezone(timezone.utc) if d.tzinfo else None


def number(value):
    return float(value) if type(value) in (int, float) and isfinite(value) else None


def fraction(value):
    p = number(value)
    if p is None:
        return None
    if p > 1:
        p /= 100.0
    return p if 0 < p < 1 else None


def wilson_lower(wins, n, z=1.96):
    if n <= 0:
        return 0.0
    rate = wins / n
    z2 = z * z
    return max(0.0, (rate + z2/(2*n) - z*sqrt((rate*(1-rate)+z2/(4*n))/n)) / (1+z2/n))


def _bucket_risk(tracker, league, key, family):
    """Utilise seulement des observations déjà clôturées, sans surinterpréter de petits échantillons."""
    if not isinstance(tracker, dict):
        return False, 0.0
    paths = (
        ("by_selection", key),
        ("by_family", family),
        ("by_league_market", league + "|" + key if league else ""),
    )
    confidence_from_history = []
    for section, label in paths:
        bucket = (tracker.get(section) or {}).get(label) if label else None
        if not isinstance(bucket, dict):
            continue
        try:
            n = int(bucket.get("n") or 0)
            wins = int(bucket.get("wins") or 0)
        except (TypeError, ValueError):
            continue
        if n >= 50 and 0 <= wins <= n:
            if v21_bucket_gap(bucket) > MAX_OVERCONFIDENCE:
                return True, 0.0
            confidence_from_history.append(wilson_lower(wins, n))
    return False, min(confidence_from_history) if confidence_from_history else 0.0


def _unique_picks(match):
    picks = [match.get("prediction")]
    extras = match.get("predictions") or []
    if isinstance(extras, list):
        picks.extend(extras)
    seen = set()
    for p in picks:
        if not isinstance(p, dict):
            continue
        key = str(p.get("selection_key") or "")
        if key and key not in seen:
            seen.add(key)
            yield p


def check(match, pick, feed, now):
    """Retourne (choix évalué, motif de rejet), sans basculer vers un autre marché."""
    if not eligible_feed_match(match) or not eligible_feed_selection(match, pick):
        return None, "publication_gate"
    if match.get("source") != "bsd" or match.get("combo_only") or match.get("is_finished"):
        return None, "non_bsd_or_combo_or_finished"
    if str(match.get("status") or "").lower() not in ("notstarted", "upcoming"):
        return None, "match_started"
    if match.get("recommendation_eligible") is not True or pick.get("recommendation_eligible") is not True:
        return None, "not_recommended"
    key = str(pick.get("selection_key") or "")
    if not key or key in BANNED_KEYS:
        return None, "banned_market"
    kickoff = utc(match.get("event_date"))
    if kickoff is None or kickoff.date() != now.date() or kickoff <= now + timedelta(minutes=MIN_LEAD_MINUTES):
        return None, "wrong_day_or_too_late"
    source = pick.get("odds_source")
    odds = number(pick.get("odds"))
    if (source not in VERIFIED_ODDS_SOURCES or pick.get("estimated_odds") is not False
            or odds is None or not MIN_ODDS < odds <= 100):
        return None, "unverified_or_low_odds"
    updated = utc(pick.get("odds_updated_at"))
    if (updated is None or updated > now or updated >= kickoff
            or now-updated > timedelta(hours=MAX_QUOTE_AGE_HOURS)):
        return None, "stale_quote"
    p = fraction(pick.get("conservative_probability"))
    model_p = fraction(pick.get("model_probability"))
    if p is None or model_p is None or p < MIN_CONSERVATIVE_PROB:
        return None, "weak_conservative_probability"
    cal = number(pick.get("calibration_samples"))
    if cal is not None and cal < MIN_CALIBRATION_SAMPLES:
        return None, "insufficient_calibration"
    family = market_family(pick)
    league = str(match.get("league") or "")
    tracker = feed.get("performance_tracker") or {}
    bucket = (tracker.get("by_league_market") or {}).get(league + "|" + key)
    selected = {
        "key": key, "market": pick.get("market"), "odds_source": source,
        "bookmaker_odds": odds, "conservative_probability": p,
        "probability": model_p,
    }
    if not post_price_value_guard(selected).get("passed"):
        return None, "failed_value_guard"
    accepted, why = v21_accept_priced(selected, tracker, bucket)
    if not accepted:
        return None, "v21_" + str(why)
    edge = p - 1.0/odds
    if edge < MIN_PRICE_EDGE:
        return None, "insufficient_conservative_edge"
    drift, historic_lower = _bucket_risk(tracker, league, key, family)
    if drift:
        return None, "historical_overconfidence"
    # En dernier seulement, la cote et l'historique départagent des probabilités déjà qualifiées.
    score = (0.75*p + 0.15*min(edge, .20) + 0.08*historic_lower
             + (0.01 if source == "bsd_bookmaker" and pick.get("odds_bookmaker") else 0)
             + (0.01*min(cal/150, 1) if cal is not None else 0))
    return {
        "id": str(match.get("id")),
        "source_event_id": match.get("source_event_id"),
        "date": now.date().isoformat(),
        "kickoff_utc": kickoff.isoformat(),
        "league": league,
        "home_team": match.get("home_team"),
        "away_team": match.get("away_team"),
        "selection_key": key,
        "market_label": pick.get("label") or pick.get("type") or key,
        "market": pick.get("market"),
        "odds": odds,
        "odds_source": source,
        "bookmaker": pick.get("odds_bookmaker"),
        "quote_updated_at": updated.isoformat(),
        "model_probability_percent": round(model_p*100, 2),
        "conservative_probability_percent": round(p*100, 2),
        "implied_probability_percent": round(100/odds, 2),
        "conservative_edge_points": round(100*edge, 2),
        "history_lower_bound_percent": round(100*historic_lower, 2) if historic_lower else None,
        "score": round(score, 6),
        "requires_manual_bookmaker_verification": True,
        "not_a_placed_bet": True,
    }, None


def choose(feed, ledger, *, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now doit être timezone-aware")
    now = now.astimezone(timezone.utc)
    day = now.date().isoformat()
    if not isinstance(feed, dict) or feed.get("source") != "bsd" or feed.get("model_version") != "bsd-v2-isolated":
        raise ValueError("Flux BSD V2 invalide")
    if not isinstance(feed.get("matches"), list):
        raise ValueError("matches manquant ou invalide")
    if not isinstance(ledger, dict) or ledger.get("schema") not in (None, POLICY):
        raise ValueError("Ledger montante incompatible")
    days = ledger.get("days") or {}
    if not isinstance(days, dict):
        raise ValueError("Ledger montante invalide")
    frozen = days.get(day)
    if frozen is not None:
        if not isinstance(frozen, dict) or frozen.get("date") != day or not frozen.get("selection_key"):
            raise ValueError("Sélection immuable altérée")
        return ({"date": day, "status": "selected", "selection": frozen,
                 "frozen": True, "policy": POLICY, "rejections": {}, "eligible_count": 1},
                {"schema": POLICY, "days": days})
    generated = utc(feed.get("generated_at"))
    if generated is None or generated > now or now - generated > timedelta(hours=MAX_FEED_AGE_HOURS):
        return {"date": day, "status": "no_pick", "selection": None,
                "reason": "stale_or_missing_feed_timestamp", "frozen": False,
                "policy": POLICY, "rejections": {}, "eligible_count": 0}, {"schema": POLICY, "days": days}
    rejects = Counter()
    candidates = []
    seen = set()
    for match in feed["matches"]:
        if not isinstance(match, dict):
            rejects["invalid_match"] += 1
            continue
        ident = str(match.get("source_event_id") or match.get("id") or "")
        if ident in seen:
            rejects["duplicate_event"] += 1
            continue
        seen.add(ident)
        for pick in _unique_picks(match):
            candidate, error = check(match, pick, feed, now)
            if candidate:
                candidates.append(candidate)
            else:
                rejects[error] += 1
    if not candidates:
        return {"date": day, "status": "no_pick", "selection": None,
                "reason": "no_qualified_real_quote", "frozen": False,
                "policy": POLICY, "rejections": dict(rejects), "eligible_count": 0}, {"schema": POLICY, "days": days}
    # Départage déterministe sans amplifier artificiellement une cote supérieure.
    candidates.sort(key=lambda r: (-r["score"], -r["conservative_probability_percent"],
                                   r["kickoff_utc"], r["id"], r["selection_key"]))
    selected = dict(candidates[0], selected_at_utc=now.isoformat())
    new_days = dict(days)
    new_days[day] = selected
    return {"date": day, "status": "selected", "selection": selected,
            "frozen": False, "policy": POLICY, "rejections": dict(rejects),
            "eligible_count": len(candidates)}, {"schema": POLICY, "days": new_days}


def markdown_report(result):
    date = result["date"]
    if result["status"] != "selected":
        return (f"# Montante BSD V2 — {date} (UTC)\n\n"
                "**Aucun pari retenu.** Les critères de qualité et de cotes réelles sont prioritaires.\n")
    s = result["selection"]
    return (f"# Montante BSD V2 — {date} (UTC)\n\n"
            f"**{s['home_team']} – {s['away_team']}** ({s['league']})\n\n"
            f"- Début : {s['kickoff_utc']}\n"
            f"- Sélection : **{s['market_label']}** (`{s['selection_key']}`)\n"
            f"- Cote observée : **{s['odds']:.2f}** ({s['odds_source']})\n"
            f"- Probabilité conservatrice du modèle : {s['conservative_probability_percent']:.1f} %\n"
            f"- Écart sur probabilité implicite : {s['conservative_edge_points']:.1f} points\n\n"
            "**Vérifier la même sélection et sa cote chez le bookmaker avant de parier.** "
            "Une cote consensus n'est pas une offre garantie; aucun pari n'a été passé. "
            "Une perte reste possible.\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", default="data.json")
    parser.add_argument("--ledger", default="montante/ledger.json")
    parser.add_argument("--json-output", default="montante/daily.json")
    parser.add_argument("--markdown-output", default="montante/du-jour.md")
    args = parser.parse_args(argv)
    feed = json.loads(Path(args.feed).read_text(encoding="utf-8"))
    path = Path(args.ledger)
    ledger = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"schema": POLICY, "days": {}}
    result, updated_ledger = choose(feed, ledger)
    for dest, doc in ((path, json.dumps(updated_ledger, ensure_ascii=False, indent=2) + "\n"),
                      (Path(args.json_output), json.dumps(result, ensure_ascii=False, indent=2) + "\n"),
                      (Path(args.markdown_output), markdown_report(result))):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(doc, encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("date", "status", "eligible_count", "rejections")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())