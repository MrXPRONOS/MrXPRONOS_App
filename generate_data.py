#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_data.py - Moteur de pronostics football (double chance) avec API V2
Intègre les métriques avancées : Elo, xG, fatigue, piège bookmaker et score AI.
Version améliorée avec poids dynamiques, value bet avancé, suspicion detection.
"""

import os
import sys
import json
import time
import random
import hashlib
import requests
from datetime import datetime, timedelta, timezone
from math import exp, factorial
from typing import Dict, List, Optional, Tuple, Any

# =======================================================
# CONFIGURATION
# =======================================================

# Récupération des clés API (rotation)
API_KEYS = []
for i in range(1, 6):
    key = os.environ.get(f"SPORTDATA_API_KEY_{i}")
    if key:
        API_KEYS.append(key)
if not API_KEYS:
    single_key = os.environ.get("SPORTDATA_API_KEY")
    if single_key:
        API_KEYS = [single_key]
    else:
        raise ValueError("Aucune clé API trouvée. Définissez SPORTDATA_API_KEY_1..5 ou SPORTDATA_API_KEY")

# API V2
V2_BASE = "https://v2.football.sportsapipro.com"
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Paramètres
HOME_ADVANTAGE = 0.1
CONFIDENCE_THRESHOLD = 50
GOAL_DIFF_THRESHOLD = 0.1
XPRONOS_THRESHOLD = 35
DOMINANCE_THRESHOLD = 0.4
BET_SCORE_THRESHOLD = 55  # seuil pour accepter un match

BAD_LEAGUES = ["friendly", "u21", "u19", "women", "reserve", "youth", "amateur"]

# =======================================================
# FONCTIONS DE CACHE ET REQUÊTES
# =======================================================

def cache_get(key: str):
    """Récupère une entrée du cache local."""
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            pass
    return None

def cache_set(key: str, data):
    """Enregistre une entrée dans le cache local."""
    path = os.path.join(CACHE_DIR, f"{key}.json")
    with open(path, 'w') as f:
        json.dump(data, f)

def make_request_v2(endpoint: str, params: dict = None, use_cache: bool = True, max_retries: int = 3):
    """
    Effectue une requête vers l'API V2 avec rotation de clés, retry et cache.
    endpoint: chemin complet après la base (ex: /api/live)
    """
    url = f"{V2_BASE}{endpoint}"
    if params:
        # Construction de la query string
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"

    # Clé de cache (basée sur endpoint + paramètres)
    cache_key = endpoint.replace('/', '_') + (f"_{hash(str(params))}" if params else "")
    if use_cache:
        cached = cache_get(cache_key)
        if cached:
            return cached

    for attempt in range(max_retries):
        # Rotation des clés
        api_key = API_KEYS[attempt % len(API_KEYS)]
        headers = {"x-api-key": api_key}
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if use_cache:
                    cache_set(cache_key, data)
                return data
            else:
                print(f"⚠️ V2 {endpoint}: erreur {resp.status_code} avec clé {api_key[:8]}...")
        except Exception as e:
            print(f"⚠️ V2 {endpoint}: tentative {attempt+1}/{max_retries} échouée: {e}")
            time.sleep(1)
    raise Exception(f"Impossible d'appeler V2 {endpoint} après {max_retries} tentatives")

# =======================================================
# DÉCOUVERTE DES IDS (avec cache)
# =======================================================

def search_entity(query: str, entity_type: str):
    """
    Recherche un ID par nom via /api/search.
    entity_type: 'teams', 'players', 'tournaments'
    Retourne le premier ID trouvé, ou None.
    """
    data = make_request_v2("/api/search", params={"q": query})
    for item in data.get(entity_type, []):
        if item["name"].lower() == query.lower():
            return item["id"]
    # Fallback: premier résultat
    if data.get(entity_type):
        return data[entity_type][0]["id"]
    return None

def get_team_id(team_name: str) -> Optional[int]:
    """Retourne l'ID d'une équipe via cache."""
    cache_key = f"team_id_{team_name}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    team_id = search_entity(team_name, "teams")
    if team_id:
        cache_set(cache_key, team_id)
    return team_id

def get_tournament_id(league_name: str) -> Optional[int]:
    """Retourne l'ID d'une compétition."""
    cache_key = f"tournament_id_{league_name}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    tourn_id = search_entity(league_name, "tournaments")
    if tourn_id:
        cache_set(cache_key, tourn_id)
    return tourn_id

def get_current_season(tournament_id: int) -> Optional[int]:
    """
    Récupère l'ID de la saison en cours pour un tournoi.
    """
    cache_key = f"season_{tournament_id}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    try:
        data = make_request_v2(f"/api/tournaments/{tournament_id}/seasons")
        seasons = data.get("seasons", [])
        if not seasons:
            return None
        # Trouver la saison en cours (celle qui n'est pas terminée)
        today = datetime.now().date()
        for s in seasons:
            start = datetime.fromisoformat(s.get("start", "")).date() if s.get("start") else None
            end = datetime.fromisoformat(s.get("end", "")).date() if s.get("end") else None
            if start and end and start <= today <= end:
                season_id = s["id"]
                cache_set(cache_key, season_id)
                return season_id
        # Fallback: première saison
        season_id = seasons[0]["id"]
        cache_set(cache_key, season_id)
        return season_id
    except Exception as e:
        print(f"⚠️ Erreur récupération saison pour {tournament_id}: {e}")
        return None

# =======================================================
# RÉCUPÉRATION DES MATCHS VIA V2
# =======================================================

def fetch_games_v2(date_from: datetime, date_to: datetime) -> List[dict]:
    """
    Récupère les matchs pour une plage de dates via l'API V2.
    Utilise l'endpoint /api/schedule/{date}.
    """
    games = []
    current = date_from
    while current <= date_to:
        date_str = current.strftime("%Y-%m-%d")
        try:
            data = make_request_v2(f"/api/schedule/{date_str}")
            games.extend(data.get("events", []))
        except Exception as e:
            print(f"❌ Erreur V2 pour {date_str}: {e}")
        current += timedelta(days=1)
    return games

def extract_game_info_v2(game: dict) -> dict:
    """Extrait les informations de base d'un match V2."""
    home = game.get("homeTeam", {})
    away = game.get("awayTeam", {})
    tournament = game.get("tournament", {})
    start_time = game.get("startTime") or game.get("start_time")
    home_score = home.get("score")
    away_score = away.get("score")
    if home_score == -1: home_score = None
    if away_score == -1: away_score = None
    status = game.get("statusText", "")
    is_finished = status.lower() in ("finished", "terminé", "ended")
    return {
        "id": str(game["id"]),
        "start_time": start_time,
        "date": start_time[:10] if start_time else "",
        "home_team": home.get("name", ""),
        "away_team": away.get("name", ""),
        "home_team_id": home.get("id"),
        "away_team_id": away.get("id"),
        "competition": tournament.get("name", ""),
        "competition_id": tournament.get("id"),
        "home_score": home_score,
        "away_score": away_score,
        "status": status,
        "is_finished": is_finished,
        "odds": extract_odds_v2(game.get("odds", {})),
        "live_stats": extract_live_stats_v2(game),
    }

