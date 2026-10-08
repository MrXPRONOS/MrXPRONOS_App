#!/usr/bin/env python3
"""Backfill BSD 2016-2024 : historique JSON progressif, borné par requêtes.

Le code ne modifie ni data.json ni SportData. Il n'utilise que les saisons
explicitement retournées par BSD; impossible de supposer la couverture 2016.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from bsd_api import BSDClient, BSDAPIError, BSDQuotaError, BSDRequestBudgetError
from bsd_history import ingest_events
from bsd_archive import MATCHES_FILE, STATE_FILE, initial_state, _write_json, _read_json


def items_from_leagues(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise BSDAPIError("Format catalogue leagues inattendu")
    if not isinstance(payload.get("count"), int):
        raise BSDAPIError("Count des championnats absent")
    return payload["results"], payload["count"]


def league_id(item):
    if not isinstance(item, dict) or item.get("id") is None:
        raise BSDAPIError("Ligue BSD sans ID")
    return int(item["id"])


def season_year(season):
    year = season.get("year")
    if year is not None:
        try:
            return int(str(year)[:4])
        except ValueError:
            pass
    name = str(season.get("name") or "")
    import re
    match = re.search(r"(?<!\d)(20(?:1[6-9]|2[0-4]))(?!\d)", name)
    return int(match.group(1)) if match else None


def load():
    matches = _read_json(MATCHES_FILE, [])
    state = _read_json(STATE_FILE, initial_state())
    if not isinstance(matches, list) or not isinstance(state, dict):
        raise ValueError("Historique BSD local non initialise : executer restore")
    if state.get("provider") != "BSD" or state.get("year_from") != 2016 or state.get("year_to") != 2024:
        raise ValueError("Etat BSD incompatible avec 2016-2024")
    return matches, state


def save(matches, state):
    _write_json(MATCHES_FILE, matches)
    _write_json(STATE_FILE, state)


def run(request_budget=90, league_page_size=100, max_season_pages=10):
    if not 1 <= request_budget <= 500:
        raise ValueError("Budget 1-500 par lancement")
    client = BSDClient(max_requests=request_budget)
    matches, state = load()
    known = set(str(i) for i in state.get("league_ids", []))
    completed = set(str(x) for x in state.get("completed_seasons", []))
    tasks = state.get("season_tasks", [])
    if not isinstance(tasks, list):
        raise ValueError("season_tasks invalide")

    # Découverte incrémentale de toutes les ligues, une page à la fois.
    while not state.get("catalog_complete") and client.requests_made < request_budget:
        off = state.get("discovery_index", 0)
        try:
            payload = client.get_json("/leagues/", {"limit": league_page_size, "offset": off}, ttl=0)
            leagues, total = items_from_leagues(payload)
            for item in leagues:
                lid = str(league_id(item))
                if lid not in known:
                    known.add(lid)
                    state["league_ids"].append(int(lid))
            state["discovery_index"] = off + len(leagues)
            state["catalog_complete"] = state["discovery_index"] >= total or not leagues
            save(matches, state)
            print("BSD leagues: %d/%d" % (state["discovery_index"], total))
        except (BSDAPIError, BSDRequestBudgetError, BSDQuotaError) as exc:
            print("Arret decouverte: %s" % exc)
            break

    # Complète ensuite chaque ligue en une saison par exécution si le quota le permet.
    cursor = int(state.get("league_cursor", 0))
    while cursor < len(state["league_ids"]) and client.requests_made + max_season_pages + 1 <= request_budget:
        lid = state["league_ids"][cursor]
        try:
            seasons = client.list_league_seasons(lid, ttl=0)
            for season in seasons:
                year = season_year(season)
                if year is not None and 2016 <= year <= 2024:
                    sid = int(season["id"])
                    token = "%d:%d" % (lid, sid)
                    if token not in completed and not any(t["key"] == token for t in tasks):
                        tasks.append({"key": token, "league_id": lid, "season_id": sid, "year": year})
            cursor += 1
            state["league_cursor"] = cursor
            state["season_tasks"] = tasks
            save(matches, state)
        except (BSDAPIError, BSDQuotaError) as exc:
            print("Erreur saison ligue %s: %s" % (lid, exc))
            break

    # Importations terminées d'un bloc seulement, jamais de saisons partielles silencieuses.
    task_cursor = int(state.get("task_cursor", 0))
    while task_cursor < len(tasks) and client.requests_made + max_season_pages <= request_budget:
        task = tasks[task_cursor]
        try:
            page = client.list_season_events(task["league_id"], task["season_id"], max_pages=max_season_pages, ttl=0)
            if not page.complete:
                print("Saison %s incomplete (%d/%d) : augmenter --season-pages" % (task["key"], len(page.events), page.total_reported))
                # Ne jamais marquer une saison partielle comme terminee.
                state["incomplete_task"] = task["key"]
                save(matches, state)
                break
            finished = [m for m in page.events if str(m.get("status") or "").lower() == "finished"]
            matches = ingest_events(matches, finished)
            completed.add(task["key"])
            state["completed_seasons"] = sorted(completed)
            state.pop("incomplete_task", None)
            task_cursor += 1
            state["task_cursor"] = task_cursor
            save(matches, state)
            print("Saison %s: %d matchs termines; total JSON=%d" % (task["key"], len(finished), len(matches)))
        except (BSDAPIError, BSDQuotaError) as exc:
            print("Erreur import saison %s: %s" % (task["key"], exc))
            break
    state["last_calls"] = client.requests_made
    state["last_quota_remaining"] = client.rate_limit_remaining
    save(matches, state)
    print("BSD_BACKFILL: %s" % json.dumps({
        "matches": len(matches), "leagues_discovered": len(known),
        "seasons_planned": len(tasks), "seasons_done": len(completed),
        "http_calls": client.requests_made, "quota_remaining": client.rate_limit_remaining,
        "catalog_complete": state["catalog_complete"],
    }))
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--budget", type=int, default=90)
    p.add_argument("--season-pages", type=int, default=10)
    args = p.parse_args()
    try:
        raise SystemExit(run(args.budget, max_season_pages=args.season_pages))
    except (BSDAPIError, ValueError) as exc:
        print("ERREUR BSD:", exc, file=sys.stderr)
        raise SystemExit(1)
