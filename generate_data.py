#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_data.py - UTILISE EXCLUSIVEMENT THESPORTSDB POUR LES SCORES
BSD = uniquement prédictions ML + H2H
Logs détaillés pour chaque tentative TheSportsDB (avec URL)
"""

import requests
import json
from datetime import datetime, timedelta
import os
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =======================================================
# CONFIGURATION
# =======================================================
API_TOKEN = os.environ.get("BSD_API_TOKEN")
if not API_TOKEN:
    raise ValueError("BSD_API_TOKEN manquante")

BASE_URL = "https://sports.bzzoiro.com/api"
HEADERS = {"Authorization": f"Token {API_TOKEN}"}

session = requests.Session()
retries = Retry(total=5, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

today = datetime.now().date()
tomorrow = today + timedelta(days=1)
yesterday = today - timedelta(days=1)
fourteen_days_ago = today - timedelta(days=14)

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)
GLOBAL_CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")
TSDB_CACHE_FILE = os.path.join(CACHE_DIR, "tsdb_cache.json")
DATA_FILE = "data.json"

print("="*60)
print(f"🚀 GÉNÉRATION DES DONNÉES - {today}")
print("="*60)

# =======================================================
# FONCTIONS BSD (uniquement pour les prédictions et H2H)
# =======================================================
def fetch_events(date_from, date_to):
    """Récupère les événements BSD (pour avoir les IDs et les noms d'équipes)."""
    url = f"{BASE_URL}/events/"
    params = {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()}
    all_events = []
    page = 1
    while True:
        params["page"] = page
        try:
            print(f"   📡 Requête BSD events page {page}...")
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
            print(f"   📡 Requête BSD predictions page {page}...")
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
# CACHE THESPORTSDB + NORMALISATION + LOGS AVEC URL
# =======================================================
def load_tsdb_cache():
    if os.path.exists(TSDB_CACHE_FILE) and os.path.getsize(TSDB_CACHE_FILE) > 0:
        with open(TSDB_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_tsdb_cache(cache):
    with open(TSDB_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

def get_tsdb_key(home, away, date_str):
    return hashlib.md5(f"{home}|{away}|{date_str}".encode()).hexdigest()

def normalize_team(name: str) -> str:
    """Normalise les noms d'équipes pour TheSportsDB."""
    mapping = {
        "Man Utd": "Manchester United",
        "Man United": "Manchester United",
        "Man City": "Manchester City",
        "Spurs": "Tottenham Hotspur",
        "Tottenham": "Tottenham Hotspur",
        "Wolves": "Wolverhampton Wanderers",
        "Brighton": "Brighton & Hove Albion",
        "West Ham": "West Ham United",
        "Newcastle": "Newcastle United",
        "Leicester": "Leicester City",
        "Nottm Forest": "Nottingham Forest",
        "Forest": "Nottingham Forest",
        "St. Louis": "St Louis",
        "St.Louis": "St Louis",
        "NYC": "New York City",
        "NYCFC": "New York City",
        "LAFC": "Los Angeles FC",
        "LA Galaxy": "Los Angeles Galaxy",
        "Inter Miami": "Inter Miami CF",
        "Miami": "Inter Miami CF",
        "Philadelphia Union": "Philadelphia",
        "Portland Timbers": "Portland",
        "Seattle Sounders": "Seattle",
        "Atlanta United": "Atlanta",
        "FC Cincinnati": "Cincinnati",
        "Columbus Crew": "Columbus",
        "DC United": "D.C. United",
        "San Jose Earthquakes": "San Jose",
        "Sporting KC": "Sporting Kansas City",
        "Kansas City": "Sporting Kansas City",
        "Real Salt Lake": "Salt Lake",
        "Salt Lake": "Real Salt Lake",
        "Minnesota United": "Minnesota",
        "Minnesota": "Minnesota United",
        "CF Montréal": "Montreal",
        "Montreal": "CF Montréal",
        "Toronto FC": "Toronto",
        "Toronto": "Toronto FC",
        "Vancouver Whitecaps": "Vancouver",
        "Vancouver": "Vancouver Whitecaps",
        "Colorado Rapids": "Colorado",
        "Colorado": "Colorado Rapids",
        "Houston Dynamo": "Houston",
        "Houston": "Houston Dynamo",
        "FC Dallas": "Dallas",
        "Dallas": "FC Dallas",
        "Austin FC": "Austin",
        "Austin": "Austin FC",
        "Nashville SC": "Nashville",
        "Nashville": "Nashville SC",
        "Charlotte FC": "Charlotte",
        "Charlotte": "Charlotte FC",
        "Chicago Fire": "Chicago",
        "Chicago": "Chicago Fire",
        "New England Revolution": "New England",
        "New England": "New England Revolution",
        "Orlando City": "Orlando",
        "Orlando": "Orlando City SC",
        "San Diego FC": "San Diego",
        "San Diego": "San Diego FC"
    }
    name_clean = name.strip()
    # Remplacer les & et autres
    name_clean = name_clean.replace("&", "and")
    # Si le nom est directement dans le mapping, on le prend
    if name_clean in mapping:
        return mapping[name_clean]
    # Sinon, on cherche une correspondance partielle (ex: "Manchester United" -> "Man United")
    for key, value in mapping.items():
        if key in name_clean or name_clean in key:
            return value
    return name_clean

def fetch_tsdb_match(home, away, date_str, tsdb_cache):
    """Interroge TheSportsDB avec logs détaillés et affichage de l'URL."""
    key = get_tsdb_key(home, away, date_str)
    if key in tsdb_cache:
        cached = tsdb_cache[key]
        if cached:
            # Extraire les scores du cache pour log
            if cached.get("intHomeScore") is not None:
                print(f"      🔍 Cache TheSportsDB: {home} {cached['intHomeScore']}-{cached['intAwayScore']} {away}")
        return cached

    home_n = normalize_team(home)
    away_n = normalize_team(away)
    print(f"      📡 TheSportsDB recherche: {home_n} vs {away_n} le {date_str}")

    # Essayer plusieurs formats
    formats = [
        f"{home_n.replace(' ', '_')}_vs_{away_n.replace(' ', '_')}",
        f"{away_n.replace(' ', '_')}_vs_{home_n.replace(' ', '_')}",
        f"{home.replace(' ', '_')}_vs_{away.replace(' ', '_')}",
        f"{away.replace(' ', '_')}_vs_{home.replace(' ', '_')}"
    ]

    for event_name in formats:
        url = f"https://www.thesportsdb.com/api/v1/json/123/searchevents.php?e={event_name}&d={date_str}"
        print(f"      🔗 Tentative URL: {url}")
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                events = resp.json().get("event", [])
                if events:
                    tsdb_cache[key] = events[0]
                    print(f"      ✅ Trouvé: {home} vs {away} → {events[0]['intHomeScore']}-{events[0]['intAwayScore']}")
                    return events[0]
        except Exception as e:
            print(f"      ⚠️ Erreur requête: {e}")

    tsdb_cache[key] = None
    print(f"      ❌ Aucun match trouvé sur TheSportsDB pour {home} vs {away}")
    return None

def extract_tsdb_info(event):
    if not event:
        return None
    try:
        return {
            "home_score": int(event["intHomeScore"]) if event.get("intHomeScore") not in (None, "") else None,
            "away_score": int(event["intAwayScore"]) if event.get("intAwayScore") not in (None, "") else None,
            "status": "finished" if "Finished" in event.get("strStatus", "") else event.get("strStatus", "finished").lower(),
            "banner": event.get("strBanner"),
            "venue": event.get("strVenue"),
            "league_badge": event.get("strLeagueBadge"),
            "home_badge": event.get("strHomeTeamBadge"),
            "away_badge": event.get("strAwayTeamBadge"),
        }
    except Exception as e:
        print(f"      ⚠️ Erreur extraction: {e}")
        return None

# =======================================================
# FONCTIONS H2H (inchangées mais utilisent le cache global)
# =======================================================
def weight_by_date(date_str):
    try:
        match_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        days_old = (datetime.now() - match_date).days
        return 1.5 if days_old < 180 else 1.2 if days_old < 365 else 1.0
    except:
        return 1.0

def get_h2h_from_cache(team_id_a, team_id_b, global_cache):
    h2h = []
    for m in global_cache:
        home_obj = m.get("home_team_obj") or {"id": None, "name": m.get("home_team", "")}
        away_obj = m.get("away_team_obj") or {"id": None, "name": m.get("away_team", "")}
        if (home_obj.get("id") == team_id_a and away_obj.get("id") == team_id_b) or \
           (home_obj.get("id") == team_id_b and away_obj.get("id") == team_id_a):
            if m.get("status") == "finished" and m.get("home_score") is not None and m.get("away_score") is not None:
                h2h.append({
                    "date": m["event_date"],
                    "home_team": home_obj["name"],
                    "away_team": away_obj["name"],
                    "home_score": m["home_score"],
                    "away_score": m["away_score"],
                    "status": m["status"],
                    "league": m.get("league", {}).get("name", m.get("league", ""))
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

def verify_prediction(match, prediction):
    match['result'] = None
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
    roi = (wins / total_bets * 100) if total_bets else 0
    return {"total_bets": total_bets, "wins": wins, "losses": losses, "roi": round(roi, 2)}

# =======================================================
# FONCTION PRINCIPALE
# =======================================================
def main():
    print("\n📅 Récupération des matchs BSD (uniquement pour les noms et IDs)...")
    events_today = fetch_events(today, today)
    events_tomorrow = fetch_events(tomorrow, tomorrow)
    events_yesterday = fetch_events(yesterday, yesterday)

    all_new_events = events_today + events_tomorrow + events_yesterday
    print(f"\n✅ {len(all_new_events)} événements BSD récupérés (utilisés pour les noms d'équipes)")

    # Charger caches
    tsdb_cache = load_tsdb_cache()
    global_cache = []
    if os.path.exists(GLOBAL_CACHE_FILE) and os.path.getsize(GLOBAL_CACHE_FILE) > 0:
        with open(GLOBAL_CACHE_FILE, 'r', encoding='utf-8') as f:
            global_cache = json.load(f)
        print(f"📂 Cache global H2H chargé : {len(global_cache)} matchs")
    else:
        print("ℹ️ Cache global H2H vide ou inexistant")

    # === PARALLÉLISATION DES REQUÊTES THESPORTSDB AVEC LOGS ===
    print("\n🌐 Récupération des données TheSportsDB en parallèle...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_event = {}
        for e in all_new_events:
            home_obj = e.get("home_team_obj")
            away_obj = e.get("away_team_obj")
            if home_obj and away_obj:
                future = executor.submit(
                    fetch_tsdb_match,
                    home_obj["name"],
                    away_obj["name"],
                    e["event_date"][:10],
                    tsdb_cache
                )
                future_to_event[future] = e

        for future in as_completed(future_to_event):
            future.result()  # le cache est mis à jour et les logs s'affichent

    save_tsdb_cache(tsdb_cache)
    print(f"✅ Cache TheSportsDB mis à jour : {len(tsdb_cache)} entrées")

    # Récupérer les prédictions BSD
    print("\n📈 Récupération des prédictions BSD...")
    predictions_upcoming = fetch_predictions(upcoming=True)
    predictions_past = fetch_predictions(upcoming=False)
    all_predictions = predictions_upcoming + predictions_past
    pred_dict = {p['event']['id']: p for p in all_predictions}
    print(f"✅ {len(all_predictions)} prédictions BSD récupérées")

    # Charger ancien fichier
    old_data = {}
    old_matches_by_id = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
            old_matches_by_id = {m['id']: m for m in old_data.get('matches', [])}
        print(f"📂 Ancien fichier chargé : {len(old_matches_by_id)} matchs")

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
        if ml_pred:
            predicted_result = ml_pred.get('predicted_result', '')
            if predicted_result == "H":
                api_double_chance = "1X"
            elif predicted_result == "A":
                api_double_chance = "X2"
            elif predicted_result == "D":
                api_double_chance = "12"

        agreement = (prediction_h2h["double_chance"] == api_double_chance) if api_double_chance else False

        if not agreement:
            print(f"   ❌ Pas d'accord H2H/BSD, match ignoré")
            continue

        score = calculate_confidence_score(analysis, ml_pred, agreement)
        badge = get_badge(score)
        category = get_category(score)

        # === RÉCUPÉRATION DES SCORES THESPORTSDB (LOGS DÉJÀ FAITS) ===
        key = get_tsdb_key(home_obj["name"], away_obj["name"], event_date)
        tsdb_event = tsdb_cache.get(key)
        tsdb_info = extract_tsdb_info(tsdb_event)

        if tsdb_info and tsdb_info["home_score"] is not None:
            # Utiliser les données TheSportsDB
            home_score = tsdb_info["home_score"]
            away_score = tsdb_info["away_score"]
            status = tsdb_info["status"]
            venue = tsdb_info.get("venue") or event.get("venue", "")
            home_logo = tsdb_info.get("home_badge") or f"https://sports.bzzoiro.com/img/team/{home_obj['api_id']}/?token={API_TOKEN}"
            away_logo = tsdb_info.get("away_badge") or f"https://sports.bzzoiro.com/img/team/{away_obj['api_id']}/?token={API_TOKEN}"
            league_logo = tsdb_info.get("league_badge") or f"https://sports.bzzoiro.com/img/league/{league['api_id']}/?token={API_TOKEN}"
            print(f"   ✅ Score TheSportsDB: {home_score}-{away_score}")
        else:
            # Si TheSportsDB n'a rien, on laisse les champs vides (pas de fallback BSD)
            home_score = None
            away_score = None
            status = event.get("status", "unknown")
            venue = event.get("venue", "")
            home_logo = f"https://sports.bzzoiro.com/img/team/{home_obj['api_id']}/?token={API_TOKEN}"
            away_logo = f"https://sports.bzzoiro.com/img/team/{away_obj['api_id']}/?token={API_TOKEN}"
            league_logo = f"https://sports.bzzoiro.com/img/league/{league['api_id']}/?token={API_TOKEN}"
            print(f"   ⚠️ Aucun score trouvé sur TheSportsDB pour ce match")

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
            "venue": venue,
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
            "result": None,
            "ml_full": ml_pred,
            "tsdb_banner": tsdb_info.get("banner") if tsdb_info else None
        }

        verify_prediction(match_data, match_data["prediction"])

        new_matches.append(match_data)
        categories[category].append(match_data)
        print(f"   ✅ Score final: {home_score}-{away_score}, Résultat: {match_data.get('result')}")

        # Mise à jour du cache global H2H (version normalisée)
        if home_score is not None and away_score is not None:
            cache_entry = {
                "event_date": event_datetime,
                "status": status,
                "home_score": home_score,
                "away_score": away_score,
                "home_team_obj": {"id": home_obj["id"], "name": home_obj["name"]},
                "away_team_obj": {"id": away_obj["id"], "name": away_obj["name"]},
                "league": {"name": league["name"]}
            }
            if cache_entry not in global_cache:
                global_cache.append(cache_entry)

    # Sauvegarde du cache global (limité aux 5000 derniers)
    with open(GLOBAL_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(global_cache[-5000:], f, indent=2, ensure_ascii=False)

    # Fusion avec les anciens matchs (14 derniers jours) – on garde ceux qui ont des scores
    new_ids = {m['id'] for m in new_matches}
    for old_id, old_match in old_matches_by_id.items():
        try:
            old_date_str = old_match.get('event_date')
            if not old_date_str:
                continue
            old_date = datetime.fromisoformat(old_date_str.replace('Z', '+00:00')).date()
            if old_date >= fourteen_days_ago and old_id not in new_ids:
                # On ne garde que les anciens matchs qui ont des scores (sinon ils sont inutiles)
                if old_match.get('home_score') is not None and old_match.get('away_score') is not None:
                    new_matches.append(old_match)
                    categories[old_match['category']].append(old_match)
        except:
            pass

    # Tri par date décroissante
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