"""Permanent BSD publication audit.

The public feed is a display window, NOT the historical source of truth.
A first-observed selection is frozen in this ledger, including selections
that later disappear from the public feed. Scores are settled independently
without silently treating pending selections as defeats.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from bsd_markets import candidates_from_goals, realized

SCHEMA = "bsd-v2-publication-ledger-1"
VERIFIED_SOURCES = frozenset(("bsd_consensus", "bsd_bookmaker"))
MIN_CATEGORY_SAMPLE = 100
MIN_CALIBRATION_SAMPLE = 30
KEYS = {row.key: row for row in candidates_from_goals(1.3, 1.1)}


def _utc(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _identity(match):
    ident = match.get("source_event_id", match.get("id"))
    kickoff = _utc(match.get("event_date"))
    if ident is None or kickoff is None:
        return None
    return str(ident).removeprefix("bsd:") + "|" + kickoff.isoformat()


def _price(pick):
    if not isinstance(pick, dict):
        return None
    key = str(pick.get("selection_key") or "")
    if not key:
        return None
    odds = pick.get("odds")
    price = float(odds) if type(odds) in (int, float) and math.isfinite(odds) and odds > 1 else None
    confidence = pick.get("confidence")
    probability = float(confidence) / 100 if type(confidence) in (int, float) and 0 < confidence < 100 else None
    source = str(pick.get("odds_source") or "unknown")
    return {"selection_key": key, "market": pick.get("market"),
            "confidence": probability, "odds": price, "odds_source": source,
            "odds_verified": source in VERIFIED_SOURCES and price is not None}


def _picks(match):
    primary = _price(match.get("prediction"))
    others = []
    for p in match.get("predictions") or []:
        item = _price(p)
        if item and item["selection_key"] != (primary or {}).get("selection_key") and not any(
            x["selection_key"] == item["selection_key"] for x in others
        ):
            others.append(item)
    return primary, others


def _valid_score(value):
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def settle_entry(entry, event):
    """Mutates only the settlement fields, and only for a verified finished event."""
    if not isinstance(event, dict) or str(event.get("status") or "").lower() != "finished":
        return False
    if _identity(event) != entry.get("key"):
        return False
    h = _valid_score(event.get("home_score"))
    a = _valid_score(event.get("away_score"))
    if h is None or a is None:
        return False
    picks = [entry["original_pick"]] + entry.get("secondary_picks", [])
    answers = []
    for pick in picks:
        candidate = KEYS.get(pick["selection_key"])
        answers.append(bool(realized(candidate, h, a)) if candidate else None)
    entry["settlement"] = {
        "status": "finished", "home_score": h, "away_score": a,
        "primary_won": answers[0], "secondary_won": answers[1:],
    }
    return True


def update_ledger(ledger, feed_matches, fixtures=(), *, observed_at, retired=()):
    """Idempotent append-only identities and first-published selections."""
    if not isinstance(ledger, dict) or ledger.get("schema") != SCHEMA:
        ledger = {"schema": SCHEMA, "entries": []}
    entries = [dict(x) for x in ledger.get("entries", []) if isinstance(x, dict) and x.get("key")]
    by_key = {e["key"]: e for e in entries}
    active = set()
    new_count = 0
    for match in feed_matches or []:
        if not isinstance(match, dict) or match.get("source") != "bsd":
            continue
        ident = _identity(match)
        primary, secondary = _picks(match)
        if ident is None or primary is None:
            continue
        active.add(ident)
        if ident not in by_key:
            entry = {
                "key": ident, "id": str(match.get("id") or ""),
                "source_event_id": str(match.get("source_event_id") or ""),
                "event_date": _utc(match["event_date"]).isoformat(),
                "first_observed_at": observed_at,
                "origin": "site_feed",
                "home_team": match.get("home_team"), "away_team": match.get("away_team"),
                "league": match.get("league"), "category_original": match.get("category"),
                "signal_tier_original": match.get("signal_tier"),
                "original_pick": primary, "secondary_picks": secondary,
                "feed_state": "active", "settlement": {"status": "pending"},
            }
            entries.append(entry)
            by_key[ident] = entry
            new_count += 1
        entry = by_key[ident]
        entry["last_observed_in_feed_at"] = observed_at
        entry["feed_state"] = "active"
        entry.pop("withdrawal_reason", None)
    for entry in entries:
        if entry["key"] not in active:
            entry["feed_state"] = "absent_from_current_feed"
            kickoff = _utc(entry.get("event_date"))
            observed = _utc(observed_at)
            if kickoff and observed and (observed-kickoff).days > 14:
                entry["withdrawal_reason"] = "outside_public_history_window"
            else:
                entry["withdrawal_reason"] = "unexplained_absence_needs_review"
    for retired_row in retired or []:
        key = _identity(retired_row)
        if key in by_key and key not in active:
            by_key[key]["withdrawal_reason"] = str(retired_row.get("reason") or "policy_retirement")
    indexed = {}
    for event in list(fixtures or []) + list(feed_matches or []):
        if not isinstance(event, dict):
            continue
        key = _identity(event)
        if key and key in by_key and str(event.get("status") or "").lower() == "finished":
            indexed[key] = event
    settled_count = 0
    for key, event in indexed.items():
        previous = by_key[key].get("settlement") or {}
        if settle_entry(by_key[key], event) and previous.get("status") != "finished":
            settled_count += 1
    ledger = {"schema": SCHEMA, "updated_at": observed_at, "entries": entries,
              "last_run": {"new": new_count, "new_settlements": settled_count,
                           "active": len(active), "total": len(entries)}}
    return ledger


def _interval(wins, n):
    if not n:
        return None
    z = 1.96
    p = wins / n
    center = (p + z*z/(2*n)) / (1 + z*z/n)
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return [round(center-half, 4), round(center+half, 4)]


def _aggregate(records, *, min_samples=MIN_CALIBRATION_SAMPLE):
    """Actual outcome and calibration; returns NO profitability for estimated odds."""
    n = len(records)
    wins = sum(int(x[1]) for x in records)
    probabilities = [x[0].get("confidence") for x in records]
    paired = [(p, int(row[1])) for p, row in zip(probabilities, records) if p is not None]
    priced = [(row[0]["odds"], bool(row[1])) for row in records
              if row[0].get("odds_verified") and row[0].get("odds") is not None]
    unit_net = sum((odds-1 if won else -1) for odds, won in priced)
    return {
        "n": n, "wins": wins, "losses": n-wins,
        "hit_rate": round(wins/n, 4) if n else None,
        "wilson95": _interval(wins, n),
        "mean_forecast": round(sum(p for p, _ in paired)/len(paired), 4) if paired else None,
        "brier": round(sum((p-w)**2 for p, w in paired)/len(paired), 5) if paired else None,
        "calibration_gap": round(sum(p-w for p, w in paired)/len(paired), 4) if paired else None,
        "statistically_qualified": n >= min_samples,
        "priced_by_verified_source": len(priced),
        "estimated_or_unpriced": n-len(priced),
        "theoretical_flat_stake_net_units_on_verified_quotes":
            round(unit_net, 4) if priced else None,
        "theoretical_flat_stake_yield_on_verified_quotes":
            round(unit_net/len(priced), 4) if priced else None,
    }


def audit_report(ledger, *, generated_at=None):
    entries = list(ledger.get("entries", []))
    primary = []
    secondary = []
    groupings = {"by_category": defaultdict(list), "by_market": defaultdict(list),
                 "by_signal_tier": defaultdict(list), "by_price_source": defaultdict(list),
                 "by_confidence_band": defaultdict(list)}
    missing = []
    pending = []
    for entry in entries:
        if entry.get("feed_state") == "absent_from_current_feed":
            missing.append({"key": entry["key"], "reason": entry.get("withdrawal_reason")})
        result = entry.get("settlement") or {}
        if result.get("status") != "finished" or type(result.get("primary_won")) is not bool:
            pending.append(entry["key"])
            continue
        p = entry["original_pick"]
        sample = (p, result["primary_won"])
        primary.append(sample)
        probability = p.get("confidence")
        band = "unknown" if probability is None else "%.2f-%.2f" % (
            math.floor(probability * 10)/10, math.floor(probability * 10)/10 + .1)
        for group, key in (
            ("by_category", str(entry.get("category_original") or "unknown")),
            ("by_market", p["selection_key"]),
            ("by_signal_tier", str(entry.get("signal_tier_original") or "unknown")),
            ("by_price_source", p["odds_source"]),
            ("by_confidence_band", band)
        ):
            groupings[group][key].append(sample)
        for i, pick in enumerate(entry.get("secondary_picks", [])):
            outcomes = result.get("secondary_won") or []
            if i < len(outcomes) and type(outcomes[i]) is bool:
                secondary.append((pick, outcomes[i]))
    groups = {}
    for name, pairs in groupings.items():
        min_n = MIN_CATEGORY_SAMPLE if name in ("by_category", "by_signal_tier") else MIN_CALIBRATION_SAMPLE
        groups[name] = {key: _aggregate(values, min_samples=min_n)
                        for key, values in sorted(pairs.items())}
    alerts = []
    for key, metrics in groups["by_category"].items():
        if metrics["statistically_qualified"] and metrics["calibration_gap"] is not None and metrics["calibration_gap"] > .06:
            alerts.append({"type": "category_overconfidence", "category": key,
                           "gap": metrics["calibration_gap"]})
    for key, metrics in groups["by_market"].items():
        if metrics["statistically_qualified"] and metrics["calibration_gap"] is not None and metrics["calibration_gap"] > .06:
            alerts.append({"type": "market_overconfidence", "market": key,
                           "gap": metrics["calibration_gap"]})
    return {
        "schema": "bsd-v2-quality-report-1",
        "generated_at": generated_at or ledger.get("updated_at"),
        "total_ever_observed": len(entries), "in_current_feed": sum(
            e.get("feed_state") == "active" for e in entries),
        "absent_from_current_feed": len(missing),
        "unexplained_absences": sum(e["reason"] == "unexplained_absence_needs_review" for e in missing),
        "unsettled": len(pending), "settled": len(primary),
        "primary": _aggregate(primary), "secondary": _aggregate(secondary),
        **groups, "risk_alerts": alerts,
        "limitations": [
            "Feed observation is not proof of a Telegram message or an executable bookmaker price.",
            "Missing scores stay pending and never count as lost bets.",
            "Prices estimated by the same model are excluded from theoretical yield.",
            "Theoretical unit yield is not actual betting ROI; stakes and execution are unknown.",
            "Secondary selections are not confirmed published combinés; actual sent combos require Supabase ledger.",
            "Category and calibration warnings require adequate sample sizes.",
        ],
    }


def write_audit(feed, fixtures=(), *, observed_at, ledger_path="bsd/publication_ledger.json",
                report_path="bsd/quality_report.json", retired=()):
    path = Path(ledger_path)
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    ledger = update_ledger(previous, feed, fixtures, observed_at=observed_at, retired=retired)
    report = audit_report(ledger, generated_at=observed_at)
    path.parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data.json")
    parser.add_argument("--ledger", default="bsd/publication_ledger.json")
    parser.add_argument("--report", default="bsd/quality_report.json")
    args = parser.parse_args()
    feed = json.loads(Path(args.data).read_text(encoding="utf-8"))
    report = write_audit(feed.get("matches") or [],
                         observed_at=datetime.now(timezone.utc).isoformat(),
                         ledger_path=args.ledger, report_path=args.report,
                         retired=feed.get("retired_predictions") or [])
    print("BSD_QUALITY_AUDIT", json.dumps({
        "tracked": report["total_ever_observed"], "settled": report["settled"],
        "unexplained": report["unexplained_absences"]}))


if __name__ == "__main__":
    main()
