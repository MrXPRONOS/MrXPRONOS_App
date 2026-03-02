#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_historical_cache.py - Télécharge les fichiers CSV de football-data.co.uk
et les convertit en un fichier JSON historique (historical_scores.json).
Exécution recommandée : hebdomadaire (via GitHub Actions).
"""

import csv
import json
import requests
from datetime import datetime, timedelta
import os
import time

# Liste des ligues à télécharger (codes football-data.co.uk)
LEAGUES = [
    ("E0", "Premier League"),
    ("E1", "Championship"),
    ("E2", "League One"),
    ("E3", "League Two"),
    ("EC", "Conference"),
    ("SC0", "Scottish Premiership"),
    ("SC1", "Scottish Championship"),
    ("D1", "Bundesliga"),
    ("D2", "2. Bundesliga"),
    ("I1", "Serie A"),
    ("I2", "Serie B"),
    ("SP1", "LaLiga"),
    ("SP2", "LaLiga 2"),
    ("F1", "Ligue 1"),
    ("F2", "Ligue 2"),
    ("N1", "Eredivisie"),
    ("B1", "Pro League"),
    ("P1", "Primeira Liga"),
    ("T1", "Super Lig"),
    ("G1", "Brasileirão"),
    ("MLS", "MLS"),
]

BASE_URL = "https://www.football-data.co.uk/mmz4281"
OUTPUT_FILE = "historical_scores.json"

def download_league_csv(league_code, season):
    """Télécharge le CSV pour une ligue et une saison donnée."""
    url = f"{BASE_URL}/{season}/{league_code}.csv"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text
        else:
            print(f"   ⚠️ {league_code} {season} non trouvé")
            return None
    except Exception as e:
        print(f"   ❌ Erreur téléchargement {league_code} {season}: {e}")
        return None

def parse_csv_data(csv_text, league_name):
    """Convertit le CSV en liste de matchs avec scores."""
    matches = []
    reader = csv.DictReader(csv_text.splitlines())
    for row in reader:
        try:
            date_str = row['Date']
            # Conversion en YYYY-MM-DD (format DD/MM/YY ou DD/MM/YYYY)
            try:
                date_obj = datetime.strptime(date_str, '%d/%m/%y')
            except:
                try:
                    date_obj = datetime.strptime(date_str, '%d/%m/%Y')
                except:
                    continue
            event_date = date_obj.strftime('%Y-%m-%d')

            home_team = row['HomeTeam'].strip()
            away_team = row['AwayTeam'].strip()
            home_score = row.get('FTHG')  # Full Time Home Goals
            away_score = row.get('FTAG')  # Full Time Away Goals

            if home_score and away_score:
                matches.append({
                    "date": event_date,
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_score": int(home_score),
                    "away_score": int(away_score),
                    "league": league_name
                })
        except Exception as e:
            # Ignorer les lignes mal formées
            continue
    return matches

def load_existing():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_matches(matches):
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)

def main():
    print("="*60)
    print("🚀 MISE À JOUR DE L'HISTORIQUE LOCAL")
    print("="*60)

    existing = load_existing()
    existing_keys = {(m["date"], m["home_team"], m["away_team"]) for m in existing}
    print(f"📂 {len(existing)} matchs existants")

    current_year = datetime.now().year
    # Télécharger les 5 dernières saisons
    for season in range(current_year-5, current_year+1):
        season_code = f"{str(season)[2:]}{str(season+1)[2:]}"  # ex: 2425
        print(f"\n📅 Saison {season}-{season+1} (code {season_code})")
        for league_code, league_name in LEAGUES:
            print(f"   📡 {league_name} ({league_code})")
            csv_text = download_league_csv(league_code, season_code)
            if csv_text:
                matches = parse_csv_data(csv_text, league_name)
                new_count = 0
                for m in matches:
                    key = (m["date"], m["home_team"], m["away_team"])
                    if key not in existing_keys:
                        existing.append(m)
                        existing_keys.add(key)
                        new_count += 1
                print(f"      → {len(matches)} matchs, {new_count} nouveaux")
            time.sleep(1)  # pause entre les requêtes

    save_matches(existing)
    print(f"\n✅ Historique mis à jour : {len(existing)} matchs")

if __name__ == "__main__":
    main()