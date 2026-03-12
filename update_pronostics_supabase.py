#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_pronostics_supabase.py - Met à jour la table des pronostics dans Supabase
à partir du fichier data.json généré par generate_data.py.
Gère aujourd'hui, demain et hier (résultats validés).
Utilise la variable d'environnement SUPABASE_KEY.
"""

import os
import json
from supabase import create_client
from datetime import datetime, timedelta

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Les variables d'environnement SUPABASE_URL et SUPABASE_KEY sont requises")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def main():
    # Vérifier que le fichier data.json existe
    if not os.path.exists('data.json'):
        print("❌ data.json introuvable. Rien à mettre à jour.")
        return

    # Charger les données
    with open('data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    matches = data.get('matches', [])
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)

    # Filtrer les matchs par date
    today_matches = [m for m in matches if m.get('date') == today.isoformat()]
    tomorrow_matches = [m for m in matches if m.get('date') == tomorrow.isoformat()]
    yesterday_matches = [m for m in matches if m.get('date') == yesterday.isoformat()]

    print(f"📅 Mise à jour des pronostics dans Supabase...")
    print(f"   Aujourd'hui ({today}) : {len(today_matches)} matchs")
    print(f"   Demain ({tomorrow}) : {len(tomorrow_matches)} matchs")
    print(f"   Hier ({yesterday}) : {len(yesterday_matches)} matchs")

    # Insérer ou mettre à jour les matchs d'aujourd'hui et demain
    for m in today_matches + tomorrow_matches:
        pronostic = {
            'match': f"{m['home_team']} vs {m['away_team']}",
            'prediction': m['prediction']['double_chance'],
            'cote': m['prediction'].get('odds'),
            'competition': m['league'],
            'date': m['date'],
            'valide': False  # par défaut non validé
        }
        # Upsert avec contrainte unique sur (match, date)
        result = supabase.table('pronostics').upsert(pronostic, on_conflict='match,date').execute()
        if hasattr(result, 'error') and result.error:
            print(f"⚠️ Erreur pour {pronostic['match']}: {result.error}")

    # Mettre à jour les résultats d'hier (marquer comme validé avec le résultat réel)
    for m in yesterday_matches:
        # Déterminer si le pronostic a été validé
        verified = m.get('verified_double', False)
        pronostic = {
            'match': f"{m['home_team']} vs {m['away_team']}",
            'prediction': m['prediction']['double_chance'],
            'cote': m['prediction'].get('odds'),
            'competition': m['league'],
            'date': m['date'],
            'valide': verified
        }
        result = supabase.table('pronostics').upsert(pronostic, on_conflict='match,date').execute()
        if hasattr(result, 'error') and result.error:
            print(f"⚠️ Erreur pour {pronostic['match']}: {result.error}")

    print("✅ Mise à jour terminée.")

if __name__ == '__main__':
    main()