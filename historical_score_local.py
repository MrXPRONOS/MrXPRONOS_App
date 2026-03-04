import csv
import json
import requests
from datetime import datetime
import os

# Liste des ligues à télécharger (codes utilisés par football-data.co.uk)
LEAGUES = [
    ("E0", "Premier League"),
    ("E1", "Championship"),
    ("F1", "Ligue 1"),
    ("F2", "Ligue 2"),
    ("SP1", "LaLiga"),
    ("SP2", "LaLiga 2"),
    ("I1", "Serie A"),
    ("D1", "Bundesliga"),
    ("N1", "Eredivisie"),
    ("P1", "Primeira Liga"),
    ("T1", "Super Lig"),
    ("G1", "Brasileirão"),
    ("MLS", "MLS"),
]

BASE_URL = "https://www.football-data.co.uk/mmz4281"
OUTPUT_FILE = "historical_scores.json"

def download_league_csv(league_code, season):
    """Télécharge le CSV pour une ligue et une saison donnée (ex: 2024)."""
    url = f"{BASE_URL}/{season}/{league_code}.csv"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text
        else:
            print(f"   ⚠️ {league_code} {season} non trouvé")
            return None
    except:
        return None

def parse_csv_data(csv_text, league_name):
    """Convertit le CSV en liste de matchs avec scores."""
    matches = []
    reader = csv.DictReader(csv_text.splitlines())
    for row in reader:
        # Format de la date: DD/MM/YY (parfois avec 4 chiffres)
        try:
            date_str = row['Date']
            # Conversion en YYYY-MM-DD
            date_obj = datetime.strptime(date_str, '%d/%m/%y')
            event_date = date_obj.strftime('%Y-%m-%d')
        except:
            # Essayer avec 4 chiffres
            try:
                date_obj = datetime.strptime(date_str, '%d/%m/%Y')
                event_date = date_obj.strftime('%Y-%m-%d')
            except:
                continue

        home_team = row['HomeTeam']
        away_team = row['AwayTeam']
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
    return matches

def main():
    all_matches = []
    # Télécharger les 5 dernières saisons (exemple)
    current_year = datetime.now().year
    for season in range(current_year-5, current_year+1):
        season_code = str(season)[2:] + str(season+1)[2:]  # ex: 2425 pour 2024-2025
        print(f"📅 Saison {season}-{season+1}...")
        for league_code, league_name in LEAGUES:
            print(f"   📡 {league_name} ({league_code})")
            csv_text = download_league_csv(league_code, season_code)
            if csv_text:
                matches = parse_csv_data(csv_text, league_name)
                all_matches.extend(matches)
                print(f"      → {len(matches)} matchs ajoutés")

    # Sauvegarder en JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_matches, f, indent=2, ensure_ascii=False)
    print(f"\n✅ {len(all_matches)} matchs sauvegardés dans {OUTPUT_FILE}")

if __name__ == "__main__":
    main()