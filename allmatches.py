#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
allmatches.py - Télécharge tous les matchs depuis 2024 jusqu'à hier
via SportData, mois par mois, et sauvegarde dans cache/all_matches.json.
À exécuter localement une fois.
"""

import os
import json
import requests
import time
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

START_DATE = datetime(2024,1,1).date()
END_DATE = datetime.now().date() - timedelta(days=1)

CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")

def fetch_games(date_from, date_to):
    params = {
        "startDate": date_from.strftime("%d/%m/%Y"),
        "endDate": date_to.strftime("%d/%m/%Y"),
        "sports": 1,
        "showOdds": "false",
        "onlyMajorGames": "false"
    }
    try:
        resp = session.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("games", [])
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return []

def extract_game_info(game):
    start_time = game.get("startTime")
    competition = game.get("competitionDisplayName", "")
    home = game.get("homeCompetitor", {})
    away = game.get("awayCompetitor", {})
    home_score = home.get("score")
    away_score = away.get("score")
    if home_score == -1: home_score = None
    if away_score == -1: away_score = None
    return {
        "id": game.get("id"),
        "start_time": start_time,
        "home_team": home.get("name",""),
        "away_team": away.get("name",""),
        "competition": competition,
        "home_score": home_score,
        "away_score": away_score,
        "status_group": game.get("statusGroup"),
        "status_text": game.get("statusText"),
        "is_finished": (game.get("statusGroup") == 4)
    }

def main():
    print("="*60)
    print("🚀 TÉLÉCHARGEMENT HISTORIQUE DES MATCHS DEPUIS 2024")
    print(f"Période : {START_DATE.strftime('%d/%m/%Y')} → {END_DATE.strftime('%d/%m/%Y')}")
    print("="*60)
    all_matches = []
    current = START_DATE
    while current <= END_DATE:
        if current.month == 12:
            next_month = current.replace(year=current.year+1, month=1, day=1)
        else:
            next_month = current.replace(month=current.month+1, day=1)
        month_end = min(next_month - timedelta(days=1), END_DATE)
        print(f"\n📅 Mois : {current.strftime('%Y-%m')}")
        games = fetch_games(current, month_end)
        if games:
            extracted = [extract_game_info(g) for g in games]
            all_matches.extend(extracted)
            print(f"   ✅ {len(extracted)} matchs ajoutés (total {len(all_matches)})")
        else:
            print(f"   ⚠️ Aucune donnée pour ce mois")
        current = next_month
        time.sleep(1)
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_matches, f, indent=2, ensure_ascii=False)
    print(f"\n💾 {len(all_matches)} matchs sauvegardés dans {CACHE_FILE}")

if __name__ == "__main__":
    main()