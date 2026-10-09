#!/usr/bin/env python3
"""Diagnostic BSD en lecture seule. Ne publie aucun pronostic."""
import argparse
import json
import os
import sys
from datetime import date, timedelta

from bsd_api import BSDAPIError, BSDClient, BSDQuotaError


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD en UTC")
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--max-requests", type=int, default=5)
    args = parser.parse_args(argv)
    try:
        run_date = date.fromisoformat(args.date)
        if not 1 <= args.max_pages <= 10:
            parser.error("--max-pages doit être entre 1 et 10")
        if not 1 <= args.max_requests <= 25:
            parser.error("--max-requests doit être entre 1 et 25")
        client = BSDClient(max_requests=args.max_requests)
        result = client.list_events(run_date, run_date, max_pages=args.max_pages, ttl=300)
        print("BSD_DIAGNOSTIC:", json.dumps({
            "date_utc": run_date.isoformat(),
            "total_reported": result.total_reported,
            "loaded": len(result.events),
            "complete": result.complete,
            "pages_fetched": result.pages_fetched,
            "requests_made": client.requests_made,
            "cache_hits": client.cache_hits,
            "quota_remaining": client.rate_limit_remaining,
            "sample_event_ids": [str(e["id"]) for e in result.events[:5]],
            "sample_statuses": [str(e.get("status", "")) for e in result.events[:5]],
        }, ensure_ascii=False))
        if not result.complete:
            print("AVERTISSEMENT: pagination incomplète, aucune génération ne doit exploiter cette liste.", file=sys.stderr)
            return 2
        return 0
    except (BSDAPIError, ValueError) as exc:
        print("ERREUR BSD:", str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
