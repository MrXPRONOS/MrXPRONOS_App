#!/usr/bin/env python3
"""Diagnostic de la récupération saisonnière BSD (aucun fichier publié)."""
import argparse
import json
import sys

from bsd_api import BSDAPIError, BSDClient
from bsd_history import ingest_events
from bsd_h2h import local_h2h


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--league-id", type=int, default=85)
    p.add_argument("--season-id", type=int, default=0)
    p.add_argument("--pages", type=int, default=3)
    args = p.parse_args()
    if args.league_id <= 0 or args.season_id < 0 or not 1 <= args.pages <= 3:
        p.error("Valeurs invalides")
    try:
        client = BSDClient(max_requests=5)
        seasons = client.list_league_seasons(args.league_id)
        candidates = [{"id": s.get("id"), "year": s.get("year"), "name": s.get("name")} for s in seasons]
        season_id = args.season_id or next(
            (int(s["id"]) for s in seasons if s.get("is_current")),
            (int(seasons[0]["id"]) if seasons else None),
        )
        if season_id is None:
            print("Pas de saison trouvée", file=sys.stderr)
            return 2
        result = client.list_season_events(
            args.league_id, season_id, max_pages=args.pages, ttl=0,
        )
        events = ingest_events([], result.events)
        pairs = 0
        completed = 0
        sample = None
        for row in events:
            if row.get("home_team_id") is not None and row.get("away_team_id") is not None:
                pairs += 1
            if row.get("status") == "finished":
                completed += 1
            if sample is None and row.get("event_date") and row.get("home_team_id") and row.get("away_team_id"):
                sample = row
        print("BSD_SEASON_DIAGNOSTIC:", json.dumps({
            "league_id": args.league_id,
            "seasons": candidates[:8],
            "selected_season_id": season_id,
            "reported": result.total_reported,
            "loaded": len(events),
            "pages": result.pages_fetched,
            "complete": result.complete,
            "events_with_team_ids": pairs,
            "finished": completed,
            "requests": client.requests_made,
            "quota_remaining": client.rate_limit_remaining,
            "event_example": {
                "id": sample.get("id"),
                "status": sample.get("status"),
                "event_date": sample.get("event_date"),
                "home_team_id": sample.get("home_team_id"),
                "away_team_id": sample.get("away_team_id"),
                "home_score": sample.get("home_score"),
                "away_score": sample.get("away_score"),
            } if sample else None,
        }, ensure_ascii=False))
        if not result.complete:
            print("AVERTISSEMENT: saison tronquée par --pages. Aucun import définitif.", file=sys.stderr)
            return 2
        if events and pairs == 0:
            print("ERREUR: schéma équipes non reconnu, ne pas importer.", file=sys.stderr)
            return 3
        return 0
    except (BSDAPIError, ValueError) as exc:
        print("Erreur diagnostic saison:", str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
