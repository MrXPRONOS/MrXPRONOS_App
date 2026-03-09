#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_data.py - Moteur de pronostics football (double chance) avec Elo, xG, fatigue, et score AI.
Utilise rotation de clés API.
"""

import os
import json
import requests
import random
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from math import exp, factorial, log10
from collections import defaultdict

# =======================================================
# IMPORT DU MODULE PARTAGÉ POUR LES REQUÊTES
# =======================================================
from api_utils import make_request

# =======================================================
# CONFIGURATION GÉNÉRALE
# =======================================================
SPORTDATA_URL = "https://v1.football.sportsapipro.com/games/allscores"
PREDICTIONS_URL = "https://v1.football.sportsapipro.com/games/predictions"

today = datetime.now().date()
tomorrow = today + timedelta(days=1)
yesterday = today - timedelta(days=1)

DATA_FILE = "data.json"
CACHE_DIR = "cache"
GLOBAL_CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")
ELO_CACHE_FILE = os.path.join(CACHE_DIR, "elo_ratings.json")
LOGOS_DIR = "assets/images/logos"
COMPETITION_LOGOS_DIR = os.path.join(LOGOS_DIR, "competitions")
os.makedirs(COMPETITION_LOGOS_DIR, exist_ok=True)

HOME_ADVANTAGE = 0.1
CONFIDENCE_THRESHOLD = 50
GOAL_DIFF_THRESHOLD = 0.1
XPRONOS_THRESHOLD = 45
DOMINANCE_THRESHOLD = 0.4

# Paramètres Elo
ELO_K_FACTOR = 20
ELO_K_CUP = 30
INITIAL_ELO = 1500

print("=" * 60)
print(f"🚀 GÉNÉRATION DES PRONOSTICS AVANCÉS (double chance) - {today}")
print("=" * 60)


# =======================================================
# FONCTIONS DE TÉLÉCHARGEMENT DES LOGOS (inchangées)
# =======================================================
def get_competitor_logo_url(competitor_id, image_version=None):
    base_url = "https://v1.football.sportsapipro.com/images/competitors"
    if image_version:
        return f"{base_url}/{competitor_id}?imageVersion={image_version}"
    return f"{base_url}/{competitor_id}"

def download_logo(competitor_id, image_version=None):
    filename = f"competitor_{competitor_id}.png"
    filepath = os.path.join(LOGOS_DIR, filename)
    rel_path = f"assets/images/logos/{filename}"
    if os.path.exists(filepath):
        return rel_path
    url = get_competitor_logo_url(competitor_id, image_version)
    try:
        resp = make_request('GET', url, timeout=10)
        if resp.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(resp.content)
            print(f"✅ Logo téléchargé : {competitor_id}")
            return rel_path
        else:
            print(f"⚠️ Échec téléchargement logo {competitor_id} (code {resp.status_code})")
    except Exception as e:
        print(f"⚠️ Erreur téléchargement logo {competitor_id}: {e}")
    return None

def get_competition_logo_url(competition_id, image_version=None):
    base_url = "https://v1.football.sportsapipro.com/images/competitions"
    if image_version:
        return f"{base_url}/{competition_id}?imageVersion={image_version}"
    return f"{base_url}/{competition_id}"

def download_competition_logo(competition_id, image_version=None):
    filename = f"competition_{competition_id}.png"
    filepath = os.path.join(COMPETITION_LOGOS_DIR, filename)
    rel_path = f"assets/images/logos/competitions/{filename}"
    if os.path.exists(filepath):
        return rel_path
    url = get_competition_logo_url(competition_id, image_version)
    try:
        resp = make_request('GET', url, timeout=10)
        if resp.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(resp.content)
            print(f"✅ Logo compétition téléchargé : {competition_id}")
            return rel_path
        else:
            print(f"⚠️ Échec téléchargement logo compétition {competition_id} (code {resp.status_code})")
    except Exception as e:
        print(f"⚠️ Erreur téléchargement logo compétition {competition_id}: {e}")
    return None

# =======================================================
# FONCTIONS DE RÉCUPÉRATION DES DONNÉES SPORTDATA
# =======================================================
def fetch_games_with_comps(date_from, date_to):
    params = {
        "startDate": date_from.strftime("%d/%m/%Y"),
        "endDate": date_to.strftime("%d/%m/%Y"),
        "sports": 1,
        "showOdds": "true",
        "onlyMajorGames": "false"
    }
    try:
        resp = make_request('GET', SPORTDATA_URL, params=params, timeout=30)
        data = resp.json()
        games = data.get("games", [])
        competitions = data.get("competitions", [])
        return games, competitions
    except Exception as e:
        print(f"❌ Erreur SportData: {e}")
        return [], []

def fetch_predictions(game_id):
    params = {"gameId": game_id}
    try:
        resp = make_request('GET', PREDICTIONS_URL, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            games = data.get("games", [])
            if games:
                game_data = games[0]
                promoted = game_data.get("promotedPredictions", {})
                predictions = promoted.get("predictions", [])
                for pred in predictions:
                    if pred.get("type") == 1:
                        return pred
        return None
    except Exception as e:
        print(f"⚠️ Erreur lors de la récupération des votes pour le match {game_id}: {e}")
        return None

def extract_game_info(game, comp_image_map):
    start_time = game.get("startTime")
    competition = game.get("competitionDisplayName", "")
    competition_id = game.get("competitionId")
    competition_image_version = comp_image_map.get(competition_id)
    home = game.get("homeCompetitor", {})
    away = game.get("awayCompetitor", {})
    home_score = home.get("score")
    away_score = away.get("score")
    if home_score == -1:
        home_score = None
    if away_score == -1:
        away_score = None
    odds_data = game.get("odds")
    odds = None
    if odds_data:
        options = odds_data.get("options", [])
        cotes = {}
        for opt in options:
            num = opt.get("num")
            rate = opt.get("rate", {})
            decimal = rate.get("decimal")
            if num == 1:
                cotes["home"] = decimal
            elif num == 2:
                cotes["draw"] = decimal
            elif num == 3:
                cotes["away"] = decimal
        if cotes:
            odds = cotes
    return {
        "id": game.get("id"),
        "start_time": start_time,
        "date": start_time[:10] if start_time else "",
        "home_team": home.get("name", ""),
        "away_team": away.get("name", ""),
        "home_competitor_id": home.get("id"),
        "away_competitor_id": away.get("id"),
        "home_image_version": home.get("imageVersion"),
        "away_image_version": away.get("imageVersion"),
        "competition": competition,
        "competition_id": competition_id,
        "competition_image_version": competition_image_version,
        "home_score": home_score,
        "away_score": away_score,
        "status_group": game.get("statusGroup"),
        "status_text": game.get("statusText"),
        "is_finished": (game.get("statusGroup") == 4),
        "odds": odds
    }

# =======================================================
# FONCTIONS D'ANALYSE (FORME, H2H, etc.)
# =======================================================
def build_team_history(historical):
    team_matches = {}
    for m in historical:
        home = m["home_team"]
        away = m["away_team"]
        try:
            date = datetime.fromisoformat(m["start_time"].replace('Z', '+00:00')).replace(tzinfo=None)
        except:
            continue
        if home not in team_matches:
            team_matches[home] = []
        team_matches[home].append((date, m, "home"))
        if away not in team_matches:
            team_matches[away] = []
        team_matches[away].append((date, m, "away"))
    for team in team_matches:
        team_matches[team].sort(key=lambda x: x[0], reverse=True)
    return team_matches

def get_team_form(team, team_matches, last_games=5, max_days=365):
    matches = team_matches.get(team, [])
    recent = []
    for date, match, side in matches:
        if match.get("is_finished") and match["home_score"] is not None:
            days_old = (datetime.now() - date).days
            if days_old <= max_days:
                recent.append((date, match, side))
        if len(recent) >= last_games:
            break
    if not recent:
        return None
    wins = draws = losses = 0.0
    goals_for = goals_against = 0.0
    total_weight = 0.0
    for i, (date, match, side) in enumerate(recent):
        weight = 1.5 ** (len(recent) - i - 1)
        total_weight += weight
        if side == "home":
            gf = match["home_score"]
            ga = match["away_score"]
        else:
            gf = match["away_score"]
            ga = match["home_score"]
        goals_for += gf * weight
        goals_against += ga * weight
        if gf > ga:
            wins += 1 * weight
        elif gf == ga:
            draws += 1 * weight
        else:
            losses += 1 * weight
    wins /= total_weight
    draws /= total_weight
    losses /= total_weight
    goals_for /= total_weight
    goals_against /= total_weight
    points_per_game = (wins * 3 + draws) / (wins + draws + losses) if (wins+draws+losses) > 0 else 0
    form_score = points_per_game / 3
    return {
        "wins": round(wins, 2),
        "draws": round(draws, 2),
        "losses": round(losses, 2),
        "goals_for": round(goals_for, 2),
        "goals_against": round(goals_against, 2),
        "form_score": round(form_score, 3),
        "matches_used": len(recent)
    }

def weight_by_date(date_str):
    try:
        match_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).replace(tzinfo=None)
        days_old = (datetime.now() - match_date).days
        if days_old < 180:
            return 1.5
        elif days_old < 365:
            return 1.2
        else:
            return 1.0
    except:
        return 1.0

def competition_weight(competition):
    comp_lower = competition.lower()
    if "friendly" in comp_lower:
        return 0.5
    if "cup" in comp_lower or "playoff" in comp_lower:
        return 1.3
    return 1.0

def get_h2h(historical, home_team, away_team, years=2):
    cutoff_date = (datetime.now() - timedelta(days=365*years)).date()
    h2h = []
    for m in historical:
        if (m["home_team"].lower() == home_team.lower() and m["away_team"].lower() == away_team.lower()) or \
           (m["home_team"].lower() == away_team.lower() and m["away_team"].lower() == home_team.lower()):
            try:
                match_date = datetime.fromisoformat(m["start_time"].replace('Z', '+00:00')).date()
            except:
                continue
            if match_date >= cutoff_date:
                h2h.append(m)
    h2h.sort(key=lambda x: x["start_time"], reverse=True)
    return h2h

def analyze_h2h(h2h_list, current_home_team, current_away_team):
    home_score = 0.0
    away_score = 0.0
    draws_score = 0.0
    matches_count = 0
    for match in h2h_list:
        if not match.get("is_finished") or match["home_score"] is None or match["away_score"] is None:
            continue
        date_weight = weight_by_date(match["start_time"])
        comp_weight = competition_weight(match.get("competition", ""))
        weight = date_weight * comp_weight
        matches_count += 1
        if match["home_score"] > match["away_score"]:
            if match["home_team"].lower() == current_home_team.lower():
                home_score += weight
            else:
                away_score += weight
        elif match["home_score"] < match["away_score"]:
            if match["away_team"].lower() == current_home_team.lower():
                home_score += weight
            else:
                away_score += weight
        else:
            draws_score += weight
    total_weighted = home_score + away_score + draws_score
    home_dominance = home_score / total_weighted if total_weighted > 0 else 0
    away_dominance = away_score / total_weighted if total_weighted > 0 else 0
    draw_rate = draws_score / total_weighted if total_weighted > 0 else 0
    return {
        "total_matches": matches_count,
        "home_wins": round(home_score, 2),
        "away_wins": round(away_score, 2),
        "draws": round(draws_score, 2),
        "home_dominance": round(home_dominance, 3),
        "away_dominance": round(away_dominance, 3),
        "draw_rate": round(draw_rate, 3)
    }

def generate_prediction(analysis, home_form, away_form, league):
    home_dom = analysis["home_dominance"] + HOME_ADVANTAGE
    away_dom = analysis["away_dominance"]
    seuil = DOMINANCE_THRESHOLD
    if home_dom > away_dom + seuil:
        double_chance = "1X"
    elif away_dom > home_dom + seuil:
        double_chance = "X2"
    else:
        double_chance = "12"
    confiance = 50
    confiance += min(20, analysis["total_matches"] * 3)
    if max(home_dom, away_dom) > 0.7:
        confiance += 10
    if home_form and away_form:
        form_diff = abs(home_form["form_score"] - away_form["form_score"])
        if form_diff > 0.2:
            confiance += 5
        if home_form["form_score"] > 0.7 and away_form["form_score"] < 0.4:
            confiance += 5
        attack_diff = home_form["goals_for"] - away_form["goals_for"]
        if attack_diff > 0.8:
            confiance += 5
        defense_diff = away_form["goals_against"] - home_form["goals_against"]
        if defense_diff > 0.8:
            confiance += 5
    if analysis["draw_rate"] > 0.4:
        confiance -= 10
    confiance = max(0, min(100, confiance))
    return {"double_chance": double_chance, "confidence": confiance}

def load_historical_matches():
    if not os.path.exists(GLOBAL_CACHE_FILE):
        print("⚠️ Fichier historique introuvable. Exécutez d'abord allmatches.py.")
        return []
    with open(GLOBAL_CACHE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# =======================================================
# NOUVELLES FONCTIONS : ELO, xG, FATIGUE, SCORE AI
# =======================================================

def compute_elo_ratings(historical):
    """
    Calcule les ratings Elo pour toutes les équapes à partir de l'historique.
    Retourne un dictionnaire {team: elo} et une liste de matchs avec elo avant match.
    """
    elo = defaultdict(lambda: INITIAL_ELO)
    matches_with_elo = []
    # Trier les matchs par date croissante
    sorted_matches = sorted(historical, key=lambda m: m.get("start_time", ""))
    for match in sorted_matches:
        if not match.get("is_finished") or match["home_score"] is None or match["away_score"] is None:
            continue
        home = match["home_team"]
        away = match["away_team"]
        home_score = match["home_score"]
        away_score = match["away_score"]
        # Elo avant match
        elo_home = elo[home]
        elo_away = elo[away]
        # Espérance
        exp_home = 1 / (1 + 10 ** ((elo_away - elo_home) / 400))
        exp_away = 1 - exp_home
        # Résultat
        if home_score > away_score:
            result_home = 1.0
            result_away = 0.0
        elif home_score < away_score:
            result_home = 0.0
            result_away = 1.0
        else:
            result_home = 0.5
            result_away = 0.5
        # Facteur K (simple : on utilise 20, on pourrait affiner par compétition)
        k = ELO_K_FACTOR
        # Mise à jour
        elo[home] += k * (result_home - exp_home)
        elo[away] += k * (result_away - exp_away)
        # Stocker les Elo avant match pour ce match
        matches_with_elo.append({
            "id": match["id"],
            "home_team": home,
            "away_team": away,
            "elo_home": elo_home,
            "elo_away": elo_away
        })
    return elo, matches_with_elo

def compute_team_stats(historical):
    """
    Calcule les statistiques d'attaque/défense moyennes par équipe.
    Retourne un dict : team -> {"attack": buts marqués par match, "defense": buts encaissés par match}
    """
    team_goals_for = defaultdict(float)
    team_goals_against = defaultdict(float)
    team_matches_count = defaultdict(int)
    for match in historical:
        if not match.get("is_finished") or match["home_score"] is None or match["away_score"] is None:
            continue
        home = match["home_team"]
        away = match["away_team"]
        gf_h = match["home_score"]
        ga_h = match["away_score"]
        gf_a = match["away_score"]
        ga_a = match["home_score"]
        team_goals_for[home] += gf_h
        team_goals_against[home] += ga_h
        team_goals_for[away] += gf_a
        team_goals_against[away] += ga_a
        team_matches_count[home] += 1
        team_matches_count[away] += 1
    stats = {}
    for team in team_matches_count:
        cnt = team_matches_count[team]
        stats[team] = {
            "attack": team_goals_for[team] / cnt,
            "defense": team_goals_against[team] / cnt
        }
    return stats

def poisson_probability(lambda_home, lambda_away, max_goals=6):
    p_home = 0
    p_draw = 0
    p_away = 0
    for i in range(max_goals+1):
        for j in range(max_goals+1):
            prob = (exp(-lambda_home) * lambda_home**i / factorial(i)) * \
                   (exp(-lambda_away) * lambda_away**j / factorial(j))
            if i > j:
                p_home += prob
            elif i == j:
                p_draw += prob
            else:
                p_away += prob
    return p_home, p_draw, p_away

def get_fatigue(team, team_matches, days=7):
    """
    Compte le nombre de matchs joués par une équipe dans les 'days' derniers jours.
    """
    now = datetime.now()
    cutoff = now - timedelta(days=days)
    count = 0
    if team in team_matches:
        for date, match, side in team_matches[team]:
            if date >= cutoff:
                count += 1
    return count

def implied_probability(odds_decimal):
    if odds_decimal and odds_decimal > 0:
        return 1 / odds_decimal
    return 0

def estimate_dc_odds(odds, double_chance):
    prob_home = implied_probability(odds.get('home'))
    prob_draw = implied_probability(odds.get('draw'))
    prob_away = implied_probability(odds.get('away'))
    total = prob_home + prob_draw + prob_away
    if total == 0:
        return 0
    if double_chance == '1X':
        prob = (prob_home + prob_draw) / total
    elif double_chance == 'X2':
        prob = (prob_draw + prob_away) / total
    elif double_chance == '12':
        prob = (prob_home + prob_away) / total
    else:
        return 0
    return 1 / prob if prob > 0 else 0

def calculate_ai_score(xpronos_score, form_home, form_away, elo_diff, poisson_prob_dc, value_bet):
    """
    Calcule un score AI composite (0-100).
    """
    # Normalisation des facteurs
    # xpronos_score déjà 0-100
    # forme : on prend la moyenne des form_score (0-1) * 100
    form_avg = ((form_home["form_score"] if form_home else 0) + (form_away["form_score"] if form_away else 0)) / 2 * 100
    # Elo diff : différence normalisée entre -400 et +400 -> 0-100
    # On utilise sigmoïde : 1/(1+10^(-diff/400)) * 100
    elo_factor = 1 / (1 + 10 ** (-elo_diff / 400)) * 100
    # Poisson : probabilité du double chance (0-1) * 100
    poisson_factor = poisson_prob_dc * 100
    # Value bet : 10 points si value_bet
    value_factor = 10 if value_bet else 0

    # Pondérations (ajustables)
    weights = {
        "xpronos": 0.25,
        "form": 0.20,
        "elo": 0.25,
        "poisson": 0.20,
        "value": 0.10
    }
    ai = (xpronos_score * weights["xpronos"] +
          form_avg * weights["form"] +
          elo_factor * weights["elo"] +
          poisson_factor * weights["poisson"] +
          value_factor)
    return min(100, max(0, int(ai)))

# =======================================================
# FONCTION PRINCIPALE
# =======================================================
def main():
    # 1. Charger l'existant
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
            existing_matches = {m["id"]: m for m in existing_data.get("matches", [])}
    else:
        existing_data = {"matches": [], "categories": {"simple": [], "pro": [], "vip": []}, "stats": {}, "bookmakers": []}
        existing_matches = {}

    # 2. Récupérer les matchs du jour/demain/hier
    print("\n📅 Récupération des matchs via SportData...")
    games_today, comps_today = fetch_games_with_comps(today, today)
    games_tomorrow, comps_tomorrow = fetch_games_with_comps(tomorrow, tomorrow)
    games_yesterday, comps_yesterday = fetch_games_with_comps(yesterday, yesterday)

    all_new_games = games_today + games_tomorrow + games_yesterday
    all_comps = comps_today + comps_tomorrow + comps_yesterday

    comp_image_map = {}
    for comp in all_comps:
        comp_id = comp.get("id")
        if comp_id:
            comp_image_map[comp_id] = comp.get("imageVersion")

    print(f"✅ {len(all_new_games)} matchs récupérés, {len(all_comps)} compétitions")

    # 3. Construire un dictionnaire des infos de base
    new_infos = {g["id"]: extract_game_info(g, comp_image_map) for g in all_new_games}

    # 4. Charger l'historique H2H
    historical = load_historical_matches()
    print(f"📂 Historique chargé : {len(historical)} matchs")

    # 5. Construire l'historique des équipes pour la forme récente
    team_matches = build_team_history(historical)
    print(f"📊 Statistiques de forme calculées pour {len(team_matches)} équipes")

    # 6. Calculer les Elo
    elo_ratings, matches_elo = compute_elo_ratings(historical)
    # Créer un dictionnaire match_id -> elo avant match
    elo_before = {m["id"]: {"home": m["elo_home"], "away": m["elo_away"]} for m in matches_elo}
    print(f"🏆 Ratings Elo calculés pour {len(elo_ratings)} équipes")

    # 7. Calculer les statistiques d'attaque/défense
    team_stats = compute_team_stats(historical)
    print(f"📈 Statistiques d'attaque/défense calculées")

    # 8. Préparer les nouvelles listes
    matches = []
    categories = {"simple": [], "pro": [], "vip": []}

    all_ids = set(existing_matches.keys()) | set(new_infos.keys())
    for gid in all_ids:
        if gid not in new_infos:
            match = existing_matches[gid]
            matches.append(match)
            categories[match["category"]].append(match)
            continue

        base = new_infos[gid]
        existing = existing_matches.get(gid)
        home_score = base["home_score"] if base["home_score"] is not None else (existing.get("home_score") if existing else None)
        away_score = base["away_score"] if base["away_score"] is not None else (existing.get("away_score") if existing else None)
        status = base["status_text"] if base["status_text"] else (existing.get("status") if existing else "")

        home_form = get_team_form(base["home_team"], team_matches, last_games=5)
        away_form = get_team_form(base["away_team"], team_matches, last_games=5)

        # Vérifier forme minimale (assouplie)
        if home_form is None and away_form is None:
            print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (pas de forme)")
            continue
        if home_form is None and away_form and away_form["matches_used"] < 1:
            print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (forme insuffisante)")
            continue
        if away_form is None and home_form and home_form["matches_used"] < 1:
            print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (forme insuffisante)")
            continue
        if home_form and home_form["matches_used"] < 1 and away_form and away_form["matches_used"] < 1:
            print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (peu de forme)")
            continue

        # Récupérer H2H
        h2h_list = get_h2h(historical, base["home_team"], base["away_team"], years=2)
        if len(h2h_list) >= 2:
            analysis = analyze_h2h(h2h_list, base["home_team"], base["away_team"])
            print(f"📊 Match {base['home_team']} vs {base['away_team']} - H2H OK")
        else:
            # Fallback Poisson
            if home_form and away_form and home_form["matches_used"] >= 2 and away_form["matches_used"] >= 2:
                print(f"⚠️ Match {base['home_team']} vs {base['away_team']} - H2H insuffisant, utilisation du modèle Poisson")
                lambda_home = (home_form["goals_for"] + away_form["goals_against"]) / 2
                lambda_away = (away_form["goals_for"] + home_form["goals_against"]) / 2
                p_home, p_draw, p_away = poisson_probability(lambda_home, lambda_away)
                analysis = {
                    "total_matches": 0,
                    "home_wins": 0,
                    "away_wins": 0,
                    "draws": 0,
                    "home_dominance": p_home,
                    "away_dominance": p_away,
                    "draw_rate": p_draw
                }
            else:
                print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (H2H insuffisant et forme insuffisante)")
                continue

        # Filtre sur draw_rate
        if analysis["draw_rate"] > 0.45:
            print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (draw_rate > 0.45)")
            continue

        prediction = generate_prediction(analysis, home_form, away_form, base["competition"])

        if prediction["double_chance"] == "12":
            print(f"   ⚠️ Pronostic 12 (match équilibré) ignoré")
            continue

        if prediction["confidence"] < CONFIDENCE_THRESHOLD:
            print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (confiance {prediction['confidence']} < {CONFIDENCE_THRESHOLD})")
            continue

        if home_form and away_form:
            goal_diff = abs(home_form["goals_for"] - away_form["goals_for"])
            if goal_diff < GOAL_DIFF_THRESHOLD:
                print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (différence buts trop faible: {goal_diff:.2f})")
                continue

        odds = base.get("odds")
        if odds:
            dc = prediction["double_chance"]
            if dc == "1X" and odds.get("home") and odds["home"] < 1.20:
                print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (cote home trop faible pour 1X)")
                continue
            if dc == "X2" and odds.get("away") and odds["away"] < 1.20:
                print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (cote away trop faible pour X2)")
                continue

        score = calculate_xpronos_score(analysis, home_form, away_form, base["competition"])  # à définir avant
        category = get_category(score)   # à définir avant
        badge = get_badge(score)         # à définir avant

        if score < XPRONOS_THRESHOLD:
            print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (score xPronos {score} < {XPRONOS_THRESHOLD})")
            continue

        # Téléchargement des logos
        home_logo = download_logo(base["home_competitor_id"], base["home_image_version"])
        away_logo = download_logo(base["away_competitor_id"], base["away_image_version"])
        league_logo = download_competition_logo(base["competition_id"], base.get("competition_image_version"))

        # Récupération des votes publics
        public_votes = None
        if category in ["pro", "vip"]:
            votes = fetch_predictions(gid)
            if votes:
                options = votes.get("options", [])
                vote_dict = {}
                for opt in options:
                    num = opt.get("num")
                    vote_data = opt.get("vote", {})
                    percentage = vote_data.get("percentage")
                    if num == 1:
                        vote_dict["home"] = percentage
                    elif num == 2:
                        vote_dict["draw"] = percentage
                    elif num == 3:
                        vote_dict["away"] = percentage
                if vote_dict:
                    public_votes = vote_dict

        # Détection des pièges
        is_trap = False
        if public_votes:
            dc = prediction["double_chance"]
            if dc == "1X":
                total_votes = (public_votes.get("home") or 0) + (public_votes.get("draw") or 0)
                if total_votes > 70:
                    is_trap = True
            elif dc == "X2":
                total_votes = (public_votes.get("draw") or 0) + (public_votes.get("away") or 0)
                if total_votes > 70:
                    is_trap = True
            elif dc == "12":
                total_votes = (public_votes.get("home") or 0) + (public_votes.get("away") or 0)
                if total_votes > 70:
                    is_trap = True

        # Calcul de la value bet
        value_bet = False
        if odds:
            dc = prediction["double_chance"]
            home_dom = analysis["home_dominance"] + HOME_ADVANTAGE
            away_dom = analysis["away_dominance"]
            if dc == "1X":
                our_prob = (home_dom * 0.6) + (analysis["draw_rate"] * 0.4)
                if home_form and away_form:
                    form_diff = home_form["form_score"] - away_form["form_score"]
                    our_prob += max(0, form_diff * 0.2)
            elif dc == "X2":
                our_prob = (away_dom * 0.6) + (analysis["draw_rate"] * 0.4)
                if home_form and away_form:
                    form_diff = home_form["form_score"] - away_form["form_score"]
                    our_prob += max(0, -form_diff * 0.2)
            elif dc == "12":
                our_prob = home_dom + away_dom
            else:
                our_prob = 0
            our_prob = min(our_prob, 0.95)
            dc_odds = estimate_dc_odds(odds, dc)
            if dc_odds > 0:
                book_prob = 1 / dc_odds
                if our_prob > book_prob + 0.05:
                    value_bet = True

        # --- NOUVEAU : Elo ---
        elo_diff = 0
        if gid in elo_before:
            elo_diff = elo_before[gid]["home"] - elo_before[gid]["away"]
        else:
            # Fallback : utiliser les Elo actuels (si pas de match dans l'historique)
            elo_home = elo_ratings.get(base["home_team"], INITIAL_ELO)
            elo_away = elo_ratings.get(base["away_team"], INITIAL_ELO)
            elo_diff = elo_home - elo_away

        # --- NOUVEAU : xG estimé ---
        league_avg_goals = 2.5  # valeur par défaut, on pourrait calculer par championnat
        home_stats = team_stats.get(base["home_team"], {"attack": 1.0, "defense": 1.0})
        away_stats = team_stats.get(base["away_team"], {"attack": 1.0, "defense": 1.0})
        xG_home = home_stats["attack"] * away_stats["defense"] * league_avg_goals
        xG_away = away_stats["attack"] * home_stats["defense"] * league_avg_goals
        # Probabilités Poisson à partir des xG
        p_home, p_draw, p_away = poisson_probability(xG_home, xG_away)
        poisson_dc_prob = 0
        if prediction["double_chance"] == "1X":
            poisson_dc_prob = p_home + p_draw
        elif prediction["double_chance"] == "X2":
            poisson_dc_prob = p_draw + p_away
        elif prediction["double_chance"] == "12":
            poisson_dc_prob = p_home + p_away

        # --- NOUVEAU : fatigue ---
        fatigue_home_7 = get_fatigue(base["home_team"], team_matches, 7)
        fatigue_away_7 = get_fatigue(base["away_team"], team_matches, 7)
        fatigue_home_14 = get_fatigue(base["home_team"], team_matches, 14)
        fatigue_away_14 = get_fatigue(base["away_team"], team_matches, 14)
        fatigue_penalty = 0
        if fatigue_home_7 > 3:
            fatigue_penalty -= 5
        if fatigue_away_7 > 3:
            fatigue_penalty -= 5
        # On pourrait intégrer cette pénalité dans le score final

        # --- NOUVEAU : score AI ---
        ai_score = calculate_ai_score(
            xpronos_score=score,
            form_home=home_form,
            form_away=away_form,
            elo_diff=elo_diff,
            poisson_prob_dc=poisson_dc_prob,
            value_bet=value_bet
        )

        # Construction de la prédiction finale
        final_prediction = {
            "double_chance": prediction["double_chance"],
            "confidence": prediction["confidence"],
            "odds": estimate_odds(category, prediction["double_chance"])  # fallback
        }

        match = {
            "id": gid,
            "date": base["date"],
            "event_date": base["start_time"],
            "home_team": base["home_team"],
            "away_team": base["away_team"],
            "home_logo": home_logo,
            "away_logo": away_logo,
            "league": base["competition"],
            "league_logo": league_logo,
            "venue": "",
            "status": status,
            "home_score": home_score,
            "away_score": away_score,
            "h2h_analysis": analysis,
            "home_form": home_form,
            "away_form": away_form,
            "prediction": final_prediction,
            "xpronos_score": score,
            "badge": badge,
            "category": category,
            "verified_double": False,
            "verified_btts": False,
            "verified_over": False,
            "odds": odds,
            "public_votes": public_votes,
            "value_bet": value_bet,
            "is_finished": base["is_finished"],
            "elo_diff": round(elo_diff, 1),
            "xG_home": round(xG_home, 2),
            "xG_away": round(xG_away, 2),
            "poisson_probs": {"home": round(p_home,3), "draw": round(p_draw,3), "away": round(p_away,3)},
            "fatigue": {"home_7": fatigue_home_7, "away_7": fatigue_away_7},
            "is_trap": is_trap,
            "ai_score": ai_score
        }

        # Vérification si terminé
        if base["is_finished"] and home_score is not None and away_score is not None:
            dc = prediction["double_chance"]
            if dc == "1X":
                match["verified_double"] = (home_score > away_score) or (home_score == away_score)
            elif dc == "X2":
                match["verified_double"] = (home_score == away_score) or (home_score < away_score)

        matches.append(match)
        categories[category].append(match)

    # Tri par ai_score décroissant
    matches.sort(key=lambda x: x.get("ai_score", 0), reverse=True)

    # =======================================================
    # CALCUL DU ROI (inchangé)
    # =======================================================
    total_bets = 0
    total_wins = 0
    total_stake = 0
    total_return = 0
    for m in matches:
        if m.get("verified_double"):
            total_wins += 1
            odds = m.get("odds")
            if odds:
                dc = m["prediction"]["double_chance"]
                dc_odds = estimate_dc_odds(odds, dc)
                if dc_odds > 0:
                    odds_value = dc_odds
                else:
                    odds_value = m["prediction"].get("odds", 2.0)
            else:
                odds_value = m["prediction"].get("odds", 2.0)
            total_return += odds_value
        if m.get("is_finished"):
            total_bets += 1
            total_stake += 1
    if total_bets > 0:
        roi = ((total_return - total_stake) / total_stake) * 100
    else:
        roi = 0
    stats = {"total_bets": total_bets, "wins": total_wins, "roi": round(roi, 1)}

    default_bookmakers = [
        {"name": "1xBet", "logo": "assets/images/1xbet.webp", "url": "https://refpa58144.com/L?tag=d_2054511m_1599c_&site=2054511&ad=1599"},
        {"name": "1win", "logo": "assets/images/1win.webp", "url": "https://1wrbgb.com/?open=register&p=qqcw"},
        {"name": "Betwinner", "logo": "assets/images/betwinner.webp", "url": "https://bwredir.com/299Y"},
        {"name": "Melbet", "logo": "assets/images/melbet.webp", "url": "https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041"},
        {"name": "Linebet", "logo": "assets/images/linebet.webp", "url": "https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3072389&ad=22611"},
        {"name": "BetClic", "logo": "assets/images/betclic.webp", "url": "https://betpari-click.com/2vY0?extid=USD"}
    ]

    data = {
        "matches": matches,
        "categories": categories,
        "stats": stats,
        "bookmakers": existing_data.get("bookmakers", default_bookmakers)
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n💾 {DATA_FILE} généré avec {len(matches)} matchs")
    print(f"📊 Catégories : Simple: {len(categories['simple'])}, Pro: {len(categories['pro'])}, VIP: {len(categories['vip'])}")
    print(f"💰 ROI estimé : {stats['roi']}% sur {stats['total_bets']} matchs terminés")
    print(f"🖼️ Logos téléchargés dans {LOGOS_DIR}")

# Fonctions auxiliaires (doivent être définies avant main)
def calculate_xpronos_score(analysis, home_form, away_form, league):
    score = 0
    score += min(40, analysis["total_matches"] * 6)
    dominance = max(analysis["home_dominance"], analysis["away_dominance"])
    score += min(30, int(dominance * 100 * 0.5))
    if home_form and away_form:
        score += min(20, int((home_form["form_score"] + away_form["form_score"]) * 10))
    if analysis["draw_rate"] > 0.4:
        score -= 10
    return min(score, 100)

def get_category(score):
    if score >= 55:
        return "vip"
    elif score >= 50:
        return "pro"
    else:
        return "simple"

def get_badge(score):
    if score >= 70:
        return "🏆 PREMIUM LOCK"
    elif score >= 60:
        return "💎 VIP ELITE"
    elif score >= 50:
        return "🔥 ULTRA SAFE"
    return ""

def estimate_odds(category, double_chance):
    if category == "vip":
        if double_chance == "1X":
            return 1.25
        elif double_chance == "X2":
            return 1.35
    elif category == "pro":
        if double_chance == "1X":
            return 1.35
        elif double_chance == "X2":
            return 1.45
    else:  # simple
        if double_chance == "1X":
            return 1.45
        elif double_chance == "X2":
            return 1.60
    return 1.40

if __name__ == "__main__":
    main()