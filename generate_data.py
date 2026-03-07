#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_data.py - Génère les pronostics à partir des données SportData
et des scores déjà en base (mis à jour par update_scores.py).
Version améliorée avec prise en compte de la forme récente,
de l'avantage domicile, de la pondération des compétitions,
et des combos (double chance + BTTS) pour les VIP.
"""

import os
import json
import requests
from datetime import datetime, timedelta, timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =======================================================
# CONFIGURATION
# =======================================================
SPORTDATA_API_KEY = os.environ.get("SPORTDATA_API_KEY")
if not SPORTDATA_API_KEY:
    raise ValueError("La variable d'environnement SPORTDATA_API_KEY n'est pas définie")

# Clé publique pour TheSportsDB
THESPORTSDB_API_KEY = "3"

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
LOGO_CACHE_FILE = os.path.join(CACHE_DIR, "logos_cache.json")

# Ligues considérées comme fiables (pour ajuster la confiance)
TRUSTED_LEAGUES = [
    "Premier League",
    "LaLiga",
    "Serie A",
    "Bundesliga",
    "Ligue 1",
    "Eredivisie",
    "Primeira Liga",
    "Russian Premier League",
    "MLS",
    "Brasileirão",
    "Super Lig"
]

# Ligues avec une moyenne de buts élevée (pour over 2.5)
HIGH_SCORING_LEAGUES = [
    "Bundesliga",
    "Eredivisie",
    "Premier League",
    "MLS",
    "Brasileirão"
]

print("="*60)
print(f"🚀 GÉNÉRATION DES PRONOSTICS AMÉLIORÉS - {today}")
print("="*60)

# =======================================================
# GESTION DU CACHE DES LOGOS
# =======================================================
logo_cache = {}
if os.path.exists(LOGO_CACHE_FILE):
    with open(LOGO_CACHE_FILE, 'r', encoding='utf-8') as f:
        logo_cache = json.load(f)

def save_logo_cache():
    with open(LOGO_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(logo_cache, f, indent=2)

def get_logo_thesportsdb(team_name):
    """Interroge TheSportsDB pour obtenir le logo d'une équipe."""
    if team_name in logo_cache:
        return logo_cache[team_name]
    try:
        url = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_API_KEY}/searchteams.php?t={requests.utils.quote(team_name)}"
        resp = session.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            teams = data.get("teams", [])
            if teams:
                logo = teams[0].get("strTeamBadge") or teams[0].get("strTeamLogo")
                logo_cache[team_name] = logo
                return logo
    except Exception as e:
        print(f"⚠️ Erreur lors de la récupération du logo pour {team_name}: {e}")
    logo_cache[team_name] = None
    return None

def get_team_logo(team_name):
    """Obtenir le logo d'une équipe avec cache."""
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
# FONCTIONS D'ANALYSE DE LA FORME DES ÉQUIPES
# =======================================================
def build_team_history(historical):
    """Construit un dictionnaire avec tous les matchs par équipe, triés par date."""
    team_matches = {}
    for m in historical:
        home = m["home_team"]
        away = m["away_team"]
        try:
            date = datetime.fromisoformat(m["start_time"].replace('Z', '+00:00')).replace(tzinfo=None)
        except:
            continue
        # Pour l'équipe à domicile
        if home not in team_matches:
            team_matches[home] = []
        team_matches[home].append((date, m, "home"))
        # Pour l'équipe à l'extérieur
        if away not in team_matches:
            team_matches[away] = []
        team_matches[away].append((date, m, "away"))
    # Trier par date pour chaque équipe (du plus récent au plus ancien)
    for team in team_matches:
        team_matches[team].sort(key=lambda x: x[0], reverse=True)
    return team_matches

