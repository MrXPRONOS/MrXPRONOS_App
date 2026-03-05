#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_scores.py - Met à jour uniquement les scores et statuts des matchs
dans data.json, en conservant les pronostics existants.
Exécution toutes les 20 minutes.
Version corrigée : récupère les matchs des 3 derniers jours.
"""

import os
import json
import requests
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SPORTDATA_API_KEY = os.environ.get("SPORTDATA_API_KEY")
if not SPORTDATA_API_KEY:
    raise ValueError("SPORTDATA_API_KEY non définie")

BASE_URL = "https://v1.football.sportsapipro.com/games/allscores"
HEADERS = {"x-api-key": SPORTDATA_API_KEY}

session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[429,500,502,503,504])
session.mount('https://', HTTPAdapter(max_retries=retries))

DATA_FILE = "data.json"
today = datetime.now().date()
# On récupère les 3 derniers jours pour rattraper les scores manquants
days_to_fetch = [today, today - timedelta(days=1), today - timedelta(days=2)]

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
        resp = session.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("games", [])
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
    print(f"✅ Total : {len(all_games)} matchs récupérés")

    if not all_games:
        print("Aucun nouveau match, arrêt.")
        return

    scores_dict = {}
    for g in all_games:
        gid = g.get("id")
        home_comp = g.get("homeCompetitor", {})
        away_comp = g.get("awayCompetitor", {})
        home_score = home_comp.get("score")
        away_score = away_comp.get("score")
        if home_score == -1:
            home_score = None
        if away_score == -1:
            away_score = None
        scores_dict[gid] = {
            "home_score": home_score,
            "away_score": away_score,
            "status_group": g.get("statusGroup"),
            "status_text": g.get("statusText")
        }

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {"matches": [], "categories": {"simple": [], "pro": [], "vip": []}, "stats": {}, "bookmakers": []}

    updated = 0
    for match in data.get("matches", []):
        gid = match.get("id")
        if gid in scores_dict:
            s = scores_dict[gid]
            match["home_score"] = s["home_score"]
            match["away_score"] = s["away_score"]
            match["status"] = s["status_text"]
            updated += 1

    print(f"✅ {updated} matchs mis à jour dans data.json")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()