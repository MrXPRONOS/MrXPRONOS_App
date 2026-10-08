#!/usr/bin/env python3
"""Backtest BSD glissant sur les N derniers jours UTC TERMINES.

Sans publication: interroge BSD uniquement pour les scores officiels des dates
cible; chaque prediction est calculee depuis un historique figé AVANT la fenêtre.
Le gel volontaire des données à J-3 est conservateur (pas de fuite temporelle).
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from bsd_api import BSDClient
from bsd_archive import MATCHES_FILE, _read_json
from bsd_backtest import wilson_interval
from bsd_h2h import _utc, _valid_score
from bsd_markets import MarketCalibrator, candidates_from_goals, realized
from bsd_predict import HistoryIndex, predict_fixture

REPORT = Path("bsd/recent_backtest_report.json")
BASELINES = ("1X", "X2", "12", "OVER_15", "UNDER_35", "BTTS_YES")


def window_dates(end_date: date, days: int, *, today: date) -> List[date]:
    if not 3 <= days <= 14:
        raise ValueError("La fenêtre de backtest doit contenir de 3 à 14 jours.")
    if end_date >= today:
        raise ValueError("Seules les journées UTC terminées peuvent être vérifiées.")
    start = end_date - timedelta(days=days - 1)
    if start < date(2024, 1, 1) or end_date > date(2026, 12, 31):
        raise ValueError("Dates hors de l'historique BSD 2024-2026.")
    return [start + timedelta(days=i) for i in range(days)]


def collect_results(client: BSDClient, days: List[date], *, max_pages: int = 10) -> Dict[str, List[dict]]:
    if not days:
        raise ValueError("Journées manquantes.")
    if not 1 <= max_pages <= 20:
        raise ValueError("max_pages hors limites.")
    out = {}
    for day in days:
        page = client.list_events(day, day, max_pages=max_pages, ttl=0)
        if not page.complete:
            raise RuntimeError("Résultats BSD incomplets pour %s : %d/%d." %
                               (day, len(page.events), page.total_reported))
        out[day.isoformat()] = page.events
    return out


def _rate(wins: int, total: int) -> Optional[float]:
    return round(wins / total, 4) if total else None


def _summarize(counter: Counter) -> Dict[str, Any]:
    n = counter["selected"]
    return {
        "fixtures": counter["fixtures"],
        "finished_with_scores": counter["finished_with_scores"],
        "not_finished_or_missing_scores": counter["unsettled"],
        "selected": n,
        "wins": counter["wins"],
        "losses": n - counter["wins"],
        "hit_rate": _rate(counter["wins"], n),
        "wilson_95_interval": wilson_interval(counter["wins"], n),
        "prediction_coverage_of_finished": _rate(n, counter["finished_with_scores"]),
    }


def evaluate_recent(
    fixtures_by_day: Dict[str, List[dict]],
    history: List[dict],
    calibration: MarketCalibrator,
    *,
    end_date: date,
    days: int = 3,
) -> Dict[str, Any]:
    targets = window_dates(end_date, days, today=end_date + timedelta(days=1))
    if not isinstance(history, list) or not history:
        raise ValueError("Historique BSD absent.")
    if any(day.isoformat() not in fixtures_by_day for day in targets):
        raise ValueError("Il manque au moins une journée dans les résultats de l'API.")
    start = targets[0]
    # Le match de la veille peut avoir été encore en cours après minuit.
    # Aucun match joué pendant les trois jours testés ne sert à prédire ceux-ci.
    freeze_at = datetime.combine(start, time.min, tzinfo=timezone.utc) - timedelta(hours=4)
    historical = []
    for event in history:
        if not isinstance(event, dict):
            continue
        try:
            if _utc(str(event.get("event_date") or "")) < freeze_at:
                historical.append(event)
        except (TypeError, ValueError):
            continue
    index = HistoryIndex(historical)
    totals = Counter()
    per_day = {day.isoformat(): Counter() for day in targets}
    per_market = defaultdict_counter()
    rejected = Counter()
    baseline = Counter()
    predicted_sum = 0.0
    brier_sum = 0.0
    examples = []
    seen = set()
    raw_api_ids = 0

    for day in targets:
        key = day.isoformat()
        daily = per_day[key]
        for event in fixtures_by_day[key]:
            totals["fixtures"] += 1
            daily["fixtures"] += 1
            if not isinstance(event, dict):
                rejected["invalid_event"] += 1
                totals["unsettled"] += 1
                daily["unsettled"] += 1
                continue
            mid = event.get("id")
            if mid is None or str(mid) in seen:
                rejected["duplicate_or_missing_event_id"] += 1
                totals["unsettled"] += 1
                daily["unsettled"] += 1
                continue
            seen.add(str(mid))
            raw_api_ids += 1
            try:
                actual_day = _utc(str(event.get("event_date") or "")).date()
            except (ValueError, TypeError):
                rejected["invalid_event_date"] += 1
                totals["unsettled"] += 1
                daily["unsettled"] += 1
                continue
            if actual_day != day:
                rejected["date_mismatch"] += 1
                totals["unsettled"] += 1
                daily["unsettled"] += 1
                continue
            home_score = _valid_score(event.get("home_score"))
            away_score = _valid_score(event.get("away_score"))
            if str(event.get("status") or "").lower() != "finished" or home_score is None or away_score is None:
                totals["unsettled"] += 1
                daily["unsettled"] += 1
                continue
            totals["finished_with_scores"] += 1
            daily["finished_with_scores"] += 1
            fixture = dict(event)
            fixture["status"] = "notstarted"
            # Aucune information de score courant transmise au prédicteur.
            fixture["home_score"] = None
            fixture["away_score"] = None
            kickoff = _utc(str(fixture["event_date"]))
            pred, reason = predict_fixture(
                fixture, index, calibration=calibration, clock=kickoff - timedelta(seconds=1),
            )
            if pred is None:
                rejected[reason] += 1
                continue
            pick = pred["prediction"]
            markets = {
                m.key: m for m in candidates_from_goals(
                    pred["estimated_goals"]["home"], pred["estimated_goals"]["away"]
                )
            }
            selection = pick["selection_key"]
            if selection not in markets:
                rejected["selection_not_recognized"] += 1
                continue
            outcome = realized(markets[selection], home_score, away_score)
            totals["selected"] += 1
            daily["selected"] += 1
            totals["wins"] += outcome
            daily["wins"] += outcome
            per_market[selection]["selected"] += 1
            per_market[selection]["wins"] += outcome
            p = pick["confidence"] / 100
            predicted_sum += p
            brier_sum += (p - outcome) ** 2
            for market in BASELINES:
                baseline[(market, "total")] += 1
                baseline[(market, "wins")] += realized(markets[market], home_score, away_score)
            # Enregistre une sélection dérivée, jamais la base d'événements bruts.
            examples.append({
                "date": key,
                "fixture_id": str(mid),
                "home_team": pred["home_team"],
                "away_team": pred["away_team"],
                "pick": pick["type"],
                "selection": selection,
                "market_code_internal": pick["market_code"],
                "estimated_probability": pick["confidence"],
                "won": bool(outcome),
            })

    report = {
        "mode": "three_day_pre_window_snapshot_backtest",
        "experimental": True,
        "days": days,
        "start_date_utc": start.isoformat(),
        "end_date_utc": end_date.isoformat(),
        "history_frozen_before_utc": freeze_at.isoformat(),
        "history_events_used": index.eligible,
        "summary": _summarize(totals),
        "by_day": {k: _summarize(per_day[k]) for k in sorted(per_day)},
        "rejected_predictions": dict(sorted(rejected.items())),
        "by_market": {
            market: {
                "selected": stat["selected"], "wins": stat["wins"],
                "hit_rate": _rate(stat["wins"], stat["selected"]),
                "wilson_95_interval": wilson_interval(stat["wins"], stat["selected"]),
            }
            for market, stat in sorted(per_market.items())
        },
        "fixed_market_baselines_same_selected_fixtures": {
            market: {"selected": baseline[(market, "total")],
                     "hit_rate": _rate(baseline[(market, "wins")], baseline[(market, "total")])}
            for market in BASELINES
            if baseline[(market, "total")]
        },
        "average_predicted": round(predicted_sum / totals["selected"], 4) if totals["selected"] else None,
        "brier_score": round(brier_sum / totals["selected"], 5) if totals["selected"] else None,
        "predictions": examples,
        "limitations": (
            "Test rétrospectif, non prospectif. Le gel de l'historique avant la fenêtre limite la fuite "
            "temporelle, mais les données historiques peuvent avoir été révisées après coup. "
            "Sans les cotes disponibles au moment de chaque match, aucun ROI ne peut être calculé."
        ),
    }
    if raw_api_ids == 0 or totals["finished_with_scores"] == 0:
        raise RuntimeError("Aucun match terminé et vérifiable pendant la période demandée.")
    return report


def defaultdict_counter():
    from collections import defaultdict
    return defaultdict(Counter)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest BSD sur 3 à 14 journées UTC complètes.")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--end-date", default="", help="Date UTC de dernière journée, exclut aujourd'hui.")
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--max-requests", type=int, default=45)
    parser.add_argument("--output", default=str(REPORT))
    args = parser.parse_args()
    today = datetime.now(timezone.utc).date()
    end_date = date.fromisoformat(args.end_date) if args.end_date else today - timedelta(days=1)
    targets = window_dates(end_date, args.days, today=today)
    history = _read_json(MATCHES_FILE, None)
    if not isinstance(history, list) or not history:
        parser.error("Historique BSD absent : restaurer l'archive.")
    cal_path = Path("bsd/calibration_bsd.json")
    if not cal_path.exists():
        parser.error("Calibration absente : exécuter bsd_calibrate.py auparavant.")
    calibration = MarketCalibrator.from_dict(json.loads(cal_path.read_text(encoding="utf-8")))
    client = BSDClient(max_requests=args.max_requests)
    fixtures_by_day = collect_results(client, targets, max_pages=args.max_pages)
    report = evaluate_recent(fixtures_by_day, history, calibration, end_date=end_date, days=args.days)
    report["http_calls"] = client.requests_made
    report["quota_remaining"] = client.rate_limit_remaining
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    print("BSD_RECENT_BACKTEST:", json.dumps({
        k: report[k] for k in ("start_date_utc", "end_date_utc", "history_frozen_before_utc",
                              "history_events_used", "summary", "by_day", "by_market",
                              "fixed_market_baselines_same_selected_fixtures",
                              "average_predicted", "brier_score", "http_calls", "quota_remaining")
    }, ensure_ascii=False))
    print("BSD_RECENT_BACKTEST_DETAILS: %s (%d selections)" % (path, len(report["predictions"])))


if __name__ == "__main__":
    main()
