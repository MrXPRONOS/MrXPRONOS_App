#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_data.py - Génère les pronostics à partir des données SportData
et des scores déjà en base (mis à jour par update_scores.py).

⚠️ Système de calcul INCHANGÉ :
- exclusion des pronostics "12"
- seuils et H2H identiques
- rétention 14 jours dans data.json
- stats réelles calculées
- intégration ML (auto_train / ml_model) SANS casser la logique métier

✅ Amélioration UNIQUEMENT logos :
1) SportData Images (public) -> v1.football.sportsapipro.com/images/competitors/{id}?imageVersion={v}
2) TheSportsDB fallback
3) fallback home.webp / away.webp
"""

import os
import re
import json
import requests
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ml_model import load_model, predict_proba, build_feature_vector_from_row

# =======================================================
# CONFIGURATION
# =======================================================
SPORTDATA_API_KEY = os.environ.get("SPORTDATA_API_KEY")
if not SPORTDATA_API_KEY:
    raise ValueError("La variable d'environnement SPORTDATA_API_KEY n'est pas définie")

THESPORTSDB_API_KEY = "3"  # clé publique TheSportsDB

SPORTDATA_URL = "https://v1.football.sportsapipro.com/games/allscores"
HEADERS = {"x-api-key": SPORTDATA_API_KEY}

# Images SportData / SportsAPI Pro (public, pas de clé)
SPORTDATA_V1_IMAGES_BASE = "https://v1.football.sportsapipro.com/images"

session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

today = datetime.now().date()
tomorrow = today + timedelta(days=1)
yesterday = today - timedelta(days=1)

DATA_FILE = "data.json"
CACHE_DIR = "cache"
GLOBAL_CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")
LOGO_CACHE_FILE = os.path.join(CACHE_DIR, "logos_cache.json")

TEAM_LOGO_DIR = os.path.join("assets", "images", "teams")

RETENTION_DAYS = 14

print("=" * 60)
print(f"🚀 GÉNÉRATION DES PRONOSTICS - {today} (rétention {RETENTION_DAYS} jours)")
print("=" * 60)

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(TEAM_LOGO_DIR, exist_ok=True)

# =======================================================
# GESTION DU CACHE DES LOGOS
# =======================================================
logo_cache = {}
if os.path.exists(LOGO_CACHE_FILE):
    try:
        with open(LOGO_CACHE_FILE, "r", encoding="utf-8") as f:
            logo_cache = json.load(f)
    except Exception:
        logo_cache = {}

def save_logo_cache():
    with open(LOGO_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(logo_cache, f, indent=2, ensure_ascii=False)

def norm_path(p: str) -> str:
    return (p or "").replace("\\", "/")

def safe_filename(name: str) -> str:
    name = (name or "").lower().strip()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name or "team"

def resolve_existing_path(path: str) -> str | None:
    """Si le fichier a changé d'extension (convert_images), essayer quelques variantes."""
    if not path:
        return None
    p = norm_path(path)
    if os.path.exists(p) and os.path.getsize(p) > 200:
        return p
    base, _ext = os.path.splitext(p)
    for ext in (".webp", ".png", ".jpg", ".jpeg", ".svg"):
        cand = base + ext
        if os.path.exists(cand) and os.path.getsize(cand) > 200:
            return norm_path(cand)
    return None

def download_image(url: str, local_path: str) -> str | None:
    try:
        local_path = norm_path(local_path)
        if os.path.exists(local_path) and os.path.getsize(local_path) > 200:
            return local_path

        resp = session.get(url, timeout=20)
        if resp.status_code != 200 or not resp.content:
            return None

        # évite d'écrire du HTML d'erreur
        ctype = (resp.headers.get("content-type") or "").lower()
        if "text/html" in ctype or "application/json" in ctype:
            return None

        with open(local_path, "wb") as f:
            f.write(resp.content)

        if os.path.getsize(local_path) > 200:
            return local_path
        return None
    except Exception:
        return None

def cache_key_sportdata(competitor_id, image_version):
    cid = str(competitor_id) if competitor_id is not None else ""
    ver = str(image_version) if image_version is not None else "0"
    return f"sdimg:{cid}:v{ver}"

