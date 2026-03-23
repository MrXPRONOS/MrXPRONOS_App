#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_data.py - Génération optimisée des pronostics football
Version quota-aware et orientée fiabilité.

Objectifs :
- minimiser les requêtes API
- enrichir seulement les meilleurs matchs
- éviter les faux signaux si données manquantes
- produire un data.json propre et stable
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
# CONFIG
# =======================================================

SPORTDATA_URL = "https://v1.football.sportsapipro.com/games/allscores"
PREDICTIONS_URL = "https://v1.football.sportsapipro.com/games/predictions"
PREGAME_STATS_URL = "https://v1.football.sportsapipro.com/stats/preGame"
CURRENT_GAMES_URL = "https://v1.football.sportsapipro.com/games/current"

UTC = timezone.utc
today = datetime.now(UTC).date()
tomorrow = today + timedelta(days=1)

DATA_FILE = "data.json"
CACHE_DIR = "cache"
GLOBAL_CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")
REQUEST_STATE_FILE = os.path.join(CACHE_DIR, "request_state.json")
ENRICH_CACHE_FILE = os.path.join(CACHE_DIR, "enrichment_cache.json")

HOME_ADVANTAGE = 0.1
CONFIDENCE_THRESHOLD = 50
GOAL_DIFF_THRESHOLD = 0.1
XPRONOS_THRESHOLD = 35
DOMINANCE_THRESHOLD = 0.4

DRAW_RATE_MAX = 0.45
DOM_DIFF_MIN = 0.15
MATCH_TOO_CLOSE_SECONDS = 1800

DAILY_REQUEST_BUDGET = 80
TOP_N_ENRICHED_MATCHES = 10
MAX_PREDICTIONS_CALLS = 8
MAX_PREGAME_CALLS = 5

PREDICTIONS_CACHE_TTL_HOURS = 12
PREGAME_CACHE_TTL_HOURS = 24
CURRENT_CACHE_TTL_MINUTES = 10

BAD_LEAGUES = [
    "friendly",
    "u21",
    "u19",
    "women",
    "reserve",
    "youth",
    "amateur",
]

os.makedirs(CACHE_DIR, exist_ok=True)

print("=" * 60)
print(f"🚀 GÉNÉRATION DES PRONOSTICS OPTIMISÉE - {today}")
print("=" * 60)


# =======================================================
# HELPERS
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
    except Exception:
        return None


def get_now_utc() -> datetime:
    return datetime.now(UTC)