def extract_odds_v2(odds_data: dict) -> Optional[dict]:
    """
    Extrait les cotes 1X2 depuis la structure V2.
    """
    # Exemple: odds_data peut contenir "pre_match", "live", etc.
    pre = odds_data.get("pre_match", {})
    markets = pre.get("markets", [])
    for market in markets:
        if market.get("name") == "Match Winner" or market.get("type") == 1:
            outcomes = market.get("outcomes", [])
            odds = {}
            for o in outcomes:
                if o.get("name") == "Home":
                    odds["home"] = o.get("decimal")
                elif o.get("name") == "Draw":
                    odds["draw"] = o.get("decimal")
                elif o.get("name") == "Away":
                    odds["away"] = o.get("decimal")
            if odds:
                return odds
    return None

def extract_live_stats_v2(game: dict) -> dict:
    """
    Extrait les statistiques live (si disponibles) de la réponse V2.
    """
    # Les stats live sont souvent dans "live" -> "statistics"
    live = game.get("live", {})
    stats = live.get("statistics", {})
    # Structure attendue: { "home": {...}, "away": {...} }
    return stats

# =======================================================
# RÉCUPÉRATION DES DONNÉES DE FORME
# =======================================================

def get_team_form_v2(team_id: int, tournament_id: int, season_id: int, max_games: int = 5) -> Optional[dict]:
    """
    Récupère les résultats récents d'une équipe via V2 (endpoint events/last).
    Retourne un dictionnaire similaire à l'ancien format.
    """
    try:
        data = make_request_v2(f"/api/teams/{team_id}/events/last/0")
        events = data.get("events", [])[:max_games]
        if not events:
            return None
        wins = draws = losses = 0.0
        goals_for = goals_against = 0.0
        for ev in events:
            home = ev.get("homeTeam", {})
            away = ev.get("awayTeam", {})
            home_score = home.get("score")
            away_score = away.get("score")
            if home_score is None or away_score is None:
                continue
            if ev.get("status") == "finished":
                if home.get("id") == team_id:
                    gf = home_score
                    ga = away_score
                else:
                    gf = away_score
                    ga = home_score
                goals_for += gf
                goals_against += ga
                if gf > ga:
                    wins += 1
                elif gf == ga:
                    draws += 1
                else:
                    losses += 1
        total = wins + draws + losses
        if total == 0:
            return None
        form_score = (wins * 3 + draws) / (total * 3)
        return {
            "wins": wins / total,
            "draws": draws / total,
            "losses": losses / total,
            "goals_for": goals_for / total,
            "goals_against": goals_against / total,
            "form_score": form_score,
            "matches_used": total
        }
    except Exception as e:
        print(f"⚠️ Erreur forme équipe {team_id}: {e}")
        return None

