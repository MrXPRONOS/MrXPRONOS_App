#!/usr/bin/env python3
"""
update_live.py - Récupère les matchs en direct depuis l'API BSD,
met à jour la table live_matches et valide les prédictions.
"""

import os
import sys
import requests
from supabase import create_client
from datetime import datetime, timedelta
import math

# Vérification des variables d'environnement
missing = []
SUPABASE_URL = os.environ.get("SUPABASE_URL")
if not SUPABASE_URL:
    missing.append("SUPABASE_URL")

SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_KEY:
    missing.append("SUPABASE_KEY")

BSD_API_TOKEN = os.environ.get("BSD_API_TOKEN")
if not BSD_API_TOKEN:
    missing.append("BSD_API_TOKEN")

if missing:
    print("❌ Variables d'environnement manquantes :", ", ".join(missing))
    sys.exit(1)

print("✅ Toutes les variables d'environnement sont présentes.")

# Initialisation Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {"Authorization": f"Token {BSD_API_TOKEN}"}
BASE_URL = "https://sports.bzzoiro.com/api"


def fetch_live():
    """Récupère les matchs en direct depuis l'API BSD."""
    try:
        resp = requests.get(f"{BASE_URL}/live/", headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des matchs live : {e}")
        return []


def compute_momentum(stats):
    """Calcule le momentum à partir des statistiques live."""
    h = stats.get("home", {})
    a = stats.get("away", {})

    def mom(t):
        return (
            t.get("total_shots", 0) * 2
            + t.get("shots_on_target", 0) * 3
            + t.get("corner_kicks", 0) * 1.5
            + t.get("ball_possession", 50) * 0.1
        )

    hm = mom(h)
    am = mom(a)
    total = hm + am
    home_ratio = (hm / total * 100) if total > 0 else 50

    dominance = "home" if home_ratio > 60 else "away" if home_ratio < 40 else "balanced"
    intensity = "high" if total > 50 else ("medium" if total > 25 else "low")

    return {
        "home": round(hm, 1),
        "away": round(am, 1),
        "total": round(total, 1),
        "home_ratio": round(home_ratio, 1),
        "away_ratio": round(100 - home_ratio, 1),
        "dominance": dominance,
        "intensity": intensity,
    }


def compute_pressure(stats, minute):
    """Calcule l'indice de pression."""
    h = stats.get("home", {})
    a = stats.get("away", {})
    if minute <= 0:
        return {"ratio": 1.0, "territory": "balanced"}

    h_attacks = (h.get("attacks") or h.get("total_shots", 0) * 2) / minute
    a_attacks = (a.get("attacks") or a.get("total_shots", 0) * 2) / minute
    h_poss = h.get("ball_possession", 50) / 50
    a_poss = a.get("ball_possession", 50) / 50

    pressure_h = h_attacks * h_poss
    pressure_a = a_attacks * a_poss
    ratio = pressure_h / pressure_a if pressure_a > 0 else 1.0

    territory = (
        "home_dominant" if ratio > 1.5 else "away_dominant" if ratio < 0.67 else "balanced"
    )
    return {"ratio": round(ratio, 2), "territory": territory}


def compute_xg(stats, minute):
    """Calcule l'Expected Goals simplifié."""
    if minute <= 0:
        return 0.0, 0.0
    h = stats.get("home", {})
    a = stats.get("away", {})
    h_quality = (
        h.get("shots_on_target", 0) / h.get("total_shots", 1) if h.get("total_shots") else 0.3
    )
    a_quality = (
        a.get("shots_on_target", 0) / a.get("total_shots", 1) if a.get("total_shots") else 0.3
    )
    xg_h = h.get("shots_on_target", 0) * 0.3 * (1 + h_quality)
    xg_a = a.get("shots_on_target", 0) * 0.3 * (1 + a_quality)
    return round(xg_h, 2), round(xg_a, 2)


def process_match(match):
    """Transforme un match brut en objet pour Supabase."""
    stats = match.get("live_stats", {})
    minute = match.get("current_minute", 0)

    momentum = compute_momentum(stats)
    pressure = compute_pressure(stats, minute)
    xg_h, xg_a = compute_xg(stats, minute)

    return {
        "id": match["id"],
        "home_team": match.get("home_team", ""),
        "away_team": match.get("away_team", ""),
        "home_score": match.get("home_score", 0),
        "away_score": match.get("away_score", 0),
        "minute": minute,
        "period": match.get("period", ""),
        "league": match.get("league", {}),
        "status": match.get("status", ""),
        "stats": stats,
        "momentum": momentum,
        "pressure": pressure,
        "xg_home": xg_h,
        "xg_away": xg_a,
        "updated_at": datetime.utcnow().isoformat(),
    }


def validate_predictions():
    """Valide les prédictions en cours avec les matchs terminés des dernières 48h."""
    try:
        # Récupérer les prédictions non validées
        preds_resp = supabase.table("predictions").select("*").eq("validated", False).execute()
        predictions = preds_resp.data
        if not predictions:
            return

        # Récupérer les matchs terminés des dernières 48h depuis BSD
        now = datetime.utcnow()
        from_date = (now - timedelta(days=2)).strftime("%Y-%m-%d")
        to_date = now.strftime("%Y-%m-%d")
        events_resp = requests.get(
            f"{BASE_URL}/events/",
            headers=HEADERS,
            params={"date_from": from_date, "date_to": to_date, "status": "finished"},
            timeout=15,
        )
        events_resp.raise_for_status()
        finished_matches = events_resp.json().get("results", [])

        # Créer un dictionnaire pour un accès rapide
        match_map = {m["id"]: m for m in finished_matches}

        for pred in predictions:
            match = match_map.get(pred["match_id"])
            if not match:
                continue

            # Récupérer les stats finales
            stats = match.get("live_stats", {})
            outcome = False
            if pred["type"] == "total_shots":
                total = (stats.get("home", {}).get("total_shots", 0) +
                         stats.get("away", {}).get("total_shots", 0))
                outcome = total > pred["threshold"]
            elif pred["type"] == "total_corners":
                total = (stats.get("home", {}).get("corner_kicks", 0) +
                         stats.get("away", {}).get("corner_kicks", 0))
                outcome = total > pred["threshold"]
            elif pred["type"] == "total_fouls":
                total = (stats.get("home", {}).get("fouls", 0) +
                         stats.get("away", {}).get("fouls", 0))
                outcome = total > pred["threshold"]
            # Ajouter d'autres types si nécessaire

            # Mettre à jour la prédiction
            supabase.table("predictions").update({
                "validated": True,
                "outcome": "success" if outcome else "failure",
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", pred["id"]).execute()

            # Créer une notification pour l'utilisateur
            supabase.table("notifications").insert({
                "user_id": "all",
                "title": "Pronostic validé",
                "message": f"{pred['match_label']} : {pred['type']} - {'✅ réussi' if outcome else '❌ échoué'}",
                "priority": "normal",
                "read": False,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

            print(f"✅ Prédiction {pred['id']} validée : {outcome}")

    except Exception as e:
        print(f"❌ Erreur lors de la validation des prédictions : {e}")


def main():
    print(f"[{datetime.utcnow()}] Début de la mise à jour live...")
    live = fetch_live()
    print(f"Récupéré {len(live)} matchs live")

    live_ids = set()
    for m in live:
        enriched = process_match(m)
        supabase.table("live_matches").upsert(enriched, on_conflict="id").execute()
        live_ids.add(m["id"])

    # Supprimer les matchs qui ne sont plus en live
    if live_ids:
        supabase.table("live_matches").delete().not_.in_("id", list(live_ids)).execute()
    else:
        supabase.table("live_matches").delete().neq("id", 0).execute()

    print("Mise à jour des matchs live terminée")

    # Lancer la validation des prédictions
    validate_predictions()
    print("Validation des prédictions terminée")


if __name__ == "__main__":
    main()