#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_data.py - Moteur de pronostics football (double chance) avec rotation de clés API
Intègre les métriques avancées : Elo, xG, fatigue, piège bookmaker et score AI.
Version améliorée avec normalisation des cotes, filtres, modèle ensemble, etc.
"""

import os
import json
import random
from datetime import datetime, timedelta, timezone
from math import exp, factorial
from api_utils import make_request  # Import du module partagé

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
LOGOS_DIR = "assets/images/logos"
COMPETITION_LOGOS_DIR = os.path.join(LOGOS_DIR, "competitions")
os.makedirs(COMPETITION_LOGOS_DIR, exist_ok=True)

HOME_ADVANTAGE = 0.1
CONFIDENCE_THRESHOLD = 50      # On ignore les matchs avec confidence < 50
GOAL_DIFF_THRESHOLD = 0.1      # Différence de buts minimum
XPRONOS_THRESHOLD = 45         # Score xPronos minimum
DOMINANCE_THRESHOLD = 0.4      # Seuil pour décider du double chance

# Liste des ligues à ignorer (imprévisibles)
BAD_LEAGUES = [
    "friendly",
    "u21",
    "u19",
    "women",
    "reserve",
    "youth",
    "amateur"
]

def is_bad_league(name):
    name = name.lower()
    return any(b in name for b in BAD_LEAGUES)

print("=" * 60)
print(f"🚀 GÉNÉRATION DES PRONOSTICS (DOUBLE CHANCE UNIQUEMENT) - {today}")
print("=" * 60)


# =======================================================
# FONCTIONS DE TÉLÉCHARGEMENT DES LOGOS (utilisent make_request)
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
# FONCTIONS DE RÉCUPÉRATION DES DONNÉES SPORTDATA (utilisent make_request)
# =======================================================
def fetch_games_with_comps(date_from, date_to):
    """Retourne (liste des matchs, liste des compétitions) pour une plage de dates."""
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
    """Récupère les votes publics pour un match via /games/predictions."""
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
                    if pred.get("type") == 1:  # Full Time Result
                        return pred
        return None
    except Exception as e:
        print(f"⚠️ Erreur lors de la récupération des votes pour le match {game_id}: {e}")
        return None


def extract_game_info(game, comp_image_map):
    """Extrait les informations de base d'un match, y compris les cotes."""
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

    # Extraire les cotes
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
# FONCTIONS D'ANALYSE DE LA FORME DES ÉQUIPES
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

    points_per_game = (wins * 3 + draws) / (wins + draws + losses) if (wins + draws + losses) > 0 else 0
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


