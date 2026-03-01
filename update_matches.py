#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_matches.py - Ajoute les matchs d'hier au cache global all_matches.json.
Exécution quotidienne (à minuit).
"""

import requests
import json
import os
from datetime import datetime, timedelta
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_TOKEN = os.environ.get("BSD_API_TOKEN")
if not API_TOKEN:
    raise ValueError("La variable BSD_API_TOKEN n'est pas définie")

BASE_URL = "https://sports.bzzoiro.com/api"
HEADERS = {"Authorization": f"Token {API_TOKEN}"}

session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")

def fetch_events_day(date):
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
                break
            data = resp.json()
            events = data.get("results", [])
            all_events.extend(events)
            if data.get("next") is None:
                break
            page += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"Erreur: {e}")
            break
    return all_events

def load_existing():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return []

def save(matches):
    with open(CACHE_FILE, 'w') as f:
        json.dump(matches, f, indent=2)

def main():
    yesterday = datetime.now().date() - timedelta(days=1)
    print(f"Mise à jour avec les matchs du {yesterday}")
    new = fetch_events_day(yesterday)
    print(f"→ {len(new)} matchs trouvés")
    if not new:
        return
    all_matches = load_existing()
    existing_ids = {m['id'] for m in all_matches}
    to_add = [m for m in new if m['id'] not in existing_ids]
    print(f"→ {len(to_add)} nouveaux")
    if to_add:
        all_matches.extend(to_add)
        save(all_matches)
        print("Cache mis à jour")
    else:
        print("Cache déjà à jour")

if __name__ == "__main__":
    main()