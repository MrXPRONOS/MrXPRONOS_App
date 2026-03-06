#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_data.py - Génère les pronostics à partir des données SportData
et des scores déjà en base (mis à jour par update_scores.py).

Ce script :
- Récupère les matchs du jour, d'hier et de demain via l'API SportData.
- Enrichit chaque match avec une analyse des confrontations directes (H2H)
  basée sur l'historique chargé depuis all_matches.json.
- Calcule un pronostic (double chance, over 2.5, confiance) et un score.
- Catégorise les matchs en Simple / Pro / VIP selon le score.
- Récupère les logos des équipes via TheSportsDB (avec cache local).
- Sauvegarde le tout dans data.json, en conservant les bookmakers existants
  ou en utilisant une liste par défaut.
- Exclut les matchs avec un pronostic "12" (trop équilibré).
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

# Clé API SportData (obligatoire)
SPORTDATA_API_KEY = os.environ.get("SPORTDATA_API_KEY")
if not SPORTDATA_API_KEY:
    raise ValueError("La variable d'environnement SPORTDATA_API_KEY n'est pas définie")

# Clé publique pour TheSportsDB (gratuite)
THESPORTSDB_API_KEY = "3"

# URL de base de l'API SportData
SPORTDATA_URL = "https://v1.football.sportsapipro.com/games/allscores"
HEADERS = {"x-api-key": SPORTDATA_API_KEY}

# Configuration des requêtes avec retry en cas d'échec
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

# Dates d'intérêt
today = datetime.now().date()
tomorrow = today + timedelta(days=1)
yesterday = today - timedelta(days=1)

# Fichiers
DATA_FILE = "data.json"
CACHE_DIR = "cache"
GLOBAL_CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")   # Historique complet des matchs
LOGO_CACHE_FILE = os.path.join(CACHE_DIR, "logos_cache.json")     # Cache des logos d'équipes

print("="*60)
print(f"🚀 GÉNÉRATION DES PRONOSTICS - {today}")
print("="*60)

# =======================================================
# GESTION DU CACHE DES LOGOS
# =======================================================

logo_cache = {}
if os.path.exists(LOGO_CACHE_FILE):
    with open(LOGO_CACHE_FILE, 'r', encoding='utf-8') as f:
        logo_cache = json.load(f)

def save_logo_cache():
    """Sauvegarde le dictionnaire des logos dans le fichier cache."""
    with open(LOGO_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(logo_cache, f, indent=2)

def get_logo_thesportsdb(team_name):
    """
    Interroge TheSportsDB pour obtenir l'URL du logo d'une équipe.
    Utilise le cache pour éviter des appels répétés.
    Retourne l'URL du logo ou None si non trouvé.
    """
    if team_name in logo_cache:
        return logo_cache[team_name]
    try:
        url = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_API_KEY}/searchteams.php?t={requests.utils.quote(team_name)}"
        resp = session.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            teams = data.get("teams", [])
            if teams:
                # On préfère le badge (strTeamBadge) sinon le logo classique
                logo = teams[0].get("strTeamBadge") or teams[0].get("strTeamLogo")
                logo_cache[team_name] = logo
                return logo
    except Exception as e:
        print(f"   ⚠️ Erreur lors de la récupération du logo pour {team_name}: {e}")
    logo_cache[team_name] = None
    return None

def get_team_logo(team_name):
    """Wrapper pour obtenir un logo avec gestion du cache."""
    return get_logo_thesportsdb(team_name)

# =======================================================
# FONCTIONS DE RÉCUPÉRATION DES DONNÉES SPORTDATA
# =======================================================

def fetch_games(date_from, date_to):
    """
    Récupère les matchs pour une période donnée via l'API SportData.
    Retourne la liste des jeux (games) ou [] en cas d'erreur.
    """
    params = {
        "startDate": date_from.strftime("%d/%m/%Y"),
        "endDate": date_to.strftime("%d/%m/%Y"),
        "sports": 1,                # football
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
    """
    Extrait les informations de base d'un match SportData.
    Retourne un dictionnaire avec les champs utiles.
    """
    start_time = game.get("startTime")
    competition = game.get("competitionDisplayName", "")
    home = game.get("homeCompetitor", {})
    away = game.get("awayCompetitor", {})
    home_score = home.get("score")
    away_score = away.get("score")
    # Convertir les -1 (score non disponible) en None
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
        "is_finished": (game.get("statusGroup") == 4)   # 4 = terminé
    }

