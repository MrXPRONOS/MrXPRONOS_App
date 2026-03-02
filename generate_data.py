#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_data.py - Génère data.json avec les matchs du jour/demain/hier,
les prédictions ML et les analyses H2H améliorées.
Conserve les 14 derniers jours pour l'historique.
Récupère les scores depuis les prédictions passées.
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
API_TOKEN = os.environ.get("BSD_API_TOKEN")
if not API_TOKEN:
    raise ValueError("La variable d'environnement BSD_API_TOKEN n'est pas définie")

BASE_URL = "https://sports.bzzoiro.com/api"
HEADERS = {"Authorization": f"Token {API_TOKEN}"}

session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

today = datetime.now().date()
tomorrow = today + timedelta(days=1)
yesterday = today - timedelta(days=1)
fourteen_days_ago = today - timedelta(days=14)

CACHE_DIR = "cache"
GLOBAL_CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")
DATA_FILE = "data.json"

print("="*60)
print(f"🚀 GÉNÉRATION DES DONNÉES - {today}")
print("="*60)

# =======================================================
# FONCTIONS DE RÉCUPÉRATION API
# =======================================================

def fetch_events(date_from, date_to):
    url = f"{BASE_URL}/events/"
    params = {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()}
    all_events = []
    page = 1
    while True:
        params["page"] = page
        try:
            print(f"   📡 Requête events page {page}...")
            resp = session.get(url, headers=HEADERS, params=params, timeout=10)
            if resp.status_code != 200:
                break
            data = resp.json()
            events = data.get("results", [])
            all_events.extend(events)
            if data.get("next") is None:
                break
            page += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            break
    return all_events

def fetch_predictions(upcoming=True):
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
# FONCTIONS D'ANALYSE H2H
# =======================================================

def weight_by_date(date_str):
    try:
        match_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        days_old = (datetime.now() - match_date).days
        if days_old < 180:
            return 1.5
        elif days_old < 365:
            return 1.2
        else:
            return 1.0
    except:
        return 1.0

def get_h2h_from_cache(team_id_a, team_id_b, global_cache):
    h2h = []
    for m in global_cache:
        home_obj = m.get("home_team_obj")
        away_obj = m.get("away_team_obj")
        if home_obj and away_obj:
            if (home_obj["id"] == team_id_a and away_obj["id"] == team_id_b) or \
               (home_obj["id"] == team_id_b and away_obj["id"] == team_id_a):
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
    h2h.sort(key=lambda x: x["date"], reverse=True)
    return h2h

def analyze_h2h(h2h_list, current_home_team, current_away_team):
    home_score = 0.0
    away_score = 0.0
    draws_score = 0.0
    total_goals = 0
    matches_count = 0
    last_4 = h2h_list[:4]

    for match in h2h_list:
        weight = weight_by_date(match["date"])
        matches_count += 1
        total_goals += (match["home_score"] + match["away_score"]) * weight
        if match["home_score"] > match["away_score"]:
            if match["home_team"] == current_home_team:
                home_score += weight
            else:
                away_score += weight
        elif match["home_score"] < match["away_score"]:
            if match["away_team"] == current_home_team:
                home_score += weight
            else:
                away_score += weight
        else:
            draws_score += weight

    total_weighted = home_score + away_score + draws_score
    if total_weighted > 0:
        home_dominance = home_score / total_weighted
        away_dominance = away_score / total_weighted
    else:
        home_dominance = away_dominance = 0.0

    goals_avg = total_goals / matches_count if matches_count > 0 else 2.5

    return {
        "total_matches": matches_count,
        "home_dominance": round(home_dominance, 3),
        "away_dominance": round(away_dominance, 3),
        "goals_avg": round(goals_avg, 2),
        "last_4": last_4
    }

def generate_prediction_h2h(analysis):
    if analysis["home_dominance"] > analysis["away_dominance"] + 0.1:
        double_chance = "1X"
    elif analysis["away_dominance"] > analysis["home_dominance"] + 0.1:
        double_chance = "X2"
    else:
        double_chance = "12"

    confidence = 50 + (analysis["total_matches"] * 5)
    confidence = min(confidence, 95)
    if max(analysis["home_dominance"], analysis["away_dominance"]) > 0.7:
        confidence = min(confidence + 10, 100)
    return {
        "double_chance": double_chance,
        "confidence": confidence
    }

# =======================================================
# FONCTIONS DE CALCUL DU SCORE DE CONFIANCE
# =======================================================

def calculate_confidence_score(analysis, ml_pred, agreement):
    score = 0
    if agreement:
        score += 50

    if ml_pred:
        prob_home = ml_pred.get('prob_home_win', 0)
        prob_away = ml_pred.get('prob_away_win', 0)
        prob_draw = ml_pred.get('prob_draw', 0)
        max_prob = max(prob_home, prob_away, prob_draw)
        score += min(20, int(max_prob / 5))
        if max_prob > 65:
            score += 5

    dominance = max(analysis["home_dominance"], analysis["away_dominance"])
    score += min(20, int(dominance * 30))

    score += min(10, analysis["total_matches"] * 2)

    return min(score, 100)

