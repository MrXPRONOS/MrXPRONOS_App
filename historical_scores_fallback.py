#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
historical_scores_fallback.py - Utilise football-data.co.uk pour récupérer les scores historiques.
Version corrigée avec import manquant et point d'entrée.
"""

import pandas as pd
import requests
from io import StringIO
import os
import json
import time
from datetime import datetime

class HistoricalScoresFallback:
    """
    Récupère les scores depuis football-data.co.uk.
    Les données sont téléchargées une fois et stockées localement.
    """
    
    BASE_URL = "https://www.football-data.co.uk/mmz4281"
    CACHE_FILE = "cache/historical_scores.json"
    
    def __init__(self):
        self.data = None
        self._load_cache()
    
    def _load_cache(self):
        """Charge le cache s'il existe."""
        if os.path.exists(self.CACHE_FILE):
            with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        else:
            self.data = []
    
    def download_season(self, year):
        """
        Télécharge les données pour une saison donnée (ex: 2024 pour 2023-2024).
        """
        season_code = f"{year-1}{year}"[-4:]  # 2324 pour 2023-24
        leagues = ['E0', 'E1', 'E2', 'E3', 'SC0', 'SC1', 'D1', 'D2', 'I1', 'I2', 'SP1', 'SP2', 'F1', 'F2', 'N1']
        all_matches = []
        
        for league in leagues:
            url = f"{self.BASE_URL}/{season_code}/{league}.csv"
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    df = pd.read_csv(StringIO(response.text))
                    # Renommer les colonnes pour correspondre à notre format
                    df = df.rename(columns={
                        'Date': 'date',
                        'HomeTeam': 'home_team',
                        'AwayTeam': 'away_team',
                        'FTHG': 'home_score',
                        'FTAG': 'away_score'
                    })
                    df = df[['date', 'home_team', 'away_team', 'home_score', 'away_score']]
                    # Convertir la date
                    df['date'] = pd.to_datetime(df['date'], format='%d/%m/%y').dt.strftime('%Y-%m-%d')
                    # Filtrer les lignes avec scores
                    df = df.dropna(subset=['home_score', 'away_score'])
                    matches = df.to_dict('records')
                    all_matches.extend(matches)
                    print(f"   ✓ {league} : {len(matches)} matchs")
                time.sleep(0.5)
            except Exception as e:
                print(f"   ⚠️ Erreur pour {league}: {e}")
        
        return all_matches
    
    def update_cache(self, years=None):
        """
        Met à jour le cache pour les années spécifiées.
        years : liste d'années (ex: [2024, 2023, 2022]).
        """
        if years is None:
            current_year = datetime.now().year
            years = [current_year, current_year-1, current_year-2]
        
        new_data = []
        for year in years:
            print(f"📥 Téléchargement saison {year-1}-{year}...")
            matches = self.download_season(year)
            new_data.extend(matches)
        
        # Fusion avec les données existantes (éviter les doublons)
        existing_keys = {(m['date'], m['home_team'], m['away_team']) for m in self.data}
        for m in new_data:
            key = (m['date'], m['home_team'], m['away_team'])
            if key not in existing_keys:
                self.data.append(m)
        
        # Sauvegarder
        os.makedirs(os.path.dirname(self.CACHE_FILE), exist_ok=True)
        with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        print(f"✅ Cache mis à jour : {len(self.data)} matchs")
    
    def get_score(self, home_team, away_team, match_date):
        """
        Recherche le score dans les données locales.
        Retourne (home_score, away_score) ou (None, None).
        """
        # Normalisation basique des noms
        def normalize(name):
            name = name.lower()
            name = name.replace('fc', '').replace('afc', '').replace('united', '').replace('city', '').replace('real', '').strip()
            return name
        
        home_norm = normalize(home_team)
        away_norm = normalize(away_team)
        
        for m in self.data:
            if m['date'] == match_date[:10]:
                m_home = normalize(m['home_team'])
                m_away = normalize(m['away_team'])
                if (m_home in home_norm or home_norm in m_home) and (m_away in away_norm or away_norm in m_away):
                    return m['home_score'], m['away_score']
                # Essayer l'inverse (domicile/extérieur inversé dans les données)
                if (m_home in away_norm or away_norm in m_home) and (m_away in home_norm or home_norm in m_away):
                    return m['away_score'], m['home_score']
        return None, None

if __name__ == "__main__":
    fb = HistoricalScoresFallback()
    fb.update_cache()