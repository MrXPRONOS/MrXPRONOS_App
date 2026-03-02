#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_data.py - Génère data.json avec les matchs du jour/demain/hier,
les prédictions ML et les analyses H2H améliorées (pondération temporelle,
fusion ML+H2H, BTTS, stake, ROI, etc.)
Exécutable toutes les heures pour mettre à jour les statuts et vérifications.
Version avec fusion intelligente et optimisation cache.
"""

import requests
import json
from datetime import datetime, timedelta
import os
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =======================================================
# CONFIGURATION (variables d'environnement)
# =======================================================
API_TOKEN = os.environ.get("BSD_API_TOKEN")
if not API_TOKEN:
    raise ValueError("La variable d'environnement BSD_API_TOKEN n'est pas définie")

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
DATA_FILE = "data.json"

print("="*60)
print(f"🚀 GÉNÉRATION DES DONNÉES - {today}")
print("="*60)

# =======================================================
# FONCTIONS DE RÉCUPÉRATION API
# =======================================================

def fetch_events(date_from, date_to):
    """Récupère tous les événements entre deux dates (pagination gérée)."""
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
    """Récupère les prédictions de l'API."""
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
# FONCTIONS D'ANALYSE H2H (AVEC PONDÉRATION TEMPORELLE)
# =======================================================

def weight_by_date(date_str):
    """Pondère les matchs selon leur ancienneté (les plus récents ont plus de poids)."""
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
    """Récupère l'historique des confrontations depuis le cache global (préchargé)."""
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
    """
    Analyse la liste H2H avec pondération temporelle.
    Retourne un dict avec scores pondérés, dominance, BTTS, etc.
    """
    home_score = 0.0
    away_score = 0.0
    draws_score = 0.0
    total_goals = 0
    matches_count = 0
    btts_count = 0
    last_4 = h2h_list[:4]  # pour l'affichage

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

        if match["home_score"] > 0 and match["away_score"] > 0:
            btts_count += 1

    # Calcul de la dominance
    total_weighted = home_score + away_score + draws_score
    if total_weighted > 0:
        home_dominance = home_score / total_weighted
        away_dominance = away_score / total_weighted
    else:
        home_dominance = away_dominance = 0.0

    goals_avg = total_goals / matches_count if matches_count > 0 else 2.5

    # Probabilité BTTS basée sur les 4 derniers
    btts_last4 = sum(1 for m in h2h_list[:4] if m["home_score"] > 0 and m["away_score"] > 0)
    btts_recommend = btts_last4 >= 3

    return {
        "total_matches": matches_count,
        "home_score": round(home_score, 2),
        "away_score": round(away_score, 2),
        "draws_score": round(draws_score, 2),
        "home_dominance": round(home_dominance, 3),
        "away_dominance": round(away_dominance, 3),
        "goals_avg": round(goals_avg, 2),
        "last_4": last_4,
        "btts_last4": btts_last4,
        "btts_recommend": btts_recommend
    }

def generate_prediction_h2h(analysis, home_team, away_team):
    """
    Génère un pronostic H2H basé sur l'analyse pondérée.
    Retourne double_chance, over_25, btts, confidence.
    """
    # Double chance basé sur dominance
    if analysis["home_dominance"] > analysis["away_dominance"] + 0.1:
        double_chance = "1X"
    elif analysis["away_dominance"] > analysis["home_dominance"] + 0.1:
        double_chance = "X2"
    else:
        double_chance = "12"

    # Over/Under basé sur la moyenne de buts des 4 derniers (ou globale)
    last_4_goals = [m["home_score"] + m["away_score"] for m in analysis["last_4"] if m.get("home_score") and m.get("away_score")]
    avg_goals_last4 = sum(last_4_goals) / len(last_4_goals) if last_4_goals else analysis["goals_avg"]
    over_25 = avg_goals_last4 > 2.5

    # Confiance basée sur la dominance et le nombre de matchs
    dominance = max(analysis["home_dominance"], analysis["away_dominance"])
    base_conf = 50 + (analysis["total_matches"] * 5)
    conf = min(base_conf, 95)
    # Bonus de dominance
    if dominance > 0.7:
        conf = min(conf + 10, 100)
    elif dominance > 0.6:
        conf = min(conf + 5, 100)

    return {
        "double_chance": double_chance,
        "over_25": over_25,
        "btts": analysis["btts_recommend"],
        "confidence": conf
    }

# =======================================================
# FONCTIONS DE FUSION ML + H2H ET CLASSIFICATION
# =======================================================

