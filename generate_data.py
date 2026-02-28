#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_data.py - Script de génération du fichier data.json pour Mr XPRONOS
Utilise le cache global all_matches.json pour les analyses H2H.
Rôle :
- Récupérer les matchs d'aujourd'hui, demain, hier depuis l'API BSD
- Obtenir les prédictions de l'API /predictions/
- Analyser les confrontations directes (H2H) via le cache
- Classer les matchs en Simple, Pro, VIP selon les règles
- Vérifier les pronostics des matchs d'hier
- Sauvegarder le tout dans data.json
- Inclure les données ML complètes pour les analyses VIP
"""

import requests
import json
from datetime import datetime, timedelta
import os
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =======================================================
# CONFIGURATION
# =======================================================
API_TOKEN = os.getenv("BSD_API_TOKEN", "3d0b228fb2f078287b8e6720304f2eea2800cc6d")
BASE_URL = "https://sports.bzzoiro.com/api"
HEADERS = {"Authorization": f"Token {API_TOKEN}"}

# Configuration des retries
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

# Dates cibles
today = datetime.now().date()
tomorrow = today + timedelta(days=1)
yesterday = today - timedelta(days=1)

CACHE_DIR = "cache"
GLOBAL_CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")

print("="*60)
print(f"🚀 GÉNÉRATION DES DONNÉES - {today}")
print("="*60)

# =======================================================
# FONCTIONS DE RÉCUPÉRATION API (pour les matchs récents)
# =======================================================

def fetch_events(date_from, date_to):
    """
    Récupère tous les événements entre deux dates (pagination gérée).
    Retourne une liste d'événements.
    """
    url = f"{BASE_URL}/events/"
    params = {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat()
    }
    all_events = []
    page = 1
    while True:
        params["page"] = page
        try:
            print(f"   📡 Requête events page {page}...")
            resp = session.get(url, headers=HEADERS, params=params, timeout=10)
            if resp.status_code != 200:
                print(f"   ❌ Erreur {resp.status_code}: {resp.text}")
                break
            data = resp.json()
            events = data.get("results", [])
            all_events.extend(events)
            print(f"      → {len(events)} événements reçus")
            if data.get("next") is None:
                break
            page += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            break
    return all_events

def fetch_predictions(upcoming=True):
    """
    Récupère les prédictions de l'API.
    upcoming=True : prédictions à venir, False : prédictions passées.
    """
    url = f"{BASE_URL}/predictions/"
    params = {"upcoming": "true" if upcoming else "false"}
    all_predictions = []
    page = 1
    while True:
        params["page"] = page
        try:
            print(f"   📡 Requête predictions page {page}...")
            resp = session.get(url, headers=HEADERS, params=params, timeout=10)
            if resp.status_code != 200:
                print(f"   ❌ Erreur {resp.status_code}")
                break
            data = resp.json()
            preds = data.get("results", [])
            all_predictions.extend(preds)
            if data.get("next") is None:
                break
            page += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            break
    return all_predictions

# =======================================================
# FONCTIONS D'ANALYSE H2H (UTILISANT LE CACHE GLOBAL)
# =======================================================

def get_h2h_from_cache(team_id_a, team_id_b):
    """
    Récupère l'historique des confrontations entre deux équipes depuis le cache global.
    Retourne une liste de matchs triée par date décroissante.
    """
    if not os.path.exists(GLOBAL_CACHE_FILE):
        print("   ⚠️ Cache global introuvable. Veuillez d'abord exécuter allmatches.py")
        return []

    with open(GLOBAL_CACHE_FILE, 'r', encoding='utf-8') as f:
        all_matches = json.load(f)

    h2h = []
    for m in all_matches:
        home_obj = m.get("home_team_obj")
        away_obj = m.get("away_team_obj")
        if home_obj and away_obj:
            if (home_obj["id"] == team_id_a and away_obj["id"] == team_id_b) or \
               (home_obj["id"] == team_id_b and away_obj["id"] == team_id_a):
                # On ne garde que les matchs terminés avec scores
                if m["status"] == "finished" and m["home_score"] is not None and m["away_score"] is not None:
                    h2h.append({
                        "date": m["event_date"],
                        "home_team": home_obj["name"],
                        "away_team": away_obj["name"],
                        "home_score": m["home_score"],
                        "away_score": m["away_score"],
                        "status": m["status"],
                        "league": m["league"]["name"]
                    })
    # Trier par date décroissante
    h2h.sort(key=lambda x: x["date"], reverse=True)
    return h2h

def analyze_h2h(h2h_list, current_home_team, current_away_team):
    """
    Analyse la liste H2H pour déterminer :
    - Nombre total de matchs
    - Victoires domicile/extérieur/nuls
    - Moyenne de buts
    - Les 4 derniers matchs (filtrés pour ne garder que les terminés)
    """
    home_wins = 0
    away_wins = 0
    draws = 0
    total_goals = 0
    matches_count = 0

    # Les 4 derniers matchs terminés
    last_4 = h2h_list[:4]

    for match in h2h_list:
        matches_count += 1
        total_goals += match["home_score"] + match["away_score"]
        if match["home_score"] > match["away_score"]:
            if match["home_team"] == current_home_team:
                home_wins += 1
            else:
                away_wins += 1
        elif match["home_score"] < match["away_score"]:
            if match["away_team"] == current_home_team:
                home_wins += 1
            else:
                away_wins += 1
        else:
            draws += 1

    goals_avg = total_goals / matches_count if matches_count > 0 else 0
    return {
        "total_matches": matches_count,
        "home_wins": home_wins,
        "away_wins": away_wins,
        "draws": draws,
        "goals_avg": goals_avg,
        "last_4": last_4
    }

def classify_match_h2h(analysis):
    """
    Classification :
    - Si au moins 4 matchs H2H et une équipe a gagné 3 ou 4 fois → VIP
    - Si au moins 5 matchs H2H et une équipe a gagné au moins N-1 fois → VIP
    - Sinon → Simple
    """
    n = analysis["total_matches"]
    if n >= 4:
        if analysis["home_wins"] >= 3 or analysis["away_wins"] >= 3:
            return "vip"
    if n >= 5:
        if analysis["home_wins"] >= n-1 or analysis["away_wins"] >= n-1:
            return "vip"
    return "simple"

def generate_prediction_h2h(analysis, home_team, away_team):
    """
    Génère un pronostic simple basé sur les 4 derniers H2H terminés.
    Retourne un dictionnaire avec double_chance, over_25, confidence.
    """
    last_4 = analysis["last_4"]
    home_wins_last4 = 0
    away_wins_last4 = 0
    draws_last4 = 0
    goals_last4 = []

    for m in last_4:
        goals_last4.append(m["home_score"] + m["away_score"])
        if m["home_score"] > m["away_score"]:
            if m["home_team"] == home_team:
                home_wins_last4 += 1
            else:
                away_wins_last4 += 1
        elif m["home_score"] < m["away_score"]:
            if m["away_team"] == home_team:
                home_wins_last4 += 1
            else:
                away_wins_last4 += 1
        else:
            draws_last4 += 1

    # Double chance
    if home_wins_last4 > away_wins_last4 + draws_last4:
        double_chance = "1X"
    elif away_wins_last4 > home_wins_last4 + draws_last4:
        double_chance = "X2"
    else:
        double_chance = "12"

    # Over/Under 2.5
    avg_goals = sum(goals_last4) / len(goals_last4) if goals_last4 else 2.5
    over_25 = avg_goals > 2.5

    # Confiance basée sur le nombre de matchs analysés (max 95)
    confidence = 50 + (analysis["total_matches"] * 5)
    confidence = min(confidence, 95)

    return {
        "double_chance": double_chance,
        "over_25": over_25,
        "confidence": confidence
    }

# =======================================================
# FONCTIONS DE VÉRIFICATION DES MATCHS D'HIER
# =======================================================

def verify_prediction(match, prediction):
    """
    Vérifie si le pronostic (double chance et over 2.5) est validé par le résultat réel.
    """
    match['verified_double'] = False
    match['verified_over'] = False

    if match['status'] != 'finished':
        return

    home_score = match['home_score']
    away_score = match['away_score']
    if home_score is None or away_score is None:
        return

    total_goals = home_score + away_score

    dc = prediction.get('double_chance', '')
    if dc == '1X':
        match['verified_double'] = (home_score > away_score) or (home_score == away_score)
    elif dc == 'X2':
        match['verified_double'] = (home_score == away_score) or (home_score < away_score)
    elif dc == '12':
        match['verified_double'] = (home_score > away_score) or (home_score < away_score)

    if prediction.get('over_25'):
        match['verified_over'] = total_goals > 2.5
    else:
        match['verified_over'] = total_goals <= 2.5

# =======================================================
# FONCTION PRINCIPALE
# =======================================================

def main():
    print("\n📅 Récupération des matchs du jour, demain, hier...")
    events_today = fetch_events(today, today)
    events_tomorrow = fetch_events(tomorrow, tomorrow)
    events_yesterday = fetch_events(yesterday, yesterday)

    all_events = events_today + events_tomorrow + events_yesterday
    print(f"\n✅ Total événements récupérés : {len(all_events)}")

    if len(all_events) == 0:
        print("❌ Aucun événement récupéré. Conservation de l'ancien fichier.")
        return

    print("\n📈 Récupération des prédictions ML...")
    predictions_upcoming = fetch_predictions(upcoming=True)
    predictions_past = fetch_predictions(upcoming=False)
    all_predictions = predictions_upcoming + predictions_past
    print(f"✅ {len(all_predictions)} prédictions récupérées")

    pred_dict = {p['event']['id']: p for p in all_predictions}

    data = {
        "matches": [],
        "categories": {"simple": [], "pro": [], "vip": []},
        "bookmakers": [
            {"name": "1xBet", "logo": "/assets/images/1xbet.png", "url": "https://affiliation.com/1xbet"},
            {"name": "1win", "logo": "/assets/images/1win.png", "url": "https://affiliation.com/1win"},
            {"name": "Betwinner", "logo": "/assets/images/betwinner.png", "url": "https://affiliation.com/betwinner"},
            {"name": "Melbet", "logo": "/assets/images/melbet.png", "url": "https://affiliation.com/melbet"},
            {"name": "Linebet", "logo": "/assets/images/linebet.png", "url": "https://affiliation.com/linebet"},
            {"name": "888starz", "logo": "/assets/images/888starz.png", "url": "https://affiliation.com/888starz"}
        ]
    }

    for idx, event in enumerate(all_events, 1):
        print(f"\n🔍 Analyse match {idx}/{len(all_events)}")
        match_id = event["id"]
        home_team_obj = event.get("home_team_obj")
        away_team_obj = event.get("away_team_obj")
        if not home_team_obj or not away_team_obj:
            print("   ⚠️  Équipes manquantes, ignoré")
            continue

        league = event["league"]
        event_date = event["event_date"][:10]
        event_datetime = event["event_date"]

        print(f"   {home_team_obj['name']} vs {away_team_obj['name']} ({league['name']})")

        h2h = get_h2h_from_cache(home_team_obj["id"], away_team_obj["id"])
        print(f"   → {len(h2h)} confrontations H2H trouvées dans le cache")

        analysis_h2h = analyze_h2h(h2h, home_team_obj["name"], away_team_obj["name"])
        prediction_h2h = generate_prediction_h2h(analysis_h2h, home_team_obj["name"], away_team_obj["name"])

        if analysis_h2h["home_wins"] > analysis_h2h["away_wins"]:
            prediction_h2h["confidence"] = min(prediction_h2h["confidence"] + 10, 100)

        ml_pred = pred_dict.get(match_id)
        ml_full = None
        if ml_pred:
            # Sauvegarder toutes les données ML pour les analyses VIP
            ml_full = {
                "prob_home_win": ml_pred.get('prob_home_win'),
                "prob_draw": ml_pred.get('prob_draw'),
                "prob_away_win": ml_pred.get('prob_away_win'),
                "predicted_result": ml_pred.get('predicted_result'),
                "expected_home_goals": ml_pred.get('expected_home_goals'),
                "expected_away_goals": ml_pred.get('expected_away_goals'),
                "prob_over_25": ml_pred.get('prob_over_25'),
                "over_25_recommend": ml_pred.get('over_25_recommend'),
                "prob_btts_yes": ml_pred.get('prob_btts_yes'),
                "btts_recommend": ml_pred.get('btts_recommend'),
                "most_likely_score": ml_pred.get('most_likely_score'),
                "favorite": ml_pred.get('favorite'),
                "favorite_prob": ml_pred.get('favorite_prob'),
                "confidence": ml_pred.get('confidence')
            }

            prob_home = ml_pred.get('prob_home_win', 0)
            prob_away = ml_pred.get('prob_away_win', 0)
            predicted_result = ml_pred.get('predicted_result', '')
            if prob_home > 55 or prob_away > 55:
                if predicted_result == "H":
                    double_chance_ml = "1X"
                elif predicted_result == "A":
                    double_chance_ml = "X2"
                else:
                    double_chance_ml = "12"
                over_25_ml = ml_pred.get('over_25_recommend', False)
                raw_confidence = ml_pred.get('confidence', 0.5)
                if raw_confidence <= 1:
                    confidence_ml = round(raw_confidence * 100, 1)
                else:
                    confidence_ml = round(raw_confidence, 1)
                prediction_ml = {
                    "double_chance": double_chance_ml,
                    "over_25": over_25_ml,
                    "confidence": confidence_ml,
                    "source": "ML"
                }
                category = "pro"
                prediction_used = prediction_ml
            else:
                category = classify_match_h2h(analysis_h2h)
                prediction_used = prediction_h2h
        else:
            category = classify_match_h2h(analysis_h2h)
            prediction_used = prediction_h2h

        home_logo = f"https://sports.bzzoiro.com/img/team/{home_team_obj['api_id']}/?token={API_TOKEN}"
        away_logo = f"https://sports.bzzoiro.com/img/team/{away_team_obj['api_id']}/?token={API_TOKEN}"
        league_logo = f"https://sports.bzzoiro.com/img/league/{league['api_id']}/?token={API_TOKEN}"

        match_data = {
            "id": match_id,
            "date": event_date,
            "event_date": event_datetime,
            "home_team": home_team_obj["name"],
            "away_team": away_team_obj["name"],
            "home_logo": home_logo,
            "away_logo": away_logo,
            "league": league["name"],
            "league_logo": league_logo,
            "venue": event.get("venue", ""),
            "status": event["status"],
            "home_score": event["home_score"],
            "away_score": event["away_score"],
            "h2h_analysis": analysis_h2h,
            "prediction": prediction_used,
            "category": category,
            "verified_double": False,
            "verified_over": False,
            "ml_full": ml_full  # Données ML complètes pour analyses VIP
        }

        if event_date == yesterday.isoformat():
            verify_prediction(match_data, prediction_used)
            if match_data["verified_double"] or match_data["verified_over"]:
                print(f"   ✅ Vérification : Double chance {'OK' if match_data['verified_double'] else 'KO'}, Over {'OK' if match_data['verified_over'] else 'KO'}")

        data["matches"].append(match_data)
        data["categories"][category].append(match_data)

        print(f"   ✅ Catégorie: {category}, Confiance: {prediction_used['confidence']}%")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("\n💾 Fichier data.json généré avec succès !")

if __name__ == "__main__":
    main()