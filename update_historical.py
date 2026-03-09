#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_historical.py - Ajoute les matchs d'hier au cache global all_matches.json
pour maintenir l'historique à jour.
Utilise la rotation de clés API via api_utils.
Exécution quotidienne.
"""

import os
import json
from datetime import datetime, timedelta
from api_utils import make_request

SPORTDATA_URL = "https://v1.football.sportsapipro.com/games/allscores"
CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")
yesterday = datetime.now().date() - timedelta(days=1)

def fetch_games(date):
    """Récupère les matchs pour une date donnée via l'API SportData."""
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
        print(f"❌ Erreur lors de la récupération des matchs pour {date}: {e}")
        return []

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
    """Charge le fichier de cache existant."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save(matches):
    """Sauvegarde la liste des matchs dans le cache."""
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
    existing_ids = {m['id'] for m in all_matches if m.get('id')}

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