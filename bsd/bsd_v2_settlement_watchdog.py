#!/usr/bin/env python3
"""Watchdog de règlement BSD V2.

Réessaie les matchs publiés après leur coup d'envoi sans jamais changer le pari :
- H+4 : premier contrôle BSD sans cache ;
- H+8 : nouveau contrôle complet ;
- H+12 : contrôle de secours par endpoint événement ;
- si le score reste indisponible, statut explicite settlement_pending.

Les lignes non terminées ne sont jamais intégrées au suivi de performance.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bsd_api import BSDClient
from bsd_h2h import _utc
from bsd_v2_guardrails import update_performance_tracker
from bsd_v2_publish import update_settlement


FIRST_RETRY_HOURS = 4
SECOND_RETRY_HOURS = 8
FALLBACK_HOURS = 12


def unresolved_published(matches, now):
    rows = []
    for row in matches or []:
        if not isinstance(row, dict) or str(row.get("source", "")).lower() != "bsd":
            continue
        if row.get("is_finished") or str(row.get("status", "")).lower() == "finished":
            continue
        try:
            kickoff = _utc(str(row.get("event_date") or ""))
        except (ValueError, TypeError):
            continue
        age = now - kickoff
        if age >= timedelta(hours=FIRST_RETRY_HOURS):
            rows.append((row, kickoff, age))
    return rows


def settlement_stage(age):
    hours = age.total_seconds() / 3600
    if hours >= FALLBACK_HOURS:
        return "fallback"
    if hours >= SECOND_RETRY_HOURS:
        return "h8"
    return "h4"


def apply_watchdog(data, events_by_id, *, now, detail_fetcher=None):
    """Pure update function, injectable in tests."""
    output = dict(data or {})
    matches = []
    stats = {
        "checked": 0, "settled": 0, "pending": 0,
        "h4": 0, "h8": 0, "fallback": 0, "detail_hits": 0,
    }
    for original in output.get("matches", []):
        row = original
        if not isinstance(original, dict):
            matches.append(original)
            continue
        try:
            kickoff = _utc(str(original.get("event_date") or ""))
        except (ValueError, TypeError):
            matches.append(original)
            continue
        age = now - kickoff
        if (original.get("is_finished") or
                str(original.get("status", "")).lower() == "finished" or
                age < timedelta(hours=FIRST_RETRY_HOURS)):
            matches.append(original)
            continue

        stats["checked"] += 1
        stage = settlement_stage(age)
        stats[stage] += 1
        event_id = str(original.get("source_event_id",
                                    str(original.get("id", "")).removeprefix("bsd:")))
        event = events_by_id.get(event_id)
        if (not isinstance(event, dict) or
                str(event.get("status", "")).lower() != "finished") and stage == "fallback" and detail_fetcher:
            try:
                detail = detail_fetcher(event_id)
            except Exception:
                detail = None
            if isinstance(detail, dict):
                event = detail
                stats["detail_hits"] += 1

        updated = update_settlement(original, event) if isinstance(event, dict) else original
        if updated is not original and updated.get("is_finished"):
            updated = dict(updated)
            updated["settlement_watchdog"] = {
                "stage": stage,
                "settled_at": now.isoformat(),
                "pending": False,
            }
            stats["settled"] += 1
            matches.append(updated)
            continue

        pending = dict(original)
        pending["status"] = "settlement_pending"
        pending["is_finished"] = False
        pending["settlement_pending"] = True
        pending["settlement_checked_at"] = now.isoformat()
        pending["settlement_watchdog"] = {
            "stage": stage,
            "pending": True,
            "next_retry_after": (now + timedelta(hours=4)).isoformat(),
        }
        stats["pending"] += 1
        matches.append(pending)

    output["matches"] = matches
    output["performance_tracker"] = update_performance_tracker(
        output.get("performance_tracker"), matches, now=now)
    output["settlement_watchdog"] = {
        "updated_at": now.isoformat(),
        **stats,
    }
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data.json")
    parser.add_argument("--max-requests", type=int, default=120)
    args = parser.parse_args()

    path = Path(args.data)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("source") != "bsd" or data.get("model_version") != "bsd-v2-isolated":
        raise RuntimeError("Le feed actif n'est pas BSD V2")

    now = datetime.now(timezone.utc)
    pending = unresolved_published(data.get("matches", []), now)
    if not pending:
        print("BSD_SETTLEMENT_WATCHDOG:", json.dumps({"checked": 0, "reason": "nothing_due"}))
        return

    client = BSDClient(max_requests=args.max_requests)
    days = sorted({kickoff.date() for _, kickoff, _ in pending})
    events = {}
    for day in days:
        page = client.list_events(day, day, max_pages=15, ttl=0)
        if not page.complete:
            raise RuntimeError("BSD incomplete settlement page for %s" % day)
        for event in page.events:
            if isinstance(event, dict) and event.get("id") is not None:
                events[str(event["id"])] = event

    def detail_fetcher(event_id):
        return client.get_json("/events/%s/" % int(event_id), ttl=0)

    updated = apply_watchdog(data, events, now=now, detail_fetcher=detail_fetcher)
    temp = path.with_suffix(".settlement.tmp")
    temp.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    print("BSD_SETTLEMENT_WATCHDOG:", json.dumps({
        **updated["settlement_watchdog"],
        "api_calls": client.requests_made,
    }))


if __name__ == "__main__":
    main()