def cache_key_thesportsdb(team_name: str):
    return f"tsdb:{(team_name or '').strip().lower()}"

def get_logo_sportdata(competitor_id, image_version) -> str | None:
    """
    1) SPORTDATA (public) : /images/competitors/{id}?imageVersion={version}
    On enregistre localement dans assets/images/teams/
    """
    if not competitor_id:
        return None

    key = cache_key_sportdata(competitor_id, image_version)
    if key in logo_cache:
        cached = resolve_existing_path(logo_cache.get(key))
        if cached:
            logo_cache[key] = cached
            return cached
        if logo_cache.get(key) is None:
            return None

    # URL avec imageVersion (recommandé) sinon sans
    if image_version:
        url = f"{SPORTDATA_V1_IMAGES_BASE}/competitors/{competitor_id}?imageVersion={image_version}"
        filename = f"sd-{competitor_id}-v{image_version}.png"
    else:
        url = f"{SPORTDATA_V1_IMAGES_BASE}/competitors/{competitor_id}"
        filename = f"sd-{competitor_id}.png"

    local_path = norm_path(os.path.join(TEAM_LOGO_DIR, filename))
    p = download_image(url, local_path)

    logo_cache[key] = p  # p peut être None
    return p

def get_logo_thesportsdb(team_name: str) -> str | None:
    """
    2) Fallback TheSportsDB :
    Télécharge UNE seule fois en local dans assets/images/teams/
    """
    if not team_name:
        return None

    key = cache_key_thesportsdb(team_name)
    if key in logo_cache:
        cached = resolve_existing_path(logo_cache.get(key))
        if cached:
            logo_cache[key] = cached
            return cached
        if logo_cache.get(key) is None:
            return None

    try:
        search_url = (
            f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_API_KEY}/searchteams.php"
            f"?t={requests.utils.quote(team_name)}"
        )
        resp = session.get(search_url, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            teams = data.get("teams", [])
            if teams:
                logo_url = teams[0].get("strTeamBadge") or teams[0].get("strTeamLogo")
                if logo_url:
                    filename = safe_filename(team_name) + ".png"
                    local_path = norm_path(os.path.join(TEAM_LOGO_DIR, filename))

                    # déjà téléchargé ?
                    if os.path.exists(local_path) and os.path.getsize(local_path) > 200:
                        logo_cache[key] = local_path
                        return local_path

                    # téléchargement
                    img_resp = session.get(logo_url, timeout=15)
                    if img_resp.status_code == 200 and img_resp.content:
                        with open(local_path, "wb") as f:
                            f.write(img_resp.content)
                        if os.path.getsize(local_path) > 200:
                            logo_cache[key] = local_path
                            return local_path
    except Exception:
        pass

    logo_cache[key] = None
    return None

def get_team_logo(team_name: str, competitor_id=None, image_version=None, side: str = "home") -> str | None:
    """
    PRIORITÉ demandée :
    1) SportData images (public)
    2) TheSportsDB
    3) fallback home.webp / away.webp
    """
    # 1) SportData
    p = get_logo_sportdata(competitor_id, image_version)
    if p:
        return p

    # 2) TheSportsDB
    p = get_logo_thesportsdb(team_name)
    if p:
        return p

    # 3) fallback final
    if side == "away":
        return "assets/images/away.webp"
    return "assets/images/home.webp"

# =======================================================
# FONCTIONS SPORTDATA
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

    home = game.get("homeCompetitor", {}) or {}
    away = game.get("awayCompetitor", {}) or {}

    home_score = home.get("score")
    away_score = away.get("score")

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
        "is_finished": (game.get("statusGroup") == 4),

        # ✅ IDs + imageVersion (pour logos SportData)
        "home_competitor_id": home.get("id"),
        "away_competitor_id": away.get("id"),
        "home_image_version": home.get("imageVersion"),
        "away_image_version": away.get("imageVersion"),
    }

