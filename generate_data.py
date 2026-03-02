#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_data.py - VERSION PRO MR XPRONOS
Génère data.json avec matchs + score XPRONOS + XGBoost + H2H optimisé
Version avec calcul de la forme des équipes à partir du cache global.
"""

import requests
import json
import os
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
import joblib
import xgboost as xgb
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =======================================================
# CONFIGURATION & LOGGING
# =======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_TOKEN = os.environ.get("BSD_API_TOKEN")
if not API_TOKEN:
    raise ValueError("❌ BSD_API_TOKEN manquant dans les variables d'environnement")

BASE_URL = "https://sports.bzzoiro.com/api"
HEADERS = {"Authorization": f"Token {API_TOKEN}"}
session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

today = datetime.now().date()
tomorrow = today + timedelta(days=1)
yesterday = today - timedelta(days=1)

CACHE_DIR = "cache"
GLOBAL_CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")
DATA_FILE = "data.json"
MODEL_FILE = "xpronos_model.joblib"

logger.info(f"🚀 GÉNÉRATION DES DONNÉES - {today}")

# =======================================================
# FONCTIONS API
# =======================================================
def fetch_events(date_from, date_to):
    url = f"{BASE_URL}/events/"
    params = {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()}
    all_events = []
    page = 1
    while True:
        params["page"] = page
        try:
            resp = session.get(url, headers=HEADERS, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            all_events.extend(data.get("results", []))
            if not data.get("next"):
                break
            page += 1
            time.sleep(0.6)
        except Exception as e:
            logger.error(f"❌ Events page {page}: {e}")
            break
    return all_events

def fetch_predictions(upcoming=True):
    url = f"{BASE_URL}/predictions/"
    params = {"upcoming": "true" if upcoming else "false"}
    all_preds = []
    page = 1
    while True:
        params["page"] = page
        try:
            resp = session.get(url, headers=HEADERS, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            all_preds.extend(data.get("results", []))
            if not data.get("next"):
                break
            page += 1
            time.sleep(0.6)
        except Exception as e:
            logger.error(f"❌ Predictions page {page}: {e}")
            break
    return all_preds

# =======================================================
# CONSTRUCTION DE L'HISTORIQUE DES ÉQUIPES (pour la forme)
# =======================================================
def build_team_history(global_cache):
    """
    Construit un dictionnaire pour chaque équipe avec la liste de ses matchs triés.
    Chaque élément : (date, match, side) où side = 'home' ou 'away'.
    """
    team_matches = defaultdict(list)
    for m in global_cache:
        if m.get("status") != "finished":
            continue
        home_obj = m.get("home_team_obj")
        away_obj = m.get("away_team_obj")
        if not home_obj or not away_obj:
            continue
        try:
            date = datetime.fromisoformat(m["event_date"].replace('Z', '+00:00'))
        except:
            continue
        team_matches[home_obj["id"]].append((date, m, "home"))
        team_matches[away_obj["id"]].append((date, m, "away"))
    # Trier chaque liste par date
    for team in team_matches:
        team_matches[team].sort(key=lambda x: x[0])
    logger.info(f"✅ Historique des équipes construit pour {len(team_matches)} équipes")
    return team_matches

def get_team_form(team_id, match_date, team_matches, n=5):
    """
    Retourne les statistiques des n derniers matchs de l'équipe avant match_date.
    Retourne un dict avec : matches_played, wins, draws, losses, goals_for, goals_against, avg_goals_for, avg_goals_against.
    Si pas assez de matchs, retourne des valeurs par défaut (0 ou moyenne neutre).
    """
    matches = team_matches.get(team_id, [])
    # On prend les matchs dont la date < match_date
    past_matches = [(date, m, side) for date, m, side in matches if date < match_date]
    # On prend les n derniers
    last_n = past_matches[-n:]
    if not last_n:
        return {
            "matches_played": 0,
            "wins": 0, "draws": 0, "losses": 0,
            "goals_for": 0, "goals_against": 0,
            "avg_goals_for": 1.5,  # valeur neutre
            "avg_goals_against": 1.5
        }
    wins = draws = losses = 0
    goals_for = goals_against = 0
    for date, m, side in last_n:
        if side == "home":
            gf = m["home_score"]
            ga = m["away_score"]
        else:
            gf = m["away_score"]
            ga = m["home_score"]
        goals_for += gf
        goals_against += ga
        if gf > ga:
            wins += 1
        elif gf < ga:
            losses += 1
        else:
            draws += 1
    played = len(last_n)
    return {
        "matches_played": played,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "avg_goals_for": round(goals_for / played, 2),
        "avg_goals_against": round(goals_against / played, 2)
    }

# =======================================================
# H2H ULTRA OPTIMISÉ (Index)
# =======================================================
def build_h2h_index(global_cache):
    h2h_index = {}
    for m in global_cache:
        if m.get("status") != "finished" or not m.get("home_score") or not m.get("away_score"):
            continue
        home_obj = m.get("home_team_obj")
        away_obj = m.get("away_team_obj")
        if not home_obj or not away_obj:
            continue
        h = home_obj["id"]
        a = away_obj["id"]
        key = tuple(sorted([h, a]))
        if key not in h2h_index:
            h2h_index[key] = []
        h2h_index[key].append({
            "date": m["event_date"],
            "home_team": home_obj["name"],
            "away_team": away_obj["name"],
            "home_score": m["home_score"],
            "away_score": m["away_score"],
            "league": m["league"]["name"]
        })
    logger.info(f"✅ Index H2H construit : {len(h2h_index)} paires d'équipes")
    return h2h_index

def get_h2h_from_cache(team_id_a, team_id_b, h2h_index):
    key = tuple(sorted([team_id_a, team_id_b]))
    h2h = h2h_index.get(key, [])
    h2h.sort(key=lambda x: x["date"], reverse=True)
    return h2h[:20]  # 20 derniers suffisent

def weight_by_date(date_str):
    try:
        match_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        days = (datetime.now() - match_date).days
        return 1.8 if days < 180 else 1.3 if days < 365 else 1.0
    except:
        return 1.0

def analyze_h2h(h2h_list, current_home, current_away):
    home_score = away_score = draws_score = total_goals = matches_count = over25_count = btts_count = 0
    for match in h2h_list:
        weight = weight_by_date(match["date"])
        matches_count += 1
        total_goals += (match["home_score"] + match["away_score"]) * weight
        if match["home_score"] > match["away_score"]:
            (home_score if match["home_team"] == current_home else away_score) += weight
        elif match["home_score"] < match["away_score"]:
            (away_score if match["home_team"] == current_home else home_score) += weight
        else:
            draws_score += weight
        if match["home_score"] + match["away_score"] > 2.5:
            over25_count += 1
        if match["home_score"] > 0 and match["away_score"] > 0:
            btts_count += 1

    total_weighted = home_score + away_score + draws_score or 1
    goals_avg = total_goals / matches_count if matches_count else 2.5

    return {
        "total_matches": matches_count,
        "home_dominance": round(home_score / total_weighted, 3),
        "away_dominance": round(away_score / total_weighted, 3),
        "draws_percent": round(draws_score / total_weighted * 100, 1),
        "goals_avg": round(goals_avg, 2),
        "over25_percent": round(over25_count / matches_count * 100, 1) if matches_count else 50,
        "btts_percent": round(btts_count / matches_count * 100, 1) if matches_count else 50,
        "last_5": h2h_list[:5]
    }

# =======================================================
# XGBoost MODEL
# =======================================================
def train_or_load_model(training_data):
    if os.path.exists(MODEL_FILE):
        model = joblib.load(MODEL_FILE)
        logger.info("✅ Modèle XGBoost chargé")
        return model

    if not training_data or len(training_data) < 10:
        logger.warning("⚠️ Pas assez de données d'entraînement (<10) → modèle désactivé")
        return None

    X = np.array([
        [e["form_diff"], e["h2h_diff"], e["over25_percent"], e["btts_percent"], e["goals_avg"]]
        for e in training_data
    ])
    y = np.array([e["result"] for e in training_data])  # 0=Home, 1=Draw, 2=Away

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric="mlogloss"
    )
    model.fit(X, y)
    joblib.dump(model, MODEL_FILE)
    logger.info("✅ Nouveau modèle XGBoost entraîné et sauvegardé")
    return model

# =======================================================
# SCORE XPRONOS + BADGE (triple validation)
# =======================================================
def calculate_xpronos_score(home_form, away_form, analysis, api_pred, ml_pred):
    score = 0
    # Différence de forme (30 pts)
    form_diff = abs(home_form.get("avg_goals_for", 1.5) - away_form.get("avg_goals_for", 1.5)) * 10  # exemple
    # On peut aussi utiliser les victoires, etc. Simplifions :
    form_strength = (home_form.get("wins", 0) - away_form.get("wins", 0)) * 5
    score += min(30, abs(form_strength) + form_diff)

    # H2H (20 pts)
    h2h_diff = abs(analysis["home_dominance"] - analysis["away_dominance"]) * 100
    score += min(20, h2h_diff * 2)

    # Over 2.5 (15 pts)
    if analysis["over25_percent"] > 60:
        score += 15
    # BTTS (10 pts)
    if analysis["btts_percent"] > 60:
        score += 10
    # Triple validation (25 pts)
    if api_pred and ml_pred and api_pred == ml_pred:
        score += 25

    return min(score, 100)

def get_badge(score):
    if score >= 90: return "🏆 PREMIUM LOCK"
    if score >= 85: return "💎 VIP ELITE"
    if score >= 75: return "🔥 ULTRA SAFE"
    return ""

# =======================================================
# VÉRIFICATION & ROI
# =======================================================
def verify_prediction(match, prediction):
    if match["status"] != "finished" or match.get("home_score") is None:
        return
    total = match["home_score"] + match["away_score"]
    dc = prediction.get("double_chance", "")
    match["verified_double"] = (
        (dc == "1X" and match["home_score"] >= match["away_score"]) or
        (dc == "X2" and match["home_score"] <= match["away_score"]) or
        (dc == "12")
    )
    match["verified_over25"] = total > 2.5

def update_bankroll(matches):
    bets = wins = 0
    for m in matches:
        if m["status"] == "finished" and m.get("verified_double") is not None:
            bets += 1
            if m["verified_double"]:
                wins += 1
    roi = (wins / bets * 100) if bets else 0
    return {"total_bets": bets, "wins": wins, "roi": round(roi, 2)}

# =======================================================
# MAIN
# =======================================================
def main():
    logger.info("📅 Récupération événements + prédictions...")
    events_today = fetch_events(today, today)
    events_tomorrow = fetch_events(tomorrow, tomorrow)
    events_yesterday = fetch_events(yesterday, yesterday)
    events = events_today + events_tomorrow + events_yesterday

    predictions = fetch_predictions(True) + fetch_predictions(False)
    pred_dict = {p['event']['id']: p for p in predictions}

    # Charger le cache global
    if not os.path.exists(GLOBAL_CACHE_FILE):
        logger.error("❌ Cache global introuvable. Exécutez d'abord allmatches.py")
        return
    with open(GLOBAL_CACHE_FILE, 'r', encoding='utf-8') as f:
        global_cache = json.load(f)
    logger.info(f"📂 Cache global chargé : {len(global_cache)} matchs")

    # Construire l'index H2H et l'historique des équipes
    h2h_index = build_h2h_index(global_cache)
    team_matches = build_team_history(global_cache)

    # Charger ancien data pour entraînement et fusion
    old_data = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            old_data = json.load(f)

    # Préparer les données d'entraînement à partir de l'ancien fichier (matchs terminés avec analyse)
    training_data = []
    for m in old_data.get("matches", []):
        if m["status"] == "finished" and "h2h_analysis" in m and "xpronos_score" in m:
            # Calculer la forme à partir du cache pour ce match (mais on a pas l'info, on utilise une valeur par défaut)
            # Ici on pourrait récupérer la forme du match depuis le cache, mais c'est complexe.
            # On va utiliser les données de l'ancien fichier telles quelles.
            form_home = m.get("form_home", {}).get("avg_goals_for", 1.5)
            form_away = m.get("form_away", {}).get("avg_goals_for", 1.5)
            analysis = m["h2h_analysis"]
            training_data.append({
                "form_diff": abs(form_home - form_away),
                "h2h_diff": abs(analysis["home_dominance"] - analysis["away_dominance"]) * 100,
                "over25_percent": analysis["over25_percent"],
                "btts_percent": analysis["btts_percent"],
                "goals_avg": analysis["goals_avg"],
                "result": 0 if m["home_score"] > m["away_score"] else 1 if m["home_score"] == m["away_score"] else 2
            })

    model = train_or_load_model(training_data)

    new_matches = []
    categories = {"simple": [], "pro": [], "vip": []}

    for event in events:
        match_id = event.get("id")
        if not isinstance(match_id, int):
            continue
        home = event.get("home_team_obj")
        away = event.get("away_team_obj")
        if not home or not away:
            continue
        league = event.get("league", {})

        # Date du match
        try:
            match_date = datetime.fromisoformat(event["event_date"].replace('Z', '+00:00'))
        except:
            match_date = datetime.now()

        # Récupérer la forme des équipes
        home_form = get_team_form(home["id"], match_date, team_matches, 5)
        away_form = get_team_form(away["id"], match_date, team_matches, 5)

        # Récupérer H2H
        h2h_list = get_h2h_from_cache(home["id"], away["id"], h2h_index)
        analysis = analyze_h2h(h2h_list, home["name"], away["name"])

        # Prédictions
        ml_pred = pred_dict.get(match_id)
        api_pred = None
        if ml_pred:
            prob_home = ml_pred.get("prob_home_win", 0)
            prob_away = ml_pred.get("prob_away_win", 0)
            api_pred = "H" if prob_home > 55 else "A" if prob_away > 55 else "D"

        # ML XGBoost
        ml_class = None
        if model:
            # Calculer les features pour ce match
            form_diff = abs(home_form.get("avg_goals_for", 1.5) - away_form.get("avg_goals_for", 1.5))
            h2h_diff = abs(analysis["home_dominance"] - analysis["away_dominance"]) * 100
            X_ml = np.array([[form_diff, h2h_diff, analysis["over25_percent"], analysis["btts_percent"], analysis["goals_avg"]]])
            ml_class = int(model.predict(X_ml)[0])
            ml_class = "H" if ml_class == 0 else "D" if ml_class == 1 else "A"

        # Score final
        score = calculate_xpronos_score(home_form, away_form, analysis, api_pred, ml_class)
        badge = get_badge(score)
        category = "vip" if score >= 85 else "pro" if score >= 70 else "simple"

        # Construction match
        match_data = {
            "id": match_id,
            "date": event["event_date"][:10],
            "event_date": event["event_date"],
            "home_team": home["name"], "away_team": away["name"],
            "home_logo": f"https://sports.bzzoiro.com/img/team/{home['api_id']}/?token={API_TOKEN}",
            "away_logo": f"https://sports.bzzoiro.com/img/team/{away['api_id']}/?token={API_TOKEN}",
            "league": league.get("name", "Inconnue"),
            "league_logo": f"https://sports.bzzoiro.com/img/league/{league.get('api_id', '')}/?token={API_TOKEN}",
            "status": event["status"],
            "home_score": event.get("home_score"),
            "away_score": event.get("away_score"),
            "home_form": home_form,
            "away_form": away_form,
            "h2h_analysis": analysis,
            "prediction": {
                "double_chance": "1X" if analysis["home_dominance"] > 0.55 else "X2" if analysis["away_dominance"] > 0.55 else "12",
                "over25": analysis["over25_percent"] > 60,
                "confidence": min(50 + analysis["total_matches"] * 3, 95)
            },
            "xpronos_score": score,
            "badge": badge,
            "category": category,
            "ml_prediction": ml_class,
            "api_prediction": api_pred
        }

        if event["event_date"][:10] == yesterday.isoformat():
            verify_prediction(match_data, match_data["prediction"])

        new_matches.append(match_data)
        categories[category].append(match_data)
        logger.debug(f"✅ {home['name']} vs {away['name']} → Score {score} {badge}")

    # Fusion avec anciens matchs
    old_matches_by_id = {m['id']: m for m in old_data.get('matches', [])}
    new_ids = {m['id'] for m in new_matches}
    for old_id, old_match in old_matches_by_id.items():
        if old_id not in new_ids:
            new_matches.append(old_match)
            categories[old_match['category']].append(old_match)
            logger.debug(f"📌 Conservation ancien match {old_id}")

    stats = update_bankroll(new_matches)
    data = {
        "matches": new_matches,
        "categories": categories,
        "stats": stats,
        "last_update": datetime.now().isoformat(),
        "bookmakers": old_data.get("bookmakers", [
            {"name": "1xBet", "logo": "assets/images/1xbet.png", "url": "https://affiliation.com/1xbet"},
            {"name": "Betwinner", "logo": "assets/images/betwinner.png", "url": "https://affiliation.com/betwinner"}
        ])
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"💾 {DATA_FILE} généré avec {len(new_matches)} matchs | ROI: {stats['roi']}%")

if __name__ == "__main__":
    main()