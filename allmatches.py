#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
allmatches.py - Télécharge tous les matchs depuis le 1er janvier 2023 jusqu'à hier
et les sauvegarde dans un fichier cache global (cache/all_matches.json).
Version avec vérification du token API.
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
API_TOKEN = os.environ.get("BSD_API_TOKEN")
if not API_TOKEN:
    raise ValueError("❌ La variable d'environnement BSD_API_TOKEN n'est pas définie. Veuillez la définir avant d'exécuter ce script.")

BASE_URL = "https://sports.bzzoiro.com/api"
HEADERS = {"Authorization": f"Token {API_TOKEN}"}

# Configuration des retries
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

# Période à télécharger : du 1er janvier 2023 à hier
START_DATE = datetime(2023, 1, 1).date()
END_DATE = datetime.now().date() - timedelta(days=1)  # hier

CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")

print("="*60)
print("🚀 TÉLÉCHARGEMENT DE TOUS LES MATCHS DEPUIS 2023")
print(f"Période : {START_DATE} → {END_DATE}")
print("="*60)

def fetch_events_page(date_from, date_to, page=1):
    """Récupère une page d'événements entre deux dates."""
    url = f"{BASE_URL}/events/"
    params = {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "page": page
    }
    try:
        resp = session.get(url, headers=HEADERS, params=params, timeout=10)
        if resp.status_code != 200:
            print(f"   ❌ Erreur {resp.status_code}: {resp.text}")
            return None
        return resp.json()
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return None

def fetch_all_events_in_range(date_from, date_to):
    """Télécharge tous les événements sur une période (gère la pagination)."""
    all_events = []
    page = 1
    while True:
        print(f"   📡 Page {page}...")
        data = fetch_events_page(date_from, date_to, page)
        if not data:
            break
        events = data.get("results", [])
        all_events.extend(events)
        print(f"      → {len(events)} événements (total {len(all_events)})")
        if data.get("next") is None:
            break
        page += 1
        time.sleep(0.5)
    return all_events

def download_all_matches():
    """Télécharge tous les matchs mois par mois."""
    all_matches = []
    current_start = START_DATE
    while current_start <= END_DATE:
        # Calcul de la fin du mois en cours
        if current_start.month == 12:
            next_month = current_start.replace(year=current_start.year+1, month=1, day=1)
        else:
            next_month = current_start.replace(month=current_start.month+1, day=1)
        month_end = min(next_month - timedelta(days=1), END_DATE)
        
        print(f"\n📅 Mois : {current_start.strftime('%Y-%m')}")
        events = fetch_all_events_in_range(current_start, month_end)
        all_matches.extend(events)
        print(f"   ✅ {len(events)} matchs ajoutés (total {len(all_matches)})")
        
        current_start = next_month
        time.sleep(1)
    
    return all_matches

def save_to_cache(matches):
    """Sauvegarde la liste des matchs dans le fichier cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)
    print(f"\n💾 {len(matches)} matchs sauvegardés dans {CACHE_FILE}")

def main():
    print("\n🔄 Téléchargement en cours...")
    matches = download_all_matches()
    save_to_cache(matches)
    print("\n✅ Téléchargement terminé !")

if __name__ == "__main__":
    main()