#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_scores.py - Met à jour les scores et statuts des matchs.
Version avec rotation de clés API.
"""

import os
import json
from datetime import datetime, timedelta
from api_utils import make_request

SPORTDATA_URL = "https://v1.football.sportsapipro.com/games/allscores"
today = datetime.now().date()
days_to_fetch = [today, today - timedelta(days=1), today - timedelta(days=2)]
DATA_FILE = "data.json"

print("="*60)
print(f"🔄 MISE À JOUR DES SCORES - {today} {datetime.now().strftime('%H:%M')}")
print("="*60)

def fetch_games(date):
    params = {
        "startDate": date.strftime("%d/%m/%Y"),
        "endDate": date.strftime("%d/%m/%Y"),
        "sports": 1,
        "showOdds": "false",
        "onlyMajorGames": "false"
    }
    try:
        resp = make_request('GET', SPORTDATA_URL, params=params, timeout=30)
        return resp.json().get("games", [])
    except Exception as e:
        print(f"❌ Erreur pour {date}: {e}")
        return []

def main():
    all_games = []
    for day in days_to_fetch:
        print(f"📅 Récupération des matchs du {day}...")
        games = fetch_games(day)
        all_games.extend(games)
        print(f"   {len(games)} matchs")

    if not all_games:
        print("Aucun nouveau match, arrêt.")
        return

    scores_dict = {}
    for g in all_games:
        gid = g.get("id")
        home = g.get("homeCompetitor", {})
        away = g.get("awayCompetitor", {})
        home_score = home.get("score")
        away_score = away.get("score")
        if home_score == -1: home_score = None
        if away_score == -1: away_score = None
        scores_dict[gid] = {
            "home_score": home_score,
            "away_score": away_score,
            "status_text": g.get("statusText")
        }

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updated = 0
    for match in data.get("matches", []):
        gid = match.get("id")
        if gid in scores_dict:
            s = scores_dict[gid]
            match["home_score"] = s["home_score"]
            match["away_score"] = s["away_score"]
            match["status"] = s["status_text"]
            updated += 1

    print(f"✅ {updated} matchs mis à jour")
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()