def get_category(score):
    if score >= 85:
        return "vip"
    elif score >= 70:
        return "pro"
    else:
        return "simple"

def get_badge(score):
    if score >= 90:
        return "🏆 PREMIUM LOCK"
    elif score >= 85:
        return "💎 VIP ELITE"
    elif score >= 75:
        return "🔥 ULTRA SAFE"
    return ""

# =======================================================
# FONCTIONS DE VÉRIFICATION
# =======================================================

def verify_prediction(match, prediction):
    match['verified_double'] = False

    if match['status'] != 'finished':
        return

    home_score = match['home_score']
    away_score = match['away_score']
    if home_score is None or away_score is None:
        return

    dc = prediction.get('double_chance', '')

    if dc == '1X':
        match['verified_double'] = (home_score > away_score) or (home_score == away_score)
    elif dc == 'X2':
        match['verified_double'] = (home_score == away_score) or (home_score < away_score)
    elif dc == '12':
        match['verified_double'] = (home_score > away_score) or (home_score < away_score)

def update_bankroll(matches):
    total_bets = 0
    wins = 0
    for m in matches:
        if m["status"] == "finished" and (m.get("verified_double") is not None):
            total_bets += 1
            if m["verified_double"]:
                wins += 1
    roi = (wins / total_bets * 100) if total_bets else 0
    return {"total_bets": total_bets, "wins": wins, "roi": round(roi, 2)}

# =======================================================
# FONCTION PRINCIPALE
# =======================================================

