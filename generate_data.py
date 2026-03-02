#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_data.py - Génère data.json avec les matchs du jour/demain/hier,
les prédictions ML et les analyses H2H améliorées.
Utilise un cache permanent des scores et un fallback via TheSportsDB pour les scores manquants.
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
SCORES_CACHE_FILE = os.path.join(CACHE_DIR, "scores_cache.json")  # Cache permanent des scores
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
# FONCTION DE FALLBACK VIA THESPORTSDB
# =======================================================

def fetch_score_from_thesportsdb(home_team, away_team, match_date):
    """
    Tente de récupérer le score via TheSportsDB API (gratuite).
    Retourne un dict {'home_score': int, 'away_score': int, 'status': str} ou None.
    """
    url = f"https://www.thesportsdb.com/api/v1/json/123/eventsday.php?d={match_date}"
    try:
        print(f"      📡 Tentative TheSportsDB pour {home_team} vs {away_team} le {match_date}...")
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            print(f"      ❌ Erreur HTTP {resp.status_code}")
            return None
        data = resp.json()
        events = data.get('events', [])
        if not events:
            print(f"      ℹ️ Aucun événement trouvé pour cette date.")
            return None
        for e in events:
            db_home = e.get('strHomeTeam', '')
            db_away = e.get('strAwayTeam', '')
            # Comparaison approximative (insensible à la casse)
            if (home_team.lower() in db_home.lower() or db_home.lower() in home_team.lower()) and \
               (away_team.lower() in db_away.lower() or db_away.lower() in away_team.lower()):
                home_score = e.get('intHomeScore')
                away_score = e.get('intAwayScore')
                if home_score is not None and away_score is not None:
                    print(f"      ✅ Match trouvé: {db_home} {home_score}-{away_score} {db_away}")
                    return {
                        'home_score': int(home_score),
                        'away_score': int(away_score),
                        'status': e.get('strStatus', 'finished')
                    }
        print(f"      ℹ️ Aucun match correspondant trouvé.")
        return None
    except Exception as e:
        print(f"      ⚠️ Erreur TheSportsDB: {e}")
        return None

# =======================================================
# GESTION DU CACHE PERMANENT DES SCORES
# =======================================================