# =======================================================
# FONCTIONS D'ANALYSE H2H
# =======================================================
def load_historical_matches():
    if not os.path.exists(GLOBAL_CACHE_FILE):
        print("⚠️ Fichier historique introuvable. Exécutez d'abord allmatches.py.")
        return []
    with open(GLOBAL_CACHE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


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
    cutoff_date = (datetime.now() - timedelta(days=365 * years)).date()
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

    return {
        "double_chance": double_chance,
        "confidence": confiance
    }


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
    elif score >= 47:
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


# =======================================================
# FONCTIONS DE CALCUL DE VALUE BET ET MODÈLE POISSON
# =======================================================
def normalize_odds(odds):
    """Normalise les cotes pour obtenir les probabilités sans marge."""
    if not odds or any(v is None for v in odds.values()):
        return None
    prob_home = 1 / odds["home"]
    prob_draw = 1 / odds["draw"]
    prob_away = 1 / odds["away"]
    total = prob_home + prob_draw + prob_away
    return {
        "home": prob_home / total,
        "draw": prob_draw / total,
        "away": prob_away / total
    }


def estimate_dc_odds(odds, double_chance, margin=0.05):
    """
    Estime la cote double chance à partir des cotes 1X2.
    odds: dict avec 'home', 'draw', 'away'
    double_chance: '1X', 'X2' ou '12'
    Retourne une cote décimale approximative (sans marge appliquée).
    """
    probs = normalize_odds(odds)
    if not probs:
        return 0
    if double_chance == '1X':
        prob = probs["home"] + probs["draw"]
    elif double_chance == 'X2':
        prob = probs["draw"] + probs["away"]
    elif double_chance == '12':
        prob = probs["home"] + probs["away"]
    else:
        return 0
    return 1 / prob if prob > 0 else 0


def poisson_probability(lambda_home, lambda_away, max_goals=6):
    """
    Calcule les probabilités de victoire, nul, défaite selon un modèle de Poisson.
    lambda_home : moyenne de buts attendue pour l'équipe à domicile
    lambda_away : moyenne de buts attendue pour l'équipe à l'extérieur
    Retourne (p_home, p_draw, p_away)
    """
    p_home = 0
    p_draw = 0
    p_away = 0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            prob = (exp(-lambda_home) * lambda_home ** i / factorial(i)) * \
                   (exp(-lambda_away) * lambda_away ** j / factorial(j))
            if i > j:
                p_home += prob
            elif i == j:
                p_draw += prob
            else:
                p_away += prob
    return p_home, p_draw, p_away


def estimate_odds(category, double_chance):
    """Estime une cote moyenne pour le double chance selon la catégorie (fallback)."""
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

    # 2. Récupérer les matchs du jour/demain/hier avec compétitions
    print("\n📅 Récupération des matchs via SportData...")
    games_today, comps_today = fetch_games_with_comps(today, today)
    games_tomorrow, comps_tomorrow = fetch_games_with_comps(tomorrow, tomorrow)
    games_yesterday, comps_yesterday = fetch_games_with_comps(yesterday, yesterday)

    all_new_games = games_today + games_tomorrow + games_yesterday
    all_comps = comps_today + comps_tomorrow + comps_yesterday

    # Créer un mapping competition_id -> imageVersion
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

    # 6. Préparer les nouvelles listes
    matches = []
    categories = {"simple": [], "pro": [], "vip": []}

    # Parcourir tous les IDs (existants + nouveaux)
    all_ids = set(existing_matches.keys()) | set(new_infos.keys())
    for gid in all_ids:
        # Si l'ID n'est pas dans les nouvelles infos, on garde l'ancien match (non mis à jour)
        if gid not in new_infos:
            match = existing_matches[gid]
            matches.append(match)
            categories[match["category"]].append(match)
            continue

        base = new_infos[gid]
        existing = existing_matches.get(gid)

        # On utilise les scores et statut du nouveau si disponibles, sinon ceux de l'existant
        home_score = base["home_score"] if base["home_score"] is not None else (existing.get("home_score") if existing else None)
        away_score = base["away_score"] if base["away_score"] is not None else (existing.get("away_score") if existing else None)
        status = base["status_text"] if base["status_text"] else (existing.get("status") if existing else "")

        # Filtre sur les ligues faibles
        if is_bad_league(base["competition"]):
            print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (ligue faible)")
            continue

        # Analyses H2H et forme
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
            # Analyse H2H normale
            analysis = analyze_h2h(h2h_list, base["home_team"], base["away_team"])
            print(f"📊 Match {base['home_team']} vs {base['away_team']} - H2H OK")
        else:
            # Fallback Poisson si les deux équipes ont une forme minimale
            if home_form and away_form and home_form["matches_used"] >= 2 and away_form["matches_used"] >= 2:
                print(f"⚠️ Match {base['home_team']} vs {base['away_team']} - H2H insuffisant, utilisation du modèle Poisson")
                # Calculer les moyennes de buts attendues avec amélioration
                lambda_home = (home_form["goals_for"] * 1.1 + away_form["goals_against"] * 0.9) / 2
                lambda_away = (away_form["goals_for"] * 0.9 + home_form["goals_against"] * 1.1) / 2
                p_home, p_draw, p_away = poisson_probability(lambda_home, lambda_away)
                # Construire une analyse fictive
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

        # Filtre sur draw_rate trop élevé
        if analysis["draw_rate"] > 0.45:
            print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (draw_rate > 0.45)")
            continue

        # Filtre sur matchs trop équilibrés (écart de dominance < 0.15)
        if abs(analysis["home_dominance"] - analysis["away_dominance"]) < 0.15:
            print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (trop équilibré)")
            continue

        prediction = generate_prediction(analysis, home_form, away_form, base["competition"])

        if prediction["double_chance"] == "12":
            print(f"   ⚠️ Pronostic 12 (match équilibré) ignoré")
            continue

        # Filtre sur la confiance
        if prediction["confidence"] < CONFIDENCE_THRESHOLD:
            print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (confiance {prediction['confidence']} < {CONFIDENCE_THRESHOLD})")
            continue

        # Filtre sur la différence de buts moyens
        if home_form and away_form:
            goal_diff = abs(home_form["goals_for"] - away_form["goals_for"])
            if goal_diff < GOAL_DIFF_THRESHOLD:
                print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (différence buts trop faible: {goal_diff:.2f})")
                continue

        # Filtre temporel : ignorer les matchs dans moins de 30 minutes
        try:
            match_time = datetime.fromisoformat(base["start_time"].replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            if (match_time - now).total_seconds() < 1800 and match_time > now:
                print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (trop proche)")
                continue
        except:
            pass

        # Filtre anti-surprise : écart de cotes trop grand
        odds = base.get("odds")
        if odds and odds.get("home") and odds.get("away"):
            if abs(odds["home"] - odds["away"]) > 3:
                print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (écart de cotes trop grand)")
                continue

        # Filtre sur les cotes trop faibles (adapté au double chance)
        if odds:
            dc = prediction["double_chance"]
            if dc == "1X" and odds.get("home") and odds["home"] < 1.20:
                print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (cote home trop faible pour 1X)")
                continue
            if dc == "X2" and odds.get("away") and odds["away"] < 1.20:
                print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (cote away trop faible pour X2)")
                continue

        score = calculate_xpronos_score(analysis, home_form, away_form, base["competition"])
        category = get_category(score)
        badge = get_badge(score)

        # Filtre optionnel sur le score xPronos (abaissé)
        if score < XPRONOS_THRESHOLD:
            print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (score xPronos {score} < {XPRONOS_THRESHOLD})")
            continue

        # Téléchargement des logos
        home_logo = download_logo(base["home_competitor_id"], base["home_image_version"])
        away_logo = download_logo(base["away_competitor_id"], base["away_image_version"])
        league_logo = download_competition_logo(base["competition_id"], base.get("competition_image_version"))

        # Récupération des votes publics (uniquement pour les catégories pro et vip)
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

        # =======================================================
        # CALCUL DE LA VALUE BET
        # =======================================================
        value_bet = False
        if odds:
            dc = prediction["double_chance"]
            # Notre probabilité estimée (combinaison de plusieurs sources)
            # Utilisation de l'analyse H2H et forme
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

        # =======================================================
        # CALCUL DES MÉTRIQUES AVANCÉES
        # =======================================================

        # 1. Elo rating simplifié (basé sur la forme)
        elo_base = 1500
        if home_form:
            elo_home = int(elo_base + (home_form["form_score"] * 200))
        else:
            elo_home = elo_base
        if away_form:
            elo_away = int(elo_base + (away_form["form_score"] * 200))
        else:
            elo_away = elo_base

        # 2. Expected Goals (xG) estimé avec amélioration
        if home_form and away_form:
            xg_home = (home_form["goals_for"] * 1.1 + away_form["goals_against"] * 0.9) / 2
            xg_away = (away_form["goals_for"] * 0.9 + home_form["goals_against"] * 1.1) / 2
        else:
            xg_home = xg_away = 1.2  # valeur par défaut

        # 3. Fatigue (nombre de matchs récents)
        fatigue_home = home_form["matches_used"] if home_form else 0
        fatigue_away = away_form["matches_used"] if away_form else 0

        # 4. Détection des pièges bookmakers (améliorée)
        trap_detected = False
        if public_votes and odds:
            dc = prediction["double_chance"]
            votes_home = public_votes.get("home", 0)
            votes_draw = public_votes.get("draw", 0)
            votes_away = public_votes.get("away", 0)
            # Si le public est trop confiant (>75%) sur un résultat différent du nôtre, on considère un piège
            if (votes_home > 75 and dc != "1X") or (votes_draw > 75 and dc != "X2") or (votes_away > 75 and dc != "12"):
                trap_detected = True
            # Autre piège : public >75% sur une équipe et cote > 2 (anormal)
            if votes_home > 75 and odds.get("home") and odds["home"] > 2:
                trap_detected = True
            if votes_away > 75 and odds.get("away") and odds["away"] > 2:
                trap_detected = True

        # 5. Score AI (combinaison pondérée)
        # Normalisation de la différence Elo (max ~200 points)
        elo_diff = (elo_home - elo_away) / 200.0
        # Pondérations
        ai_score = (
            score * 0.4 +                     # xPronos
            prediction["confidence"] * 0.3 +   # confiance
            max(0, min(100, elo_diff * 50))    # contribution Elo (max 50)
        )
        ai_score = min(100, max(0, ai_score))  # on ramène entre 0 et 100

        # =======================================================
        # MODÈLE ENSEMBLE (combinaison de probabilités)
        # =======================================================
        # Probabilité du marché normalisée
        market_probs = normalize_odds(odds) if odds else None
        # Probabilité du modèle Poisson
        if home_form and away_form:
            lambda_home_ens = (home_form["goals_for"] * 1.1 + away_form["goals_against"] * 0.9) / 2
            lambda_away_ens = (away_form["goals_for"] * 0.9 + home_form["goals_against"] * 1.1) / 2
            poisson_h, poisson_d, poisson_a = poisson_probability(lambda_home_ens, lambda_away_ens)
        else:
            poisson_h = poisson_d = poisson_a = 0.33

        # Probabilité H2H (à partir de l'analyse)
        h2h_h = analysis["home_dominance"]
        h2h_d = analysis["draw_rate"]
        h2h_a = analysis["away_dominance"]

        # Probabilité forme (simple)
        form_h = home_form["form_score"] if home_form else 0.5
        form_a = away_form["form_score"] if away_form else 0.5
        form_d = 1 - form_h - form_a  # approximation

        # Pondérations (ajustables)
        ensemble_h = (h2h_h * 0.4 + poisson_h * 0.3 + form_h * 0.3)
        ensemble_d = (h2h_d * 0.4 + poisson_d * 0.3 + form_d * 0.3)
        ensemble_a = (h2h_a * 0.4 + poisson_a * 0.3 + form_a * 0.3)
        # Normalisation
        total_ens = ensemble_h + ensemble_d + ensemble_a
        ensemble_h /= total_ens
        ensemble_d /= total_ens
        ensemble_a /= total_ens

        # Probabilité de double chance selon notre ensemble
        if prediction["double_chance"] == "1X":
            ensemble_prob_dc = ensemble_h + ensemble_d
        elif prediction["double_chance"] == "X2":
            ensemble_prob_dc = ensemble_d + ensemble_a
        else:
            ensemble_prob_dc = ensemble_h + ensemble_a

        # =======================================================

        # Construction de la prédiction finale
        final_prediction = {
            "double_chance": prediction["double_chance"],
            "confidence": prediction["confidence"],
            "odds": estimate_odds(category, prediction["double_chance"])  # fallback
        }

        # Score final de fiabilité (nouvelle formule)
        value_bet_bonus = 10 if value_bet else 0
        final_score = (
            score * 0.35 +
            prediction["confidence"] * 0.25 +
            ai_score * 0.25 +
            value_bet_bonus * 0.15
        )

        # Calcul des probabilités Poisson (pour info)
        poisson_probs = None
        if home_form and away_form:
            lambda_home = (home_form["goals_for"] * 1.1 + away_form["goals_against"] * 0.9) / 2
            lambda_away = (away_form["goals_for"] * 0.9 + home_form["goals_against"] * 1.1) / 2
            p_home, p_draw, p_away = poisson_probability(lambda_home, lambda_away)
            poisson_probs = {
                "home": round(p_home, 3),
                "draw": round(p_draw, 3),
                "away": round(p_away, 3)
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
            "poisson_probs": poisson_probs,
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
            "final_score": round(final_score, 1),
            # Nouveaux champs pour métriques avancées
            "ai_score": round(ai_score, 1),
            "elo_home": elo_home,
            "elo_away": elo_away,
            "xg_home": round(xg_home, 2),
            "xg_away": round(xg_away, 2),
            "fatigue_home": fatigue_home,
            "fatigue_away": fatigue_away,
            "trap_detected": trap_detected,
            # Champs supplémentaires pour l'analyse
            "ensemble_prob_home": round(ensemble_h, 3),
            "ensemble_prob_draw": round(ensemble_d, 3),
            "ensemble_prob_away": round(ensemble_a, 3),
            "ensemble_prob_dc": round(ensemble_prob_dc, 3)
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

    # Tri intelligent par score final décroissant
    matches.sort(key=lambda x: x.get("final_score", 0), reverse=True)

    # =======================================================
    # CALCUL DU ROI
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

    stats = {
        "total_bets": total_bets,
        "wins": total_wins,
        "roi": round(roi, 1)
    }

    default_bookmakers = [
        {"name": "1xBet", "logo": "assets/images/1xbet.webp",
         "url": "https://refpa58144.com/L?tag=d_2054511m_1599c_&site=2054511&ad=1599"},
        {"name": "1win", "logo": "assets/images/1win.webp",
         "url": "https://1wrbgb.com/?open=register&p=qqcw"},
        {"name": "Betwinner", "logo": "assets/images/betwinner.webp",
         "url": "https://bwredir.com/299Y"},
        {"name": "Melbet", "logo": "assets/images/melbet.webp",
         "url": "https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041"},
        {"name": "Linebet", "logo": "assets/images/linebet.webp",
         "url": "https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3072389&ad=22611"},
        {"name": "BetClic", "logo": "assets/images/betclic.webp",
         "url": "https://betpari-click.com/2vY0?extid=USD"}
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


if __name__ == "__main__":
    main()