def calculate_stake(confidence):
    """Détermine le nombre d'unités à miser en fonction de la confiance."""
    if confidence >= 85:
        return 3
    elif confidence >= 70:
        return 2
    else:
        return 1

def classify_by_confidence(final_conf):
    """Classement basé sur la confiance finale."""
    if final_conf >= 85:
        return "vip"
    elif final_conf >= 70:
        return "pro"
    else:
        return "simple"

def model_agreement(h2h_pred, ml_pred):
    """Vérifie si les deux modèles sont d'accord sur le résultat."""
    # On compare le double chance : si les deux sont dans la même direction
    # Simplification : on regarde si le favori est le même
    # Ici on utilise le double_chance, mais pour une vraie comparaison on pourrait utiliser predicted_result
    return h2h_pred.get("double_chance") == ml_pred.get("double_chance")

# =======================================================
# FONCTIONS DE VÉRIFICATION ET ROI
# =======================================================

def verify_prediction(match, prediction):
    """Vérifie si le pronostic est validé par le résultat réel."""
    match['verified_double'] = False
    match['verified_over'] = False
    match['verified_btts'] = False

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

    # BTTS vérification
    if prediction.get('btts'):
        match['verified_btts'] = (home_score > 0 and away_score > 0)
    else:
        match['verified_btts'] = (home_score == 0 or away_score == 0)

def update_bankroll(matches):
    """Calcule les statistiques de ROI à partir des matchs terminés."""
    total_bets = 0
    wins = 0
    for m in matches:
        if m["status"] == "finished" and (m.get("verified_double") is not None):
            total_bets += 1
            # On considère un pari gagnant si double chance validé (ou on peut combiner plusieurs critères)
            if m["verified_double"]:
                wins += 1
    roi = (wins / total_bets * 100) if total_bets else 0
    return {
        "total_bets": total_bets,
        "wins": wins,
        "roi": round(roi, 2)
    }

# =======================================================
# FONCTION PRINCIPALE
# =======================================================

