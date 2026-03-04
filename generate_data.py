#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_data.py - Génère les pronostics à partir des données SportData
et des scores déjà en base (mis à jour par update_scores.py).
Version avec exclusion des pronostics "12", seuils ajustés, et logos via TheSportsDB.
"""

import os
import json
import requests
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =======================================================
# CONFIGURATION
# =======================================================
SPORTDATA_API_KEY = os.environ.get("SPORTDATA_API_KEY")
if not SPORTDATA_API_KEY:
    raise ValueError("La variable d'environnement SPORTDATA_API_KEY n'est pas définie")

BSD_API_TOKEN = os.environ.get("BSD_API_TOKEN")  # optionnel
THESPORTSDB_API_KEY = "3"  # clé publique pour thesportsdb

SPORTDATA_URL = "https://v1.football.sportsapipro.com/games/allscores"
HEADERS = {"x-api-key": SPORTDATA_API_KEY}

session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429,500,502,503,504])
session.mount('https://', HTTPAdapter(max_retries=retries))

today = datetime.now().date()
tomorrow = today + timedelta(days=1)
yesterday = today - timedelta(days=1)

DATA_FILE = "data.json"
CACHE_DIR = "cache"
GLOBAL_CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")

print("="*60)
print(f"🚀 GÉNÉRATION DES PRONOSTICS - {today}")
print("="*60)

# =======================================================
# FONCTIONS POUR LES LOGOS (BSD puis TheSportsDB)
# =======================================================
def get_logo_bsd(team_name):
    """Interroge BSD pour obtenir le logo d'une équipe (nécessite mapping)."""
    if not BSD_API_TOKEN:
        return None
    # Ici, vous pourriez ajouter un dictionnaire de correspondance
    # Exemple : team_mapping = {"Real Madrid": 131, ...}
    # puis construire l'URL avec l'ID correspondant.
    # Faute de mapping, on retourne None et on utilisera le fallback TheSportsDB.
    return None

def get_logo_thesportsdb(team_name):
    """Interroge TheSportsDB pour obtenir le logo d'une équipe."""
    try:
        url = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_API_KEY}/searchteams.php?t={requests.utils.quote(team_name)}"
        resp = session.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            teams = data.get("teams", [])
            if teams:
                return teams[0].get("strTeamBadge") or teams[0].get("strTeamLogo")
    except:
        pass
    return None

def get_team_logo(team_name):
    """Obtenir le logo d'une équipe : BSD -> TheSportsDB -> None."""
    logo = get_logo_bsd(team_name)
    if logo:
        return logo
    return get_logo_thesportsdb(team_name)