def load_json_file(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json_file(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def is_cache_fresh(iso_time: Optional[str], ttl_hours: int) -> bool:
    if not iso_time:
        return False
    dt = parse_datetime_safe(iso_time)
    if not dt:
        return False
    return (get_now_utc() - dt) <= timedelta(hours=ttl_hours)


# =======================================================
# REQUEST BUDGET MANAGER
# =======================================================

def load_request_state() -> dict:
    state = load_json_file(REQUEST_STATE_FILE, {})
    if state.get("date") != str(today):
        return {"date": str(today), "count": 0}
    return state


def save_request_state(state: dict):
    save_json_file(REQUEST_STATE_FILE, state)


def can_make_request(state: dict, count: int = 1) -> bool:
    return state.get("count", 0) + count <= DAILY_REQUEST_BUDGET


def register_request(state: dict, count: int = 1):
    state["count"] = state.get("count", 0) + count
    save_request_state(state)


def budget_remaining(state: dict) -> int:
    return max(0, DAILY_REQUEST_BUDGET - state.get("count", 0))


# =======================================================
# ENRICHMENT CACHE
# =======================================================

def load_enrich_cache() -> dict:
    return load_json_file(ENRICH_CACHE_FILE, {
        "predictions": {},
        "pregame": {},
        "current_games": {}
    })


def save_enrich_cache(cache: dict):
    save_json_file(ENRICH_CACHE_FILE, cache)


# =======================================================
# API FETCH
# =======================================================

def quota_request(state: dict, method: str, url: str, **kwargs):
    if not can_make_request(state, 1):
        print(f"⛔ Budget API épuisé, requête ignorée: {url}")
        return None
    resp = make_request(method, url, **kwargs)
    register_request(state, 1)
    return resp


def fetch_games_with_comps(date_from, date_to, state: dict) -> Tuple[List[dict], List[dict]]:
    params = {
        "startDate": date_from.strftime("%d/%m/%Y"),
        "endDate": date_to.strftime("%d/%m/%Y"),
        "sports": 1,
        "showOdds": "true",
        "onlyMajorGames": "false",
    }

    try:
        resp = quota_request(state, "GET", SPORTDATA_URL, params=params, timeout=30)
        if resp is None:
            return [], []
        resp.raise_for_status()
        data = resp.json()

        games = data.get("games", [])
        competitions = data.get("competitions", [])
        return games if isinstance(games, list) else [], competitions if isinstance(competitions, list) else []

    except Exception as e:
        print(f"❌ Erreur fetch games {date_from} -> {date_to}: {e}")
        return [], []


def fetch_game_predictions(game_id: str, state: dict, enrich_cache: dict) -> Optional[dict]:
    cached = enrich_cache["predictions"].get(str(game_id))
    if cached and is_cache_fresh(cached.get("fetched_at"), PREDICTIONS_CACHE_TTL_HOURS):
        return cached.get("data")

    try:
        resp = quota_request(state, "GET", PREDICTIONS_URL, params={"gameId": game_id}, timeout=15)
        if resp is None:
            return None
        if resp.status_code != 200:
            return None

        data = resp.json()
        enrich_cache["predictions"][str(game_id)] = {
            "fetched_at": get_now_utc().isoformat(),
            "data": data
        }
        return data
    except Exception as e:
        print(f"⚠️ Erreur fetch predictions game {game_id}: {e}")
        return None


def fetch_pregame_stats(game_id: str, state: dict, enrich_cache: dict) -> Optional[dict]:
    cached = enrich_cache["pregame"].get(str(game_id))
    if cached and is_cache_fresh(cached.get("fetched_at"), PREGAME_CACHE_TTL_HOURS):
        return cached.get("data")

    try:
        params = {
            "game": game_id,
            "onlyMajor": "true",
            "topBookmaker": 14
        }
        resp = quota_request(state, "GET", PREGAME_STATS_URL, params=params, timeout=20)
        if resp is None:
            return None
        if resp.status_code != 200:
            return None

        data = resp.json()
        enrich_cache["pregame"][str(game_id)] = {
            "fetched_at": get_now_utc().isoformat(),
            "data": data
        }
        return data
    except Exception as e:
        print(f"⚠️ Erreur fetch pregame game {game_id}: {e}")
        return None


# =======================================================
# EXTRACTION
# =======================================================

def extract_game_info(game: dict) -> Optional[dict]:
    if not isinstance(game, dict):
        return None

    try:
        start_time = game.get("start_time") or game.get("startTime", "")
        competition = game.get("competitionDisplayName", "")
        competition_id = game.get("competitionId")

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

        return {
            "id": str(game.get("id", "")),
            "start_time": start_time,
            "date": start_time[:10] if start_time else "",
            "home_team": str(home.get("name", "")),
            "away_team": str(away.get("name", "")),
            "home_competitor_id": str(home.get("id")) if home.get("id") else None,
            "away_competitor_id": str(away.get("id")) if away.get("id") else None,
            "competition": str(competition),
            "competition_id": str(competition_id) if competition_id else None,
            "home_score": home_score,
            "away_score": away_score,
            "status_group": game.get("statusGroup"),
            "status_text": game.get("statusText", ""),
            "is_finished": str(game.get("statusGroup")) == "4",
            "odds": odds,
        }
    except Exception as e:
        print(f"❌ Erreur extraction info match: {e}")
        return None


# =======================================================
# HISTORICAL
# =======================================================

def load_historical_matches() -> List[dict]:
    data = load_json_file(GLOBAL_CACHE_FILE, [])
    return data if isinstance(data, list) else []


def build_team_history(historical: List[dict]) -> dict:
    team_matches = {}

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


def get_team_form(team: str, team_matches: dict, last_games: int = 5, max_days: int = 365) -> Optional[dict]:
    matches = team_matches.get(team, [])
    if not matches:
        return None

    recent = []
    now = get_now_utc()

    for date, match, side in matches:
        if date > now:
            continue
        if match.get("is_finished") and match.get("home_score") is not None and match.get("away_score") is not None:
            if (now - date).days <= max_days:
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

    points_per_game = safe_division(wins * 3 + draws, wins + draws + losses, 0)
    form_score = safe_division(points_per_game, 3, 0)

    return {
        "wins": round(wins / total_weight, 2),
        "draws": round(draws / total_weight, 2),
        "losses": round(losses / total_weight, 2),
        "goals_for": round(goals_for / total_weight, 2),
        "goals_against": round(goals_against / total_weight, 2),
        "form_score": round(form_score, 3),
        "matches_used": len(recent),
    }


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


def analyze_h2h(h2h_list: List[dict], current_home_team: str) -> dict:
    home_score = 0.0
    away_score = 0.0
    draws_score = 0.0
    matches_count = 0

    current_home_lower = current_home_team.lower()

    for match in h2h_list:
        if not match.get("is_finished"):
            continue
        if match.get("home_score") is None or match.get("away_score") is None:
            continue

        matches_count += 1
        home_s = match.get("home_score", 0)
        away_s = match.get("away_score", 0)
        match_home_team = (match.get("home_team") or "").lower()

        weight = 1.0

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
        "home_dominance": safe_division(home_score, total, 0),
        "away_dominance": safe_division(away_score, total, 0),
        "draw_rate": safe_division(draws_score, total, 0),
    }


# =======================================================
# MATH / MODEL
# =======================================================

def poisson_probability(lambda_home: float, lambda_away: float, max_goals: int = 6):
    lambda_home = max(0.1, float(lambda_home))
    lambda_away = max(0.1, float(lambda_away))

    p_home = p_draw = p_away = 0.0

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
    except Exception:
        return 0.33, 0.34, 0.33

    total = p_home + p_draw + p_away
    if total > 0:
        return p_home / total, p_draw / total, p_away / total
    return 0.33, 0.34, 0.33


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

    prob_home = 1 / home
    prob_draw = 1 / draw
    prob_away = 1 / away
    total = prob_home + prob_draw + prob_away

    return {
        "home": prob_home / total,
        "draw": prob_draw / total,
        "away": prob_away / total,
    }


# =======================================================
# LOCAL SCORING
# =======================================================

def compute_local_candidate_score(home_form, away_form, analysis, odds):
    score = 0

    if analysis.get("total_matches", 0) >= 2:
        score += 15

    dom = max(analysis.get("home_dominance", 0), analysis.get("away_dominance", 0))
    score += int(dom * 25)

    if home_form and away_form:
        form_diff = abs(home_form.get("form_score", 0) - away_form.get("form_score", 0))
        score += min(20, int(form_diff * 50))

        gf_diff = abs(home_form.get("goals_for", 0) - away_form.get("goals_for", 0))
        score += min(15, int(gf_diff * 10))

    if odds:
        probs = normalize_odds(odds)
        if probs:
            market_gap = abs(probs["home"] - probs["away"])
            score += min(20, int(market_gap * 100))

    if analysis.get("draw_rate", 0) > 0.4:
        score -= 10

    return int(clamp(score, 0, 100))


def generate_prediction_from_analysis(analysis, home_form, away_form):
    home_dom = analysis.get("home_dominance", 0) + HOME_ADVANTAGE
    away_dom = analysis.get("away_dominance", 0)

    if home_dom > away_dom + DOMINANCE_THRESHOLD:
        dc = "1X"
    elif away_dom > home_dom + DOMINANCE_THRESHOLD:
        dc = "X2"
    else:
        dc = "12"

    confidence = 50
    confidence += min(20, analysis.get("total_matches", 0) * 3)

    if home_form and away_form:
        form_diff = abs(home_form.get("form_score", 0) - away_form.get("form_score", 0))
        confidence += min(10, int(form_diff * 25))

    if analysis.get("draw_rate", 0) > 0.4:
        confidence -= 10

    confidence = int(clamp(confidence, 0, 100))

    return {"double_chance": dc, "confidence": confidence}


def calculate_xpronos_score(analysis, home_form, away_form):
    score = 0
    score += min(40, analysis.get("total_matches", 0) * 6)
    score += min(25, int(max(analysis.get("home_dominance", 0), analysis.get("away_dominance", 0)) * 50))

    if home_form and away_form:
        score += min(20, int((home_form.get("form_score", 0) + away_form.get("form_score", 0)) * 10))

    if analysis.get("draw_rate", 0) > 0.4:
        score -= 10

    return int(clamp(score, 0, 100))


def get_category(score: int) -> str:
    if score >= 70:
        return "vip"
    if score >= 50:
        return "pro"
    return "simple"


def get_badge(score: int) -> str:
    if score >= 70:
        return "🏆 PREMIUM LOCK"
    if score >= 60:
        return "💎 VIP ELITE"
    if score >= 50:
        return "🔥 ULTRA SAFE"
    return ""


# =======================================================
# API ENRICHMENT
# =======================================================

def extract_provider_prediction_signal(pred_data: Optional[dict]) -> dict:
    if not pred_data or not isinstance(pred_data, dict):
        return {"provider_alignment": 0, "provider_confidence": 0}

    try:
        games = pred_data.get("games", [])
        if not games or not isinstance(games, list):
            return {"provider_alignment": 0, "provider_confidence": 0}

        game = games[0]
        promoted = game.get("promotedPredictions", {}) or {}
        predictions = promoted.get("predictions", [])

        if not isinstance(predictions, list):
            return {"provider_alignment": 0, "provider_confidence": 0}

        best = None
        for pred in predictions:
            if pred.get("type") == 1:
                best = pred
                break

        if not best:
            return {"provider_alignment": 0, "provider_confidence": 0}

        options = best.get("options", [])
        if not isinstance(options, list):
            return {"provider_alignment": 0, "provider_confidence": 0}

        values = {}
        for opt in options:
            num = opt.get("num")
            vote = opt.get("vote", {}) or {}
            pct = to_float_safe(vote.get("percentage"), 0) or 0
            if num == 1:
                values["home"] = pct
            elif num == 2:
                values["draw"] = pct
            elif num == 3:
                values["away"] = pct

        if not values:
            return {"provider_alignment": 0, "provider_confidence": 0}

        winner = max(values, key=values.get)
        return {
            "provider_alignment": winner,
            "provider_confidence": round(values[winner], 1)
        }
    except Exception:
        return {"provider_alignment": 0, "provider_confidence": 0}


def extract_pregame_signal(pregame_data: Optional[dict]) -> dict:
    if not pregame_data or not isinstance(pregame_data, dict):
        return {"pregame_quality": 0}

    score = 0
    try:
        if pregame_data.get("statistics"):
            score += 30
        if pregame_data.get("teams"):
            score += 20
        if pregame_data.get("competition"):
            score += 10
    except Exception:
        pass

    return {"pregame_quality": int(clamp(score, 0, 100))}


# =======================================================
# MAIN
# =======================================================

def main():
    request_state = load_request_state()
    enrich_cache = load_enrich_cache()

    print(f"📦 Budget API restant avant run : {budget_remaining(request_state)} requêtes")

    existing_data = load_json_file(DATA_FILE, {
        "matches": [],
        "categories": {"simple": [], "pro": [], "vip": []},
        "stats": {},
        "bookmakers": [],
    })

    existing_matches = {
        str(m.get("id", "")): m
        for m in existing_data.get("matches", [])
        if isinstance(m, dict)
    }

    print("📅 Récupération minimale des matchs...")
    games_today, comps_today = fetch_games_with_comps(today, today, request_state)
    games_tomorrow, comps_tomorrow = fetch_games_with_comps(tomorrow, tomorrow, request_state)

    all_new_games = (games_today or []) + (games_tomorrow or [])
    print(f"✅ {len(all_new_games)} matchs récupérés")

    new_infos = {}
    for g in all_new_games:
        info = extract_game_info(g)
        if info and info.get("id"):
            new_infos[info["id"]] = info

    historical = load_historical_matches()
    team_matches = build_team_history(historical)

    print(f"📂 Historique chargé : {len(historical)} matchs")
    print(f"📊 Équipes avec historique : {len(team_matches)}")

    candidate_matches = []
    total_skipped = 0

    for gid, base in new_infos.items():
        home_team = base.get("home_team", "")
        away_team = base.get("away_team", "")

        if is_bad_league(base.get("competition", "")):
            total_skipped += 1
            continue

        home_form = get_team_form(home_team, team_matches, last_games=5) if home_team else None
        away_form = get_team_form(away_team, team_matches, last_games=5) if away_team else None

        form_valid = False
        if home_form or away_form:
            if (home_form and home_form.get("matches_used", 0) > 0) or (away_form and away_form.get("matches_used", 0) > 0):
                form_valid = True

        if not form_valid:
            total_skipped += 1
            continue

        h2h_list = get_h2h(historical, home_team, away_team, years=2)
        used_poisson_fallback = False

        if len(h2h_list) >= 2:
            analysis = analyze_h2h(h2h_list, home_team)
        else:
            hm = home_form.get("matches_used", 0) if home_form else 0
            am = away_form.get("matches_used", 0) if away_form else 0

            if hm >= 2 and am >= 2:
                used_poisson_fallback = True
                gf_h = home_form.get("goals_for", 1.2)
                ga_h = home_form.get("goals_against", 1.2)
                gf_a = away_form.get("goals_for", 1.2)
                ga_a = away_form.get("goals_against", 1.2)

                lambda_home = (gf_h * 1.1 + ga_a * 0.9) / 2
                lambda_away = (gf_a * 0.9 + ga_h * 1.1) / 2
                p_home, p_draw, p_away = poisson_probability(lambda_home, lambda_away)

                analysis = {
                    "total_matches": 0,
                    "home_dominance": p_home,
                    "away_dominance": p_away,
                    "draw_rate": p_draw,
                }
            else:
                total_skipped += 1
                continue

        if analysis.get("draw_rate", 0) > DRAW_RATE_MAX:
            total_skipped += 1
            continue

        dom_diff = abs(analysis.get("home_dominance", 0) - analysis.get("away_dominance", 0))
        if dom_diff < DOM_DIFF_MIN:
            total_skipped += 1
            continue

        prediction = generate_prediction_from_analysis(analysis, home_form, away_form)

        if prediction["double_chance"] == "12":
            total_skipped += 1
            continue

        if prediction["confidence"] < CONFIDENCE_THRESHOLD:
            total_skipped += 1
            continue

        if home_form and away_form:
            goal_diff = abs(home_form.get("goals_for", 0) - away_form.get("goals_for", 0))
            if goal_diff < GOAL_DIFF_THRESHOLD:
                total_skipped += 1
                continue

        score = calculate_xpronos_score(analysis, home_form, away_form)
        if score < XPRONOS_THRESHOLD:
            total_skipped += 1
            continue

        local_candidate_score = compute_local_candidate_score(home_form, away_form, analysis, base.get("odds"))

        candidate_matches.append({
            "gid": gid,
            "base": base,
            "home_form": home_form,
            "away_form": away_form,
            "analysis": analysis,
            "prediction": prediction,
            "local_candidate_score": local_candidate_score,
            "xpronos_score": score,
            "used_poisson_fallback": used_poisson_fallback,
        })

    print(f"🎯 Matchs candidats locaux : {len(candidate_matches)}")
    print(f"⚠️ Matchs ignorés : {total_skipped}")

    # Enrichissement ciblé uniquement sur top N
    candidate_matches.sort(key=lambda x: x["local_candidate_score"], reverse=True)
    enriched_ids_predictions = 0
    enriched_ids_pregame = 0

    for idx, item in enumerate(candidate_matches):
        item["provider_signal"] = {"provider_alignment": 0, "provider_confidence": 0}
        item["pregame_signal"] = {"pregame_quality": 0}

        if idx >= TOP_N_ENRICHED_MATCHES:
            continue

        gid = item["gid"]

        if enriched_ids_predictions < MAX_PREDICTIONS_CALLS and budget_remaining(request_state) > 5:
            pred_data = fetch_game_predictions(gid, request_state, enrich_cache)
            item["provider_signal"] = extract_provider_prediction_signal(pred_data)
            enriched_ids_predictions += 1

        if enriched_ids_pregame < MAX_PREGAME_CALLS and budget_remaining(request_state) > 5:
            pregame_data = fetch_pregame_stats(gid, request_state, enrich_cache)
            item["pregame_signal"] = extract_pregame_signal(pregame_data)
            enriched_ids_pregame += 1

    matches = []

    for item in candidate_matches:
        base = item["base"]
        analysis = item["analysis"]
        prediction = item["prediction"]
        home_form = item["home_form"]
        away_form = item["away_form"]
        score = item["xpronos_score"]

        provider_signal = item.get("provider_signal", {})
        pregame_signal = item.get("pregame_signal", {})

        final_conf = prediction["confidence"]
        provider_alignment = provider_signal.get("provider_alignment")
        provider_confidence = provider_signal.get("provider_confidence", 0)

        dc = prediction["double_chance"]

        if provider_alignment:
            aligns = (
                (dc == "1X" and provider_alignment in ("home", "draw")) or
                (dc == "X2" and provider_alignment in ("away", "draw"))
            )
            if aligns:
                final_conf += min(8, int(provider_confidence / 15))
            else:
                final_conf -= min(8, int(provider_confidence / 20))

        final_conf += int((pregame_signal.get("pregame_quality", 0) / 100) * 5)
        final_conf = int(clamp(final_conf, 0, 100))

        if final_conf < CONFIDENCE_THRESHOLD:
            continue

        category = get_category(score)
        badge = get_badge(score)

        odds = base.get("odds")
        value_bet = False
        if odds:
            probs = normalize_odds(odds)
            if probs:
                if dc == "1X":
                    our_prob = analysis.get("home_dominance", 0) + analysis.get("draw_rate", 0)
                    book_prob = probs["home"] + probs["draw"]
                elif dc == "X2":
                    our_prob = analysis.get("away_dominance", 0) + analysis.get("draw_rate", 0)
                    book_prob = probs["away"] + probs["draw"]
                else:
                    our_prob = 0
                    book_prob = 1
                value_bet = our_prob > (book_prob + 0.05)

        final_score = (
            score * 0.35 +
            final_conf * 0.35 +
            item["local_candidate_score"] * 0.20 +
            pregame_signal.get("pregame_quality", 0) * 0.10
        )
        final_score = clamp(final_score, 0, 100)

        match = {
            "id": item["gid"],
            "date": base.get("date", ""),
            "event_date": base.get("start_time", ""),
            "start_time": base.get("start_time", ""),
            "home_team": base.get("home_team", ""),
            "away_team": base.get("away_team", ""),
            "home_logo": None,
            "away_logo": None,
            "league": base.get("competition", ""),
            "competition": base.get("competition", ""),
            "league_logo": None,
            "status": base.get("status_text", ""),
            "home_score": base.get("home_score"),
            "away_score": base.get("away_score"),
            "h2h_analysis": analysis,
            "home_form": home_form,
            "away_form": away_form,
            "prediction": {
                "double_chance": dc,
                "confidence": final_conf,
                "odds": None
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
            "provider_signal": provider_signal,
            "pregame_signal": pregame_signal,
            "used_poisson_fallback": item["used_poisson_fallback"],
            "local_candidate_score": item["local_candidate_score"],
            "data_quality_score": (
                40 +
                (20 if home_form else 0) +
                (20 if away_form else 0) +
                (20 if odds else 0)
            )
        }

        if match["is_finished"] and match["home_score"] is not None and match["away_score"] is not None:
            if dc == "1X":
                match["verified_double"] = match["home_score"] >= match["away_score"]
            elif dc == "X2":
                match["verified_double"] = match["away_score"] >= match["home_score"]

        matches.append(match)

    matches.sort(key=lambda x: x.get("final_score", 0), reverse=True)

    categories = {"simple": [], "pro": [], "vip": []}
    for m in matches:
        categories[m.get("category", "simple")].append(m)

    total_bets = 0
    total_wins = 0
    for m in matches:
        if m.get("is_finished"):
            total_bets += 1
            if m.get("verified_double"):
                total_wins += 1

    roi = safe_division((total_wins - total_bets), total_bets, 0) * 100 if total_bets else 0

    bookmakers = existing_data.get("bookmakers", [])
    if not isinstance(bookmakers, list):
        bookmakers = []

    data = {
        "matches": matches,
        "categories": categories,
        "stats": {
            "total_bets": total_bets,
            "wins": total_wins,
            "roi": round(roi, 1),
            "api_requests_used_today": request_state.get("count", 0),
            "api_budget_remaining": budget_remaining(request_state),
        },
        "bookmakers": bookmakers,
        "generated_at": get_now_utc().isoformat()
    }

    save_json_file(DATA_FILE, data)
    save_enrich_cache(enrich_cache)

    print(f"💾 {DATA_FILE} généré")
    print(f"📈 Simple: {len(categories['simple'])} | Pro: {len(categories['pro'])} | VIP: {len(categories['vip'])}")
    print(f"📦 Budget API restant après run : {budget_remaining(request_state)}")
    print(f"🔁 Enrichissements faits : predictions={enriched_ids_predictions}, pregame={enriched_ids_pregame}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()