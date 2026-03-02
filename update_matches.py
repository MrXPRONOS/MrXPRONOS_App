#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_matches.py - Ajoute les matchs d'hier au cache global all_matches.json
Exécution quotidienne (par exemple à minuit) pour maintenir le cache à jour.
"""

import requests
import json
import os
from datetime import datetime, timedelta
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =======================================================
# CONFIGURATION
# =======================================================
API_TOKEN = os.getenv("BSD_API_TOKEN", "3d0b228fb2f078287b8e6720304f2eea2800cc6d")
BASE_URL = "https://sports.bzzoiro.com/api"
HEADERS = {"Authorization": f"Token {API_TOKEN}"}

session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")

print("="*60)
print("🔄 MISE À JOUR QUOTIDIENNE DU CACHE")
print("="*60)

def fetch_events_day(date):
    """
    Récupère tous les événements d'une journée spécifique.
    """
    url = f"{BASE_URL}/events/"
    params = {
        "date_from": date.isoformat(),
        "date_to": date.isoformat()
    }
    all_events = []
    page = 1
    while True:
        params["page"] = page
        try:
            resp = session.get(url, headers=HEADERS, params=params, timeout=10)
            if resp.status_code != 200:
                print(f"❌ Erreur {resp.status_code}")
                break
            data = resp.json()
            events = data.get("results", [])
            all_events.extend(events)
            if data.get("next") is None:
                break
            page += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"❌ Exception: {e}")
            break
    return all_events

def load_existing_matches():
    """
    Charge le cache existant, retourne une liste vide si le fichier n'existe pas.
    """
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_matches(matches):
    """
    Sauvegarde la liste dans le cache.
    """
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)

def main():
    yesterday = datetime.now().date() - timedelta(days=1)
    print(f"\n📅 Mise à jour avec les matchs du {yesterday}")

    # Récupérer les matchs d'hier
    new_matches = fetch_events_day(yesterday)
    print(f"   → {len(new_matches)} matchs trouvés")

    if not new_matches:
        print("✅ Aucun nouveau match.")
        return

    # Charger le cache existant
    all_matches = load_existing_matches()
    existing_ids = {m['id'] for m in all_matches}

    # Filtrer les nouveaux qui ne sont pas déjà dans le cache
    to_add = [m for m in new_matches if m['id'] not in existing_ids]
    print(f"   → {len(to_add)} nouveaux matchs à ajouter")

    if to_add:
        all_matches.extend(to_add)
        save_matches(all_matches)
        print(f"✅ Cache mis à jour : maintenant {len(all_matches)} matchs")
    else:
        print("✅ Cache déjà à jour.")

if __name__ == "__main__":
    main()