# =======================================================
# FONCTIONS DE RÉCUPÉRATION DES DONNÉES SPORTDATA
# =======================================================
def fetch_games(date_from, date_to):
    params = {
        "startDate": date_from.strftime("%d/%m/%Y"),
        "endDate": date_to.strftime("%d/%m/%Y"),
        "sports": 1,
        "showOdds": "false",
        "onlyMajorGames": "false"
    }
    try:
        resp = session.get(SPORTDATA_URL, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("games", [])
    except Exception as e:
        print(f"❌ Erreur SportData: {e}")
        return []

def extract_game_info(game):
    """Extrait les infos de base d'un match SportData."""
    start_time = game.get("startTime")
    competition = game.get("competitionDisplayName", "")
    home = game.get("homeCompetitor", {})
    away = game.get("awayCompetitor", {})
    home_score = home.get("score")
    away_score = away.get("score")
    # Convertir les -1 en None
    if home_score == -1:
        home_score = None
    if away_score == -1:
        away_score = None
    return {
        "id": game.get("id"),
        "start_time": start_time,
        "date": start_time[:10] if start_time else "",
        "home_team": home.get("name", ""),
        "away_team": away.get("name", ""),
        "competition": competition,
        "home_score": home_score,
        "away_score": away_score,
        "status_group": game.get("statusGroup"),
        "status_text": game.get("statusText"),
        "is_finished": (game.get("statusGroup") == 4)
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

def get_h2h(historical, home_team, away_team, years=2):
    cutoff_date = (datetime.now() - timedelta(days=365*years)).date()
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
    total_goals = 0.0
    matches_count = 0
    over_25_count = 0

    for match in h2h_list:
        if not match.get("is_finished") or match["home_score"] is None or match["away_score"] is None:
            continue
        weight = weight_by_date(match["start_time"])
        matches_count += 1
        total_goals += (match["home_score"] + match["away_score"]) * weight
        if match["home_score"] + match["away_score"] > 2.5:
            over_25_count += 1

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
    goals_avg = total_goals / matches_count if matches_count > 0 else 2.5
    over_25_prob = over_25_count / matches_count if matches_count > 0 else 0.5

    return {
        "total_matches": matches_count,
        "home_wins": round(home_score, 2),
        "away_wins": round(away_score, 2),
        "draws": round(draws_score, 2),
        "home_dominance": round(home_dominance, 3),
        "away_dominance": round(away_dominance, 3),
        "goals_avg": round(goals_avg, 2),
        "over_25_prob": round(over_25_prob, 3)
    }

def generate_prediction(analysis):
    total = analysis["total_matches"]
    seuil = max(0.05, 0.5 / (total ** 0.5) if total > 0 else 0.1)
    if analysis["home_dominance"] > analysis["away_dominance"] + seuil:
        double_chance = "1X"
    elif analysis["away_dominance"] > analysis["home_dominance"] + seuil:
        double_chance = "X2"
    else:
        double_chance = "12"

    over_25 = analysis["over_25_prob"] > 0.6

    confidence = 50 + min(30, analysis["total_matches"] * 3)
    if max(analysis["home_dominance"], analysis["away_dominance"]) > 0.7:
        confidence = min(confidence + 10, 95)
    if analysis["over_25_prob"] > 0.7 or analysis["over_25_prob"] < 0.3:
        confidence = min(confidence + 5, 95)

    return {
        "double_chance": double_chance,
        "over_25": over_25,
        "confidence": confidence
    }

def calculate_xpronos_score(analysis, prediction):
    score = 0
    score += min(42, analysis["total_matches"] * 7)
    dominance = max(analysis["home_dominance"], analysis["away_dominance"])
    score += min(50, int(dominance * 100 * 0.7))
    if prediction["over_25"]:
        score += 20
    return min(score, 100)

def get_category(score):
    if score >= 75:
        return "vip"
    elif score >= 60:
        return "pro"
    else:
        return "simple"

def get_badge(score):
    if score >= 90:
        return "🏆 PREMIUM LOCK"
    elif score >= 80:
        return "💎 VIP ELITE"
    elif score >= 70:
        return "🔥 ULTRA SAFE"
    return ""

# =======================================================
# FONCTION PRINCIPALE
# =======================================================
def main():
    # 1. Charger l'existant (scores déjà mis à jour)
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
            existing_matches = {m["id"]: m for m in existing_data.get("matches", [])}
    else:
        existing_data = {"matches": [], "categories": {"simple": [], "pro": [], "vip": []}, "stats": {}, "bookmakers": []}
        existing_matches = {}

    # 2. Récupérer les matchs du jour/demain/hier via SportData
    print("\n📅 Récupération des matchs via SportData...")
    games_today = fetch_games(today, today)
    games_tomorrow = fetch_games(tomorrow, tomorrow)
    games_yesterday = fetch_games(yesterday, yesterday)
    all_new_games = games_today + games_tomorrow + games_yesterday
    print(f"✅ {len(all_new_games)} matchs récupérés")

    # 3. Construire un dictionnaire des infos de base
    new_infos = {g["id"]: extract_game_info(g) for g in all_new_games}

    # 4. Charger l'historique H2H
    historical = load_historical_matches()
    print(f"📂 Historique chargé : {len(historical)} matchs")

    # 5. Préparer les nouvelles listes
    matches = []
    categories = {"simple": [], "pro": [], "vip": []}

    # Pour chaque match présent dans l'existant ou dans les nouvelles données
    all_ids = set(existing_matches.keys()) | set(new_infos.keys())
    for gid in all_ids:
        base = new_infos.get(gid)
        if base is None:
            # Match uniquement dans l'existant (ancien), on le garde tel quel
            match = existing_matches[gid]
            matches.append(match)
            categories[match["category"]].append(match)
            continue

        # Match récent (aujourd'hui/demain/hier)
        existing = existing_matches.get(gid)
        if existing:
            # Utiliser les scores de l'existant (plus frais)
            home_score = existing.get("home_score")
            away_score = existing.get("away_score")
            status = existing.get("status")
        else:
            # Nouveau match, utiliser les scores de SportData
            home_score = base["home_score"]
            away_score = base["away_score"]
            status = base["status_text"]

        # Calculer les H2H
        h2h_list = get_h2h(historical, base["home_team"], base["away_team"], years=2)
        if len(h2h_list) < 2:
            print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (H2H insuffisant)")
            continue

        analysis = analyze_h2h(h2h_list, base["home_team"], base["away_team"])
        prediction = generate_prediction(analysis)

        # === Ignorer les pronostics "12" ===
        if prediction["double_chance"] == "12":
            print(f"   ⚠️ Pronostic 12 (match équilibré) ignoré")
            continue
        # ===================================

        score = calculate_xpronos_score(analysis, prediction)
        category = get_category(score)
        badge = get_badge(score)

        # Logos
        home_logo = get_team_logo(base["home_team"])
        away_logo = get_team_logo(base["away_team"])

        match = {
            "id": gid,
            "date": base["date"],
            "event_date": base["start_time"],
            "home_team": base["home_team"],
            "away_team": base["away_team"],
            "home_logo": home_logo,
            "away_logo": away_logo,
            "league": base["competition"],
            "league_logo": None,
            "venue": "",
            "status": status,
            "home_score": home_score,
            "away_score": away_score,
            "h2h_analysis": analysis,
            "prediction": prediction,
            "xpronos_score": score,
            "badge": badge,
            "category": category,
            "verified_double": False,
            "verified_over": False
        }

        # Vérification si terminé
        if base["is_finished"] and home_score is not None and away_score is not None:
            dc = prediction["double_chance"]
            if dc == "1X":
                match["verified_double"] = (home_score > away_score) or (home_score == away_score)
            elif dc == "X2":
                match["verified_double"] = (home_score == away_score) or (home_score < away_score)

            total_goals = home_score + away_score
            match["verified_over"] = (total_goals > 2.5) if prediction["over_25"] else (total_goals <= 2.5)

        matches.append(match)
        categories[category].append(match)

    # Trier par date
    matches.sort(key=lambda x: x["event_date"] or "", reverse=True)

    # Statistiques (à améliorer si besoin)
    stats = {"total_bets": 0, "wins": 0, "roi": 0}

    # Bookmakers par défaut (à remplacer par des URLs réelles)
    default_bookmakers = [
        {"name": "1xBet", "logo": "assets/images/1xbet.png", "url": "https://affiliation.com/1xbet"},
        {"name": "1win", "logo": "assets/images/1win.png", "url": "https://affiliation.com/1win"},
        {"name": "Betwinner", "logo": "assets/images/betwinner.png", "url": "https://affiliation.com/betwinner"},
        {"name": "Melbet", "logo": "assets/images/melbet.png", "url": "https://affiliation.com/melbet"},
        {"name": "Linebet", "logo": "assets/images/linebet.png", "url": "https://affiliation.com/linebet"},
        {"name": "888starz", "logo": "assets/images/888starz.png", "url": "https://affiliation.com/888starz"}
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

if __name__ == "__main__":
    main()