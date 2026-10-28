#!/usr/bin/env python3
"""Read-only provider HTTP and schema smoke test for BSD V2.

Never logs credentials, fixture/team names, raw response bodies, URLs with
tokens or exception messages. No Supabase, website or Telegram writes.
A 200 alone is NOT a verified usable quote.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
import requests

from bsd_odds_fallback import (from_movi, from_oddslink, from_oddslink_public,
                               from_pinnwire, utc, decimal)

ENDPOINTS = {
    "oddslink_public": "https://oddslink.app/v1/public/board/soccer",
    "moviodds": "https://moviodds.com/odds?sport=soccer&groups=40",
    "pinnwire": "https://pinnwire.com/kit/v1/prematch/fixtures?sport_id=1",
    "oddslink": "https://oddslink.app/v1/sports/soccer/odds?league=epl&oddsFormat=decimal",
}
PARSERS = {"oddslink_public": from_oddslink_public,
           "moviodds": from_movi,
           "pinnwire": from_pinnwire,
           "oddslink": from_oddslink}


def summarize(name, payload, now):
    """Distinguish a valid vendor JSON shape from current, parseable prices."""
    if name in ("oddslink",):
        valid = isinstance(payload, list)
        events = payload if valid else []
    else:
        field = {"oddslink_public": "fixtures", "moviodds": "matches",
                 "pinnwire": "events"}[name]
        valid = isinstance(payload, dict) and isinstance(payload.get(field), list)
        events = payload[field] if valid else []
    valid_prices = 0
    parsed_prices = 0
    fixtures_with_prices = 0
    for fixture in events[:250]:
        if not isinstance(fixture, dict):
            continue
        if name in ("moviodds", "oddslink_public") and fixture.get("in_play") is True:
            continue
        parsed = PARSERS[name](fixture, now)
        if not isinstance(parsed, dict):
            continue
        parsed_prices += len(parsed)
        current = sum(1 for q in parsed.values()
                      if isinstance(q, dict)
                      and decimal(q.get("odds")) is not None
                      and q.get("quote_timestamp_verified") is True
                      and (stamp := utc(q.get("updated_at"))) is not None
                      and 0 <= (now-stamp).total_seconds() <= 7200)
        valid_prices += current
        fixtures_with_prices += int(current > 0)
    return {"schema_valid": valid, "fixtures": len(events),
            "fixtures_scanned": min(250, len(events)),
            "parsed_prices": parsed_prices,
            "fresh_timestamped_prices": valid_prices,
            "fixtures_with_fresh_prices": fixtures_with_prices}


def probe(name, url, headers=None, *, session=requests, now=None):
    now = now or datetime.now(timezone.utc)
    row = {"provider": name, "connected": False, "schema_valid": False,
           "fixtures": 0, "fresh_timestamped_prices": 0}
    try:
        response = session.get(url, headers=headers or {}, timeout=25)
        row["http"] = response.status_code
        if response.status_code != 200:
            row["result"] = "restricted" if response.status_code in (401,402,403,429) else "http_error"
            return row
        row["connected"] = True
        summary = summarize(name, response.json(), now)
        row.update(summary)
        row["result"] = ("usable_prices" if summary["fresh_timestamped_prices"] > 0 else
                         "schema_only" if summary["schema_valid"] else "invalid_schema")
    except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError) as exc:
        row["result"] = "request_or_schema_error"
        row["error_type"] = type(exc).__name__
    return row


def main():
    chosen = os.getenv("ODDS_SMOKE_PROVIDER", "all")
    if chosen not in ("all", *ENDPOINTS):
        raise SystemExit("Invalid provider")
    names = list(ENDPOINTS) if chosen == "all" else [chosen]
    results = []
    for name in names:
        headers = {}
        if name == "pinnwire":
            key = os.getenv("PINNWIRE_API_KEY", "")
            if not key and os.getenv("PINNWIRE_USE_DEMO") == "1":
                key = "demo"
            if not key:
                results.append({"provider": name, "result": "skipped_no_key"})
                continue
            headers = {"x-api-key": key}
        if name == "oddslink":
            key = os.getenv("ODDSLINK_API_KEY", "")
            if not key:
                results.append({"provider": name, "result": "skipped_no_key"})
                continue
            headers = {"X-API-Key": key}
        results.append(probe(name, ENDPOINTS[name], headers))
    for item in results:
        print("ODDS_PROVIDER_HEALTH=" + json.dumps(item, sort_keys=True))
    schema_ok = any(r.get("schema_valid") for r in results)
    prices_ok = any(r.get("fresh_timestamped_prices", 0) > 0 for r in results)
    print("ODDS_SMOKE_RESULT=" + ("PASS" if prices_ok else "DEGRADED" if schema_ok else "FAIL"))
    return 0 if schema_ok else 1


if __name__ == "__main__":
    sys.exit(main())
