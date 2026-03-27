#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_pronostics_supabase.py - Synchronise les pronostics depuis data.json vers Supabase

Version robuste :
- accepte SUPABASE_SERVICE_ROLE_KEY ou SUPABASE_KEY
- ne casse pas le workflow si variables absentes
- upsert propre
- validation des matchs d'hier / aujourd'hui / demain
- sécurise les valeurs NULL problématiques (ex: cote)
"""

import os
import json
from datetime import datetime, timedelta

try:
    from supabase import create_client
except Exception as e:
    print(f"⚠️ Module supabase introuvable : {e}")
    raise SystemExit(0)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
)

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("⚠️ Variables Supabase manquantes.")
    print("⚠️ Attendu : SUPABASE_URL + (SUPABASE_SERVICE_ROLE_KEY ou SUPABASE_KEY)")
    print("⚠️ Synchronisation Supabase ignorée.")
    raise SystemExit(0)

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
except Exception as e:
    print(f"⚠️ Impossible d'initialiser Supabase : {e}")
    raise SystemExit(0)

def safe_load_data():
    if not os.path.exists("data.json"):
        print("⚠️ data.json introuvable")
        return None

    try:
        with open("data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Impossible de lire data.json : {e}")
        return None

def to_int_or_none(value):
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None

def to_float_or_zero(value):
    try:
        if value is None or value == "":
            return 0
        return float(value)
    except Exception:
        return 0

def to_float_or_none(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None

def safe_str(value):
    if value is None:
        return ""
    return str(value).strip()

def normalize_match_row(match):
    pred = match.get("prediction", {}) or {}

    cote = pred.get("odds", None)
    confidence = pred.get("confidence", None)

    return {
        "match_id": safe_str(match.get("id")),
        "match": f"{safe_str(match.get('home_team'))} vs {safe_str(match.get('away_team'))}",
        "home_team": safe_str(match.get("home_team")),
        "away_team": safe_str(match.get("away_team")),
        "prediction": safe_str(pred.get("double_chance")),
        "confidence": to_float_or_zero(confidence),
        "cote": to_float_or_zero(cote),  # ✅ correction principale
        "competition": safe_str(match.get("league")),
        "category": safe_str(match.get("category")),
        "badge": safe_str(match.get("badge")),
        "date": safe_str(match.get("date")),
        "event_date": match.get("event_date"),
        "status": safe_str(match.get("status")),
        "home_score": to_int_or_none(match.get("home_score")),
        "away_score": to_int_or_none(match.get("away_score")),
        "final_score": to_float_or_none(match.get("final_score")),
        "xpronos_score": to_float_or_none(match.get("xpronos_score")),
        "value_bet": bool(match.get("value_bet", False)),
        "verified_double": bool(match.get("verified_double", False)),
        "is_finished": bool(match.get("is_finished", False)),
        "valide": bool(match.get("verified_double", False)),
        "updated_at": datetime.utcnow().isoformat()
    }

def main():
    data = safe_load_data()
    if not data:
        print("⚠️ Aucune donnée exploitable, synchronisation annulée.")
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

    print("☁️ Synchronisation des pronostics vers Supabase...")
    print(f"📌 Total matchs ciblés : {len(relevant_matches)}")

    if not relevant_matches:
        print("⚠️ Aucun match à synchroniser.")
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
        print("⚠️ Aucune ligne valide à envoyer.")
        return

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

    print("\n☁️ RÉSUMÉ SYNC SUPABASE")
    print("-------------------------")
    print(f"Lignes envoyées : {len(rows)}")
    print(f"Succès : {success_count}")
    print(f"Erreurs : {error_count}")
    print("✅ Synchronisation terminée.")

if __name__ == "__main__":
    main()