def main():
    print("\n📅 Récupération des matchs du jour, demain, hier...")
    events_today = fetch_events(today, today)
    events_tomorrow = fetch_events(tomorrow, tomorrow)
    events_yesterday = fetch_events(yesterday, yesterday)

    all_new_events = events_today + events_tomorrow + events_yesterday
    print(f"\n✅ {len(all_new_events)} événements récupérés")

    # Récupérer les prédictions passées pour obtenir les scores
    print("\n📈 Récupération des prédictions passées (pour les scores)...")
    past_predictions = fetch_predictions(upcoming=False)
    # Créer un dictionnaire des scores par event_id
    past_scores = {}
    for p in past_predictions:
        event = p.get('event')
        if event:
            event_id = event.get('id')
            home_score = event.get('home_score')
            away_score = event.get('away_score')
            if home_score is not None and away_score is not None:
                past_scores[event_id] = {'home_score': home_score, 'away_score': away_score}

    # Récupérer les prédictions à venir (pour la comparaison)
    upcoming_predictions = fetch_predictions(upcoming=True)
    all_predictions = upcoming_predictions + past_predictions
    pred_dict = {p['event']['id']: p for p in all_predictions}

    # Charger ancien fichier
    old_data = {}
    old_matches_by_id = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
            old_matches_by_id = {m['id']: m for m in old_data.get('matches', [])}
        print(f"📂 Ancien fichier chargé : {len(old_matches_by_id)} matchs")

    # Charger cache global
    global_cache = []
    if os.path.exists(GLOBAL_CACHE_FILE):
        with open(GLOBAL_CACHE_FILE, 'r', encoding='utf-8') as f:
            global_cache = json.load(f)
        print(f"📂 Cache global chargé : {len(global_cache)} matchs")

    new_matches = []
    categories = {"simple": [], "pro": [], "vip": []}

    for event in all_new_events:
        print(f"\n🔍 Analyse match {event.get('id', 'inconnu')}")
        match_id = event.get("id")
        if not isinstance(match_id, int):
            continue

        home_obj = event.get("home_team_obj")
        away_obj = event.get("away_team_obj")
        if not home_obj or not away_obj:
            continue

        league = event["league"]
        event_date = event["event_date"][:10]
        event_datetime = event["event_date"]

        print(f"   {home_obj['name']} vs {away_obj['name']} ({league['name']})")

        h2h = get_h2h_from_cache(home_obj["id"], away_obj["id"], global_cache)
        print(f"   → {len(h2h)} confrontations H2H")

        analysis = analyze_h2h(h2h, home_obj["name"], away_obj["name"])
        prediction_h2h = generate_prediction_h2h(analysis)

        ml_pred = pred_dict.get(match_id)
        api_double_chance = None
        api_prob = 0
        if ml_pred:
            predicted_result = ml_pred.get('predicted_result', '')
            if predicted_result == "H":
                api_double_chance = "1X"
                api_prob = ml_pred.get('prob_home_win', 0)
            elif predicted_result == "A":
                api_double_chance = "X2"
                api_prob = ml_pred.get('prob_away_win', 0)
            elif predicted_result == "D":
                api_double_chance = "12"
                api_prob = ml_pred.get('prob_draw', 0)

        # Vérifier l'accord
        agreement = (prediction_h2h["double_chance"] == api_double_chance) if api_double_chance else False

        if not agreement:
            print(f"   ❌ Pas d'accord H2H/API, match ignoré")
            continue

        # Calcul du score de confiance
        score = calculate_confidence_score(analysis, ml_pred, agreement)
        badge = get_badge(score)
        category = get_category(score)

        # Construction de l'objet match
        home_logo = f"https://sports.bzzoiro.com/img/team/{home_obj['api_id']}/?token={API_TOKEN}"
        away_logo = f"https://sports.bzzoiro.com/img/team/{away_obj['api_id']}/?token={API_TOKEN}"
        league_logo = f"https://sports.bzzoiro.com/img/league/{league['api_id']}/?token={API_TOKEN}"

        match_data = {
            "id": match_id,
            "date": event_date,
            "event_date": event_datetime,
            "home_team": home_obj["name"],
            "away_team": away_obj["name"],
            "home_logo": home_logo,
            "away_logo": away_logo,
            "league": league["name"],
            "league_logo": league_logo,
            "venue": event.get("venue", ""),
            "status": event["status"],
            "home_score": event["home_score"],
            "away_score": event["away_score"],
            "h2h_analysis": analysis,
            "prediction": {
                "double_chance": prediction_h2h["double_chance"],
                "confidence": score
            },
            "xpronos_score": score,
            "badge": badge,
            "category": category,
            "verified_double": False,
            "ml_full": ml_pred
        }

        # =======================================================
        # CORRECTION DES SCORES MANQUANTS
        # =======================================================
        try:
            # Si le match est terminé mais que les scores sont absents, on cherche dans past_scores
            if (match_data["status"] == "finished" or event_date < today.isoformat()) and (match_data["home_score"] is None or match_data["away_score"] is None):
                if match_id in past_scores:
                    match_data["home_score"] = past_scores[match_id]["home_score"]
                    match_data["away_score"] = past_scores[match_id]["away_score"]
                    print(f"   📥 Scores récupérés depuis les prédictions passées pour {match_id}")
                else:
                    # Si pas dans past_scores, on utilise l'ancien fichier
                    old_match = old_matches_by_id.get(match_id)
                    if old_match:
                        match_data["home_score"] = old_match.get("home_score")
                        match_data["away_score"] = old_match.get("away_score")
                        print(f"   📥 Scores récupérés depuis l'ancien fichier pour {match_id}")
        except Exception as e:
            print(f"   ⚠️ Erreur récupération scores match {match_id}: {e}")

        # =======================================================
        # CORRECTION ROBUSTE DU STATUT POUR LES MATCHS PASSÉS
        # =======================================================
        try:
            event_dt = datetime.fromisoformat(event_datetime.replace('Z', '+00:00'))
            match_date = event_dt.date()

            if match_data["home_score"] is not None and match_data["away_score"] is not None:
                match_data["status"] = "finished"
            elif match_date < today:
                match_data["status"] = "finished"
        except Exception as e:
            print(f"   ⚠️ Erreur correction statut match {match_id}: {e}")

        # Vérification du résultat
        if match_data["status"] == "finished" and match_data.get("home_score") is not None:
            verify_prediction(match_data, match_data["prediction"])

        new_matches.append(match_data)
        categories[category].append(match_data)
        print(f"   ✅ Score: {score} - {badge} - Catégorie: {category}")

    # Fusion avec anciens matchs (pour conserver l'historique des 14 derniers jours)
    # On garde tous les anciens matchs dont la date est >= fourteen_days_ago
    for old_id, old_match in old_matches_by_id.items():
        try:
            old_date_str = old_match.get('event_date')
            if not old_date_str:
                continue
            old_date = datetime.fromisoformat(old_date_str.replace('Z', '+00:00')).date()
            if old_date >= fourteen_days_ago:
                if old_id not in {m['id'] for m in new_matches}:
                    # Mise à jour du statut si nécessaire
                    if old_date < today and old_match['status'] != 'finished':
                        old_match['status'] = 'finished'
                        if old_match.get('home_score') is not None and old_match.get('away_score') is not None:
                            verify_prediction(old_match, old_match['prediction'])
                    new_matches.append(old_match)
                    categories[old_match['category']].append(old_match)
        except:
            pass

    # Trier les matchs par date (les plus récents en premier)
    new_matches.sort(key=lambda x: x['event_date'], reverse=True)

    stats = update_bankroll(new_matches)

    data = {
        "matches": new_matches,
        "categories": categories,
        "stats": stats,
        "bookmakers": old_data.get("bookmakers", [])
    }
    if not data["bookmakers"]:
        data["bookmakers"] = [
            {"name": "1xBet", "logo": "assets/images/1xbet.png", "url": "https://affiliation.com/1xbet"},
            {"name": "1win", "logo": "assets/images/1win.png", "url": "https://affiliation.com/1win"},
            {"name": "Betwinner", "logo": "assets/images/betwinner.png", "url": "https://affiliation.com/betwinner"},
            {"name": "Melbet", "logo": "assets/images/melbet.png", "url": "https://affiliation.com/melbet"},
            {"name": "Linebet", "logo": "assets/images/linebet.png", "url": "https://affiliation.com/linebet"},
            {"name": "888starz", "logo": "assets/images/888starz.png", "url": "https://affiliation.com/888starz"}
        ]

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n💾 {DATA_FILE} généré avec {len(new_matches)} matchs (dont historiques 14 jours), ROI: {stats['roi']}%")

if __name__ == "__main__":
    main()