# =======================================================
# FONCTIONS D'ANALYSE H2H
# =======================================================

def load_historical_matches():
    """
    Charge l'historique complet des matchs depuis all_matches.json.
    Retourne une liste de matchs (format SportData) ou [] si fichier absent.
    """
    if not os.path.exists(GLOBAL_CACHE_FILE):
        print("⚠️ Fichier historique introuvable. Exécutez d'abord allmatches.py.")
        return []
    with open(GLOBAL_CACHE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def weight_by_date(date_str):
    """
    Calcule un poids en fonction de l'ancienneté du match.
    Les matchs récents (moins de 6 mois) ont un poids plus élevé.
    """
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
    """
    Récupère les confrontations directes entre deux équipes
    dans l'historique, limitées aux 'years' dernières années.
    Retourne une liste de matchs triés du plus récent au plus ancien.
    """
    cutoff_date = (datetime.now() - timedelta(days=365*years)).date()
    h2h = []
    for m in historical:
        # On vérifie si le match oppose ces deux équipes (peu importe le sens)
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
    """
    Analyse une liste de matchs H2H pour en extraire des statistiques.
    Retourne un dictionnaire avec :
        - total_matches : nombre de matchs analysés
        - home_wins, away_wins, draws : scores pondérés
        - home_dominance, away_dominance : proportions
        - goals_avg : moyenne de buts par match
        - over_25_prob : probabilité de plus de 2.5 buts
    """
    home_score = 0.0
    away_score = 0.0
    draws_score = 0.0
    total_goals = 0.0
    matches_count = 0
    over_25_count = 0

    for match in h2h_list:
        # On ne prend que les matchs terminés avec des scores
        if not match.get("is_finished") or match["home_score"] is None or match["away_score"] is None:
            continue
        weight = weight_by_date(match["start_time"])
        matches_count += 1
        total_goals += (match["home_score"] + match["away_score"]) * weight
        if match["home_score"] + match["away_score"] > 2.5:
            over_25_count += 1

        # Déterminer le vainqueur pondéré
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
    """
    Génère le pronostic à partir des statistiques H2H.
    Retourne un dictionnaire avec double_chance, over_25 et confidence.
    """
    total = analysis["total_matches"]
    # Seuil pour considérer une domination significative
    seuil = max(0.05, 0.5 / (total ** 0.5) if total > 0 else 0.1)
    if analysis["home_dominance"] > analysis["away_dominance"] + seuil:
        double_chance = "1X"
    elif analysis["away_dominance"] > analysis["home_dominance"] + seuil:
        double_chance = "X2"
    else:
        double_chance = "12"

    over_25 = analysis["over_25_prob"] > 0.6

    # Calcul de la confiance de base (entre 50 et 80)
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
    """
    Calcule un score (0-100) qui reflète la fiabilité du pronostic.
    Sert à déterminer la catégorie (Simple, Pro, VIP).
    """
    score = 0
    # Plus il y a de matchs H2H, plus le score est élevé (max 42)
    score += min(42, analysis["total_matches"] * 7)
    # Bonus pour la domination (max 50)
    dominance = max(analysis["home_dominance"], analysis["away_dominance"])
    score += min(50, int(dominance * 100 * 0.7))
    # Bonus si over_25 est significatif
    if prediction["over_25"]:
        score += 20
    return min(score, 100)

def get_category(score):
    """Retourne la catégorie en fonction du score."""
    if score >= 75:
        return "vip"
    elif score >= 60:
        return "pro"
    else:
        return "simple"

def get_badge(score):
    """Retourne un badge textuel pour les scores élevés."""
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
    # 1. Charger les données existantes (pour conserver les scores mis à jour par update_scores.py)
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
            existing_matches = {m["id"]: m for m in existing_data.get("matches", [])}
    else:
        existing_data = {
            "matches": [],
            "categories": {"simple": [], "pro": [], "vip": []},
            "stats": {},
            "bookmakers": []
        }
        existing_matches = {}

    # 2. Récupérer les matchs d'aujourd'hui, demain et hier
    print("\n📅 Récupération des matchs via SportData...")
    games_today = fetch_games(today, today)
    games_tomorrow = fetch_games(tomorrow, tomorrow)
    games_yesterday = fetch_games(yesterday, yesterday)
    all_new_games = games_today + games_tomorrow + games_yesterday
    print(f"✅ {len(all_new_games)} matchs récupérés")

    # 3. Extraire les informations de base pour chaque nouveau match
    new_infos = {g["id"]: extract_game_info(g) for g in all_new_games}

    # 4. Charger l'historique H2H
    historical = load_historical_matches()
    print(f"📂 Historique chargé : {len(historical)} matchs")

    # 5. Préparer les listes de matchs et catégories
    matches = []
    categories = {"simple": [], "pro": [], "vip": []}

    # Union de tous les IDs (existants + nouveaux)
    all_ids = set(existing_matches.keys()) | set(new_infos.keys())

    for gid in all_ids:
        base = new_infos.get(gid)
        if base is None:
            # Match uniquement dans l'existant (ancien), on le conserve tel quel
            match = existing_matches[gid]
            matches.append(match)
            categories[match["category"]].append(match)
            continue

        # Match récent (aujourd'hui/demain/hier)
        existing = existing_matches.get(gid)
        if existing:
            # Utiliser les scores de l'existant (plus frais, mis à jour par update_scores.py)
            home_score = existing.get("home_score")
            away_score = existing.get("away_score")
            status = existing.get("status")
        else:
            # Nouveau match, utiliser les scores de SportData (peut-être None)
            home_score = base["home_score"]
            away_score = base["away_score"]
            status = base["status_text"]

        # Analyser les confrontations directes
        h2h_list = get_h2h(historical, base["home_team"], base["away_team"], years=2)
        if len(h2h_list) < 2:
            print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (H2H insuffisant)")
            continue

        analysis = analyze_h2h(h2h_list, base["home_team"], base["away_team"])
        prediction = generate_prediction(analysis)

        # === Ignorer les pronostics "12" (matchs trop équilibrés) ===
        if prediction["double_chance"] == "12":
            print(f"   ⚠️ Pronostic 12 (match équilibré) ignoré")
            continue
        # =========================================================

        score = calculate_xpronos_score(analysis, prediction)
        category = get_category(score)
        badge = get_badge(score)

        # Récupérer les logos avec le cache
        home_logo = get_team_logo(base["home_team"])
        away_logo = get_team_logo(base["away_team"])

        # Construire l'objet match complet
        match = {
            "id": gid,
            "date": base["date"],
            "event_date": base["start_time"],
            "home_team": base["home_team"],
            "away_team": base["away_team"],
            "home_logo": home_logo,
            "away_logo": away_logo,
            "league": base["competition"],
            "league_logo": None,          # Non utilisé pour l'instant
            "venue": "",                  # Non fourni par l'API
            "status": status,
            "home_score": home_score,
            "away_score": away_score,
            "h2h_analysis": analysis,
            "prediction": prediction,
            "xpronos_score": score,
            "badge": badge,
            "category": category,
            "verified_double": False,      # Sera mis à jour ultérieurement
            "verified_over": False
        }

        # Vérification du pronostic si le match est déjà terminé
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

    # Sauvegarder le cache des logos
    save_logo_cache()

    # Trier les matchs par date (les plus récents en premier)
    matches.sort(key=lambda x: x["event_date"] or "", reverse=True)

    # Statistiques (pour l'instant vides, à enrichir plus tard)
    stats = {"total_bets": 0, "wins": 0, "roi": 0}

    # Liste par défaut des bookmakers (utilisée si aucune donnée existante)
    default_bookmakers = [
        {"name": "1xBet",     "logo": "assets/images/1xbet.png",     "url": "https://refpa58144.com/L?tag=d_2054511m_1599c_&site=2054511&ad=1599"},
        {"name": "1win",      "logo": "assets/images/1win.png",      "url": "https://1wrbgb.com/?open=register&p=qqcw"},
        {"name": "Betwinner", "logo": "assets/images/betwinner.png", "url": "https://bwredir.com/299Y"},
        {"name": "Melbet",    "logo": "assets/images/melbet.png",    "url": "https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041"},
        {"name": "Linebet",   "logo": "assets/images/linebet.png",   "url": "https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3072389&ad=22611"},
        {"name": "BetClic",   "logo": "assets/images/betclic.png",   "url": "https://betpari-click.com/2vY0?extid=USD"}
    ]

    # Assembler les données finales
    data = {
        "matches": matches,
        "categories": categories,
        "stats": stats,
        "bookmakers": existing_data.get("bookmakers", default_bookmakers)
    }

    # Écrire le fichier data.json
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n💾 {DATA_FILE} généré avec {len(matches)} matchs")
    print(f"📊 Catégories : Simple: {len(categories['simple'])}, Pro: {len(categories['pro'])}, VIP: {len(categories['vip'])}")

if __name__ == "__main__":
    main()