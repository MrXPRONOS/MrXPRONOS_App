#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_scores.py - Met à jour les scores et statuts des matchs dans data.json
Version robuste avec sauvegarde, logs détaillés et rotation de clés API.
Utilisé par GitHub Actions pour maintenir les scores à jour.
"""

import os
import json
from datetime import datetime, timedelta
from api_utils import make_request

# Configuration
SPORTDATA_URL = "https://v1.football.sportsapipro.com/games/allscores"
DATA_FILE = "data.json"
BACKUP_FILE = "data_backup.json"

# Périodes à analyser (aujourd'hui, hier, avant-hier)
today = datetime.utcnow().date()
days_to_fetch = [today, today - timedelta(days=1), today - timedelta(days=2)]

print("=" * 60)
print(f"🔄 MISE À JOUR DES SCORES - {today} {datetime.utcnow().strftime('%H:%M')} UTC")
print("=" * 60)


def fetch_games(date):
    """
    Récupère les matchs pour une date donnée via l'API SportData.
    Retourne une liste de matchs (games) ou une liste vide en cas d'erreur.
    """
    params = {
        "startDate": date.strftime("%d/%m/%Y"),
        "endDate": date.strftime("%d/%m/%Y"),
        "sports": 1,
        "showOdds": "false",
        "onlyMajorGames": "false"
    }

    try:
        resp = make_request('GET', SPORTDATA_URL, params=params, timeout=30)
        games = resp.json().get("games", [])
        return games
    except Exception as e:
        print(f"❌ Erreur API pour {date} : {e}")
        return []


def load_data():
    """
    Charge le fichier data.json existant.
    Si le fichier n'existe pas, retourne une structure minimale.
    """
    if not os.path.exists(DATA_FILE):
        print("⚠️ data.json introuvable, création d'une nouvelle structure.")
        return {"matches": []}
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("❌ Erreur de parsing JSON, tentative de restauration depuis backup...")
        if os.path.exists(BACKUP_FILE):
            with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {"matches": []}


def save_data(data):
    """
    Sauvegarde les données dans data.json après avoir créé une copie de sécurité.
    """
    # Créer une sauvegarde du fichier actuel s'il existe
    if os.path.exists(DATA_FILE):
        os.replace(DATA_FILE, BACKUP_FILE)

    # Écrire les nouvelles données
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("✅ Données sauvegardées dans data.json")


def main():
    all_games = []

    # 1. Récupérer les matchs pour chaque jour
    for day in days_to_fetch:
        print(f"📅 Récupération des matchs du {day}...")
        games = fetch_games(day)
        print(f"   → {len(games)} matchs")
        all_games.extend(games)

    if not all_games:
        print("⚠️ Aucun match récupéré, arrêt du script.")
        return

    # 2. Construire un dictionnaire des scores par ID de match
    scores_dict = {}
    for g in all_games:
        gid = g.get("id")
        home = g.get("homeCompetitor", {})
        away = g.get("awayCompetitor", {})
        home_score = home.get("score")
        away_score = away.get("score")

        # Normalisation : -1 signifie pas encore joué → None
        if home_score == -1:
            home_score = None
        if away_score == -1:
            away_score = None

        scores_dict[gid] = {
            "home_score": home_score,
            "away_score": away_score,
            "status": g.get("statusText")
        }

    # 3. Charger les données existantes
    data = load_data()
    matches = data.get("matches", [])

    updated = 0
    finished = 0
    live = 0

    # 4. Mettre à jour chaque match si nécessaire
    for match in matches:
        gid = match.get("id")
        if gid not in scores_dict:
            continue

        new = scores_dict[gid]
        old_home = match.get("home_score")
        old_away = match.get("away_score")
        old_status = match.get("status")

        # Vérifier si un changement a eu lieu
        if old_home != new["home_score"] or old_away != new["away_score"] or old_status != new["status"]:
            match["home_score"] = new["home_score"]
            match["away_score"] = new["away_score"]
            match["status"] = new["status"]
            updated += 1

        # Compter les matchs terminés et en direct (pour le log)
        if new["status"] and "ended" in new["status"].lower():
            finished += 1
        elif new["status"] and "inprogress" in new["status"].lower():
            live += 1

    # 5. Sauvegarder si des modifications ont été effectuées
    if updated > 0:
        save_data(data)
    else:
        print("ℹ️ Aucune modification détectée.")

    # 6. Afficher le résumé
    print("\n📊 RÉSUMÉ")
    print("------------")
    print(f"Matchs analysés : {len(all_games)}")
    print(f"Matchs mis à jour : {updated}")
    print(f"Matchs terminés : {finished}")
    print(f"Matchs en direct : {live}")
    print("✅ Mise à jour terminée.")


if __name__ == "__main__":
    main()