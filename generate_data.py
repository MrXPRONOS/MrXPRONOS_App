#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_data.py - Moteur de pronostics football (double chance 1X/X2)
Intègre H2H, forme, Poisson, Elo simplifié, xG estimés, fatigue,
piège bookmaker, value bet et score AI.
Version corrigée, robuste et optimisée.
"""

import os
import json
import time
from datetime import datetime, timedelta, timezone
from math import exp, factorial
from typing import Dict, List, Optional, Tuple, Any

try:
    from api_utils import make_request
except ImportError:
    import requests

    def make_request(method: str, url: str, **kwargs):
        if method.upper() == "GET":
            return requests.get(url, **kwargs)
        elif method.upper() == "POST":
            return requests.post(url, **kwargs)
        raise ValueError(f"Unsupported method: {method}")


# =======================================================
# CONFIGURATION GÉNÉRALE
# =======================================================
SPORTDATA_URL = "https://v1.football.sportsapipro.com/games/allscores"
PREDICTIONS_URL = "https://v1.football.sportsapipro.com/games/predictions"

UTC = timezone.utc
today = datetime.now(UTC).date()
tomorrow = today + timedelta(days=1)
yesterday = today - timedelta(days=1)

DATA_FILE = "data.json"
CACHE_DIR = "cache"
GLOBAL_CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")
LOGOS_DIR = "assets/images/logos"
COMPETITION_LOGOS_DIR = os.path.join(LOGOS_DIR, "competitions")

HOME_ADVANTAGE = 0.1
CONFIDENCE_THRESHOLD = 50
GOAL_DIFF_THRESHOLD = 0.1
XPRONOS_THRESHOLD = 35
DOMINANCE_THRESHOLD = 0.4

DRAW_RATE_MAX = 0.45
DOM_DIFF_MIN = 0.15
MATCH_TOO_CLOSE_SECONDS = 1800

DOWNLOAD_LOGOS = os.environ.get("DOWNLOAD_LOGOS", "true").lower() == "true"

BAD_LEAGUES = [
    "friendly",
    "u21",
    "u19",
    "women",
    "reserve",
    "youth",
    "amateur",
]

FAILED_LOGO_IDS = set()
FAILED_COMP_LOGO_IDS = set()

try:
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(LOGOS_DIR, exist_ok=True)
    os.makedirs(COMPETITION_LOGOS_DIR, exist_ok=True)
except OSError as e:
    print(f"❌ Erreur création répertoires: {e}")
    raise

print("=" * 60)
print(f"🚀 GÉNÉRATION DES PRONOSTICS (DOUBLE CHANCE UNIQUEMENT) - {today}")
print("=" * 60)


# =======================================================
# FONCTIONS UTILITAIRES
# =======================================================

def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def safe_division(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator in (0, None):
        return default
    return numerator / denominator


def to_float_safe(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return default


def normalize_score(value: Any) -> Optional[int]:
    if value in (None, "", -1, "-1"):
        return None
    try:
        score = int(value)
        return None if score == -1 else score
    except (ValueError, TypeError):
        return None


def is_bad_league(name: str) -> bool:
    if not name:
        return False
    name = name.lower()
    return any(b in name for b in BAD_LEAGUES)


def parse_datetime_safe(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        s = str(date_str).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except (ValueError, TypeError, AttributeError) as e:
        print(f"⚠️ Erreur parsing date {date_str}: {e}")
        return None


def get_now_utc() -> datetime:
    return datetime.now(UTC)


# =======================================================
# FONCTIONS DE TÉLÉCHARGEMENT DES LOGOS
# =======================================================

def get_competitor_logo_url(competitor_id: str, image_version: Optional[str] = None) -> str:
    base_url = "https://v1.football.sportsapipro.com/images/competitors"
    if image_version:
        return f"{base_url}/{competitor_id}?imageVersion={image_version}"
    return f"{base_url}/{competitor_id}"


def get_competition_logo_url(competition_id: str, image_version: Optional[str] = None) -> str:
    base_url = "https://v1.football.sportsapipro.com/images/competitions"
    if image_version:
        return f"{base_url}/{competition_id}?imageVersion={image_version}"
    return f"{base_url}/{competition_id}"


def download_logo(competitor_id: Optional[str], image_version: Optional[str] = None) -> Optional[str]:
    if not DOWNLOAD_LOGOS:
        return None

    if not competitor_id:
        return None

    if competitor_id in FAILED_LOGO_IDS:
        return None

    filename = f"competitor_{competitor_id}.png"
    filepath = os.path.join(LOGOS_DIR, filename)
    rel_path = f"assets/images/logos/{filename}"

    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return rel_path

    url = get_competitor_logo_url(competitor_id, image_version)

    try:
        resp = make_request("GET", url, timeout=10, max_retries=1)

        if resp is None:
            FAILED_LOGO_IDS.add(competitor_id)
            return None

        if resp.status_code == 200 and len(resp.content) > 0:
            with open(filepath, "wb") as f:
                f.write(resp.content)
            print(f"✅ Logo téléchargé : {competitor_id}")
            return rel_path

        print(f"⚠️ Échec téléchargement logo {competitor_id} (code {resp.status_code})")

    except Exception as e:
        print(f"⚠️ Erreur téléchargement logo {competitor_id}: {e}")

    FAILED_LOGO_IDS.add(competitor_id)
    return None


def download_competition_logo(competition_id: Optional[str], image_version: Optional[str] = None) -> Optional[str]:
    if not DOWNLOAD_LOGOS:
        return None

    if not competition_id:
        return None

    if competition_id in FAILED_COMP_LOGO_IDS:
        return None

    filename = f"competition_{competition_id}.png"
    filepath = os.path.join(COMPETITION_LOGOS_DIR, filename)
    rel_path = f"assets/images/logos/competitions/{filename}"

    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return rel_path

    url = get_competition_logo_url(competition_id, image_version)

    try:
        resp = make_request("GET", url, timeout=10, max_retries=1)

        if resp is None:
            FAILED_COMP_LOGO_IDS.add(competition_id)
            return None

        if resp.status_code == 200 and len(resp.content) > 0:
            with open(filepath, "wb") as f:
                f.write(resp.content)
            print(f"✅ Logo compétition téléchargé : {competition_id}")
            return rel_path

        print(f"⚠️ Échec téléchargement logo compétition {competition_id} (code {resp.status_code})")

    except Exception as e:
        print(f"⚠️ Erreur téléchargement logo compétition {competition_id}: {e}")

    FAILED_COMP_LOGO_IDS.add(competition_id)
    return None


# =======================================================
# FONCTIONS DE RÉCUPÉRATION DES DONNÉES
# =======================================================

def fetch_games_with_comps(date_from, date_to, max_retries: int = 3) -> Tuple[List[dict], List[dict]]:
    params = {
        "startDate": date_from.strftime("%d/%m/%Y"),
        "endDate": date_to.strftime("%d/%m/%Y"),
        "sports": 1,
        "showOdds": "true",
        "onlyMajorGames": "false",
    }

    for attempt in range(max_retries):
        try:
            resp = make_request("GET", SPORTDATA_URL, params=params, timeout=30)
            if resp is None:
                raise RuntimeError("Aucune réponse API")

            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, dict):
                print(f"❌ Format de réponse invalide: {type(data)}")
                return [], []

            games = data.get("games", [])
            competitions = data.get("competitions", [])

            if not isinstance(games, list) or not isinstance(competitions, list):
                print("❌ Format des données invalide")
                return [], []

            return games, competitions

        except Exception as e:
            print(f"❌ Erreur SportData (tentative {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)

    return [], []


def fetch_predictions(game_id: str, max_retries: int = 2) -> Optional[dict]:
    if not game_id:
        return None

    params = {"gameId": game_id}

    for attempt in range(max_retries):
        try:
            resp = make_request("GET", PREDICTIONS_URL, params=params, timeout=10)
            if resp is None:
                raise RuntimeError("Aucune réponse API")

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
            return None

        except Exception as e:
            print(f"⚠️ Erreur récupération votes match {game_id} (tentative {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)

    return None


def extract_game_info(game: dict, comp_image_map: dict) -> Optional[dict]:
    if not isinstance(game, dict):
        return None

    try:
        start_time = game.get("start_time") or game.get("startTime", "")
        competition = game.get("competitionDisplayName", "")
        competition_id = game.get("competitionId")
        competition_image_version = comp_image_map.get(str(competition_id)) if competition_id else None

        home = game.get("homeCompetitor", {}) or {}
        away = game.get("awayCompetitor", {}) or {}

        home_score = normalize_score(home.get("score"))
        away_score = normalize_score(away.get("score"))

        odds_data = game.get("odds")
        odds = None
        if odds_data and isinstance(odds_data, dict):
            options = odds_data.get("options", [])
            if isinstance(options, list):
                cotes = {}
                for opt in options:
                    if not isinstance(opt, dict):
                        continue
                    num = opt.get("num")
                    rate = opt.get("rate", {}) or {}
                    decimal = to_float_safe(rate.get("decimal"), None)
                    if num == 1 and decimal:
                        cotes["home"] = decimal
                    elif num == 2 and decimal:
                        cotes["draw"] = decimal
                    elif num == 3 and decimal:
                        cotes["away"] = decimal
                if cotes:
                    odds = cotes

        status_group = game.get("statusGroup")

        return {
            "id": str(game.get("id", "")),
            "start_time": start_time,
            "date": start_time[:10] if start_time else "",
            "home_team": str(home.get("name", "")),
            "away_team": str(away.get("name", "")),
            "home_competitor_id": str(home.get("id")) if home.get("id") else None,
            "away_competitor_id": str(away.get("id")) if away.get("id") else None,
            "home_image_version": home.get("imageVersion"),
            "away_image_version": away.get("imageVersion"),
            "competition": str(competition),
            "competition_id": str(competition_id) if competition_id else None,
            "competition_image_version": competition_image_version,
            "home_score": home_score,
            "away_score": away_score,
            "status_group": status_group,
            "status_text": game.get("statusText", ""),
            "is_finished": str(status_group) == "4",
            "odds": odds,
        }
    except Exception as e:
        print(f"❌ Erreur extraction info match: {e}")
        return None


# =======================================================
# FONCTIONS D'ANALYSE DE LA FORME
# =======================================================

def build_team_history(historical: List[dict]) -> dict:
    team_matches = {}

    if not isinstance(historical, list):
        return team_matches

    for m in historical:
        if not isinstance(m, dict):
            continue

        home = m.get("home_team", "")
        away = m.get("away_team", "")

        if not home or not away:
            continue

        date = parse_datetime_safe(m.get("start_time", "") or m.get("event_date", ""))
        if date is None:
            continue

        team_matches.setdefault(home, []).append((date, m, "home"))
        team_matches.setdefault(away, []).append((date, m, "away"))

    for team in team_matches:
        team_matches[team].sort(key=lambda x: x[0], reverse=True)

    return team_matches


def get_team_form(team: str, team_matches: dict, last_games: int = 5,
                  max_days: int = 365) -> Optional[dict]:
    if not team or not isinstance(team_matches, dict):
        return None

    matches = team_matches.get(team, [])
    if not matches:
        return None

    recent = []
    now = get_now_utc()

    for date, match, side in matches:
        if not isinstance(match, dict):
            continue
        if date > now:
            continue
        if match.get("is_finished") and match.get("home_score") is not None and match.get("away_score") is not None:
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

    for i, (_, match, side) in enumerate(recent):
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
        "matches_used": len(recent),
    }


def get_team_fatigue(team: str, team_matches: dict, window_days: int = 14) -> dict:
    if not team or not isinstance(team_matches, dict):
        return {"recent_matches": 0, "rest_days": None, "fatigue_index": 0}

    matches = team_matches.get(team, [])
    if not matches:
        return {"recent_matches": 0, "rest_days": None, "fatigue_index": 0}

    now = get_now_utc()
    recent_matches = 0
    last_played = None

    for date, match, _ in matches:
        if date > now:
            continue
        if not match.get("is_finished"):
            continue
        if match.get("home_score") is None or match.get("away_score") is None:
            continue

        if last_played is None:
            last_played = date

        if (now - date).days <= window_days:
            recent_matches += 1

    rest_days = max(0, (now - last_played).days) if last_played else None
    match_load = min(60, recent_matches * 15)
    rest_penalty = 0 if rest_days is None else max(0, 5 - rest_days) * 8
    fatigue_index = int(min(100, match_load + rest_penalty))

    return {
        "recent_matches": recent_matches,
        "rest_days": rest_days,
        "fatigue_index": fatigue_index,
    }


# =======================================================
# FONCTIONS D'ANALYSE H2H
# =======================================================

def load_historical_matches() -> List[dict]:
    if not os.path.exists(GLOBAL_CACHE_FILE):
        print("⚠️ Fichier historique introuvable. Exécutez d'abord allmatches.py.")
        return []

    try:
        with open(GLOBAL_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            print("⚠️ Format historique invalide")
            return []
    except json.JSONDecodeError as e:
        print(f"❌ Erreur JSON historique: {e}")
        return []
    except Exception as e:
        print(f"❌ Erreur chargement historique: {e}")
        return []


def weight_by_date(date_str: str) -> float:
    try:
        match_date = parse_datetime_safe(date_str)
        if match_date is None:
            return 1.0

        now = get_now_utc()
        days_old = (now - match_date).days

        if days_old < 180:
            return 1.5
        elif days_old < 365:
            return 1.2
        return 1.0
    except Exception:
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


def get_h2h(historical: List[dict], home_team: str, away_team: str, years: int = 2) -> List[dict]:
    if not historical or not home_team or not away_team:
        return []

    cutoff_date = (get_now_utc() - timedelta(days=365 * years)).date()
    h2h = []

    home_lower = home_team.lower()
    away_lower = away_team.lower()

    for m in historical:
        if not isinstance(m, dict):
            continue

        m_home = (m.get("home_team") or "").lower()
        m_away = (m.get("away_team") or "").lower()

        if (m_home == home_lower and m_away == away_lower) or (m_home == away_lower and m_away == home_lower):
            match_date = parse_datetime_safe(m.get("start_time", "") or m.get("event_date", ""))
            if match_date and match_date.date() >= cutoff_date:
                h2h.append(m)

    h2h.sort(key=lambda x: x.get("start_time", "") or x.get("event_date", ""), reverse=True)
    return h2h


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
            "draw_rate": 0.0,
        }

    current_home_lower = current_home_team.lower()

    for match in h2h_list:
        if not isinstance(match, dict):
            continue
        if not match.get("is_finished"):
            continue
        if match.get("home_score") is None or match.get("away_score") is None:
            continue

        date_weight = weight_by_date(match.get("start_time", "") or match.get("event_date", ""))
        comp_weight = competition_weight(match.get("competition", "") or match.get("league", ""))
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
        "draw_rate": safe_division(draws_score, total_weighted, 0),
    }


# =======================================================
# FONCTIONS DE PRÉDICTION
# =======================================================

def generate_prediction(analysis: dict, home_form: Optional[dict],
                        away_form: Optional[dict], league: str) -> dict:
    if not isinstance(analysis, dict):
        analysis = {}

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

    confiance = int(clamp(confiance, 0, 100))

    return {
        "double_chance": double_chance,
        "confidence": confiance,
    }


def calculate_xpronos_score(analysis: dict, home_form: Optional[dict],
                            away_form: Optional[dict], league: str) -> int:
    if not isinstance(analysis, dict):
        analysis = {}

    score = 0
    score += min(40, analysis.get("total_matches", 0) * 6)

    dominance = max(analysis.get("home_dominance", 0), analysis.get("away_dominance", 0))
    score += min(30, int(dominance * 100 * 0.5))

    if home_form and away_form:
        form_sum = home_form.get("form_score", 0) + away_form.get("form_score", 0)
        score += min(20, int(form_sum * 10))

    if analysis.get("draw_rate", 0) > 0.4:
        score -= 10

    return int(clamp(score, 0, 100))


def get_category(score: int) -> str:
    if score >= 70:
        return "vip"
    elif score >= 50:
        return "pro"
    return "simple"


def get_badge(score: int) -> str:
    if score >= 70:
        return "🏆 PREMIUM LOCK"
    elif score >= 60:
        return "💎 VIP ELITE"
    elif score >= 50:
        return "🔥 ULTRA SAFE"
    return ""


# =======================================================
# FONCTIONS COTES / POISSON / ENSEMBLE
# =======================================================

def normalize_odds(odds: dict) -> Optional[dict]:
    if not odds or not isinstance(odds, dict):
        return None

    home = to_float_safe(odds.get("home"), None)
    draw = to_float_safe(odds.get("draw"), None)
    away = to_float_safe(odds.get("away"), None)

    if home is None or draw is None or away is None:
        return None
    if home <= 0 or draw <= 0 or away <= 0:
        return None

    try:
        prob_home = 1 / home
        prob_draw = 1 / draw
        prob_away = 1 / away
    except ZeroDivisionError:
        return None

    total = prob_home + prob_draw + prob_away
    if total == 0:
        return None

    return {
        "home": prob_home / total,
        "draw": prob_draw / total,
        "away": prob_away / total,
    }


def estimate_dc_odds(odds: dict, double_chance: str) -> float:
    probs = normalize_odds(odds)
    if not probs:
        return 0.0

    if double_chance == "1X":
        prob = probs["home"] + probs["draw"]
    elif double_chance == "X2":
        prob = probs["draw"] + probs["away"]
    elif double_chance == "12":
        prob = probs["home"] + probs["away"]
    else:
        return 0.0

    if prob <= 0:
        return 0.0

    return 1 / prob


def poisson_probability(lambda_home: float, lambda_away: float,
                        max_goals: int = 6) -> Tuple[float, float, float]:
    lambda_home = max(0.1, float(lambda_home))
    lambda_away = max(0.1, float(lambda_away))

    p_home = 0.0
    p_draw = 0.0
    p_away = 0.0

    try:
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                prob = (
                    exp(-lambda_home) * (lambda_home ** i) / factorial(i)
                ) * (
                    exp(-lambda_away) * (lambda_away ** j) / factorial(j)
                )

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
    return 0.33, 0.34, 0.33


def estimate_odds(category: str, double_chance: str) -> float:
    odds_map = {
        "vip": {"1X": 1.25, "X2": 1.35, "12": 1.30},
        "pro": {"1X": 1.35, "X2": 1.45, "12": 1.40},
        "simple": {"1X": 1.45, "X2": 1.60, "12": 1.50},
    }
    cat_odds = odds_map.get(category, odds_map["simple"])
    return cat_odds.get(double_chance, 1.40)


def build_form_probabilities(home_form: Optional[dict], away_form: Optional[dict]) -> Tuple[float, float, float]:
    form_h = home_form.get("form_score", 0.5) if home_form else 0.5
    form_a = away_form.get("form_score", 0.5) if away_form else 0.5

    if home_form and away_form:
        avg_draw = (home_form.get("draws", 0.2) + away_form.get("draws", 0.2)) / 2
        form_diff = abs(form_h - form_a)
        closeness_boost = max(0.0, 1 - min(form_diff / 0.6, 1.0)) * 0.18
        draw_prob = clamp(avg_draw * 0.7 + closeness_boost, 0.12, 0.35)
    else:
        draw_prob = 0.22

    remaining = max(0.0, 1.0 - draw_prob)
    total_strength = max(form_h + form_a, 0.001)

    home_prob = remaining * (form_h / total_strength)
    away_prob = remaining * (form_a / total_strength)

    total = home_prob + draw_prob + away_prob
    if total > 0:
        home_prob /= total
        draw_prob /= total
        away_prob /= total

    return home_prob, draw_prob, away_prob


# =======================================================
# FONCTION PRINCIPALE
# =======================================================

def main():
    existing_data = {
        "matches": [],
        "categories": {"simple": [], "pro": [], "vip": []},
        "stats": {},
        "bookmakers": [],
    }
    existing_matches = {}

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    existing_data = loaded
                    existing_matches = {
                        str(m.get("id", "")): m
                        for m in loaded.get("matches", [])
                        if isinstance(m, dict)
                    }
        except json.JSONDecodeError as e:
            print(f"❌ Erreur JSON fichier existant: {e}")
        except Exception as e:
            print(f"❌ Erreur chargement fichier existant: {e}")

    print("\n📅 Récupération des matchs via SportData...")
    games_today, comps_today = fetch_games_with_comps(today, today)
    games_tomorrow, comps_tomorrow = fetch_games_with_comps(tomorrow, tomorrow)
    games_yesterday, comps_yesterday = fetch_games_with_comps(yesterday, yesterday)

    all_new_games = (games_today or []) + (games_tomorrow or []) + (games_yesterday or [])

    all_comps = {}
    for comp in (comps_today or []) + (comps_tomorrow or []) + (comps_yesterday or []):
        if isinstance(comp, dict) and comp.get("id"):
            all_comps[str(comp["id"])] = comp

    all_comps_list = list(all_comps.values())

    comp_image_map = {}
    for comp in all_comps_list:
        comp_id = comp.get("id")
        if comp_id:
            comp_image_map[str(comp_id)] = comp.get("imageVersion")

    print(f"✅ {len(all_new_games)} matchs récupérés, {len(all_comps_list)} compétitions uniques")

    new_infos = {}
    for g in all_new_games:
        if isinstance(g, dict):
            info = extract_game_info(g, comp_image_map)
            if info and info.get("id"):
                new_infos[info["id"]] = info

    historical = load_historical_matches()
    print(f"📂 Historique chargé : {len(historical)} matchs")

    team_matches = build_team_history(historical)
    print(f"📊 Statistiques de forme calculées pour {len(team_matches)} équipes")

    matches = []
    total_processed = 0
    total_skipped = 0

    all_ids = set(existing_matches.keys()) | set(new_infos.keys())

    for gid in all_ids:
        total_processed += 1

        if gid not in new_infos:
            match = existing_matches.get(gid)
            if match and isinstance(match, dict):
                matches.append(match)
            continue

        base = new_infos[gid]
        existing = existing_matches.get(gid, {})
        if not isinstance(existing, dict):
            existing = {}

        home_score = base.get("home_score")
        if home_score is None:
            home_score = existing.get("home_score")

        away_score = base.get("away_score")
        if away_score is None:
            away_score = existing.get("away_score")

        status = base.get("status_text") or existing.get("status", "")

        if is_bad_league(base.get("competition", "")):
            print(f"⚠️ Match {base.get('home_team', '')} vs {base.get('away_team', '')} ignoré (ligue faible)")
            total_skipped += 1
            continue

        home_team = base.get("home_team", "")
        away_team = base.get("away_team", "")

        home_form = get_team_form(home_team, team_matches, last_games=5) if home_team else None
        away_form = get_team_form(away_team, team_matches, last_games=5) if away_team else None

        form_valid = False
        if home_form is not None or away_form is not None:
            home_matches_used = home_form.get("matches_used", 0) if home_form else 0
            away_matches_used = away_form.get("matches_used", 0) if away_form else 0
            if home_matches_used > 0 or away_matches_used > 0:
                form_valid = True

        if not form_valid:
            print(f"⚠️ Match {home_team} vs {away_team} ignoré (forme insuffisante)")
            total_skipped += 1
            continue

        used_poisson_fallback = False
        h2h_list = get_h2h(historical, home_team, away_team, years=2)

        if len(h2h_list) >= 2:
            analysis = analyze_h2h(h2h_list, home_team, away_team)
            print(f"📊 Match {home_team} vs {away_team} - H2H OK ({len(h2h_list)} matchs)")
        else:
            home_matches_used = home_form.get("matches_used", 0) if home_form else 0
            away_matches_used = away_form.get("matches_used", 0) if away_form else 0

            if home_matches_used >= 2 and away_matches_used >= 2:
                used_poisson_fallback = True
                print(f"⚠️ Match {home_team} vs {away_team} - H2H insuffisant, utilisation Poisson")

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
                    "draw_rate": p_draw,
                }
            else:
                print(f"⚠️ Match {home_team} vs {away_team} ignoré (H2H et forme insuffisants)")
                total_skipped += 1
                continue

        if analysis.get("draw_rate", 0) > DRAW_RATE_MAX:
            print(f"⚠️ Match {home_team} vs {away_team} ignoré (draw_rate > {DRAW_RATE_MAX})")
            total_skipped += 1
            continue

        dom_diff = abs(analysis.get("home_dominance", 0) - analysis.get("away_dominance", 0))
        if dom_diff < DOM_DIFF_MIN:
            print(f"⚠️ Match {home_team} vs {away_team} ignoré (trop équilibré)")
            total_skipped += 1
            continue

        prediction = generate_prediction(analysis, home_form, away_form, base.get("competition", ""))

        if prediction.get("double_chance") == "12":
            print("   ⚠️ Pronostic 12 (match équilibré) ignoré")
            total_skipped += 1
            continue

        if prediction.get("confidence", 0) < CONFIDENCE_THRESHOLD:
            print(f"⚠️ Match {home_team} vs {away_team} ignoré (confiance insuffisante)")
            total_skipped += 1
            continue

        if home_form and away_form:
            goal_diff = abs(home_form.get("goals_for", 0) - away_form.get("goals_for", 0))
            if goal_diff < GOAL_DIFF_THRESHOLD:
                print(f"⚠️ Match {home_team} vs {away_team} ignoré (différence buts trop faible: {goal_diff:.2f})")
                total_skipped += 1
                continue

        try:
            match_time_str = base.get("start_time", "")
            if match_time_str:
                match_time = parse_datetime_safe(match_time_str)
                if match_time:
                    now = get_now_utc()
                    time_diff = (match_time - now).total_seconds()
                    if 0 < time_diff < MATCH_TOO_CLOSE_SECONDS:
                        print(f"⚠️ Match {home_team} vs {away_team} ignoré (trop proche: {int(time_diff / 60)}min)")
                        total_skipped += 1
                        continue
        except Exception as e:
            print(f"⚠️ Erreur vérification temps match {home_team} vs {away_team}: {e}")

        odds = base.get("odds")
        if odds and isinstance(odds, dict):
            home_odd = to_float_safe(odds.get("home"), None)
            away_odd = to_float_safe(odds.get("away"), None)

            if home_odd and away_odd and abs(home_odd - away_odd) > 3:
                print(f"⚠️ Match {home_team} vs {away_team} ignoré (écart de cotes trop grand)")
                total_skipped += 1
                continue

            dc = prediction.get("double_chance", "")
            if dc == "1X" and home_odd and home_odd < 1.20:
                print(f"⚠️ Match {home_team} vs {away_team} ignoré (cote home trop faible pour 1X)")
                total_skipped += 1
                continue
            if dc == "X2" and away_odd and away_odd < 1.20:
                print(f"⚠️ Match {home_team} vs {away_team} ignoré (cote away trop faible pour X2)")
                total_skipped += 1
                continue

        score = calculate_xpronos_score(analysis, home_form, away_form, base.get("competition", ""))
        category = get_category(score)
        badge = get_badge(score)

        if score < XPRONOS_THRESHOLD:
            print(f"⚠️ Match {home_team} vs {away_team} ignoré (score xPronos {score} < {XPRONOS_THRESHOLD})")
            total_skipped += 1
            continue

        home_logo = None
        away_logo = None
        league_logo = None

        try:
            home_logo = download_logo(base.get("home_competitor_id"), base.get("home_image_version"))
        except Exception as e:
            print(f"⚠️ Erreur logo équipe domicile {home_team}: {e}")

        try:
            away_logo = download_logo(base.get("away_competitor_id"), base.get("away_image_version"))
        except Exception as e:
            print(f"⚠️ Erreur logo équipe extérieure {away_team}: {e}")

        try:
            league_logo = download_competition_logo(base.get("competition_id"), base.get("competition_image_version"))
        except Exception as e:
            print(f"⚠️ Erreur logo compétition {base.get('competition', '')}: {e}")

        public_votes = None
        if category in ["pro", "vip"]:
            votes = fetch_predictions(gid)
            if votes and isinstance(votes, dict):
                options = votes.get("options", [])
                if isinstance(options, list):
                    vote_dict = {}
                    for opt in options:
                        if not isinstance(opt, dict):
                            continue
                        num = opt.get("num")
                        vote_data = opt.get("vote", {}) or {}
                        percentage = vote_data.get("percentage")
                        if num == 1:
                            vote_dict["home"] = percentage
                        elif num == 2:
                            vote_dict["draw"] = percentage
                        elif num == 3:
                            vote_dict["away"] = percentage
                    if vote_dict:
                        public_votes = vote_dict

        value_bet = False
        dc = prediction.get("double_chance", "")

        if odds and isinstance(odds, dict):
            home_dom = clamp(analysis.get("home_dominance", 0) + HOME_ADVANTAGE, 0, 0.95)
            away_dom = clamp(analysis.get("away_dominance", 0), 0, 0.95)
            draw_rate = clamp(analysis.get("draw_rate", 0), 0, 0.95)

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
            elif dc == "12":
                our_prob = home_dom + away_dom
            else:
                our_prob = 0.0

            our_prob = clamp(our_prob, 0.05, 0.95)
            dc_odds = estimate_dc_odds(odds, dc)

            if dc_odds > 0:
                book_prob = 1 / dc_odds
                if our_prob > book_prob + 0.05:
                    value_bet = True

        elo_base = 1500
        elo_home = int(elo_base + ((home_form.get("form_score", 0) if home_form else 0) * 200))
        elo_away = int(elo_base + ((away_form.get("form_score", 0) if away_form else 0) * 200))

        xg_home = 1.2
        xg_away = 1.2
        if home_form and away_form:
            gf_h = home_form.get("goals_for", 1.2)
            ga_h = home_form.get("goals_against", 1.2)
            gf_a = away_form.get("goals_for", 1.2)
            ga_a = away_form.get("goals_against", 1.2)

            xg_home = (gf_h * 1.1 + ga_a * 0.9) / 2
            xg_away = (gf_a * 0.9 + ga_h * 1.1) / 2

        fatigue_home_data = get_team_fatigue(home_team, team_matches)
        fatigue_away_data = get_team_fatigue(away_team, team_matches)
        fatigue_home = fatigue_home_data["fatigue_index"]
        fatigue_away = fatigue_away_data["fatigue_index"]

        trap_detected = False
        if public_votes and odds:
            votes_home = to_float_safe(public_votes.get("home"), 0) or 0
            votes_draw = to_float_safe(public_votes.get("draw"), 0) or 0
            votes_away = to_float_safe(public_votes.get("away"), 0) or 0

            includes_home = dc in ("1X", "12")
            includes_draw = dc in ("1X", "X2")
            includes_away = dc in ("X2", "12")

            if (votes_home > 75 and not includes_home) or \
               (votes_draw > 75 and not includes_draw) or \
               (votes_away > 75 and not includes_away):
                trap_detected = True

            home_odd = to_float_safe(odds.get("home"), 0) or 0
            away_odd = to_float_safe(odds.get("away"), 0) or 0

            if votes_home > 75 and home_odd > 2:
                trap_detected = True
            if votes_away > 75 and away_odd > 2:
                trap_detected = True

        if dc == "1X":
            elo_signal = (elo_home - elo_away) / 200.0
            fatigue_signal = (fatigue_away - fatigue_home) / 100.0
        elif dc == "X2":
            elo_signal = (elo_away - elo_home) / 200.0
            fatigue_signal = (fatigue_home - fatigue_away) / 100.0
        else:
            elo_signal = -abs(elo_home - elo_away) / 200.0
            fatigue_signal = abs(fatigue_home - fatigue_away) / 100.0

        elo_component = clamp(50 + elo_signal * 35, 0, 100)
        fatigue_component = clamp(50 + fatigue_signal * 25, 0, 100)

        conf = prediction.get("confidence", 0)
        trap_penalty = 7 if trap_detected else 0

        ai_score = (
            score * 0.35 +
            conf * 0.30 +
            elo_component * 0.20 +
            fatigue_component * 0.15 -
            trap_penalty
        )
        ai_score = clamp(ai_score, 0, 100)

        market_probs = normalize_odds(odds) if odds else None

        if home_form and away_form:
            gf_h = home_form.get("goals_for", 1.2)
            ga_h = home_form.get("goals_against", 1.2)
            gf_a = away_form.get("goals_for", 1.2)
            ga_a = away_form.get("goals_against", 1.2)

            lambda_home_ens = (gf_h * 1.1 + ga_a * 0.9) / 2
            lambda_away_ens = (gf_a * 0.9 + ga_h * 1.1) / 2
            poisson_h, poisson_d, poisson_a = poisson_probability(lambda_home_ens, lambda_away_ens)
        else:
            poisson_h, poisson_d, poisson_a = 0.33, 0.34, 0.33

        h2h_h = analysis.get("home_dominance", 0)
        h2h_d = analysis.get("draw_rate", 0)
        h2h_a = analysis.get("away_dominance", 0)

        form_h_norm, form_d_norm, form_a_norm = build_form_probabilities(home_form, away_form)

        if market_probs:
            if used_poisson_fallback:
                w_h2h, w_poisson, w_form, w_market = 0.0, 0.45, 0.25, 0.30
            else:
                w_h2h, w_poisson, w_form, w_market = 0.30, 0.25, 0.20, 0.25

            ensemble_h = (
                h2h_h * w_h2h +
                poisson_h * w_poisson +
                form_h_norm * w_form +
                market_probs["home"] * w_market
            )
            ensemble_d = (
                h2h_d * w_h2h +
                poisson_d * w_poisson +
                form_d_norm * w_form +
                market_probs["draw"] * w_market
            )
            ensemble_a = (
                h2h_a * w_h2h +
                poisson_a * w_poisson +
                form_a_norm * w_form +
                market_probs["away"] * w_market
            )
        else:
            if used_poisson_fallback:
                w_h2h, w_poisson, w_form = 0.0, 0.60, 0.40
            else:
                w_h2h, w_poisson, w_form = 0.40, 0.30, 0.30

            ensemble_h = h2h_h * w_h2h + poisson_h * w_poisson + form_h_norm * w_form
            ensemble_d = h2h_d * w_h2h + poisson_d * w_poisson + form_d_norm * w_form
            ensemble_a = h2h_a * w_h2h + poisson_a * w_poisson + form_a_norm * w_form

        total_ens = ensemble_h + ensemble_d + ensemble_a
        if total_ens > 0:
            ensemble_h /= total_ens
            ensemble_d /= total_ens
            ensemble_a /= total_ens
        else:
            ensemble_h, ensemble_d, ensemble_a = 0.33, 0.34, 0.33

        if dc == "1X":
            ensemble_prob_dc = ensemble_h + ensemble_d
        elif dc == "X2":
            ensemble_prob_dc = ensemble_d + ensemble_a
        else:
            ensemble_prob_dc = ensemble_h + ensemble_a

        display_odds = 0.0
        if odds:
            display_odds = estimate_dc_odds(odds, dc)
        if display_odds <= 0:
            display_odds = estimate_odds(category, dc)

        final_prediction = {
            "double_chance": dc,
            "confidence": conf,
            "odds": round(display_odds, 2),
        }

        value_bet_bonus = 10 if value_bet else 0
        final_score = (
            score * 0.28 +
            conf * 0.22 +
            ai_score * 0.22 +
            (ensemble_prob_dc * 100) * 0.18 +
            value_bet_bonus * 0.10
        )
        if trap_detected:
            final_score -= 5

        final_score = clamp(final_score, 0, 100)

        poisson_probs = None
        if home_form and away_form:
            gf_h = home_form.get("goals_for", 1.2)
            ga_h = home_form.get("goals_against", 1.2)
            gf_a = away_form.get("goals_for", 1.2)
            ga_a = away_form.get("goals_against", 1.2)

            lambda_home = (gf_h * 1.1 + ga_a * 0.9) / 2
            lambda_away = (gf_a * 0.9 + ga_h * 1.1) / 2
            p_home, p_draw, p_away = poisson_probability(lambda_home, lambda_away)
            poisson_probs = {
                "home": round(p_home, 3),
                "draw": round(p_draw, 3),
                "away": round(p_away, 3),
            }

        match = {
            "id": gid,
            "date": base.get("date", ""),
            "event_date": base.get("start_time", ""),
            "start_time": base.get("start_time", ""),
            "home_team": home_team,
            "away_team": away_team,
            "home_logo": home_logo,
            "away_logo": away_logo,
            "league": base.get("competition", ""),
            "competition": base.get("competition", ""),
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
            "home_rest_days": fatigue_home_data["rest_days"],
            "away_rest_days": fatigue_away_data["rest_days"],
            "home_recent_matches_14d": fatigue_home_data["recent_matches"],
            "away_recent_matches_14d": fatigue_away_data["recent_matches"],
            "trap_detected": trap_detected,
            "ensemble_prob_home": round(ensemble_h, 3),
            "ensemble_prob_draw": round(ensemble_d, 3),
            "ensemble_prob_away": round(ensemble_a, 3),
            "ensemble_prob_dc": round(ensemble_prob_dc, 3),
            "used_poisson_fallback": used_poisson_fallback,
        }

        if base.get("is_finished") and home_score is not None and away_score is not None:
            if dc == "1X":
                match["verified_double"] = home_score >= away_score
            elif dc == "X2":
                match["verified_double"] = away_score >= home_score
            elif dc == "12":
                match["verified_double"] = home_score != away_score

        matches.append(match)

    matches.sort(key=lambda x: x.get("final_score", 0), reverse=True)

    categories = {"simple": [], "pro": [], "vip": []}
    for m in matches:
        cat = m.get("category", "simple")
        if cat not in categories:
            cat = "simple"
        categories[cat].append(m)

    total_bets = 0
    total_wins = 0
    total_stake = 0.0
    total_return = 0.0

    for m in matches:
        if m.get("is_finished"):
            total_bets += 1
            total_stake += 1.0

            if m.get("verified_double"):
                total_wins += 1
                match_odds = m.get("odds")
                if match_odds and isinstance(match_odds, dict):
                    dc = m.get("prediction", {}).get("double_chance", "")
                    dc_odds = estimate_dc_odds(match_odds, dc)
                    if dc_odds > 0:
                        odds_value = dc_odds
                    else:
                        odds_value = m.get("prediction", {}).get("odds", 2.0)
                else:
                    odds_value = m.get("prediction", {}).get("odds", 2.0)
                total_return += odds_value

    roi = safe_division((total_return - total_stake), total_stake, 0) * 100

    stats = {
        "total_bets": total_bets,
        "wins": total_wins,
        "roi": round(roi, 1),
    }

    default_bookmakers = [
        {
            "name": "1xBet",
            "logo": "assets/images/1xbet.webp",
            "url": "https://refpa58144.com/L?tag=d_2054511m_1599c_&site=2054511&ad=1599",
        },
        {
            "name": "1win",
            "logo": "assets/images/1win.webp",
            "url": "https://1wrbgb.com/?open=register&p=qqcw",
        },
        {
            "name": "Betwinner",
            "logo": "assets/images/betwinner.webp",
            "url": "https://bwredir.com/299Y",
        },
        {
            "name": "Melbet",
            "logo": "assets/images/melbet.webp",
            "url": "https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041",
        },
        {
            "name": "Linebet",
            "logo": "assets/images/linebet.webp",
            "url": "https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3072389&ad=22611",
        },
        {
            "name": "BetClic",
            "logo": "assets/images/betclic.webp",
            "url": "https://betpari-click.com/2vY0?extid=USD",
        },
    ]

    bookmakers = existing_data.get("bookmakers", default_bookmakers)
    if not isinstance(bookmakers, list):
        bookmakers = default_bookmakers

    data = {
        "matches": matches,
        "categories": categories,
        "stats": stats,
        "bookmakers": bookmakers,
    }

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 {DATA_FILE} généré avec succès")
    except Exception as e:
        print(f"❌ Erreur sauvegarde fichier: {e}")
        return

    print(f"📊 Matchs traités: {total_processed}, ignorés: {total_skipped}")
    print(f"📈 Catégories : Simple: {len(categories['simple'])}, Pro: {len(categories['pro'])}, VIP: {len(categories['vip'])}")
    print(f"💰 ROI calculé : {stats['roi']}% sur {stats['total_bets']} matchs terminés")
    if DOWNLOAD_LOGOS:
        print(f"🖼️ Logos dans {LOGOS_DIR}")
    else:
        print("🖼️ Téléchargement des logos désactivé")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interruption par l'utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()