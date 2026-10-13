#!/usr/bin/env python3
"""Génération test BSD. Produit uniquement bsd/data_bsd.json, jamais data.json."""
from __future__ import annotations
import argparse
import json
import os
from collections import Counter
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from bsd_api import BSDAPIError, BSDClient
from bsd_archive import MATCHES_FILE, _read_json
from bsd_predict import HistoryIndex, predict_fixture
from bsd_markets import MarketCalibrator
from bsd_enrich import enrich_leagues
from free_football_providers import FreeFootballProviders

OUTPUT = Path("bsd/data_bsd.json")


def generate(fixtures, history, *, now=None, calibration=None):
    now = now or datetime.now(timezone.utc)
    index = HistoryIndex(history)
    results = []
    skipped = Counter()
    for item in fixtures:
        prediction, reason = predict_fixture(item, index, clock=now, calibration=calibration)
        if prediction is not None:
            results.append(prediction)
        else:
            skipped[reason] += 1
    results.sort(key=lambda item: (-item["final_score"], item["event_date"], item["id"]))
    return {
        "source": "bsd",
        "experimental": True,
        "published": False,
        "generated_at": now.isoformat(),
        "matches": results,
        "categories": {name: [m for m in results if m["category"] == name]
                       for name in ("simple", "pro", "vip")},
        "diagnostics": {"fixtures_read": len(fixtures), "historical_matches_read": len(history),
                        "history_eligible": index.eligible, "predictions": len(results),
                        "skipped": dict(sorted(skipped.items()))},
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    p.add_argument("--days", type=int, default=1)
    p.add_argument("--max-pages", type=int, default=5)
    p.add_argument("--max-requests", type=int, default=10)
    args = p.parse_args()
    if not 1 <= args.days <= 3 or not 1 <= args.max_pages <= 10:
        p.error("days doit etre 1-3 et max-pages 1-10")
    target = date.fromisoformat(args.date)
    history = _read_json(MATCHES_FILE, None)
    if not isinstance(history, list) or not history:
        raise RuntimeError("Historique BSD absent : executer bsd_archive.py restore")
    client = BSDClient(max_requests=args.max_requests)
    now = datetime.now(timezone.utc)
    fixtures = []
    for i in range(args.days):
        d = target + timedelta(days=i)
        batch = client.list_events(d, d, max_pages=args.max_pages, ttl=0)
        if not batch.complete:
            raise RuntimeError("Journee BSD incomplete : %s (%d/%d)" %
                               (d, len(batch.events), batch.total_reported))
        fixtures.extend(batch.events)
    # Conserver les IDs BSD indispensables au moteur, mais tenter d'abord
    # les sources gratuites pour les noms/logos de compétition afin d'éviter
    # un appel catalogue BSD purement métadonnées.
    free_hub = FreeFootballProviders(session=client.session)
    free_matches = []
    for i in range(args.days):
        d = target + timedelta(days=i)
        for result in free_hub.day(d):
            free_matches.extend(result.events)
    free_metadata_matches = 0
    for fixture in fixtures:
        base = {
            "home_team": (fixture.get("home_team") or {}).get("name")
                if isinstance(fixture.get("home_team"), dict) else fixture.get("home_team"),
            "away_team": (fixture.get("away_team") or {}).get("name")
                if isinstance(fixture.get("away_team"), dict) else fixture.get("away_team"),
            "event_date": fixture.get("event_date"),
        }
        match = free_hub.best_match(base, free_matches, threshold=.68)
        if not match:
            continue
        if not fixture.get("league_name") and match.get("league"):
            fixture["league_name"] = match["league"]
        for side in ("home", "away"):
            if not fixture.get(side + "_logo") and match.get(side + "_logo"):
                fixture[side + "_logo"] = match[side + "_logo"]
        free_metadata_matches += 1

    league_diag = enrich_leagues(fixtures, client)
    league_diag["free_metadata_matches"] = free_metadata_matches
    league_diag["free_provider_calls"] = dict(free_hub.calls)
    calibration_path = Path('bsd/calibration_bsd.json')
    if not calibration_path.exists():
        raise RuntimeError('Calibration BSD absente : lancer bsd_calibrate.py --year 2025')
    calibration = MarketCalibrator.from_dict(json.loads(calibration_path.read_text(encoding='utf-8')))
    result = generate(fixtures, history, now=now, calibration=calibration)
    result["diagnostics"].update(league_diag)
    if not fixtures:
        raise RuntimeError("BSD n'a renvoye aucun match : diagnostic, pas de remplacement du fichier")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUTPUT.with_suffix(".tmp")
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(OUTPUT)
    print("BSD_PREDICTION_DIAGNOSTIC:", json.dumps({
        **result["diagnostics"],
        "http_calls": client.requests_made,
        "quota_remaining": client.rate_limit_remaining,
        "output": str(OUTPUT),
        "experimental": True,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
