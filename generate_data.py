#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_data_optimized.py - Moteur de pronostics football (double chance)
Version ultra-optimisée avec logos désactivés (placeholders) pour éviter les erreurs 500.
"""

import os
import json
import random
import time
from datetime import datetime, timedelta
from math import exp, factorial
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# =======================================================
# CONFIGURATION
# =======================================================
SPORTDATA_URL = "https://v1.football.sportsapipro.com/games/allscores"
PREDICTIONS_URL = "https://v1.football.sportsapipro.com/games/predictions"

today = datetime.now().date()
tomorrow = today + timedelta(days=1)
yesterday = today - timedelta(days=1)

DATA_FILE = "data.json"
CACHE_DIR = "cache"
GLOBAL_CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")
PREDICTION_CACHE_FILE = os.path.join(CACHE_DIR, "predictions_cache.json")
LOGOS_DIR = "assets/images/logos"
COMPETITION_LOGOS_DIR = os.path.join(LOGOS_DIR, "competitions")

# Création des répertoires (nécessaires pour les fichiers de cache)
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(LOGOS_DIR, exist_ok=True)
os.makedirs(COMPETITION_LOGOS_DIR, exist_ok=True)

# Désactiver le téléchargement des logos pour gagner du temps (évite les erreurs 500)
LOGOS_ENABLED = False   # ← Mettre à True si vous voulez réactiver plus tard

HOME_ADVANTAGE = 0.1
CONFIDENCE_THRESHOLD = 50
GOAL_DIFF_THRESHOLD = 0.1
XPRONOS_THRESHOLD = 35
DOMINANCE_THRESHOLD = 0.4

# Liste des ligues à ignorer
BAD_LEAGUES = [
    "friendly", "u21", "u19", "women", "reserve", "youth", "amateur"
]

# DEBUG : désactiver les logs pour la vitesse
DEBUG = False

def log(msg):
    if DEBUG:
        print(msg)

# =======================================================
# FONCTIONS UTILITAIRES
# =======================================================
def safe_division(numerator, denominator, default=0.0):
    return numerator / denominator if denominator else default

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
    except Exception:
        return None

def get_now_naive():
    return datetime.now()

# =======================================================
# GESTION DE L'API (avec fallback et rotation de clés)
# =======================================================
try:
    from api_utils import make_request
except ImportError:
    def make_request(method, url, **kwargs):
        if method.upper() == 'GET':
            return requests.get(url, **kwargs)
        elif method.upper() == 'POST':
            return requests.post(url, **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")

# =======================================================
# FONCTIONS LOGOS (simulées si désactivées)
# =======================================================
def download_logo(competitor_id, image_version=None, max_retries=1):
    if not LOGOS_ENABLED:
        return None
    # Implémentation réelle si nécessaire (à garder mais non exécutée)
    return None

def download_competition_logo(competition_id, image_version=None, max_retries=1):
    if not LOGOS_ENABLED:
        return None
    return None

def download_logos_batch(competitors, comps):
    if not LOGOS_ENABLED:
        return {}
    # Version parallèle désactivée
    return {}

# =======================================================
# RÉCUPÉRATION DES PRÉDICTIONS (votes publics) EN PARALLÈLE
# =======================================================
def fetch_predictions(game_id: str) -> Optional[dict]:
    if not game_id:
        return None
    params = {"gameId": game_id}
    try:
        resp = make_request('GET', PREDICTIONS_URL, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            games = data.get("games", [])
            if games and isinstance(games, list):
                game_data = games[0]
                if isinstance(game_data, dict):
                    promoted = game_data.get("promotedPredictions", {})
                    predictions = promoted.get("predictions", [])
                    for pred in predictions:
                        if pred.get("type") == 1:
                            return pred
    except Exception as e:
        log(f"Erreur prédictions {game_id}: {e}")
    return None

def fetch_predictions_batch(game_ids: List[str]) -> Dict[str, dict]:
    """Récupère les votes publics pour une liste de matchs en parallèle."""
    cache = {}
    if os.path.exists(PREDICTION_CACHE_FILE):
        try:
            with open(PREDICTION_CACHE_FILE, 'r') as f:
                cache = json.load(f)
        except:
            pass

    results = {}
    missing = [gid for gid in game_ids if gid not in cache]

    def task(gid):
        return gid, fetch_predictions(gid)

    # Réduire le parallélisme pour ne pas surcharger l'API
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(task, gid) for gid in missing]
        for future in as_completed(futures):
            gid, pred = future.result()
            if pred:
                results[gid] = pred
                cache[gid] = pred

    with open(PREDICTION_CACHE_FILE, 'w') as f:
        json.dump(cache, f)

    for gid, pred in cache.items():
        if gid in game_ids:
            results[gid] = pred
    return results

# =======================================================
# RÉCUPÉRATION DES MATCHS (V1)
# =======================================================
def fetch_games_with_comps(date_from: datetime, date_to: datetime,
                           max_retries=3) -> Tuple[List[dict], List[dict]]:
    params = {
        "startDate": date_from.strftime("%d/%m/%Y"),
        "endDate": date_to.strftime("%d/%m/%Y"),
        "sports": 1,
        "showOdds": "true",
        "onlyMajorGames": "false"
    }
    for attempt in range(max_retries):
        try:
            resp = make_request('GET', SPORTDATA_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data.get("games", []), data.get("competitions", [])
        except Exception as e:
            log(f"Erreur API {date_from} (tent {attempt+1}): {e}")
            if attempt < max_retries-1:
                time.sleep(2)
    return [], []

def extract_game_info(game: dict, comp_image_map: dict) -> Optional[dict]:
    try:
        start_time = game.get("start_time") or game.get("startTime", "")
        competition = game.get("competitionDisplayName", "")
        competition_id = game.get("competitionId")
        comp_img_ver = comp_image_map.get(competition_id) if competition_id else None

        home = game.get("homeCompetitor", {}) or {}
        away = game.get("awayCompetitor", {}) or {}
        home_score = home.get("score")
        away_score = away.get("score")
        if home_score == -1: home_score = None
        if away_score == -1: away_score = None

        odds_data = game.get("odds")
        odds = None
        if odds_data and isinstance(odds_data, dict):
            options = odds_data.get("options", [])
            if isinstance(options, list):
                cotes = {}
                for opt in options:
                    if isinstance(opt, dict):
                        num = opt.get("num")
                        rate = opt.get("rate", {}) or {}
                        decimal = rate.get("decimal")
                        if num == 1 and decimal:
                            cotes["home"] = float(decimal)
                        elif num == 2 and decimal:
                            cotes["draw"] = float(decimal)
                        elif num == 3 and decimal:
                            cotes["away"] = float(decimal)
                if cotes:
                    odds = cotes

        return {
            "id": str(game.get("id", "")),
            "start_time": start_time,
            "date": start_time[:10] if start_time else "",
            "home_team": str(home.get("name", "")),
            "away_team": str(away.get("name", "")),
            "home_competitor_id": str(home.get("id", "")) if home.get("id") else None,
            "away_competitor_id": str(away.get("id", "")) if away.get("id") else None,
            "home_image_version": home.get("imageVersion"),
            "away_image_version": away.get("imageVersion"),
            "competition": str(competition),
            "competition_id": str(competition_id) if competition_id else None,
            "competition_image_version": comp_img_ver,
            "home_score": home_score,
            "away_score": away_score,
            "status_group": game.get("statusGroup"),
            "status_text": game.get("statusText", ""),
            "is_finished": (game.get("statusGroup") == 4),
            "odds": odds
        }
    except Exception as e:
        log(f"Erreur extraction info match: {e}")
        return None

# =======================================================
# ANALYSE H2H ET FORME (basée sur historique local)
# =======================================================
def load_historical_matches() -> List[dict]:
    if not os.path.exists(GLOBAL_CACHE_FILE):
        log("⚠️ Fichier historique introuvable.")
        return []
    try:
        with open(GLOBAL_CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        log(f"Erreur chargement historique: {e}")
        return []

def build_team_history(historical: List[dict]) -> dict:
    team_matches = {}
    for m in historical:
        if not isinstance(m, dict): continue
        home = m.get("home_team", "")
        away = m.get("away_team", "")
        if not home or not away: continue
        date = parse_datetime_safe(m.get("start_time", ""))
        if not date: continue
        if home not in team_matches: team_matches[home] = []
        if away not in team_matches: team_matches[away] = []
        team_matches[home].append((date, m, "home"))
        team_matches[away].append((date, m, "away"))
    for team in team_matches:
        team_matches[team].sort(key=lambda x: x[0], reverse=True)
    return team_matches

def get_team_form(team: str, team_matches: dict, last_games=5, max_days=365) -> Optional[dict]:
    if not team or not team_matches.get(team):
        return None
    matches = team_matches[team]
    recent = []
    now = get_now_naive()
    for date, match, side in matches:
        if match.get("is_finished") and match.get("home_score") is not None:
            if (now - date).days <= max_days:
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

def get_h2h(historical: List[dict], home_team: str, away_team: str, years=2) -> List[dict]:
    if not historical or not home_team or not away_team:
        return []
    cutoff = (datetime.now() - timedelta(days=365*years)).date()
    h2h = []
    home_lower = home_team.lower()
    away_lower = away_team.lower()
    for m in historical:
        if not isinstance(m, dict): continue
        m_home = (m.get("home_team") or "").lower()
        m_away = (m.get("away_team") or "").lower()
        if (m_home == home_lower and m_away == away_lower) or (m_home == away_lower and m_away == home_lower):
            date = parse_datetime_safe(m.get("start_time", ""))
            if date and date.date() >= cutoff:
                h2h.append(m)
    h2h.sort(key=lambda x: x.get("start_time", ""), reverse=True)
    return h2h

def analyze_h2h(h2h_list: List[dict], current_home_team: str, current_away_team: str) -> dict:
    home_score = away_score = draws_score = 0.0
    matches_count = 0
    if not h2h_list or not current_home_team or not current_away_team:
        return {"total_matches":0,"home_wins":0,"away_wins":0,"draws":0,"home_dominance":0,"away_dominance":0,"draw_rate":0}
    current_home_lower = current_home_team.lower()
    for match in h2h_list:
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
    total = home_score + away_score + draws_score
    return {
        "total_matches": matches_count,
        "home_wins": round(home_score,2),
        "away_wins": round(away_score,2),
        "draws": round(draws_score,2),
        "home_dominance": safe_division(home_score, total, 0),
        "away_dominance": safe_division(away_score, total, 0),
        "draw_rate": safe_division(draws_score, total, 0)
    }

def weight_by_date(date_str: str) -> float:
    try:
        match_date = parse_datetime_safe(date_str)
        if not match_date: return 1.0
        days = (get_now_naive() - match_date).days
        if days < 180: return 1.5
        if days < 365: return 1.2
        return 1.0
    except: return 1.0

def competition_weight(comp: str) -> float:
    if not comp: return 1.0
    comp_lower = comp.lower()
    if "friendly" in comp_lower: return 0.5
    if "cup" in comp_lower or "playoff" in comp_lower: return 1.3
    return 1.0

def generate_prediction(analysis, home_form, away_form, league):
    home_dom = analysis.get("home_dominance", 0) + HOME_ADVANTAGE
    away_dom = analysis.get("away_dominance", 0)
    if home_dom > away_dom + DOMINANCE_THRESHOLD:
        double_chance = "1X"
    elif away_dom > home_dom + DOMINANCE_THRESHOLD:
        double_chance = "X2"
    else:
        double_chance = "12"
    confiance = 50 + min(20, analysis.get("total_matches", 0) * 3)
    if max(home_dom, away_dom) > 0.7:
        confiance += 10
    if home_form and away_form:
        if abs(home_form["form_score"] - away_form["form_score"]) > 0.2:
            confiance += 5
        if home_form["form_score"] > 0.7 and away_form["form_score"] < 0.4:
            confiance += 5
        if home_form["goals_for"] - away_form["goals_for"] > 0.8:
            confiance += 5
        if away_form["goals_against"] - home_form["goals_against"] > 0.8:
            confiance += 5
    if analysis.get("draw_rate", 0) > 0.4:
        confiance -= 10
    confiance = max(0, min(100, confiance))
    return {"double_chance": double_chance, "confidence": confiance}

def calculate_xpronos_score(analysis, home_form, away_form, league):
    score = 0
    score += min(40, analysis.get("total_matches", 0) * 6)
    dom = max(analysis.get("home_dominance", 0), analysis.get("away_dominance", 0))
    score += min(30, int(dom * 100 * 0.5))
    if home_form and away_form:
        score += min(20, int((home_form["form_score"] + away_form["form_score"]) * 10))
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
    if score >= 70: return "🏆 PREMIUM LOCK"
    if score >= 60: return "💎 VIP ELITE"
    if score >= 50: return "🔥 ULTRA SAFE"
    return ""

def is_bad_league(name: str) -> bool:
    if not name: return False
    name = name.lower()
    return any(b in name for b in BAD_LEAGUES)

# =======================================================
# MODÈLE POISSON ET VALUE BET
# =======================================================
def poisson_probability(lambda_home: float, lambda_away: float, max_goals=6):
    lambda_home = max(0.1, lambda_home)
    lambda_away = max(0.1, lambda_away)
    p_home = p_draw = p_away = 0.0
    try:
        for i in range(max_goals+1):
            for j in range(max_goals+1):
                prob = (exp(-lambda_home) * (lambda_home ** i) / factorial(i)) * \
                       (exp(-lambda_away) * (lambda_away ** j) / factorial(j))
                if i > j: p_home += prob
                elif i == j: p_draw += prob
                else: p_away += prob
    except:
        return 0.33, 0.34, 0.33
    total = p_home + p_draw + p_away
    if total > 0:
        return p_home/total, p_draw/total, p_away/total
    return 0.33, 0.34, 0.33

def normalize_odds(odds: dict) -> Optional[dict]:
    if not odds: return None
    home = odds.get("home")
    draw = odds.get("draw")
    away = odds.get("away")
    if not all([home, draw, away]): return None
    try:
        prob_h = 1/float(home)
        prob_d = 1/float(draw)
        prob_a = 1/float(away)
    except: return None
    total = prob_h + prob_d + prob_a
    if total == 0: return None
    return {"home": prob_h/total, "draw": prob_d/total, "away": prob_a/total}

def estimate_dc_odds(odds: dict, double_chance: str) -> float:
    probs = normalize_odds(odds)
    if not probs: return 0.0
    if double_chance == '1X':
        prob = probs["home"] + probs["draw"]
    elif double_chance == 'X2':
        prob = probs["draw"] + probs["away"]
    elif double_chance == '12':
        prob = probs["home"] + probs["away"]
    else:
        return 0.0
    return 1/prob if prob > 0 else 0.0

def estimate_odds(category: str, double_chance: str) -> float:
    odds_map = {
        "pro": {"1X": 1.35, "X2": 1.45, "12": 1.40},
        "simple": {"1X": 1.45, "X2": 1.60, "12": 1.50}
    }
    cat_odds = odds_map.get(category, odds_map["simple"])
    return cat_odds.get(double_chance, 1.40)

# =======================================================
# FONCTION PRINCIPALE
# =======================================================
def main():
    print("="*60)
    print(f"🚀 GÉNÉRATION DES PRONOSTICS (OPTIMISÉ) - {today}")
    print("="*60)

    # 1. Charger les données existantes
    existing_data = {"matches": [], "categories": {"simple": [], "pro": [], "vip": []}, "stats": {}, "bookmakers": []}
    existing_matches = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    existing_data = loaded
                    existing_matches = {str(m.get("id", "")): m for m in loaded.get("matches", []) if isinstance(m, dict)}
        except Exception as e:
            print(f"❌ Erreur chargement fichier existant: {e}")

    # 2. Récupérer les matchs via API
    print("\n📅 Récupération des matchs via SportData...")
    games_today, comps_today = fetch_games_with_comps(today, today)
    games_tomorrow, comps_tomorrow = fetch_games_with_comps(tomorrow, tomorrow)
    games_yesterday, comps_yesterday = fetch_games_with_comps(yesterday, yesterday)

    all_new_games = games_today + games_tomorrow + games_yesterday
    # Construire le mapping des compétitions (pour les logos)
    all_comps = {}
    for comp in comps_today + comps_tomorrow + comps_yesterday:
        if isinstance(comp, dict) and comp.get("id"):
            all_comps[comp["id"]] = comp
    comp_image_map = {str(comp_id): comp.get("imageVersion") for comp_id, comp in all_comps.items()}
    print(f"✅ {len(all_new_games)} matchs récupérés, {len(all_comps)} compétitions uniques")

    # 3. Construire les infos de base des matchs
    new_infos = {}
    for g in all_new_games:
        if isinstance(g, dict):
            info = extract_game_info(g, comp_image_map)
            if info and info.get("id"):
                new_infos[info["id"]] = info

    # 4. Préparer les listes pour parallélisation
    all_ids = set(existing_matches.keys()) | set(new_infos.keys())
    all_ids_list = list(all_ids)

    # 5. Récupérer les votes publics en parallèle (uniquement pour les matchs pro/vip)
    print("📊 Récupération des votes publics en parallèle...")
    predictions_map = fetch_predictions_batch(all_ids_list)
    print(f"✅ Votes récupérés: {len(predictions_map)}")

    # 6. Charger l'historique H2H et construire la forme des équipes
    print("📂 Chargement de l'historique H2H...")
    historical = load_historical_matches()
    team_matches = build_team_history(historical)
    print(f"📊 Statistiques de forme pour {len(team_matches)} équipes")

    # 7. Traiter chaque match séquentiellement (calculs CPU)
    matches = []
    categories = {"simple": [], "pro": [], "vip": []}
    total_processed = 0
    total_skipped = 0

    for gid in all_ids_list:
        total_processed += 1
        if gid not in new_infos:
            match = existing_matches.get(gid)
            if match:
                matches.append(match)
                cat = match.get("category", "simple")
                categories[cat].append(match)
            continue

        base = new_infos[gid]
        existing = existing_matches.get(gid, {})

        # Fusion scores
        home_score = base.get("home_score") or existing.get("home_score")
        away_score = base.get("away_score") or existing.get("away_score")
        status = base.get("status_text") or existing.get("status", "")

        if is_bad_league(base.get("competition", "")):
            log(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (ligue faible)")
            total_skipped += 1
            continue

        home_team = base["home_team"]
        away_team = base["away_team"]

        home_form = get_team_form(home_team, team_matches) if home_team else None
        away_form = get_team_form(away_team, team_matches) if away_team else None

        if not home_form and not away_form:
            log(f"⚠️ Match {home_team} vs {away_team} ignoré (forme insuffisante)")
            total_skipped += 1
            continue

        h2h_list = get_h2h(historical, home_team, away_team, years=2)
        if len(h2h_list) >= 2:
            analysis = analyze_h2h(h2h_list, home_team, away_team)
        else:
            # Fallback Poisson
            if home_form and away_form:
                gf_h = home_form["goals_for"]
                ga_h = home_form["goals_against"]
                gf_a = away_form["goals_for"]
                ga_a = away_form["goals_against"]
                lh = (gf_h * 1.1 + ga_a * 0.9) / 2
                la = (gf_a * 0.9 + ga_h * 1.1) / 2
                ph, pd, pa = poisson_probability(lh, la)
                analysis = {
                    "total_matches": 0, "home_wins": 0, "away_wins": 0, "draws": 0,
                    "home_dominance": ph, "away_dominance": pa, "draw_rate": pd
                }
            else:
                log(f"⚠️ Match {home_team} vs {away_team} ignoré (H2H et forme insuffisants)")
                total_skipped += 1
                continue

        if analysis.get("draw_rate", 0) > 0.45:
            log(f"⚠️ Match {home_team} vs {away_team} ignoré (draw_rate > 0.45)")
            total_skipped += 1
            continue

        dom_diff = abs(analysis["home_dominance"] - analysis["away_dominance"])
        if dom_diff < 0.15:
            log(f"⚠️ Match {home_team} vs {away_team} ignoré (trop équilibré)")
            total_skipped += 1
            continue

        prediction = generate_prediction(analysis, home_form, away_form, base.get("competition", ""))
        if prediction["double_chance"] == "12":
            log(f"⚠️ Pronostic 12 ignoré")
            total_skipped += 1
            continue

        if prediction["confidence"] < CONFIDENCE_THRESHOLD:
            log(f"⚠️ Confiance insuffisante")
            total_skipped += 1
            continue

        if home_form and away_form and abs(home_form["goals_for"] - away_form["goals_for"]) < GOAL_DIFF_THRESHOLD:
            log(f"⚠️ Différence buts trop faible")
            total_skipped += 1
            continue

        # Filtre temporel
        try:
            match_time = parse_datetime_safe(base.get("start_time", ""))
            if match_time:
                now = get_now_naive()
                if 0 < (match_time - now).total_seconds() < 1800:
                    log(f"⚠️ Match trop proche")
                    total_skipped += 1
                    continue
        except:
            pass

        odds = base.get("odds")
        if odds and isinstance(odds, dict):
            home_odd = odds.get("home")
            away_odd = odds.get("away")
            if home_odd and away_odd and abs(home_odd - away_odd) > 3:
                log(f"⚠️ Écart de cotes trop grand")
                total_skipped += 1
                continue
            dc = prediction["double_chance"]
            if dc == "1X" and home_odd and home_odd < 1.20:
                log(f"⚠️ Cote home trop faible pour 1X")
                total_skipped += 1
                continue
            if dc == "X2" and away_odd and away_odd < 1.20:
                log(f"⚠️ Cote away trop faible pour X2")
                total_skipped += 1
                continue

        score = calculate_xpronos_score(analysis, home_form, away_form, base.get("competition", ""))
        category = get_category(score)
        badge = get_badge(score)

        if score < XPRONOS_THRESHOLD:
            log(f"⚠️ Score xPronos trop faible")
            total_skipped += 1
            continue

        # Logos : placeholders si LOGOS_ENABLED est False
        if LOGOS_ENABLED:
            home_logo = download_logo(base.get("home_competitor_id"), base.get("home_image_version"))
            away_logo = download_logo(base.get("away_competitor_id"), base.get("away_image_version"))
            league_logo = download_competition_logo(base.get("competition_id"), base.get("competition_image_version"))
        else:
            home_logo = None
            away_logo = None
            league_logo = None

        # Votes publics
        public_votes = None
        if category in ["pro", "vip"]:
            pred = predictions_map.get(gid)
            if pred and isinstance(pred, dict):
                options = pred.get("options", [])
                if isinstance(options, list):
                    vote_dict = {}
                    for opt in options:
                        if isinstance(opt, dict):
                            num = opt.get("num")
                            perc = opt.get("vote", {}).get("percentage")
                            if num == 1:
                                vote_dict["home"] = perc
                            elif num == 2:
                                vote_dict["draw"] = perc
                            elif num == 3:
                                vote_dict["away"] = perc
                    if vote_dict:
                        public_votes = vote_dict

        # Value bet
        value_bet = False
        if odds and isinstance(odds, dict):
            dc = prediction["double_chance"]
            home_dom = analysis["home_dominance"] + HOME_ADVANTAGE
            away_dom = analysis["away_dominance"]
            draw_rate = analysis["draw_rate"]
            if dc == "1X":
                our_prob = home_dom * 0.6 + draw_rate * 0.4
                if home_form and away_form:
                    our_prob += max(0, (home_form["form_score"] - away_form["form_score"]) * 0.2)
            elif dc == "X2":
                our_prob = away_dom * 0.6 + draw_rate * 0.4
                if home_form and away_form:
                    our_prob += max(0, -(home_form["form_score"] - away_form["form_score"]) * 0.2)
            else:
                our_prob = home_dom + away_dom
            our_prob = min(our_prob, 0.95)
            dc_odds = estimate_dc_odds(odds, dc)
            if dc_odds > 0 and our_prob > 1/dc_odds + 0.05:
                value_bet = True

        # Métriques avancées
        elo_base = 1500
        elo_home = elo_base + (home_form["form_score"] * 200 if home_form else 0)
        elo_away = elo_base + (away_form["form_score"] * 200 if away_form else 0)
        if home_form and away_form:
            gf_h = home_form["goals_for"]
            ga_h = home_form["goals_against"]
            gf_a = away_form["goals_for"]
            ga_a = away_form["goals_against"]
            xg_home = (gf_h * 1.1 + ga_a * 0.9) / 2
            xg_away = (gf_a * 0.9 + ga_h * 1.1) / 2
        else:
            xg_home = xg_away = 1.2
        fatigue_home = home_form["matches_used"] if home_form else 0
        fatigue_away = away_form["matches_used"] if away_form else 0

        trap_detected = False
        if public_votes and odds:
            dc = prediction["double_chance"]
            votes_home = public_votes.get("home", 0) or 0
            votes_draw = public_votes.get("draw", 0) or 0
            votes_away = public_votes.get("away", 0) or 0
            if (votes_home > 75 and dc != "1X") or (votes_draw > 75 and dc != "X2") or (votes_away > 75 and dc != "12"):
                trap_detected = True
            home_odd = odds.get("home")
            away_odd = odds.get("away")
            if votes_home > 75 and home_odd and home_odd > 2:
                trap_detected = True
            if votes_away > 75 and away_odd and away_odd > 2:
                trap_detected = True

        # Score AI
        elo_diff = (elo_home - elo_away) / 200.0
        conf = prediction["confidence"]
        ai_score = score * 0.4 + conf * 0.3 + max(0, min(100, elo_diff * 50))
        ai_score = max(0, min(100, ai_score))

        # Modèle ensemble
        poisson_h = poisson_d = poisson_a = 0.33
        if home_form and away_form:
            gf_h = home_form["goals_for"]
            ga_h = home_form["goals_against"]
            gf_a = away_form["goals_for"]
            ga_a = away_form["goals_against"]
            lh = (gf_h * 1.1 + ga_a * 0.9) / 2
            la = (gf_a * 0.9 + ga_h * 1.1) / 2
            poisson_h, poisson_d, poisson_a = poisson_probability(lh, la)
        h2h_h = analysis["home_dominance"]
        h2h_d = analysis["draw_rate"]
        h2h_a = analysis["away_dominance"]
        form_h = home_form["form_score"] if home_form else 0.5
        form_a = away_form["form_score"] if away_form else 0.5
        form_sum = form_h + form_a
        if form_sum > 0:
            form_h_norm = form_h / form_sum
            form_a_norm = form_a / form_sum
        else:
            form_h_norm = form_a_norm = 0.5
        form_d_norm = 1 - form_h_norm - form_a_norm
        if form_d_norm < 0:
            form_d_norm = 0
            total_norm = form_h_norm + form_a_norm
            if total_norm > 0:
                form_h_norm /= total_norm
                form_a_norm /= total_norm
        ensemble_h = (h2h_h * 0.4 + poisson_h * 0.3 + form_h_norm * 0.3)
        ensemble_d = (h2h_d * 0.4 + poisson_d * 0.3 + form_d_norm * 0.3)
        ensemble_a = (h2h_a * 0.4 + poisson_a * 0.3 + form_a_norm * 0.3)
        total_ens = ensemble_h + ensemble_d + ensemble_a
        if total_ens > 0:
            ensemble_h /= total_ens
            ensemble_d /= total_ens
            ensemble_a /= total_ens
        else:
            ensemble_h = ensemble_d = ensemble_a = 0.33
        dc = prediction["double_chance"]
        if dc == "1X":
            ensemble_prob_dc = ensemble_h + ensemble_d
        elif dc == "X2":
            ensemble_prob_dc = ensemble_d + ensemble_a
        else:
            ensemble_prob_dc = ensemble_h + ensemble_a

        # Final prediction
        final_prediction = {
            "double_chance": dc,
            "confidence": conf,
            "odds": estimate_odds(category, dc)
        }

        value_bet_bonus = 10 if value_bet else 0
        final_score = score * 0.35 + conf * 0.25 + ai_score * 0.25 + value_bet_bonus * 0.15

        poisson_probs = None
        if home_form and away_form:
            gf_h = home_form["goals_for"]
            ga_h = home_form["goals_against"]
            gf_a = away_form["goals_for"]
            ga_a = away_form["goals_against"]
            lh = (gf_h * 1.1 + ga_a * 0.9) / 2
            la = (gf_a * 0.9 + ga_h * 1.1) / 2
            ph, pd, pa = poisson_probability(lh, la)
            poisson_probs = {"home": round(ph,3), "draw": round(pd,3), "away": round(pa,3)}

        match = {
            "id": gid,
            "date": base.get("date", ""),
            "event_date": base.get("start_time", ""),
            "home_team": home_team,
            "away_team": away_team,
            "home_logo": home_logo,
            "away_logo": away_logo,
            "league": base.get("competition", ""),
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
            "ensemble_prob_dc": round(ensemble_prob_dc, 3)
        }

        if base.get("is_finished") and home_score is not None and away_score is not None:
            if prediction["double_chance"] == "1X":
                match["verified_double"] = (home_score > away_score) or (home_score == away_score)
            elif prediction["double_chance"] == "X2":
                match["verified_double"] = (home_score == away_score) or (home_score < away_score)

        matches.append(match)
        categories[category].append(match)

    # Tri par score final
    matches.sort(key=lambda x: x.get("final_score", 0), reverse=True)

    # Calcul ROI
    total_bets = 0
    total_wins = 0
    total_stake = 0.0
    total_return = 0.0
    for m in matches:
        if m.get("verified_double"):
            total_wins += 1
            match_odds = m.get("odds")
            if match_odds:
                dc = m.get("prediction", {}).get("double_chance", "")
                dc_odds = estimate_dc_odds(match_odds, dc)
                if dc_odds > 0:
                    odds_val = dc_odds
                else:
                    odds_val = m.get("prediction", {}).get("odds", 2.0)
            else:
                odds_val = m.get("prediction", {}).get("odds", 2.0)
            total_return += odds_val
        if m.get("is_finished"):
            total_bets += 1
            total_stake += 1.0
    roi = safe_division((total_return - total_stake), total_stake, 0) * 100
    stats = {"total_bets": total_bets, "wins": total_wins, "roi": round(roi, 1)}

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
        "bookmakers": existing_data.get("bookmakers", default_bookmakers) if isinstance(existing_data, dict) else default_bookmakers
    }

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 {DATA_FILE} généré avec succès")
    except Exception as e:
        print(f"❌ Erreur sauvegarde: {e}")
        return

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