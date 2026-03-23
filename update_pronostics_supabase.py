#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_pronostics_supabase.py - Synchronise les pronostics depuis data.json vers Supabase

Version refondue :
- plus de champs utiles
- upsert propre
- validation des matchs d'hier
- robustesse renforcée
"""

import os
import json
from datetime import datetime, timedelta
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("Les variables SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY sont requises")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def safe_load_data():
    if not os.path.exists("data.json"):
        print("❌ data.json introuvable")
        return None

    try:
        with open("data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Impossible de lire data.json : {e}")
        return None


def normalize_match_row(match):
    pred = match.get("prediction", {}) or {}

    return {
        "match_id": str(match.get("id", "")),
        "match": f"{match.get('home_team', '')} vs {match.get('away_team', '')}",
        "home_team": match.get("home_team"),
        "away_team": match.get("away_team"),
        "prediction": pred.get("double_chance"),
        "confidence": pred.get("confidence"),
        "cote": pred.get("odds"),
        "competition": match.get("league"),
        "category": match.get("category"),
        "badge": match.get("badge"),
        "date": match.get("date"),
        "event_date": match.get("event_date"),
        "status": match.get("status"),
        "home_score": match.get("home_score"),
        "away_score": match.get("away_score"),
        "final_score": match.get("final_score"),
        "xpronos_score": match.get("xpronos_score"),
        "value_bet": bool(match.get("value_bet", False)),
        "verified_double": bool(match.get("verified_double", False)),
        "is_finished": bool(match.get("is_finished", False)),
        "valide": bool(match.get("verified_double", False)),
        "updated_at": datetime.utcnow().isoformat()
    }


def main():
    data = safe_load_data()
    if not data:
        return

    matches = data.get("matches", [])
    if not isinstance(matches, list):
        print("⚠️ Format invalide : matches n'est pas une liste")
        return

    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)

    allowed_dates = {
        today.isoformat(),
        tomorrow.isoformat(),
        yesterday.isoformat()
    }

    relevant_matches = [m for m in matches if m.get("date") in allowed_dates]

    print("📅 Synchronisation des pronostics vers Supabase...")
    print(f"   Total matchs ciblés : {len(relevant_matches)}")

    if not relevant_matches:
        print("ℹ️ Aucun match à synchroniser.")
        return

    rows = []
    for m in relevant_matches:
        try:
            row = normalize_match_row(m)
            if row["match_id"] and row["match"] and row["date"]:
                rows.append(row)
        except Exception as e:
            print(f"⚠️ Match ignoré (erreur normalisation): {e}")

    if not rows:
        print("ℹ️ Aucune ligne valide à envoyer.")
        return

    # Upsert par match_id + date si possible
    success_count = 0
    error_count = 0

    for row in rows:
        try:
            result = supabase.table("pronostics").upsert(
                row,
                on_conflict="match_id,date"
            ).execute()

            if hasattr(result, "error") and result.error:
                print(f"⚠️ Erreur Supabase pour {row['match']}: {result.error}")
                error_count += 1
            else:
                success_count += 1

        except Exception as e:
            print(f"⚠️ Exception Supabase pour {row['match']}: {e}")
            error_count += 1

    print("\n📊 RÉSUMÉ SYNC SUPABASE")
    print("-------------------------")
    print(f"Lignes envoyées : {len(rows)}")
    print(f"Succès : {success_count}")
    print(f"Erreurs : {error_count}")
    print("✅ Synchronisation terminée.")


if __name__ == "__main__":
    main()