def get_team_form(team, team_matches, last_games=5, max_days=365):
    """
    Calcule les statistiques de forme d'une équipe sur ses derniers matchs.
    Retourne un dict avec victoires, nuls, défaites, buts marqués/encaissés,
    et une note de forme pondérée par la récence.
    """
    matches = team_matches.get(team, [])
    recent = []
    for date, match, side in matches:
        if match.get("is_finished") and match["home_score"] is not None:
            days_old = (datetime.now() - date).days
            if days_old <= max_days:
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
            gf = match["home_score"]
            ga = match["away_score"]
        else:
            gf = match["away_score"]
            ga = match["home_score"]

        goals_for += gf * weight
        goals_against += ga * weight

        if gf > ga:
            wins += 1 * weight
        elif gf == ga:
            draws += 1 * weight
        else:
            losses += 1 * weight

    wins /= total_weight
    draws /= total_weight
    losses /= total_weight
    goals_for /= total_weight
    goals_against /= total_weight

    points_per_game = (wins * 3 + draws) / (wins + draws + losses) if (wins+draws+losses)>0 else 0
    form_score = points_per_game / 3

    return {
        "wins": round(wins, 2),
        "draws": round(draws, 2),
        "losses": round(losses, 2),
        "goals_for": round(goals_for, 2),
        "goals_against": round(goals_against, 2),
        "form_score": round(form_score, 3),
        "matches_used": len(recent)
    }

# =======================================================
# FONCTIONS D'ANALYSE H2H ET BTTS
# =======================================================
def load_historical_matches():
    if not os.path.exists(GLOBAL_CACHE_FILE):
        print("⚠️ Fichier historique introuvable. Exécutez d'abord allmatches.py.")
        return []
    with open(GLOBAL_CACHE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def weight_by_date(date_str):
    try:
        match_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).replace(tzinfo=None)
        days_old = (datetime.now() - match_date).days
        if days_old < 180:
            return 1.5
        elif days_old < 365:
            return 1.2
        else:
            return 1.0
    except:
        return 1.0

def competition_weight(competition):
    """Pondère selon l'importance de la compétition."""
    comp_lower = competition.lower()
    if "friendly" in comp_lower:
        return 0.5
    if "cup" in comp_lower or "playoff" in comp_lower:
        return 1.3
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
        date_weight = weight_by_date(match["start_time"])
        comp_weight = competition_weight(match.get("competition", ""))
        weight = date_weight * comp_weight

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
    draw_rate = draws_score / total_weighted if total_weighted > 0 else 0
    goals_avg = total_goals / matches_count if matches_count > 0 else 2.5
    over_25_prob = over_25_count / matches_count if matches_count > 0 else 0.5

    return {
        "total_matches": matches_count,
        "home_wins": round(home_score, 2),
        "away_wins": round(away_score, 2),
        "draws": round(draws_score, 2),
        "home_dominance": round(home_dominance, 3),
        "away_dominance": round(away_dominance, 3),
        "draw_rate": round(draw_rate, 3),
        "goals_avg": round(goals_avg, 2),
        "over_25_prob": round(over_25_prob, 3)
    }

def analyze_btts(h2h_list):
    """Analyse si les deux équipes marquent souvent."""
    btts_count = 0
    matches = 0
    for m in h2h_list:
        if not m.get("is_finished"):
            continue
        if m["home_score"] is None or m["away_score"] is None:
            continue
        matches += 1
        if m["home_score"] > 0 and m["away_score"] > 0:
            btts_count += 1
    if matches == 0:
        return 0.5
    return btts_count / matches

def generate_prediction(analysis, home_form, away_form, league, h2h_list):
    # Seuil de dominance pour éviter les matchs trop équilibrés
    seuil = 0.55

    if analysis["home_dominance"] > analysis["away_dominance"] + seuil:
        double_chance = "1X"
    elif analysis["away_dominance"] > analysis["home_dominance"] + seuil:
        double_chance = "X2"
    else:
        double_chance = "12"

    # Over 2.5
    over_25 = analysis["over_25_prob"] > 0.6
    if league in HIGH_SCORING_LEAGUES:
        over_25 = over_25 or analysis["goals_avg"] > 2.8

    # BTTS
    btts_prob = analyze_btts(h2h_list)
    btts = btts_prob > 0.6

    # Combo
    combo = None
    if double_chance != "12" and btts:
        combo = f"{double_chance} + BTTS"

    # Calcul du score de confiance combiné
    confiance = 50
    confiance += min(20, analysis["total_matches"] * 3)
    if max(analysis["home_dominance"], analysis["away_dominance"]) > 0.7:
        confiance += 10
    if home_form and away_form:
        form_diff = abs(home_form["form_score"] - away_form["form_score"])
        if form_diff > 0.2:
            confiance += 5
        if home_form["form_score"] > 0.7 and away_form["form_score"] < 0.4:
            confiance += 5
    if analysis["draw_rate"] > 0.4:
        confiance -= 10
    if league in TRUSTED_LEAGUES:
        confiance += 5
    else:
        confiance -= 5

    confiance = max(0, min(100, confiance))

    return {
        "double_chance": double_chance,
        "over_25": over_25,
        "btts": btts,
        "btts_probability": round(btts_prob, 3),
        "combo": combo,
        "confidence": confiance
    }

