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

OUTPUT = Path("bsd/data_bsd.json")


def generate(fixtures, history, *, now=None):
    now = now or datetime.now(timezone.utc)
    index = HistoryIndex(history)
    results = []
    skipped = Counter()
    for item in fixtures:
        prediction, reason = predict_fixture(item, index, clock=now)
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
    result = generate(fixtures, history, now=now)
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
