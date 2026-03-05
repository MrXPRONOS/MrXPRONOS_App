#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_logos_bsd.py
Télécharge les logos des équipes depuis l'API BSD en utilisant les api_id,
et met à jour data.json avec les chemins locaux.
Utilisation : python download_logos_bsd.py
"""

import os
import json
import requests
import time
import unicodedata
from difflib import SequenceMatcher

DATA_FILE = "data.json"
LOGO_DIR = "assets/images/logos"
os.makedirs(LOGO_DIR, exist_ok=True)

BSD_API_TOKEN = os.environ.get("BSD_API_TOKEN",'3d0b228fb2f078287b8e6720304f2eea2800cc6d')
if not BSD_API_TOKEN:
    raise ValueError("La variable d'environnement BSD_API_TOKEN n'est pas définie")

BSD_BASE = "https://sports.bzzoiro.com/api"
HEADERS = {"Authorization": f"Token {BSD_API_TOKEN}"}

def normalize_name(name):
    """Normalise le nom pour comparaison (minuscule, sans accents, sans caractères spéciaux)."""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = name.lower()
    name = ''.join(c for c in name if c.isalnum() or c.isspace())
    name = ' '.join(name.split())  # supprime les espaces multiples
    return name

def load_bsd_teams():
    """Récupère toutes les équipes depuis BSD et retourne un dict {nom_normalisé: (api_id, nom_officiel)}."""
    teams = {}
    page = 1
    while True:
        url = f"{BSD_BASE}/teams/?page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            for team in data["results"]:
                name = team["name"]
                norm = normalize_name(name)
                if norm not in teams:
                    teams[norm] = (team["api_id"], name)
            if not data.get("next"):
                break
            page += 1
            time.sleep(0.1)
        except Exception as e:
            print(f"❌ Erreur lors de la récupération des équipes BSD : {e}")
            return {}
    print(f"✅ {len(teams)} équipes chargées depuis BSD.")
    return teams

def find_best_match(team_name, bsd_teams, threshold=0.7):
    """Trouve la meilleure correspondance pour un nom d'équipe."""
    norm_team = normalize_name(team_name)
    if norm_team in bsd_teams:
        return bsd_teams[norm_team]
    best = None
    best_ratio = 0
    for norm, (api_id, official) in bsd_teams.items():
        ratio = SequenceMatcher(None, norm_team, norm).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best = (api_id, official)
    if best_ratio >= threshold:
        return best
    return None

def download_logo(api_id, filename):
    """Télécharge le logo depuis BSD et le sauvegarde."""
    url = f"{BSD_BASE}/img/team/{api_id}/?token={BSD_API_TOKEN}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            with open(filename, "wb") as f:
                f.write(resp.content)
            return True
        else:
            print(f"   ⚠️ Code HTTP {resp.status_code} pour {api_id}")
    except Exception as e:
        print(f"   ⚠️ Erreur téléchargement {api_id}: {e}")
    return False

def main():
    if not os.path.exists(DATA_FILE):
        print(f"❌ Fichier {DATA_FILE} introuvable.")
        return

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    matches = data.get("matches", [])
    if not matches:
        print("❌ Aucun match trouvé dans data.json")
        return

    bsd_teams = load_bsd_teams()
    if not bsd_teams:
        return

    team_names = set()
    for m in matches:
        team_names.add(m["home_team"])
        team_names.add(m["away_team"])

    print(f"🔍 {len(team_names)} équipes uniques à traiter.")

    team_logo_path = {}
    downloaded = 0

    for team in sorted(team_names):
        print(f"📡 Traitement de {team}...")
        match = find_best_match(team, bsd_teams)
        if not match:
            print(f"   ⚠️ Aucune correspondance trouvée pour {team}")
            team_logo_path[team] = None
            continue

        api_id, official_name = match
        safe_name = normalize_name(official_name).replace(" ", "_")
        ext = "png"
        filename = f"{safe_name}_{api_id}.{ext}"
        filepath = os.path.join(LOGO_DIR, filename)

        if os.path.exists(filepath):
            print(f"   ✅ Déjà présent : {filename}")
        else:
            if download_logo(api_id, filepath):
                print(f"   ✅ Téléchargé : {filename}")
                downloaded += 1
            else:
                print(f"   ❌ Échec téléchargement pour {team}")
                team_logo_path[team] = None
                continue

        team_logo_path[team] = f"assets/images/logos/{filename}"

    print(f"\n🏁 {downloaded} nouveaux logos téléchargés dans {LOGO_DIR}")

    modified = 0
    for m in matches:
        home = m["home_team"]
        away = m["away_team"]
        new_home_logo = team_logo_path.get(home)
        new_away_logo = team_logo_path.get(away)

        if new_home_logo and m.get("home_logo") != new_home_logo:
            m["home_logo"] = new_home_logo
            modified += 1
        if new_away_logo and m.get("away_logo") != new_away_logo:
            m["away_logo"] = new_away_logo
            modified += 1

    if modified > 0:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ data.json mis à jour avec les chemins des logos ({modified} champs modifiés).")
    else:
        print("ℹ️ Aucune mise à jour nécessaire dans data.json.")

if __name__ == "__main__":
    main()