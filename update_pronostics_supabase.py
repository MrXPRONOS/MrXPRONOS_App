#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_pronostics_supabase.py - Met à jour la table des pronostics du jour dans Supabase
à partir du fichier data.json généré par generate_data.py.
Utilise la variable d'environnement SUPABASE_KEY.
"""

import os
import json
from supabase import create_client
from datetime import datetime

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")  # Utilise la variable SUPABASE_KEY

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Les variables d'environnement SUPABASE_URL et SUPABASE_KEY sont requises")

# Initialisation du client Supabase
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
    today = datetime.now().date().isoformat()

    # Filtrer les matchs du jour (aujourd'hui)
    today_matches = [m for m in matches if m.get('date') == today]

    if not today_matches:
        print(f"ℹ️ Aucun match pour aujourd'hui ({today}) dans data.json.")
        return

    print(f"📅 Mise à jour de {len(today_matches)} pronostics pour le {today} dans Supabase...")

    # Insérer ou mettre à jour chaque match dans la table 'pronostics'
    for m in today_matches:
        # Construction de l'objet à upsert
        pronostic = {
            'match': f"{m['home_team']} vs {m['away_team']}",
            'prediction': m['prediction']['double_chance'],
            'cote': m['prediction'].get('odds'),  # utiliser la cote si disponible
            'competition': m['league'],
            'date': today
        }

        # Upsert (on suppose que la colonne 'match' est unique ou on utilise un conflit sur match+date)
        result = supabase.table('pronostics').upsert(pronostic, on_conflict='match').execute()

        # Vérification basique
        if hasattr(result, 'error') and result.error:
            print(f"⚠️ Erreur pour {pronostic['match']}: {result.error}")

    print("✅ Mise à jour terminée.")

if __name__ == '__main__':
    main()