def main():
    print("\n📅 Récupération des matchs du jour, demain, hier...")
    events_today = fetch_events(today, today)
    events_tomorrow = fetch_events(tomorrow, tomorrow)
    events_yesterday = fetch_events(yesterday, yesterday)

    all_new_events = events_today + events_tomorrow + events_yesterday
    print(f"\n✅ {len(all_new_events)} événements récupérés depuis l'API")

    # Charger l'ancien fichier data.json s'il existe
    old_data = {}
    old_matches_by_id = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
            old_matches_by_id = {m['id']: m for m in old_data.get('matches', [])}
        print(f"📂 Ancien fichier chargé : {len(old_matches_by_id)} matchs")

    # Charger le cache global une seule fois
    global_cache = []
    if os.path.exists(GLOBAL_CACHE_FILE):
        with open(GLOBAL_CACHE_FILE, 'r', encoding='utf-8') as f:
            global_cache = json.load(f)
        print(f"📂 Cache global chargé : {len(global_cache)} matchs")
    else:
        print("⚠️ Cache global introuvable, les analyses H2H seront limitées.")

    print("\n📈 Récupération des prédictions ML...")
    predictions_upcoming = fetch_predictions(upcoming=True)
    predictions_past = fetch_predictions(upcoming=False)
    all_predictions = predictions_upcoming + predictions_past
    print(f"✅ {len(all_predictions)} prédictions récupérées")

    pred_dict = {p['event']['id']: p for p in all_predictions}

    # Structure pour les nouveaux matchs
    new_matches = []
    categories = {"simple": [], "pro": [], "vip": []}

    # Traiter les nouveaux événements
    for event in all_new_events:
        print(f"\n🔍 Analyse match {event.get('id', 'inconnu')}")
        match_id = event.get("id")
        if not isinstance(match_id, int):
            print("   ⚠️ ID invalide, ignoré")
            continue

        home_team_obj = event.get("home_team_obj")
        away_team_obj = event.get("away_team_obj")
        if not home_team_obj or not away_team_obj:
            print("   ⚠️ Équipes manquantes, ignoré")
            continue

        league = event["league"]
        event_date = event["event_date"][:10]
        event_datetime = event["event_date"]

        print(f"   {home_team_obj['name']} vs {away_team_obj['name']} ({league['name']})")

        # Récupérer H2H depuis le cache global
        h2h = get_h2h_from_cache(home_team_obj["id"], away_team_obj["id"], global_cache)
        print(f"   → {len(h2h)} confrontations H2H dans le cache")

        analysis_h2h = analyze_h2h(h2h, home_team_obj["name"], away_team_obj["name"])
        prediction_h2h = generate_prediction_h2h(analysis_h2h, home_team_obj["name"], away_team_obj["name"])

        ml_pred = pred_dict.get(match_id)
        ml_full = None
        confidence_ml = 0
        if ml_pred:
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
            raw_confidence = ml_pred.get('confidence', 0.5)
            if raw_confidence <= 1:
                confidence_ml = round(raw_confidence * 100, 1)
            else:
                confidence_ml = round(raw_confidence, 1)

            # Construction d'une prédiction ML simplifiée pour la fusion
            prob_home = ml_pred.get('prob_home_win', 0)
            prob_away = ml_pred.get('prob_away_win', 0)
            prob_draw = ml_pred.get('prob_draw', 0)
            predicted_result = ml_pred.get('predicted_result', '')
            if predicted_result == "H":
                double_chance_ml = "1X"
            elif predicted_result == "A":
                double_chance_ml = "X2"
            else:
                double_chance_ml = "12"
            over_25_ml = ml_pred.get('over_25_recommend', False)
            btts_ml = ml_pred.get('btts_recommend', False)
            prediction_ml = {
                "double_chance": double_chance_ml,
                "over_25": over_25_ml,
                "btts": btts_ml,
                "confidence": confidence_ml,
                "source": "ML"
            }
        else:
            prediction_ml = None

        # Fusion intelligente H2H + ML
        if prediction_ml:
            # Pondération : 40% H2H, 60% ML
            final_conf = prediction_h2h["confidence"] * 0.4 + confidence_ml * 0.6
            final_double_chance = prediction_h2h["double_chance"] if model_agreement(prediction_h2h, prediction_ml) else "12"  # en cas de désaccord, on met "12" par prudence
            final_over = prediction_h2h["over_25"] or prediction_ml["over_25"]  # OU logique
            final_btts = prediction_h2h["btts"] or prediction_ml["btts"]
            # Si accord, bonus
            if model_agreement(prediction_h2h, prediction_ml):
                final_conf = min(final_conf + 10, 100)
            source = "fusion"
        else:
            # Pas de ML, on utilise H2H
            final_conf = prediction_h2h["confidence"]
            final_double_chance = prediction_h2h["double_chance"]
            final_over = prediction_h2h["over_25"]
            final_btts = prediction_h2h["btts"]
            source = "h2h"

        final_prediction = {
            "double_chance": final_double_chance,
            "over_25": final_over,
            "btts": final_btts,
            "confidence": round(final_conf, 1),
            "source": source,
            "stake": calculate_stake(final_conf)
        }

        # Calcul du score prédit approximatif
        avg_goals = analysis_h2h["goals_avg"]
        expected_home = round(avg_goals * analysis_h2h["home_dominance"] * 2)
        expected_away = round(avg_goals * analysis_h2h["away_dominance"] * 2)
        final_prediction["predicted_score"] = f"{expected_home}-{expected_away}"

        # Classification basée sur la confiance finale
        category = classify_by_confidence(final_conf)

        # Construction de l'objet match
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
            "prediction": final_prediction,
            "category": category,
            "verified_double": False,
            "verified_over": False,
            "verified_btts": False,
            "ml_full": ml_full
        }

        if event_date == yesterday.isoformat():
            verify_prediction(match_data, final_prediction)
            if match_data["verified_double"] or match_data["verified_over"] or match_data["verified_btts"]:
                print(f"   ✅ Vérification : DC {match_data['verified_double']} / Over {match_data['verified_over']} / BTTS {match_data['verified_btts']}")

        new_matches.append(match_data)
        categories[category].append(match_data)
        print(f"   ✅ Catégorie: {category}, Confiance: {final_conf}%, Stake: {final_prediction['stake']}u")

    # Fusion avec les anciens matchs
    new_matches_by_id = {m['id']: m for m in new_matches}
    for old_id, old_match in old_matches_by_id.items():
        if old_id not in new_matches_by_id:
            print(f"📌 Conservation de l'ancien match {old_id} ({old_match['home_team']} vs {old_match['away_team']})")
            new_matches.append(old_match)
            categories[old_match['category']].append(old_match)

    # Calcul du ROI
    stats = update_bankroll(new_matches)

    # Construction du fichier final
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
    print(f"\n💾 {DATA_FILE} généré avec {len(new_matches)} matchs, ROI: {stats['roi']}%")

if __name__ == "__main__":
    main()