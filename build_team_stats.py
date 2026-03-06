#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_team_stats.py - Enrichit all_matches.json avec les statistiques de forme des équipes
(5 derniers matchs, buts marqués/encaissés, etc.)
Version corrigée pour utiliser les noms d'équipes comme clés.
Exécuter après allmatches.py et avant generate_data.py.  
"""

import json
from datetime import datetime
from collections import defaultdict

def build_team_history(matches):
    """Construit pour chaque équipe la liste de ses matchs triés par date."""
    team_matches = defaultdict(list)
    for m in matches:
        home_team = m["home_team"]
        away_team = m["away_team"]
        date = datetime.fromisoformat(m["start_time"].replace('Z', '+00:00'))
        team_matches[home_team].append((date, m, "home"))
        team_matches[away_team].append((date, m, "away"))
    # Trier par date pour chaque équipe
    for team in team_matches:
        team_matches[team].sort(key=lambda x: x[0])
    return team_matches

def get_last_n_matches(team, current_match_index, team_matches, n=5):
    """Retourne les n matchs précédant l'index donné (excluant le match courant)."""
    matches = team_matches[team]
    start = max(0, current_match_index - n)
    return [m for m in matches[start:current_match_index]]  # on exclut le match courant

def compute_form(stats_list, team_side):
    """
    Calcule les statistiques de forme à partir d'une liste de matchs.
    team_side: 'home' ou 'away' indique si l'équipe jouait à domicile ou non.
    Retourne un dict avec:
        - matches_played: nombre de matchs
        - wins: victoires
        - draws: nuls
        - losses: défaites
        - goals_for: buts marqués
        - goals_against: buts encaissés
        - avg_goals_for: moyenne buts marqués
        - avg_goals_against: moyenne buts encaissés
    """
    wins = draws = losses = 0
    goals_for = goals_against = 0
    for (date, match, side) in stats_list:
        if side == team_side:
            # l'équipe jouait à domicile ou extérieur selon team_side
            if team_side == 'home':
                gf = match["home_score"]
                ga = match["away_score"]
            else:
                gf = match["away_score"]
                ga = match["home_score"]
        else:
            # l'équipe jouait à l'opposé
            if team_side == 'home':
                gf = match["away_score"]
                ga = match["home_score"]
            else:
                gf = match["home_score"]
                ga = match["away_score"]
        goals_for += gf
        goals_against += ga
        if gf > ga:
            wins += 1
        elif gf < ga:
            losses += 1
        else:
            draws += 1
    played = len(stats_list)
    return {
        "matches_played": played,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "avg_goals_for": round(goals_for / played, 2) if played else 0,
        "avg_goals_against": round(goals_against / played, 2) if played else 0
    }

def enrich_matches(matches):
    team_matches = build_team_history(matches)
    # Pour chaque match, on a besoin de trouver son index dans la liste de chaque équipe
    # On va d'abord créer un mapping match_id -> (index_home, index_away)
    match_indices = {}
    for team, mlist in team_matches.items():
        for idx, (date, match, side) in enumerate(mlist):
            match_id = match["id"]
            if match_id not in match_indices:
                match_indices[match_id] = {}
            match_indices[match_id][side] = idx

    enriched = []
    for m in matches:
        match_id = m["id"]
        home_team = m["home_team"]
        away_team = m["away_team"]
        idx_home = match_indices[match_id].get("home")
        idx_away = match_indices[match_id].get("away")
        # Récupérer les 5 derniers matchs pour chaque équipe avant ce match
        home_last5 = get_last_n_matches(home_team, idx_home, team_matches, 5) if idx_home is not None else []
        away_last5 = get_last_n_matches(away_team, idx_away, team_matches, 5) if idx_away is not None else []
        # Calculer les statistiques de forme pour chaque équipe
        home_form = compute_form(home_last5, 'home')
        away_form = compute_form(away_last5, 'away')
        # Ajouter au match
        m["home_form"] = home_form
        m["away_form"] = away_form
        enriched.append(m)
    return enriched

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Enrichit all_matches.json avec les stats de forme")
    parser.add_argument("input", help="Fichier JSON d'entrée (all_matches.json)")
    parser.add_argument("output", help="Fichier JSON de sortie (enrichi)")
    args = parser.parse_args()

    with open(args.input, 'r', encoding='utf-8') as f:
        matches = json.load(f)
    print(f"Chargé {len(matches)} matchs")
    enriched = enrich_matches(matches)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)
    print(f"Enregistré {len(enriched)} matchs enrichis dans {args.output}")

if __name__ == "__main__":
    main()