def load_scores_cache():
    if os.path.exists(SCORES_CACHE_FILE):
        with open(SCORES_CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_scores_cache(cache):
    with open(SCORES_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

def update_scores_cache_from_events(events):
    """Met à jour le cache avec les scores des événements récupérés."""
    cache = load_scores_cache()
    for e in events:
        match_id = e.get("id")
        if match_id and e.get("home_score") is not None and e.get("away_score") is not None:
            cache[str(match_id)] = {
                "home_score": e["home_score"],
                "away_score": e["away_score"],
                "status": e["status"],
                "event_date": e["event_date"]
            }
    save_scores_cache(cache)
    return cache

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
# CALCUL DU SCORE DE CONFIANCE
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
# FONCTIONS DE VÉRIFICATION (avec distinction gagné/perdu)
# =======================================================

def verify_prediction(match, prediction):
    """Retourne 'win', 'loss' ou None si pas de score."""
    match['result'] = None  # None = pas encore de score

    if match['status'] != 'finished':
        return

    home_score = match['home_score']
    away_score = match['away_score']
    if home_score is None or away_score is None:
        return

    dc = prediction.get('double_chance', '')

    if dc == '1X':
        win = (home_score > away_score) or (home_score == away_score)
    elif dc == 'X2':
        win = (home_score == away_score) or (home_score < away_score)
    elif dc == '12':
        win = (home_score > away_score) or (home_score < away_score)
    else:
        win = False

    match['result'] = 'win' if win else 'loss'

def update_bankroll(matches):
    total_bets = 0
    wins = 0
    losses = 0
    for m in matches:
        if m.get("result") == 'win':
            wins += 1
            total_bets += 1
        elif m.get("result") == 'loss':
            losses += 1
            total_bets += 1
        # les matchs sans score ne sont pas comptés
    roi = (wins / total_bets * 100) if total_bets else 0
    return {"total_bets": total_bets, "wins": wins, "losses": losses, "roi": round(roi, 2)}

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

    # Mettre à jour le cache permanent des scores avec ces événements
    scores_cache = update_scores_cache_from_events(all_new_events)
    print(f"📦 Cache des scores mis à jour : {len(scores_cache)} entrées")

    # Récupérer les prédictions passées (pour les scores supplémentaires)
    print("\n📈 Récupération des prédictions passées...")
    past_predictions = fetch_predictions(upcoming=False)
    past_scores = {}
    for p in past_predictions:
        event = p.get('event')
        if event:
            event_id = event.get('id')
            home_score = event.get('home_score')
            away_score = event.get('away_score')
            if home_score is not None and away_score is not None:
                past_scores[event_id] = {'home_score': home_score, 'away_score': away_score}
                # Ajouter aussi au cache permanent
                scores_cache[str(event_id)] = {
                    "home_score": home_score,
                    "away_score": away_score,
                    "status": event.get("status", "finished"),
                    "event_date": event.get("event_date")
                }
    save_scores_cache(scores_cache)

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

    # Charger cache global H2H
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

        agreement = (prediction_h2h["double_chance"] == api_double_chance) if api_double_chance else False

        if not agreement:
            print(f"   ❌ Pas d'accord H2H/API, match ignoré")
            continue

        score = calculate_confidence_score(analysis, ml_pred, agreement)
        badge = get_badge(score)
        category = get_category(score)

        # Récupérer les scores depuis le cache permanent si disponibles
        cached = scores_cache.get(str(match_id))
        if cached:
            home_score = cached.get("home_score")
            away_score = cached.get("away_score")
            status = cached.get("status", event["status"])
        else:
            home_score = event.get("home_score")
            away_score = event.get("away_score")
            status = event["status"]

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
            "status": status,
            "home_score": home_score,
            "away_score": away_score,
            "h2h_analysis": analysis,
            "prediction": {
                "double_chance": prediction_h2h["double_chance"],
                "confidence": score
            },
            "xpronos_score": score,
            "badge": badge,
            "category": category,
            "result": None,  # sera rempli après vérification
            "ml_full": ml_pred
        }

        # =======================================================
        # CORRECTION DES SCORES MANQUANTS AVEC FALLBACK THESPORTSDB
        # =======================================================
        if match_data["status"] == "finished" and (match_data["home_score"] is None or match_data["away_score"] is None):
            tsdb_score = fetch_score_from_thesportsdb(home_obj["name"], away_obj["name"], event_date)
            if tsdb_score:
                match_data["home_score"] = tsdb_score["home_score"]
                match_data["away_score"] = tsdb_score["away_score"]
                if tsdb_score.get("status"):
                    match_data["status"] = tsdb_score["status"]
                # Ajouter au cache permanent
                scores_cache[str(match_id)] = {
                    "home_score": tsdb_score["home_score"],
                    "away_score": tsdb_score["away_score"],
                    "status": match_data["status"],
                    "event_date": event_datetime
                }
                save_scores_cache(scores_cache)
                print(f"   📥 Scores récupérés depuis TheSportsDB pour {match_id}")

        # Vérification du résultat
        verify_prediction(match_data, match_data["prediction"])

        new_matches.append(match_data)
        categories[category].append(match_data)
        print(f"   ✅ Score: {score} - {badge} - Catégorie: {category} - Résultat: {match_data.get('result')}")

    # Fusion avec anciens matchs (pour conserver l'historique des 14 derniers jours)
    for old_id, old_match in old_matches_by_id.items():
        try:
            old_date_str = old_match.get('event_date')
            if not old_date_str:
                continue
            old_date = datetime.fromisoformat(old_date_str.replace('Z', '+00:00')).date()
            if old_date >= fourteen_days_ago:
                if old_id not in {m['id'] for m in new_matches}:
                    # Récupérer les scores depuis le cache si disponibles
                    cached = scores_cache.get(str(old_id))
                    if cached:
                        old_match['home_score'] = cached.get('home_score')
                        old_match['away_score'] = cached.get('away_score')
                        old_match['status'] = cached.get('status', old_match['status'])
                    # Re-vérifier le résultat si maintenant on a des scores
                    if old_match.get('home_score') is not None and old_match.get('away_score') is not None:
                        verify_prediction(old_match, old_match['prediction'])
                    new_matches.append(old_match)
                    categories[old_match['category']].append(old_match)
        except:
            pass

    # Trier les matchs par date décroissante
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