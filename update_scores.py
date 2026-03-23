#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_scores.py - Met à jour les scores et statuts des matchs dans data.json
Version fiabilisée :
- gestion robuste des erreurs
- sauvegarde avec backup
- mise à jour de is_finished
- compatible avec api_utils
"""

import os
import json
from datetime import datetime, timedelta, timezone
from api_utils import make_request

SPORTDATA_URL = "https://v1.football.sportsapipro.com/games/allscores"
DATA_FILE = "data.json"
BACKUP_FILE = "data_backup.json"

UTC = timezone.utc
today = datetime.now(UTC).date()
days_to_fetch = [today, today - timedelta(days=1), today - timedelta(days=2)]

print("=" * 60)
print(f"🔄 MISE À JOUR DES SCORES - {today} {datetime.now(UTC).strftime('%H:%M')} UTC")
print("=" * 60)


def safe_load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def fetch_games(date):
    """
    Récupère les matchs pour une date donnée via l'API SportData.
    """
    params = {
        "startDate": date.strftime("%d/%m/%Y"),
        "endDate": date.strftime("%d/%m/%Y"),
        "sports": 1,
        "showOdds": "false",
        "onlyMajorGames": "false"
    }

    try:
        resp = make_request("GET", SPORTDATA_URL, params=params, timeout=30)
        if resp is None:
            print(f"⚠️ Aucune réponse API pour {date}")
            return []

        if resp.status_code != 200:
            print(f"⚠️ HTTP {resp.status_code} pour {date}")
            return []

        data = resp.json()
        games = data.get("games", [])
        return games if isinstance(games, list) else []

    except Exception as e:
        print(f"❌ Erreur API pour {date} : {e}")
        return []


def load_data():
    """
    Charge data.json ou backup si nécessaire.
    """
    if not os.path.exists(DATA_FILE):
        print("⚠️ data.json introuvable, création d'une nouvelle structure.")
        return {"matches": []}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Erreur lecture data.json : {e}")
        if os.path.exists(BACKUP_FILE):
            print("🔁 Restauration depuis data_backup.json")
            return safe_load_json(BACKUP_FILE, {"matches": []})
        return {"matches": []}


def save_data(data):
    """
    Sauvegarde data.json avec backup préalable.
    """
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                current = json.load(f)
            with open(BACKUP_FILE, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Impossible de créer le backup: {e}")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("✅ Données sauvegardées dans data.json")


def normalize_score(value):
    if value in (-1, "-1", None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return None


def is_finished_status(status_group, status_text):
    if str(status_group) == "4":
        return True

    st = str(status_text or "").lower()
    return (
        "ended" in st or
        "finished" in st or
        "terminé" in st or
        "ft" == st.strip()
    )


def is_live_status(status_text):
    st = str(status_text or "").lower()
    return (
        "inprogress" in st or
        "live" in st or
        "en cours" in st
    )


def main():
    all_games = []

    for day in days_to_fetch:
        print(f"📅 Récupération des matchs du {day}...")
        games = fetch_games(day)
        print(f"   → {len(games)} matchs")
        all_games.extend(games)

    if not all_games:
        print("⚠️ Aucun match récupéré, arrêt du script.")
        return

    scores_dict = {}

    for g in all_games:
        gid = str(g.get("id", "")).strip()
        if not gid:
            continue

        home = g.get("homeCompetitor", {}) or {}
        away = g.get("awayCompetitor", {}) or {}

        home_score = normalize_score(home.get("score"))
        away_score = normalize_score(away.get("score"))
        status_text = g.get("statusText", "")
        status_group = g.get("statusGroup")

        scores_dict[gid] = {
            "home_score": home_score,
            "away_score": away_score,
            "status": status_text,
            "status_group": status_group,
            "is_finished": is_finished_status(status_group, status_text)
        }

    data = load_data()
    matches = data.get("matches", [])
    if not isinstance(matches, list):
        matches = []
        data["matches"] = matches

    updated = 0
    finished = 0
    live = 0

    for match in matches:
        gid = str(match.get("id", "")).strip()
        if gid not in scores_dict:
            continue

        new = scores_dict[gid]

        old_home = match.get("home_score")
        old_away = match.get("away_score")
        old_status = match.get("status")
        old_finished = match.get("is_finished")

        changed = (
            old_home != new["home_score"] or
            old_away != new["away_score"] or
            old_status != new["status"] or
            old_finished != new["is_finished"]
        )

        if changed:
            match["home_score"] = new["home_score"]
            match["away_score"] = new["away_score"]
            match["status"] = new["status"]
            match["is_finished"] = new["is_finished"]
            updated += 1

        if new["is_finished"]:
            finished += 1
        elif is_live_status(new["status"]):
            live += 1

    if updated > 0:
        save_data(data)
    else:
        print("ℹ️ Aucune modification détectée.")

    print("\n📊 RÉSUMÉ")
    print("------------")
    print(f"Matchs analysés : {len(all_games)}")
    print(f"Matchs mis à jour : {updated}")
    print(f"Matchs terminés : {finished}")
    print(f"Matchs en direct : {live}")
    print("✅ Mise à jour terminée.")


if __name__ == "__main__":
    main()