# =======================================================
# RÉCUPÉRATION DE L'HISTORIQUE H2H
# =======================================================

def get_h2h_v2(match_id: int) -> List[dict]:
    """
    Récupère l'historique des confrontations directes via V2.
    Retourne une liste de matchs (format libre).
    """
    try:
        data = make_request_v2(f"/api/match/{match_id}/h2h")
        return data.get("matches", [])
    except:
        return []

# =======================================================
# FONCTIONS DE CALCUL (inchangées mais utilisées avec les nouvelles données)
# =======================================================

def safe_division(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0 or denominator is None:
        return default
    return numerator / denominator

def parse_datetime_safe(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        if 'Z' in date_str:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        elif '+' in date_str or (date_str.count('-') > 2 and 'T' in date_str):
            dt = datetime.fromisoformat(date_str)
        else:
            return datetime.fromisoformat(date_str)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except (ValueError, AttributeError) as e:
        print(f"⚠️ Erreur parsing date {date_str}: {e}")
        return None

def get_now_naive() -> datetime:
    return datetime.now()

def weight_by_date(date_str: str) -> float:
    try:
        match_date = parse_datetime_safe(date_str)
        if match_date is None:
            return 1.0
        now = get_now_naive()
        days_old = (now - match_date).days
        if days_old < 180:
            return 1.5
        elif days_old < 365:
            return 1.2
        else:
            return 1.0
    except:
        return 1.0

def competition_weight(competition: str) -> float:
    if not competition:
        return 1.0
    comp_lower = competition.lower()
    if "friendly" in comp_lower:
        return 0.5
    if "cup" in comp_lower or "playoff" in comp_lower:
        return 1.3
    return 1.0

def build_team_history(historical: List[dict]) -> dict:
    team_matches = {}
    for m in historical:
        if not isinstance(m, dict):
            continue
        home = m.get("home_team", "")
        away = m.get("away_team", "")
        if not home or not away:
            continue
        try:
            date = parse_datetime_safe(m.get("start_time", ""))
            if date is None:
                continue
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

def get_team_form(team: str, team_matches: dict, last_games: int = 5, max_days: int = 365) -> Optional[dict]:
    if not team or not isinstance(team_matches, dict):
        return None
    matches = team_matches.get(team, [])
    if not matches:
        return None
    recent = []
    now = get_now_naive()
    for date, match, side in matches:
        if not isinstance(match, dict):
            continue
        if match.get("is_finished") and match.get("home_score") is not None:
            days_old = (now - date).days
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
            gf = match.get("home_score", 0) or 0
            ga = match.get("away_score", 0) or 0
        else:
            gf = match.get("away_score", 0) or 0
            ga = match.get("home_score", 0) or 0
        goals_for += gf * weight
        goals_against += ga * weight
        if gf > ga:
            wins += weight
        elif gf == ga:
            draws += weight
        else:
            losses += weight
    if total_weight == 0:
        return None
    wins_norm = wins / total_weight
    draws_norm = draws / total_weight
    losses_norm = losses / total_weight
    goals_for_norm = goals_for / total_weight
    goals_against_norm = goals_against / total_weight
    total_results = wins + draws + losses
    points_per_game = safe_division(wins * 3 + draws, total_results, 0)
    form_score = safe_division(points_per_game, 3, 0)
    return {
        "wins": round(wins_norm, 2),
        "draws": round(draws_norm, 2),
        "losses": round(losses_norm, 2),
        "goals_for": round(goals_for_norm, 2),
        "goals_against": round(goals_against_norm, 2),
        "form_score": round(form_score, 3),
        "matches_used": len(recent)
    }

def analyze_h2h(h2h_list: List[dict], current_home_team: str, current_away_team: str) -> dict:
    home_score = 0.0
    away_score = 0.0
    draws_score = 0.0
    matches_count = 0
    if not h2h_list or not current_home_team or not current_away_team:
        return {
            "total_matches": 0,
            "home_wins": 0.0,
            "away_wins": 0.0,
            "draws": 0.0,
            "home_dominance": 0.0,
            "away_dominance": 0.0,
            "draw_rate": 0.0
        }
    current_home_lower = current_home_team.lower()
    for match in h2h_list:
        if not isinstance(match, dict):
            continue
        if not match.get("is_finished") or match.get("home_score") is None:
            continue
        date_weight = weight_by_date(match.get("start_time", ""))
        comp_weight = competition_weight(match.get("competition", ""))
        weight = date_weight * comp_weight
        matches_count += 1
        home_s = match.get("home_score", 0)
        away_s = match.get("away_score", 0)
        match_home_team = (match.get("home_team") or "").lower()
        if home_s > away_s:
            if match_home_team == current_home_lower:
                home_score += weight
            else:
                away_score += weight
        elif home_s < away_s:
            if match_home_team == current_home_lower:
                away_score += weight
            else:
                home_score += weight
        else:
            draws_score += weight
    total_weighted = home_score + away_score + draws_score
    return {
        "total_matches": matches_count,
        "home_wins": round(home_score, 2),
        "away_wins": round(away_score, 2),
        "draws": round(draws_score, 2),
        "home_dominance": safe_division(home_score, total_weighted, 0),
        "away_dominance": safe_division(away_score, total_weighted, 0),
        "draw_rate": safe_division(draws_score, total_weighted, 0)
    }

def poisson_probability(lambda_home: float, lambda_away: float, max_goals: int = 6) -> Tuple[float, float, float]:
    lambda_home = max(0.1, float(lambda_home))
    lambda_away = max(0.1, float(lambda_away))
    p_home = 0.0
    p_draw = 0.0
    p_away = 0.0
    try:
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                prob = (exp(-lambda_home) * (lambda_home ** i) / factorial(i)) * \
                       (exp(-lambda_away) * (lambda_away ** j) / factorial(j))
                if i > j:
                    p_home += prob
                elif i == j:
                    p_draw += prob
                else:
                    p_away += prob
    except (OverflowError, ValueError):
        return 0.33, 0.34, 0.33
    total = p_home + p_draw + p_away
    if total > 0:
        return p_home / total, p_draw / total, p_away / total
    else:
        return 0.33, 0.34, 0.33

def normalize_odds(odds: dict) -> Optional[dict]:
    if not odds or not isinstance(odds, dict):
        return None
    home = odds.get("home")
    draw = odds.get("draw")
    away = odds.get("away")
    if home is None or draw is None or away is None:
        return None
    if home <= 0 or draw <= 0 or away <= 0:
        return None
    try:
        prob_home = 1 / float(home)
        prob_draw = 1 / float(draw)
        prob_away = 1 / float(away)
    except (ValueError, ZeroDivisionError):
        return None
    total = prob_home + prob_draw + prob_away
    if total == 0:
        return None
    return {
        "home": prob_home / total,
        "draw": prob_draw / total,
        "away": prob_away / total
    }

def estimate_dc_odds(odds: dict, double_chance: str, margin: float = 0.05) -> float:
    probs = normalize_odds(odds)
    if not probs:
        return 0.0
    if double_chance == '1X':
        prob = probs["home"] + probs["draw"]
    elif double_chance == 'X2':
        prob = probs["draw"] + probs["away"]
    elif double_chance == '12':
        prob = probs["home"] + probs["away"]
    else:
        return 0.0
    if prob <= 0:
        return 0.0
    return 1 / prob

def dynamic_weights(h2h_count: int) -> Tuple[float, float, float]:
    if h2h_count >= 5:
        return 0.5, 0.3, 0.2
    elif h2h_count >= 2:
        return 0.3, 0.4, 0.3
    else:
        return 0.2, 0.5, 0.3

# =======================================================
# FONCTIONS DE PRÉDICTION
# =======================================================

def generate_prediction(analysis: dict, home_form: Optional[dict], away_form: Optional[dict], league: str) -> dict:
    home_dom = analysis.get("home_dominance", 0) + HOME_ADVANTAGE
    away_dom = analysis.get("away_dominance", 0)
    seuil = DOMINANCE_THRESHOLD
    if home_dom > away_dom + seuil:
        double_chance = "1X"
    elif away_dom > home_dom + seuil:
        double_chance = "X2"
    else:
        double_chance = "12"
    confiance = 50
    confiance += min(20, analysis.get("total_matches", 0) * 3)
    if max(home_dom, away_dom) > 0.7:
        confiance += 10
    if home_form and away_form:
        form_diff = abs(home_form.get("form_score", 0) - away_form.get("form_score", 0))
        if form_diff > 0.2:
            confiance += 5
        if home_form.get("form_score", 0) > 0.7 and away_form.get("form_score", 0) < 0.4:
            confiance += 5
        attack_diff = home_form.get("goals_for", 0) - away_form.get("goals_for", 0)
        if attack_diff > 0.8:
            confiance += 5
        defense_diff = away_form.get("goals_against", 0) - home_form.get("goals_against", 0)
        if defense_diff > 0.8:
            confiance += 5
    if analysis.get("draw_rate", 0) > 0.4:
        confiance -= 10
    confiance = max(0, min(100, confiance))
    return {
        "double_chance": double_chance,
        "confidence": confiance
    }

def calculate_xpronos_score(analysis: dict, home_form: Optional[dict], away_form: Optional[dict], league: str) -> int:
    score = 0
    score += min(40, analysis.get("total_matches", 0) * 6)
    dominance = max(analysis.get("home_dominance", 0), analysis.get("away_dominance", 0))
    score += min(30, int(dominance * 100 * 0.5))
    if home_form and away_form:
        form_sum = home_form.get("form_score", 0) + away_form.get("form_score", 0)
        score += min(20, int(form_sum * 10))
    if analysis.get("draw_rate", 0) > 0.4:
        score -= 10
    return max(0, min(score, 100))

def get_category(score: int) -> str:
    if score >= 50:
        return "pro"
    elif score >= 40:
        return "pro"
    else:
        return "simple"

def get_badge(score: int) -> str:
    if score >= 70:
        return "🏆 PREMIUM LOCK"
    elif score >= 60:
        return "💎 VIP ELITE"
    elif score >= 50:
        return "🔥 ULTRA SAFE"
    return ""

def is_bad_league(name: str) -> bool:
    if not name:
        return False
    name = name.lower()
    return any(b in name for b in BAD_LEAGUES)

# =======================================================
# FONCTION PRINCIPALE
# =======================================================

def main():
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)

    DATA_FILE = "data.json"

    print("="*60)
    print(f"🚀 GÉNÉRATION DES PRONOSTICS (DOUBLE CHANCE) - {today}")
    print("="*60)

    # 1. Charger les matchs via V2
    print("\n📅 Récupération des matchs via API V2...")
    games_today = fetch_games_v2(today, today)
    games_tomorrow = fetch_games_v2(tomorrow, tomorrow)
    games_yesterday = fetch_games_v2(yesterday, yesterday)
    all_new_games = games_today + games_tomorrow + games_yesterday

    # Extraire les infos de base
    new_infos = {}
    for g in all_new_games:
        info = extract_game_info_v2(g)
        if info and info.get("id"):
            new_infos[info["id"]] = info

    print(f"✅ {len(new_infos)} matchs récupérés")

    # 2. Charger l'historique H2H (à partir du cache historique local)
    #    Pour simplifier, on va utiliser un fichier global d'historique (all_matches.json)
    #    Ici on suppose qu'il existe déjà (généré par un script séparé)
    historical = []
    try:
        with open("cache/all_matches.json", "r") as f:
            historical = json.load(f)
        print(f"📂 Historique chargé : {len(historical)} matchs")
    except:
        print("⚠️ Aucun historique trouvé, les H2H seront basés sur les matchs récents.")

    team_matches = build_team_history(historical)

    # 3. Charger l'existant pour conserver les données non modifiées
    existing_data = {"matches": [], "categories": {"simple": [], "pro": [], "vip": []}, "stats": {}, "bookmakers": []}
    existing_matches = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                loaded = json.load(f)
                existing_data = loaded
                existing_matches = {str(m.get("id", "")): m for m in loaded.get("matches", [])}
        except:
            pass

    matches = []
    categories = {"simple": [], "pro": [], "vip": []}
    total_processed = 0
    total_skipped = 0

    all_ids = set(existing_matches.keys()) | set(new_infos.keys())

    for gid in all_ids:
        total_processed += 1
        if gid not in new_infos:
            match = existing_matches.get(gid)
            if match:
                matches.append(match)
                cat = match.get("category", "simple")
                if cat in categories:
                    categories[cat].append(match)
            continue

        base = new_infos[gid]
        existing = existing_matches.get(gid, {})

        home_team = base.get("home_team", "")
        away_team = base.get("away_team", "")
        league = base.get("competition", "")

        # Filtre ligue
        if is_bad_league(league):
            print(f"⚠️ Match {home_team} vs {away_team} ignoré (ligue faible)")
            total_skipped += 1
            continue

        # Récupération des formes via V2 si possible
        home_form = None
        away_form = None
        tournament_id = base.get("competition_id")
        if tournament_id:
            season_id = get_current_season(tournament_id)
            if season_id:
                home_id = base.get("home_team_id")
                away_id = base.get("away_team_id")
                if home_id:
                    home_form = get_team_form_v2(home_id, tournament_id, season_id)
                if away_id:
                    away_form = get_team_form_v2(away_id, tournament_id, season_id)
        # Fallback sur la forme locale
        if not home_form or home_form.get("matches_used", 0) == 0:
            home_form = get_team_form(home_team, team_matches, last_games=5)
        if not away_form or away_form.get("matches_used", 0) == 0:
            away_form = get_team_form(away_team, team_matches, last_games=5)

        # Vérifier qu'on a au moins une forme
        if (not home_form or home_form.get("matches_used", 0) == 0) and (not away_form or away_form.get("matches_used", 0) == 0):
            print(f"⚠️ Match {home_team} vs {away_team} ignoré (forme insuffisante)")
            total_skipped += 1
            continue

        # H2H
        h2h_list = get_h2h_v2(gid) if gid.isdigit() else []
        if len(h2h_list) >= 2:
            analysis = analyze_h2h(h2h_list, home_team, away_team)
        else:
            # Fallback Poisson basé sur la forme
            gf_h = home_form.get("goals_for", 1.2) if home_form else 1.2
            ga_h = home_form.get("goals_against", 1.2) if home_form else 1.2
            gf_a = away_form.get("goals_for", 1.2) if away_form else 1.2
            ga_a = away_form.get("goals_against", 1.2) if away_form else 1.2
            lambda_home = (gf_h * 1.1 + ga_a * 0.9) / 2
            lambda_away = (gf_a * 0.9 + ga_h * 1.1) / 2
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

        # Filtre draw_rate (downgrade au lieu de skip)
        if analysis.get("draw_rate", 0) > 0.45:
            print(f"⚠️ Match {home_team} vs {away_team} draw_rate élevé -> baisse confiance")
            # On continue mais on réduira la confiance plus tard

        # Différence de domination
        dom_diff = abs(analysis.get("home_dominance", 0) - analysis.get("away_dominance", 0))
        if dom_diff < 0.15:
            print(f"⚠️ Match {home_team} vs {away_team} trop équilibré -> baisse confiance")
            # On continue, la confiance sera ajustée

        prediction = generate_prediction(analysis, home_form, away_form, league)
        if prediction.get("double_chance") == "12":
            print(f"   ⚠️ Pronostic 12 (match équilibré) ignoré")
            total_skipped += 1
            continue

        # Ajustement confiance pour draw_rate élevé
        if analysis.get("draw_rate", 0) > 0.45:
            prediction["confidence"] = max(0, prediction["confidence"] - 10)

        # Seuil confiance
        if prediction.get("confidence", 0) < CONFIDENCE_THRESHOLD:
            print(f"⚠️ Match {home_team} vs {away_team} ignoré (confiance insuffisante)")
            total_skipped += 1
            continue

        # Filtre sur les cotes (value bet amélioré)
        odds = base.get("odds")
        value_bet = False
        if odds:
            dc = prediction.get("double_chance", "")
            home_dom = analysis.get("home_dominance", 0) + HOME_ADVANTAGE
            away_dom = analysis.get("away_dominance", 0)
            draw_rate = analysis.get("draw_rate", 0)
            if dc == "1X":
                our_prob = (home_dom * 0.6) + (draw_rate * 0.4)
                if home_form and away_form:
                    form_diff = home_form.get("form_score", 0) - away_form.get("form_score", 0)
                    our_prob += max(0, form_diff * 0.2)
            elif dc == "X2":
                our_prob = (away_dom * 0.6) + (draw_rate * 0.4)
                if home_form and away_form:
                    form_diff = home_form.get("form_score", 0) - away_form.get("form_score", 0)
                    our_prob += max(0, -form_diff * 0.2)
            else:
                our_prob = 0
            our_prob = min(our_prob, 0.95)
            dc_odds = estimate_dc_odds(odds, dc)
            if dc_odds > 0:
                book_prob = 1 / dc_odds
                edge = our_prob - book_prob
                if edge > 0.03:
                    value_bet = True
                elif edge > 0:
                    value_bet = "weak"
                else:
                    value_bet = False

        # Score xPronos
        score = calculate_xpronos_score(analysis, home_form, away_form, league)
        category = get_category(score)
        badge = get_badge(score)

        if score < XPRONOS_THRESHOLD:
            print(f"⚠️ Match {home_team} vs {away_team} ignoré (score xPronos {score})")
            total_skipped += 1
            continue

        # Mise à jour des champs avancés
        elo_home = 1500 + int((home_form.get("form_score", 0) * 200) if home_form else 0)
        elo_away = 1500 + int((away_form.get("form_score", 0) * 200) if away_form else 0)

        # xG simplifié
        if home_form and away_form:
            xg_home = (home_form.get("goals_for", 1.2) * 1.1 + away_form.get("goals_against", 1.2) * 0.9) / 2
            xg_away = (away_form.get("goals_for", 1.2) * 0.9 + home_form.get("goals_against", 1.2) * 1.1) / 2
        else:
            xg_home = xg_away = 1.2

        fatigue_home = home_form.get("matches_used", 0) if home_form else 0
        fatigue_away = away_form.get("matches_used", 0) if away_form else 0

        # Ensemble probabilities avec poids dynamiques
        h2h_h = analysis.get("home_dominance", 0)
        h2h_a = analysis.get("away_dominance", 0)
        h2h_d = analysis.get("draw_rate", 0)
        poisson_h, poisson_d, poisson_a = poisson_probability(xg_home, xg_away) if home_form and away_form else (0.33,0.34,0.33)
        form_h = home_form.get("form_score", 0.5) if home_form else 0.5
        form_a = away_form.get("form_score", 0.5) if away_form else 0.5
        form_sum = form_h + form_a
        if form_sum > 0:
            form_h_norm = form_h / form_sum
            form_a_norm = form_a / form_sum
        else:
            form_h_norm = form_a_norm = 0.5
        form_d_norm = 1 - form_h_norm - form_a_norm
        if form_d_norm < 0:
            form_d_norm = 0
            total = form_h_norm + form_a_norm
            if total > 0:
                form_h_norm /= total
                form_a_norm /= total

        w_h2h, w_poi, w_form = dynamic_weights(analysis.get("total_matches", 0))
        ensemble_h = h2h_h * w_h2h + poisson_h * w_poi + form_h_norm * w_form
        ensemble_d = h2h_d * w_h2h + poisson_d * w_poi + form_d_norm * w_form
        ensemble_a = h2h_a * w_h2h + poisson_a * w_poi + form_a_norm * w_form
        total_ens = ensemble_h + ensemble_d + ensemble_a
        if total_ens < 0.0001:
            ensemble_h, ensemble_d, ensemble_a = 0.33, 0.34, 0.33
        else:
            ensemble_h /= total_ens
            ensemble_d /= total_ens
            ensemble_a /= total_ens

        dc = prediction.get("double_chance", "")
        if dc == "1X":
            ensemble_prob_dc = ensemble_h + ensemble_d
        elif dc == "X2":
            ensemble_prob_dc = ensemble_d + ensemble_a
        else:
            ensemble_prob_dc = ensemble_h + ensemble_a

        # Détection de suspicion
        suspicion_score = 0
        # (pas de votes publics ici, mais on peut ajouter plus tard)
        if odds:
            # Écart modèle vs bookmaker
            book_probs = normalize_odds(odds)
            if book_probs:
                book_prob = book_probs["home"] if dc == "1X" else (book_probs["draw"] + book_probs["away"]) if dc == "X2" else (book_probs["home"] + book_probs["away"])
                if abs(ensemble_prob_dc - book_prob) > 0.25:
                    suspicion_score += 25
        if dom_diff < 0.1 and odds:
            suspicion_score += 15
        trap_detected = suspicion_score > 40

        # Score AI enrichi
        ai_score = (
            score * 0.25 +
            prediction.get("confidence", 0) * 0.25 +
            (ensemble_prob_dc * 100) * 0.2 +
            (10 if value_bet and value_bet != "weak" else 0) +
            (-10 if trap_detected else 0)
        )
        ai_score = max(0, min(100, ai_score))

        # Score final "bettable"
        bet_score = (
            score * 0.4 +
            (ensemble_prob_dc * 100) * 0.3 +
            (10 if value_bet and value_bet != "weak" else 0) -
            (10 if trap_detected else 0)
        )
        if bet_score < BET_SCORE_THRESHOLD:
            print(f"⚠️ Match {home_team} vs {away_team} ignoré (bet_score {bet_score:.1f} < {BET_SCORE_THRESHOLD})")
            total_skipped += 1
            continue

        final_score = (
            score * 0.35 +
            prediction.get("confidence", 0) * 0.25 +
            ai_score * 0.25 +
            (10 if value_bet and value_bet != "weak" else 0) * 0.15
        )

        # Valeur par défaut pour odds
        if not odds:
            odds = {"home": 1.85, "draw": 3.4, "away": 3.6}  # fallback

        match = {
            "id": gid,
            "date": base.get("date", ""),
            "event_date": base.get("start_time", ""),
            "home_team": home_team,
            "away_team": away_team,
            "home_logo": None,  # à implémenter via V2 /api/teams/{id}/image
            "away_logo": None,
            "league": league,
            "league_logo": None,
            "venue": "",
            "status": base.get("status", ""),
            "home_score": base.get("home_score"),
            "away_score": base.get("away_score"),
            "h2h_analysis": analysis,
            "home_form": home_form,
            "away_form": away_form,
            "poisson_probs": {
                "home": poisson_h,
                "draw": poisson_d,
                "away": poisson_a
            },
            "prediction": {
                "double_chance": dc,
                "confidence": prediction.get("confidence"),
                "odds": estimate_dc_odds(odds, dc) if odds else 1.4
            },
            "xpronos_score": score,
            "badge": badge,
            "category": category,
            "verified_double": False,
            "verified_btts": False,
            "verified_over": False,
            "odds": odds,
            "public_votes": None,
            "value_bet": value_bet,
            "is_finished": base.get("is_finished", False),
            "final_score": round(final_score, 1),
            "ai_score": round(ai_score, 1),
            "elo_home": elo_home,
            "elo_away": elo_away,
            "xg_home": round(xg_home, 2),
            "xg_away": round(xg_away, 2),
            "fatigue_home": fatigue_home,
            "fatigue_away": fatigue_away,
            "trap_detected": trap_detected,
            "ensemble_prob_home": round(ensemble_h, 3),
            "ensemble_prob_draw": round(ensemble_d, 3),
            "ensemble_prob_away": round(ensemble_a, 3),
            "ensemble_prob_dc": round(ensemble_prob_dc, 3),
            "bet_score": round(bet_score, 1),
            "suspicion_score": suspicion_score
        }

        # Vérifier si le match est terminé pour mettre à jour verified_double
        if base.get("is_finished") and base.get("home_score") is not None and base.get("away_score") is not None:
            dc = prediction.get("double_chance", "")
            if dc == "1X":
                match["verified_double"] = (base["home_score"] > base["away_score"]) or (base["home_score"] == base["away_score"])
            elif dc == "X2":
                match["verified_double"] = (base["home_score"] == base["away_score"]) or (base["home_score"] < base["away_score"])

        matches.append(match)
        categories[category].append(match)

    # Tri par bet_score décroissant
    matches.sort(key=lambda x: x.get("bet_score", 0), reverse=True)

    # Calcul ROI
    total_bets = 0
    total_wins = 0
    total_stake = 0.0
    total_return = 0.0
    for m in matches:
        if m.get("verified_double"):
            total_wins += 1
            odds_value = m.get("prediction", {}).get("odds", 2.0)
            total_return += odds_value
        if m.get("is_finished"):
            total_bets += 1
            total_stake += 1.0
    roi = safe_division((total_return - total_stake), total_stake, 0) * 100

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

    print(f"\n💾 {DATA_FILE} généré avec succès")
    print(f"📊 Matchs traités: {total_processed}, ignorés: {total_skipped}")
    print(f"📈 Catégories : Simple: {len(categories['simple'])}, Pro: {len(categories['pro'])}, VIP: {len(categories['vip'])}")
    print(f"💰 ROI estimé : {stats['roi']}% sur {stats['total_bets']} matchs terminés")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interruption par l'utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()