# =======================================================
# FONCTIONS D'ANALYSE H2H (INCHANGÉES)
# =======================================================
def load_historical_matches():
    if not os.path.exists(GLOBAL_CACHE_FILE):
        print("⚠️ Fichier historique introuvable. Exécutez d'abord allmatches.py.")
        return []
    with open(GLOBAL_CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def weight_by_date(date_str):
    try:
        match_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        days_old = (datetime.now() - match_date.replace(tzinfo=None)).days
        if days_old < 180:
            return 1.5
        elif days_old < 365:
            return 1.2
        else:
            return 1.0
    except Exception:
        return 1.0

def get_h2h(historical, home_team, away_team, years=2):
    cutoff_date = (datetime.now() - timedelta(days=365 * years)).date()
    h2h = []

    for m in historical:
        try:
            cond = (
                (m["home_team"].lower() == home_team.lower() and m["away_team"].lower() == away_team.lower()) or
                (m["home_team"].lower() == away_team.lower() and m["away_team"].lower() == home_team.lower())
            )
        except Exception:
            continue

        if cond:
            try:
                match_date = datetime.fromisoformat(m["start_time"].replace("Z", "+00:00")).date()
            except Exception:
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
# TEAM FORM (pour ML uniquement) - INCHANGÉ
# =======================================================
def build_team_history(historical):
    team_matches = {}
    for m in historical:
        if not isinstance(m, dict):
            continue
        home = m.get("home_team")
        away = m.get("away_team")
        if not home or not away:
            continue
        team_matches.setdefault(home, []).append(m)
        team_matches.setdefault(away, []).append(m)
    return team_matches

def get_team_form(team, team_history, last_games=5):
    matches = team_history.get(team, [])
    recent = []

    for m in sorted(matches, key=lambda x: x.get("start_time", ""), reverse=True):
        if not m.get("is_finished"):
            continue
        hs = m.get("home_score")
        aas = m.get("away_score")
        if hs is None or aas is None:
            continue
        recent.append(m)
        if len(recent) >= last_games:
            break

    if not recent:
        return {
            "form_score": 0,
            "goals_for": 0,
            "goals_against": 0
        }

    points = 0
    gf = 0
    ga = 0

    for m in recent:
        if m["home_team"].lower() == team.lower():
            team_goals = m["home_score"]
            opp_goals = m["away_score"]
        else:
            team_goals = m["away_score"]
            opp_goals = m["home_score"]

        gf += team_goals
        ga += opp_goals

        if team_goals > opp_goals:
            points += 3
        elif team_goals == opp_goals:
            points += 1

    form_score = points / (len(recent) * 3)

    return {
        "form_score": round(form_score, 3),
        "goals_for": round(gf / len(recent), 2),
        "goals_against": round(ga / len(recent), 2)
    }

# =======================================================
# HELPERS RETENTION / STATS - INCHANGÉ
# =======================================================
def compute_verified_fields(match):
    prediction = match.get("prediction", {})
    dc = prediction.get("double_chance")
    over_25 = prediction.get("over_25", False)
    hs = match.get("home_score")
    aas = match.get("away_score")

    match["verified_double"] = False
    match["verified_over"] = False

    if hs is None or aas is None:
        return match

    if dc == "1X":
        match["verified_double"] = (hs > aas) or (hs == aas)
    elif dc == "X2":
        match["verified_double"] = (hs == aas) or (hs < aas)

    total_goals = hs + aas
    match["verified_over"] = (total_goals > 2.5) if over_25 else (total_goals <= 2.5)

    return match

def retention_filter(matches, cutoff_date):
    kept = []
    for m in matches:
        try:
            d = str(m.get("date", ""))[:10]
            if d and d >= cutoff_date:
                kept.append(m)
        except Exception:
            continue
    return kept

def merge_match(old_match, new_match):
    merged = dict(old_match or {})
    merged.update(new_match or {})

    for field in ["home_score", "away_score", "status", "is_finished"]:
        if merged.get(field) is None and old_match.get(field) is not None:
            merged[field] = old_match.get(field)

    for field in ["home_logo", "away_logo", "league_logo"]:
        if not merged.get(field) and old_match.get(field):
            merged[field] = old_match.get(field)

    if old_match.get("verified_double") is True and not merged.get("verified_double"):
        merged["verified_double"] = True
    if old_match.get("verified_over") is True and not merged.get("verified_over"):
        merged["verified_over"] = True

    return merged

def compute_stats(matches):
    total_bets = 0
    wins = 0

    for m in matches:
        if m.get("is_finished"):
            total_bets += 1
            if m.get("verified_double"):
                wins += 1

    roi = ((wins - total_bets) / total_bets * 100) if total_bets > 0 else 0

    return {
        "total_bets": total_bets,
        "wins": wins,
        "roi": round(roi, 1)
    }

# =======================================================
# ML SCORE - INCHANGÉ
# =======================================================
def compute_ml_score(match, analysis, prediction):
    try:
        model = compute_ml_score.model
    except AttributeError:
        model = None

    if model is None:
        return 50.0

    home_form = match.get("home_form", {}) or {}
    away_form = match.get("away_form", {}) or {}

    row = {
        "confidence": prediction.get("confidence", 0),
        "xpronos_score": match.get("xpronos_score", 0),
        "final_score": match.get("xpronos_score", 0),
        "value_bet": 0,
        "used_poisson_fallback": 0,
        "h2h_total_matches": analysis.get("total_matches", 0),
        "home_dominance": analysis.get("home_dominance", 0),
        "away_dominance": analysis.get("away_dominance", 0),
        "draw_rate": max(0, 1 - analysis.get("home_dominance", 0) - analysis.get("away_dominance", 0)),
        "home_form_score": home_form.get("form_score", 0),
        "away_form_score": away_form.get("form_score", 0),
        "home_goals_for": home_form.get("goals_for", 0),
        "away_goals_for": away_form.get("goals_for", 0),
        "home_goals_against": home_form.get("goals_against", 0),
        "away_goals_against": away_form.get("goals_against", 0),
        "quality_score": min(100, 50 + analysis.get("total_matches", 0) * 5)
    }

    try:
        features = build_feature_vector_from_row(row)
        proba = predict_proba(model, features)
        return round(proba * 100, 1)
    except Exception:
        return 50.0

# =======================================================
# FONCTION PRINCIPALE
# =======================================================
def main():
    model = load_model()
    compute_ml_score.model = model
    if model:
        print("🤖 Modèle ML chargé")
    else:
        print("⚠️ Aucun modèle ML disponible, ml_score par défaut")

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
            existing_matches = {
                str(m["id"]): m
                for m in existing_data.get("matches", [])
                if m.get("id") is not None
            }
    else:
        existing_data = {
            "matches": [],
            "categories": {"simple": [], "pro": [], "vip": []},
            "stats": {},
            "bookmakers": []
        }
        existing_matches = {}

    print("\n📅 Récupération des matchs via SportData...")
    games_today = fetch_games(today, today)
    games_tomorrow = fetch_games(tomorrow, tomorrow)
    games_yesterday = fetch_games(yesterday, yesterday)
    all_new_games = games_today + games_tomorrow + games_yesterday
    print(f"✅ {len(all_new_games)} matchs récupérés")

    new_infos = {}
    for g in all_new_games:
        info = extract_game_info(g)
        if info.get("id") is not None:
            new_infos[str(info["id"])] = info

    historical = load_historical_matches()
    print(f"📂 Historique chargé : {len(historical)} matchs")
    team_history = build_team_history(historical)

    new_matches = []

    for gid, base in new_infos.items():
        existing = existing_matches.get(gid)

        if existing:
            home_score = existing.get("home_score")
            away_score = existing.get("away_score")
            status = existing.get("status")
            is_finished = existing.get("is_finished", base["is_finished"])
        else:
            home_score = base["home_score"]
            away_score = base["away_score"]
            status = base["status_text"]
            is_finished = base["is_finished"]

        h2h_list = get_h2h(historical, base["home_team"], base["away_team"], years=2)
        if len(h2h_list) < 2:
            print(f"⚠️ Match {base['home_team']} vs {base['away_team']} ignoré (H2H insuffisant)")
            continue

        analysis = analyze_h2h(h2h_list, base["home_team"], base["away_team"])
        prediction = generate_prediction(analysis)

        if prediction["double_chance"] == "12":
            print(f"   ⚠️ Pronostic 12 (match équilibré) ignoré")
            continue

        score = calculate_xpronos_score(analysis, prediction)
        category = get_category(score)
        badge = get_badge(score)

        # ✅ LOGOS (priorité SportData -> TheSportsDB -> fallback home/away.webp)
        home_logo = get_team_logo(
            base["home_team"],
            competitor_id=base.get("home_competitor_id"),
            image_version=base.get("home_image_version"),
            side="home",
        )
        away_logo = get_team_logo(
            base["away_team"],
            competitor_id=base.get("away_competitor_id"),
            image_version=base.get("away_image_version"),
            side="away",
        )

        home_form = get_team_form(base["home_team"], team_history)
        away_form = get_team_form(base["away_team"], team_history)

        match = {
            "id": base["id"],
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
            "is_finished": is_finished,

            "verified_double": False,
            "verified_over": False,
        }

        if is_finished and home_score is not None and away_score is not None:
            match = compute_verified_fields(match)

        ml_score = compute_ml_score(match, analysis, prediction)
        match["ml_score"] = ml_score

        if ml_score < 45:
            match["prediction"]["confidence"] = max(35, match["prediction"]["confidence"] - 5)
        elif ml_score >= 70:
            match["prediction"]["confidence"] = min(95, match["prediction"]["confidence"] + 4)

        match["final_score"] = round((match["xpronos_score"] * 0.75) + (ml_score * 0.25), 1)

        new_matches.append(match)

    # save cache logos
    save_logo_cache()

    cutoff = (today - timedelta(days=RETENTION_DAYS)).isoformat()

    old_retained = retention_filter(list(existing_matches.values()), cutoff)
    old_by_id = {str(m["id"]): m for m in old_retained if m.get("id") is not None}
    new_by_id = {str(m["id"]): m for m in new_matches if m.get("id") is not None}

    final_by_id = dict(old_by_id)
    for gid, nm in new_by_id.items():
        if gid in final_by_id:
            final_by_id[gid] = merge_match(final_by_id[gid], nm)
        else:
            final_by_id[gid] = nm

    final_matches = list(final_by_id.values())

    for m in final_matches:
        if m.get("is_finished") and m.get("home_score") is not None and m.get("away_score") is not None:
            compute_verified_fields(m)

    final_matches.sort(key=lambda x: (x.get("final_score", 0), x.get("event_date") or ""), reverse=True)

    final_categories = {"simple": [], "pro": [], "vip": []}
    for m in final_matches:
        cat = m.get("category", "simple")
        if cat not in final_categories:
            cat = "simple"
        final_categories[cat].append(m)

    stats = compute_stats(final_matches)

    default_bookmakers = [
        {"name": "1xBet",     "logo": "assets/images/1xbet.webp",     "url": "https://refpa58144.com/L?tag=d_2054511m_1599c_&site=2054511&ad=1599"},
        {"name": "1win",      "logo": "assets/images/1win.webp",      "url": "https://1wrbgb.com/?open=register&p=qqcw"},
        {"name": "Betwinner", "logo": "assets/images/betwinner.webp", "url": "https://bwredir.com/299Y"},
        {"name": "Melbet",    "logo": "assets/images/melbet.webp",    "url": "https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041"},
        {"name": "Linebet",   "logo": "assets/images/linebet.webp",   "url": "https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3072389&ad=22611"},
        {"name": "BetClic",   "logo": "assets/images/betclic.webp",   "url": "https://betpari-click.com/2vY0?extid=USD"}
    ]

    data = {
        "matches": final_matches,
        "categories": final_categories,
        "stats": stats,
        "bookmakers": existing_data.get("bookmakers", default_bookmakers),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "retention_days": RETENTION_DAYS
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n💾 {DATA_FILE} généré avec {len(final_matches)} matchs")
    print(f"📅 Fenêtre conservée : {cutoff} → {today.isoformat()}")
    print(f"📊 Catégories : Simple={len(final_categories['simple'])}, Pro={len(final_categories['pro'])}, VIP={len(final_categories['vip'])}")
    print(f"📈 Stats : total_bets={stats['total_bets']}, wins={stats['wins']}, roi={stats['roi']}%")

if __name__ == "__main__":
    main()