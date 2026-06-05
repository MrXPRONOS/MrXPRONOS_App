#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_data.py - Génère les pronostics à partir des données SportData
et des scores déjà en base (mis à jour par update_scores.py).

Système de calcul INCHANGÉ :
- exclusion des pronostics "12"
- seuils et H2H identiques
- rétention 14 jours dans data.json
- stats réelles calculées
- intégration ML (auto_train / ml_model) SANS casser la logique métier

Logos (priorité) :
1) SportData v2 (clé requise) -> https://v2.football.sportsapipro.com/api/teams/{teamId}/image
2) SportData v1 images (public) -> https://v1.football.sportsapipro.com/images/competitors/{id}?imageVersion={v}
3) TheSportsDB fallback
4) fallback home.webp / away.webp

Règle anti-trucage :
- une fois qu’un jour est passé, on n’ajoute plus de nouveaux matchs
- pour les matchs déjà publiés sur un jour passé, on met seulement à jour :
  score / status / is_finished / verified_*

LOGS (GitHub Actions friendly):
- logs détaillés sur: création pronostic, skip, téléchargements logos, cache hit, fallback, etc.
- niveau réglable via env LOG_LEVEL=DEBUG/INFO/WARNING (défaut INFO)
- optionnel: MAX_LOGO_DOWNLOADS_PER_RUN (0 = illimité)
"""

import os
import re
import json
import logging
import requests
from datetime import datetime, timedelta, timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ml_model import load_model, predict_proba, build_feature_vector_from_row

# =======================================================
# LOGGING
# =======================================================
LOG_LEVEL = (os.environ.get("LOG_LEVEL") or "INFO").upper().strip()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("generate_data")

# =======================================================
# CONFIGURATION
# =======================================================
SPORTDATA_API_KEY = os.environ.get("SPORTDATA_API_KEY")
if not SPORTDATA_API_KEY:
    raise ValueError("La variable d'environnement SPORTDATA_API_KEY n'est pas définie")

THESPORTSDB_API_KEY = "3"  # clé publique TheSportsDB

# SportData (matches)
SPORTDATA_URL = "https://v1.football.sportsapipro.com/games/allscores"
HEADERS = {"x-api-key": SPORTDATA_API_KEY}

# SportData v2 (logos) - clé requise
SPORTDATA_V2_BASE = "https://v2.football.sportsapipro.com/api"

# SportData v1 images (public)
SPORTDATA_V1_IMAGES_BASE = "https://v1.football.sportsapipro.com/images"

session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

UTC = timezone.utc
today = datetime.now(UTC).date()
tomorrow = today + timedelta(days=1)
yesterday = today - timedelta(days=1)

DATA_FILE = "data.json"
CACHE_DIR = "cache"
GLOBAL_CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")
LOGO_CACHE_FILE = os.path.join(CACHE_DIR, "logos_cache.json")

TEAM_LOGO_DIR = os.path.join("assets", "images", "teams")

RETENTION_DAYS = 14

# Optionnel: limiter les downloads de logos/run (0 = illimité)
try:
    MAX_LOGO_DOWNLOADS_PER_RUN = int(os.environ.get("MAX_LOGO_DOWNLOADS_PER_RUN", "0"))
except Exception:
    MAX_LOGO_DOWNLOADS_PER_RUN = 0

logger.info("=" * 70)
logger.info("GÉNÉRATION DES PRONOSTICS - %s UTC (rétention %s jours)", today, RETENTION_DAYS)
logger.info("LOG_LEVEL=%s | MAX_LOGO_DOWNLOADS_PER_RUN=%s", LOG_LEVEL, MAX_LOGO_DOWNLOADS_PER_RUN)
logger.info("=" * 70)

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(TEAM_LOGO_DIR, exist_ok=True)

# =======================================================
# STATS LOGOS (pour logs)
# =======================================================
logo_run_stats = {
    "cache_hit": 0,
    "download_ok": 0,
    "download_fail": 0,
    "fallback_used": 0,
    "skipped_by_limit": 0,
}
logo_download_count = 0

# =======================================================
# GESTION DU CACHE DES LOGOS
# =======================================================
logo_cache = {}
if os.path.exists(LOGO_CACHE_FILE):
    try:
        with open(LOGO_CACHE_FILE, "r", encoding="utf-8") as f:
            logo_cache = json.load(f)
        logger.info("Logo cache chargé: %s entrées (%s)", len(logo_cache), LOGO_CACHE_FILE)
    except Exception:
        logo_cache = {}
        logger.warning("Logo cache illisible, reset.")

def save_logo_cache():
    with open(LOGO_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(logo_cache, f, indent=2, ensure_ascii=False)
    logger.info("Logo cache sauvegardé: %s entrées (%s)", len(logo_cache), LOGO_CACHE_FILE)

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

def _can_download_more_logos() -> bool:
    global logo_download_count
    if MAX_LOGO_DOWNLOADS_PER_RUN and logo_download_count >= MAX_LOGO_DOWNLOADS_PER_RUN:
        return False
    return True

def _mark_logo_download():
    global logo_download_count
    logo_download_count += 1

def download_image(url: str, local_path: str, headers: dict | None = None, label: str = "") -> str | None:
    """
    Télécharge une image.
    - Cache local: si existe déjà > 200 bytes => pas de download
    - Refuse HTML
    - Supporte JSON contenant {"url": "..."} (au cas où)
    """
    try:
        local_path = norm_path(local_path)

        if os.path.exists(local_path) and os.path.getsize(local_path) > 200:
            logger.debug("[logo] cache-file hit (%s) -> %s", label, local_path)
            logo_run_stats["cache_hit"] += 1
            return local_path

        if not _can_download_more_logos():
            logo_run_stats["skipped_by_limit"] += 1
            logger.warning("[logo] limite atteinte, skip download (%s) url=%s", label, url)
            return None

        logger.info("[logo] téléchargement (%s) url=%s -> %s", label, url, local_path)
        _mark_logo_download()

        resp = session.get(url, headers=headers, timeout=20)
        if resp.status_code != 200 or not resp.content:
            logo_run_stats["download_fail"] += 1
            logger.warning("[logo] échec HTTP %s (%s) url=%s", resp.status_code, label, url)
            return None

        ctype = (resp.headers.get("content-type") or "").lower()

        # si JSON, tenter extraction d'une URL d'image
        if "application/json" in ctype:
            try:
                j = resp.json()
                img_url = j.get("url")
                if not img_url or img_url == url:
                    logo_run_stats["download_fail"] += 1
                    logger.warning("[logo] JSON sans url exploitable (%s) url=%s", label, url)
                    return None

                logger.info("[logo] JSON -> téléchargement binaire (%s) img_url=%s", label, img_url)
                if not _can_download_more_logos():
                    logo_run_stats["skipped_by_limit"] += 1
                    logger.warning("[logo] limite atteinte, skip download (%s) img_url=%s", label, img_url)
                    return None

                _mark_logo_download()
                resp2 = session.get(img_url, headers=headers, timeout=20)
                if resp2.status_code != 200 or not resp2.content:
                    logo_run_stats["download_fail"] += 1
                    logger.warning("[logo] échec HTTP %s (%s) img_url=%s", resp2.status_code, label, img_url)
                    return None
                ctype2 = (resp2.headers.get("content-type") or "").lower()
                if "application/json" in ctype2 or "text/html" in ctype2:
                    logo_run_stats["download_fail"] += 1
                    logger.warning("[logo] type invalide (%s): %s", label, ctype2)
                    return None
                resp = resp2
                ctype = ctype2
            except Exception as e:
                logo_run_stats["download_fail"] += 1
                logger.warning("[logo] JSON parse error (%s): %s", label, e)
                return None

        if "text/html" in ctype:
            logo_run_stats["download_fail"] += 1
            logger.warning("[logo] HTML reçu (%s), abandon url=%s", label, url)
            return None

        with open(local_path, "wb") as f:
            f.write(resp.content)

        if os.path.getsize(local_path) > 200:
            logo_run_stats["download_ok"] += 1
            logger.info("[logo] OK (%s) size=%s content-type=%s path=%s",
                        label, os.path.getsize(local_path), ctype, local_path)
            return local_path

        logo_run_stats["download_fail"] += 1
        logger.warning("[logo] fichier trop petit (%s) path=%s", label, local_path)
        return None
    except Exception as e:
        logo_run_stats["download_fail"] += 1
        logger.warning("[logo] exception (%s): %s", label, e)
        return None

# ---------- cache keys ----------
def cache_key_sportdata_v2(team_id):
    tid = str(team_id) if team_id is not None else ""
    return f"sdv2img:{tid}"

def cache_key_sportdata_v1(competitor_id, image_version):
    cid = str(competitor_id) if competitor_id is not None else ""
    ver = str(image_version) if image_version is not None else "0"
    return f"sdv1img:{cid}:v{ver}"

def cache_key_thesportsdb(team_name: str):
    return f"tsdb:{(team_name or '').strip().lower()}"

# ---------- SportData v2 logo ----------
def get_logo_sportdata_v2(team_id) -> str | None:
    if not team_id:
        return None

    key = cache_key_sportdata_v2(team_id)
    if key in logo_cache:
        cached = resolve_existing_path(logo_cache.get(key))
        if cached:
            logo_cache[key] = cached
            logo_run_stats["cache_hit"] += 1
            logger.debug("[logo] cache-hit sdv2 team_id=%s -> %s", team_id, cached)
            return cached
        if logo_cache.get(key) is None:
            logger.debug("[logo] cache-hit(sd v2) négatif team_id=%s", team_id)
            logo_run_stats["cache_hit"] += 1
            return None

    url = f"{SPORTDATA_V2_BASE}/teams/{team_id}/image"
    filename = f"sdv2-team-{team_id}.png"
    local_path = norm_path(os.path.join(TEAM_LOGO_DIR, filename))

    img_headers = dict(HEADERS)
    img_headers["Accept"] = "image/*"

    p = download_image(url, local_path, headers=img_headers, label=f"sdv2 team:{team_id}")
    logo_cache[key] = p
    return p

# ---------- SportData v1 logo (public fallback) ----------
def get_logo_sportdata_v1(competitor_id, image_version) -> str | None:
    if not competitor_id:
        return None

    key = cache_key_sportdata_v1(competitor_id, image_version)
    if key in logo_cache:
        cached = resolve_existing_path(logo_cache.get(key))
        if cached:
            logo_cache[key] = cached
            logo_run_stats["cache_hit"] += 1
            logger.debug("[logo] cache-hit sdv1 competitor=%s v=%s -> %s", competitor_id, image_version, cached)
            return cached
        if logo_cache.get(key) is None:
            logger.debug("[logo] cache-hit(sd v1) négatif competitor=%s v=%s", competitor_id, image_version)
            logo_run_stats["cache_hit"] += 1
            return None

    if image_version:
        url = f"{SPORTDATA_V1_IMAGES_BASE}/competitors/{competitor_id}?imageVersion={image_version}"
        filename = f"sdv1-{competitor_id}-v{image_version}.png"
    else:
        url = f"{SPORTDATA_V1_IMAGES_BASE}/competitors/{competitor_id}"
        filename = f"sdv1-{competitor_id}.png"

    local_path = norm_path(os.path.join(TEAM_LOGO_DIR, filename))
    p = download_image(url, local_path, headers=None, label=f"sdv1 competitor:{competitor_id}")
    logo_cache[key] = p
    return p

def get_logo_thesportsdb(team_name: str) -> str | None:
    if not team_name:
        return None

    key = cache_key_thesportsdb(team_name)
    if key in logo_cache:
        cached = resolve_existing_path(logo_cache.get(key))
        if cached:
            logo_cache[key] = cached
            logo_run_stats["cache_hit"] += 1
            logger.debug("[logo] cache-hit tsdb team=%s -> %s", team_name, cached)
            return cached
        if logo_cache.get(key) is None:
            logo_run_stats["cache_hit"] += 1
            logger.debug("[logo] cache-hit(tsdb) négatif team=%s", team_name)
            return None

    # TSDB = 2 requêtes (search puis image)
    try:
        search_url = (
            f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_API_KEY}/searchteams.php"
            f"?t={requests.utils.quote(team_name)}"
        )
        logger.info("[logo] TSDB search team=%s url=%s", team_name, search_url)
        resp = session.get(search_url, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            teams = data.get("teams", [])
            if teams:
                logo_url = teams[0].get("strTeamBadge") or teams[0].get("strTeamLogo")
                if logo_url:
                    filename = safe_filename(team_name) + ".png"
                    local_path = norm_path(os.path.join(TEAM_LOGO_DIR, filename))

                    if os.path.exists(local_path) and os.path.getsize(local_path) > 200:
                        logo_cache[key] = local_path
                        logo_run_stats["cache_hit"] += 1
                        logger.debug("[logo] cache-file hit tsdb team=%s -> %s", team_name, local_path)
                        return local_path

                    # download image
                    p = download_image(logo_url, local_path, headers=None, label=f"tsdb team:{team_name}")
                    logo_cache[key] = p
                    return p
    except Exception as e:
        logger.warning("[logo] TSDB exception team=%s: %s", team_name, e)

    logo_cache[key] = None
    return None

def get_team_logo(team_name: str, competitor_id=None, image_version=None, side: str = "home") -> str | None:
    # 1) SportData v2 (clé)
    p = get_logo_sportdata_v2(competitor_id)
    if p:
        return p

    # 2) SportData v1 (public)
    p = get_logo_sportdata_v1(competitor_id, image_version)
    if p:
        return p

    # 3) TheSportsDB fallback
    p = get_logo_thesportsdb(team_name)
    if p:
        return p

    # 4) fallback local
    logo_run_stats["fallback_used"] += 1
    fallback = "assets/images/away.webp" if side == "away" else "assets/images/home.webp"
    logger.debug("[logo] fallback local team=%s side=%s -> %s", team_name, side, fallback)
    return fallback

# =======================================================
# FONCTIONS SPORTDATA (MATCHS)
# =======================================================
def fetch_games(date_from, date_to):
    params = {
        "startDate": date_from.strftime("%d/%m/%Y"),
        "endDate": date_to.strftime("%d/%m/%Y"),
        "sports": 1,
        "showOdds": "false",
        "onlyMajorGames": "false",
    }
    try:
        logger.info("SportData fetch: %s -> %s", params["startDate"], params["endDate"])
        resp = session.get(SPORTDATA_URL, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        games = data.get("games", [])
        logger.info("SportData fetch OK: %s matchs (%s -> %s)", len(games), params["startDate"], params["endDate"])
        return games
    except Exception as e:
        logger.error("Erreur SportData fetch (%s -> %s): %s",
                     params.get("startDate"), params.get("endDate"), e)
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

    status_text = game.get("statusText", "") or ""
    status_group = game.get("statusGroup")

    lowered = status_text.lower().strip()
    is_finished = (
        status_group == 4
        and lowered not in ("postponed", "suspended", "cancelled")
        and home_score is not None
        and away_score is not None
    )

    return {
        "id": game.get("id"),
        "start_time": start_time,
        "date": start_time[:10] if start_time else "",
        "home_team": home.get("name", ""),
        "away_team": away.get("name", ""),
        "competition": competition,
        "home_score": home_score,
        "away_score": away_score,
        "status_group": status_group,
        "status_text": status_text,
        "is_finished": is_finished,

        # on réutilise ces IDs comme teamId pour v2 logos
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
        logger.warning("Historique introuvable (%s). Exécutez d'abord allmatches.py.", GLOBAL_CACHE_FILE)
        return []
    with open(GLOBAL_CACHE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

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
        "over_25_prob": round(over_25_prob, 3),
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

    return {"double_chance": double_chance, "over_25": over_25, "confidence": confidence}

def calculate_xpronos_score(analysis, prediction):
    score = 0
    score += min(42, analysis["total_matches"] * 7)
    dominance = max(analysis["home_dominance"], analysis["away_dominance"])
    score += min(50, int(dominance * 100 * 0.7))
    if prediction["over_25"]:
        score += 20
    return min(score, 100)

def get_category(score):
    if score >= 110:
        return "vip"
    elif score >= 100:
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
        return {"form_score": 0, "goals_for": 0, "goals_against": 0}

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
        "goals_against": round(ga / len(recent), 2),
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
    return {"total_bets": total_bets, "wins": wins, "roi": round(roi, 1)}

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
        "quality_score": min(100, 50 + analysis.get("total_matches", 0) * 5),
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
    # --- ML ---
    model = load_model()
    compute_ml_score.model = model
    if model:
        logger.info("Modèle ML chargé")
    else:
        logger.warning("Aucun modèle ML disponible, ml_score par défaut")

    # --- Load existing data.json ---
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
            existing_matches = {
                str(m["id"]): m
                for m in existing_data.get("matches", [])
                if m.get("id") is not None
            }
        logger.info("data.json chargé: %s matchs existants", len(existing_matches))
    else:
        existing_data = {
            "matches": [],
            "categories": {"simple": [], "pro": [], "vip": []},
            "stats": {},
            "bookmakers": [],
        }
        existing_matches = {}
        logger.info("data.json absent: initialisation d'une base vide")

    # --- Fetch games ---
    logger.info("Récupération des matchs via SportData (hier/aujourd'hui/demain)...")
    games_today = fetch_games(today, today)
    games_tomorrow = fetch_games(tomorrow, tomorrow)
    games_yesterday = fetch_games(yesterday, yesterday)
    all_new_games = games_today + games_tomorrow + games_yesterday
    logger.info("Total matchs récupérés (brut): %s", len(all_new_games))

    new_infos = {}
    for g in all_new_games:
        info = extract_game_info(g)
        if info.get("id") is not None:
            new_infos[str(info["id"])] = info
    logger.info("Matchs uniques après dédoublonnage: %s", len(new_infos))

    # --- Load historical ---
    historical = load_historical_matches()
    logger.info("Historique chargé: %s matchs", len(historical))
    team_history = build_team_history(historical)

    # --- Generation loop ---
    new_matches = []
    counters = {
        "past_new_skipped": 0,
        "past_updated": 0,
        "h2h_insufficient_skipped": 0,
        "balanced_12_skipped": 0,
        "predictions_created": 0,
    }

    for gid, base in new_infos.items():
        existing = existing_matches.get(gid)

        match_date = (base.get("date") or "")[:10]
        today_str = today.isoformat()
        is_past_day = bool(match_date) and (match_date < today_str)

        label = f"{base.get('home_team','?')} vs {base.get('away_team','?')} ({match_date}) id={gid}"

        # Anti-trucage : aucun nouveau match sur un jour déjà passé
        if is_past_day and not existing:
            counters["past_new_skipped"] += 1
            logger.info("[SKIP anti-trucage] match passé non publié: %s", label)
            continue

        # Jour passé déjà publié : uniquement scores / statut / validation
        if is_past_day and existing:
            updated = dict(existing)

            changed = False
            if base.get("home_score") is not None and base.get("home_score") != updated.get("home_score"):
                updated["home_score"] = base["home_score"]
                changed = True
            if base.get("away_score") is not None and base.get("away_score") != updated.get("away_score"):
                updated["away_score"] = base["away_score"]
                changed = True
            if base.get("status_text") and base.get("status_text") != updated.get("status"):
                updated["status"] = base["status_text"]
                changed = True

            updated["is_finished"] = bool(base.get("is_finished", updated.get("is_finished", False)))

            if not updated.get("home_logo"):
                updated["home_logo"] = get_team_logo(
                    base["home_team"],
                    competitor_id=base.get("home_competitor_id"),
                    image_version=base.get("home_image_version"),
                    side="home",
                )
            if not updated.get("away_logo"):
                updated["away_logo"] = get_team_logo(
                    base["away_team"],
                    competitor_id=base.get("away_competitor_id"),
                    image_version=base.get("away_image_version"),
                    side="away",
                )

            if updated.get("is_finished") and updated.get("home_score") is not None and updated.get("away_score") is not None:
                updated = compute_verified_fields(updated)

            counters["past_updated"] += 1
            logger.info("[UPDATE passé] %s | changed=%s | score=%s-%s | finished=%s",
                        label, changed, updated.get("home_score"), updated.get("away_score"), updated.get("is_finished"))
            new_matches.append(updated)
            continue

        # Jour courant / futur : logique normale
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
            counters["h2h_insufficient_skipped"] += 1
            logger.info("[SKIP H2H] insuffisant (%s) : %s", len(h2h_list), label)
            continue

        analysis = analyze_h2h(h2h_list, base["home_team"], base["away_team"])
        prediction = generate_prediction(analysis)

        if prediction["double_chance"] == "12":
            counters["balanced_12_skipped"] += 1
            logger.info("[SKIP pronostic=12] match équilibré: %s | h2h=%s home_dom=%.3f away_dom=%.3f",
                        label, analysis.get("total_matches"), analysis.get("home_dominance"), analysis.get("away_dominance"))
            continue

        score = calculate_xpronos_score(analysis, prediction)
        category = get_category(score)
        badge = get_badge(score)

        logger.info("[PRONO] %s | DC=%s | over25=%s | conf=%s | xpronos=%s | cat=%s",
                    label,
                    prediction.get("double_chance"),
                    prediction.get("over_25"),
                    prediction.get("confidence"),
                    score,
                    category)

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

        # Ajustement (inchangé)
        if ml_score < 45:
            match["prediction"]["confidence"] = max(35, match["prediction"]["confidence"] - 5)
        elif ml_score >= 70:
            match["prediction"]["confidence"] = min(95, match["prediction"]["confidence"] + 4)

        match["final_score"] = round((match["xpronos_score"] * 0.75) + (ml_score * 0.25), 1)

        logger.info("[SCORE] %s | ml_score=%.1f | final_score=%.1f | badge=%s",
                    label, ml_score, match["final_score"], badge)

        counters["predictions_created"] += 1
        new_matches.append(match)

    save_logo_cache()

    # --- Retention + merge ---
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

    # Recompute verification if finished
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
        {"name": "1xBet", "logo": "assets/images/1xbet.webp", "url": "https://refpa58144.com/L?tag=d_2054511m_1599c_&site=2054511&ad=1599"},
        {"name": "1win", "logo": "assets/images/1win.webp", "url": "https://1wrbgb.com/?open=register&p=qqcw"},
        {"name": "Betwinner", "logo": "assets/images/betwinner.webp", "url": "https://bwredir.com/299Y"},
        {"name": "Melbet", "logo": "assets/images/melbet.webp", "url": "https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041"},
        {"name": "Linebet", "logo": "assets/images/linebet.webp", "url": "https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3034561&ad=22611"},
        {"name": "BetClic", "logo": "assets/images/betclic.webp", "url": "https://betpari-click.com/2vY0?extid=USD"},
    ]

    data = {
        "matches": final_matches,
        "categories": final_categories,
        "stats": stats,
        "bookmakers": existing_data.get("bookmakers", default_bookmakers),
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "retention_days": RETENTION_DAYS,
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # --- Summary logs ---
    logger.info("=" * 70)
    logger.info("FIN génération")
    logger.info("data.json écrit: %s matchs", len(final_matches))
    logger.info("Fenêtre conservée: %s → %s", cutoff, today.isoformat())
    logger.info("Catégories: Simple=%s, Pro=%s, VIP=%s",
                len(final_categories["simple"]), len(final_categories["pro"]), len(final_categories["vip"]))
    logger.info("Stats: total_bets=%s, wins=%s, roi=%s%%", stats["total_bets"], stats["wins"], stats["roi"])
    logger.info("Compteurs: %s", counters)
    logger.info("Logos: downloads=%s | cache_hit=%s | download_ok=%s | download_fail=%s | fallback_used=%s | skipped_by_limit=%s",
                logo_download_count,
                logo_run_stats["cache_hit"],
                logo_run_stats["download_ok"],
                logo_run_stats["download_fail"],
                logo_run_stats["fallback_used"],
                logo_run_stats["skipped_by_limit"])
    logger.info("=" * 70)

if __name__ == "__main__":
    main()