def calculate_xpronos_score(analysis, prediction, home_form, away_form, league):
    score = 0
    score += min(40, analysis["total_matches"] * 6)
    dominance = max(analysis["home_dominance"], analysis["away_dominance"])
    score += min(30, int(dominance * 100 * 0.5))
    if prediction["over_25"]:
        score += 10
    if home_form and away_form:
        score += min(20, int((home_form["form_score"] + away_form["form_score"]) * 10))
    if league in TRUSTED_LEAGUES:
        score += 5
    if analysis["draw_rate"] > 0.4:
        score -= 10
    # Bonus pour combo BTTS
    if prediction.get("combo"):
        score += 5
    return min(score, 100)

def get_category(score, prediction, analysis):
    # Priorité VIP pour les combos avec au moins 3 matchs H2H
    if prediction.get("combo") is not None and analysis["total_matches"] >= 3:
        return "vip"
    if score >= 65:
        return "vip"
    elif score >= 55:
        return "pro"
    else:
        return "simple"

def get_badge(score):
    if score >= 85:
        return "🏆 PREMIUM LOCK"
    elif score >= 75:
        return "💎 VIP ELITE"
    elif score >= 65:
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

    # 5. Construire l'historique des équipes pour la forme récente
    team_matches = build_team_history(historical)
    print(f"📊 Statistiques de forme calculées pour {len(team_matches)} équipes")

    # 6. Préparer les nouvelles listes
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

        # Obtenir la forme des équipes
        home_form = get_team_form(base["home_team"], team_matches, last_games=5)
        away_form = get_team_form(base["away_team"], team_matches, last_games=5)

        if home_form is None or away_form is None:
            print(f"   ⚠️ Forme incomplète pour {base['home_team'] if home_form is None else base['away_team']}")

        # Générer la prédiction avec BTTS et combo
        prediction = generate_prediction(analysis, home_form, away_form, base["competition"], h2h_list)

        # Ignorer les pronostics "12"
        if prediction["double_chance"] == "12":
            print(f"   ⚠️ Pronostic 12 (match équilibré) ignoré")
            continue

        score = calculate_xpronos_score(analysis, prediction, home_form, away_form, base["competition"])
        category = get_category(score, prediction, analysis)
        badge = get_badge(score)

        # Logos avec cache
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
            "home_form": home_form,
            "away_form": away_form,
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

    # Sauvegarder le cache des logos
    save_logo_cache()

    # Trier par date
    matches.sort(key=lambda x: x["event_date"] or "", reverse=True)

    # Statistiques
    stats = {"total_bets": 0, "wins": 0, "roi": 0}

    # Bookmakers par défaut
    default_bookmakers = [
        {"name": "1xBet",     "logo": "assets/images/1xbet.png",     "url": "https://refpa58144.com/L?tag=d_2054511m_1599c_&site=2054511&ad=1599"},
        {"name": "1win",      "logo": "assets/images/1win.png",      "url": "https://1wrbgb.com/?open=register&p=qqcw"},
        {"name": "Betwinner", "logo": "assets/images/betwinner.png", "url": "https://bwredir.com/299Y"},
        {"name": "Melbet",    "logo": "assets/images/melbet.png",    "url": "https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041"},
        {"name": "Linebet",   "logo": "assets/images/linebet.png",   "url": "https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3072389&ad=22611"},
        {"name": "BetClic",   "logo": "assets/images/betclic.png",   "url": "https://betpari-click.com/2vY0?extid=USD"}
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
    print(f"🎯 Combos BTTS générés : {sum(1 for m in matches if m['prediction'].get('combo'))}")

if __name__ == "__main__":
    main()