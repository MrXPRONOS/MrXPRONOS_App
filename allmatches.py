#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
allmatches.py - Télécharge tous les matchs depuis le 1er janvier 2024 jusqu'à hier
en utilisant l'API SportData (sportsapipro.com) et les sauvegarde dans un cache local.
Exécution locale (une seule fois) pour initialiser la base de données historique.
"""

import os
import json
import requests
import time
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_KEY = os.environ.get("SPORTDATA_API_KEY", "0b4628b4-83cc-4227-bed6-82c50d806514")
BASE_URL = "https://v1.football.sportsapipro.com/games/allscores"
HEADERS = {"x-api-key": API_KEY}

session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

START_DATE = datetime(2024, 1, 1).date()
END_DATE = datetime.now().date() - timedelta(days=1)

CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")

print("="*60)
print(f"🚀 TÉLÉCHARGEMENT DE TOUS LES MATCHS DEPUIS 2024")
print(f"Période : {START_DATE.strftime('%d/%m/%Y')} → {END_DATE.strftime('%d/%m/%Y')}")
print("="*60)

def fetch_games(date_from, date_to):
    params = {
        "startDate": date_from.strftime("%d/%m/%Y"),
        "endDate": date_to.strftime("%d/%m/%Y"),
        "sports": 1,
        "showOdds": "false",
        "onlyMajorGames": "false"
    }
    try:
        print(f"   📡 Requête pour {date_from.strftime('%d/%m/%Y')} → {date_to.strftime('%d/%m/%Y')}")
        resp = session.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"   ❌ Erreur {resp.status_code}: {resp.text}")
            return None
        data = resp.json()
        games = data.get("games", [])
        print(f"      → {len(games)} matchs reçus")
        return games
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return None

def extract_match_info(game):
    start_time = game.get("startTime")
    status_group = game.get("statusGroup")
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
    return {
        "id": game.get("id"),
        "start_time": start_time,
        "date": start_time[:10] if start_time else "",
        "home_team": home_name,
        "away_team": away_name,
        "competition": competition,
        "home_score": home_score,
        "away_score": away_score,
        "status_group": status_group,
        "is_finished": (status_group == 4)
    }

def download_all_matches():
    all_matches = []
    current_start = START_DATE
    while current_start <= END_DATE:
        if current_start.month == 12:
            next_month = current_start.replace(year=current_start.year+1, month=1, day=1)
        else:
            next_month = current_start.replace(month=current_start.month+1, day=1)
        month_end = min(next_month - timedelta(days=1), END_DATE)

        print(f"\n📅 Mois : {current_start.strftime('%Y-%m')}")
        games = fetch_games(current_start, month_end)
        if games:
            extracted = [extract_match_info(g) for g in games]
            all_matches.extend(extracted)
            print(f"   ✅ {len(extracted)} matchs ajoutés (total {len(all_matches)})")
        else:
            print(f"   ⚠️ Aucune donnée pour ce mois")

        current_start = next_month
        time.sleep(1)

    return all_matches

def save_to_cache(matches):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)
    print(f"\n💾 {len(matches)} matchs sauvegardés dans {CACHE_FILE}")

def main():
    print("\n🔄 Téléchargement en cours...")
    matches = download_all_matches()
    if matches:
        save_to_cache(matches)
    else:
        print("❌ Aucun match récupéré.")
    print("\n✅ Téléchargement terminé !")

if __name__ == "__main__":
    main()