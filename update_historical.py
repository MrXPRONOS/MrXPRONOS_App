#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_historical.py - Ajoute les matchs d'hier au cache global all_matches.json
pour maintenir l'historique à jour.
Exécution quotidienne (par exemple dans le workflow update-data.yml).
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
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429,500,502,503,504])
session.mount('https://', HTTPAdapter(max_retries=retries))

CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")
yesterday = datetime.now().date() - timedelta(days=1)

def fetch_games(date):
    params = {
        "startDate": date.strftime("%d/%m/%Y"),
        "endDate": date.strftime("%d/%m/%Y"),
        "sports": 1,
        "showOdds": "false",
        "onlyMajorGames": "false"
    }
    resp = session.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("games", [])

def extract_match_info(game):
    """Extrait les informations au même format que allmatches.py."""
    start_time = game.get("startTime")
    competition = game.get("competitionDisplayName", "")
    home = game.get("homeCompetitor", {})
    away = game.get("awayCompetitor", {})
    home_name = home.get("name", "")
    away_name = away.get("name", "")
    home_score = home.get("score")
    away_score = away.get("score")
    if home_score == -1:
        home_score = None
    if away_score == -1:
        away_score = None
    status_group = game.get("statusGroup")
    return {
        "id": game.get("id"),
        "start_time": start_time,
        "home_team": home_name,
        "away_team": away_name,
        "home_score": home_score,
        "away_score": away_score,
        "status_group": status_group,
        "status_text": game.get("statusText"),
        "is_finished": (status_group == 4),
        "competition": competition
    }

def load_existing():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save(matches):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)

def main():
    print(f"📅 Mise à jour du cache avec les matchs du {yesterday}")
    games = fetch_games(yesterday)
    print(f"   → {len(games)} matchs trouvés")

    if not games:
        print("✅ Aucun nouveau match.")
        return

    # Extraire les infos
    new_matches = [extract_match_info(g) for g in games]

    # Charger l'existant
    all_matches = load_existing()
    existing_ids = {m['id'] for m in all_matches}

    # Filtrer ceux qui ne sont pas déjà dans le cache
    to_add = [m for m in new_matches if m['id'] not in existing_ids]
    print(f"   → {len(to_add)} nouveaux matchs à ajouter")

    if to_add:
        all_matches.extend(to_add)
        save(all_matches)
        print(f"✅ Cache mis à jour : maintenant {len(all_matches)} matchs")
    else:
        print("✅ Cache déjà à jour.")

if __name__ == "__main__":
    main()