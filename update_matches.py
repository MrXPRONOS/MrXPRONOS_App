#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_matches.py - Ajoute les matchs d'hier au cache global all_matches.json.
Version améliorée avec gestion d'erreurs et logs.
Exécution quotidienne (par exemple à minuit) pour maintenir le cache à jour.
"""

import requests
import json
import os
from datetime import datetime, timedelta
import time
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =======================================================
# CONFIGURATION
# =======================================================
API_TOKEN = os.environ.get("BSD_API_TOKEN")
if not API_TOKEN:
    raise ValueError("La variable d'environnement BSD_API_TOKEN n'est pas définie")

BASE_URL = "https://sports.bzzoiro.com/api"
HEADERS = {"Authorization": f"Token {API_TOKEN}"}

session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =======================================================
# FONCTIONS
# =======================================================
def fetch_events_day(date):
    """
    Récupère tous les événements d'une journée spécifique (gère la pagination).
    Retourne une liste d'événements.
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
            logger.info(f"   📡 Page {page}...")
            resp = session.get(url, headers=HEADERS, params=params, timeout=10)
            if resp.status_code != 200:
                logger.error(f"❌ Erreur {resp.status_code}")
                break
            data = resp.json()
            events = data.get("results", [])
            all_events.extend(events)
            logger.info(f"      → {len(events)} événements (total {len(all_events)})")
            if data.get("next") is None:
                break
            page += 1
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"❌ Exception: {e}")
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
    logger.info(f"💾 Cache sauvegardé : {len(matches)} matchs")

def main():
    logger.info("="*60)
    logger.info("🔄 MISE À JOUR QUOTIDIENNE DU CACHE")
    logger.info("="*60)

    yesterday = datetime.now().date() - timedelta(days=1)
    logger.info(f"📅 Mise à jour avec les matchs du {yesterday}")

    # Récupérer les matchs d'hier
    new_matches = fetch_events_day(yesterday)
    logger.info(f"   → {len(new_matches)} matchs trouvés")

    if not new_matches:
        logger.info("✅ Aucun nouveau match.")
        return

    # Charger le cache existant
    all_matches = load_existing_matches()
    existing_ids = {m['id'] for m in all_matches}
    logger.info(f"📂 Cache existant : {len(all_matches)} matchs")

    # Filtrer les nouveaux qui ne sont pas déjà dans le cache
    to_add = [m for m in new_matches if m['id'] not in existing_ids]
    logger.info(f"   → {len(to_add)} nouveaux matchs à ajouter")

    if to_add:
        all_matches.extend(to_add)
        # Trier par date (optionnel, mais peut aider)
        all_matches.sort(key=lambda x: x.get('event_date', ''), reverse=True)
        save_matches(all_matches)
        logger.info(f"✅ Cache mis à jour : maintenant {len(all_matches)} matchs")
    else:
        logger.info("✅ Cache déjà à jour.")

if __name__ == "__main__":
    main()