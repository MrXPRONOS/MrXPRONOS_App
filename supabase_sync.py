#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
supabase_sync.py - Synchronise les données avec Supabase
- Envoie les pronostics générés
- Récupère les statistiques d'événements
- Met à jour les bookmakers et bonus depuis la base
- Utilise des fonctions RPC sécurisées
"""

import os
import json
from supabase import create_client, Client
from datetime import datetime, timedelta

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("Variables SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY non définies")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def sync_pronostics():
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("⚠️ data.json introuvable, ignoré.")
        return

    # Appel à une fonction RPC sécurisée (à créer dans Supabase)
    # Exemple : rpc('upsert_pronostics', {'data': data})
    # Pour simplifier, on utilise upsert direct (mais avec RLS adaptée)
    supabase.table('pronostics').upsert({
        'id': 'current',
        'data': data,
        'updated_at': datetime.now().isoformat()
    }).execute()
    print("✅ Pronostics synchronisés")

def get_stats():
    thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
    response = supabase.table('events').select('*').gte('timestamp', thirty_days_ago).execute()
    events = response.data

    total_visits = sum(1 for e in events if e['type'] == 'visit')
    total_shares = sum(1 for e in events if e['type'] == 'share')
    unique_users = len(set(e.get('user_id') for e in events if e.get('user_id')))

    page_counts = {}
    for e in events:
        page = e.get('page', 'inconnu')
        page_counts[page] = page_counts.get(page, 0) + 1

    stats = {
        'total_visits': total_visits,
        'total_shares': total_shares,
        'unique_users': unique_users,
        'page_counts': page_counts,
        'events': events[-100:]
    }

    with open('stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"📊 Statistiques sauvegardées : {total_visits} visites, {total_shares} partages, {unique_users} utilisateurs uniques")
    return stats

def get_bookmakers():
    response = supabase.table('bookmakers').select('*').execute()
    return response.data

def get_bonus():
    response = supabase.table('bonus').select('*').eq('active', True).execute()
    return response.data

def update_data_json_with_supabase():
    try:
        with open('data.json', 'r+', encoding='utf-8') as f:
            data = json.load(f)
            data['bookmakers'] = get_bookmakers()
            data['bonus'] = get_bonus()
            f.seek(0)
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.truncate()
        print("✅ data.json mis à jour avec bookmakers et bonus")
    except Exception as e:
        print(f"❌ Erreur mise à jour data.json: {e}")

if __name__ == '__main__':
    sync_pronostics()
    get_stats()
    update_data_json_with_supabase()
    print("✅ Synchronisation terminée")