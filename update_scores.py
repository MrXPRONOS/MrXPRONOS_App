
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_scores.py - Met à jour les scores et statuts des matchs dans data.json

Version améliorée :
- UTC cohérent avec GitHub Actions
- récupère uniquement les dates utiles (basées sur data.json)
- mise à jour robuste (scores/status/is_finished)
- recalcul automatique de verified_double quand match terminé
- sauvegarde avec backup
- logs + debug
- compatible avec api_utils (rotation de clés)
- évite de considérer postponed/suspended/cancelled comme terminés
"""

import os
import json
from datetime import datetime, timedelta, timezone
from sportdata_api import fetch_games as fetch_sportdata_games

SPORTDATA_URL = "https://v1.football.sportsapipro.com/games/allscores"
DATA_FILE = "data.json"
BACKUP_FILE = "data_backup.json"

UTC = timezone.utc
now_utc = datetime.now(UTC)
today = now_utc.date()

print("=" * 60)
print(f"🔄 MISE À JOUR DES SCORES - {today} {now_utc.strftime('%H:%M')} UTC")
print("=" * 60)

def safe_load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def load_data():
    """
    Charge data.json ou backup si nécessaire.
    """
    if not os.path.exists(DATA_FILE):
        print("⚠️ data.json introuvable, création d'une nouvelle structure.")
        return {"matches": []}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Erreur lecture data.json : {e}")
        if os.path.exists(BACKUP_FILE):
            print("↩️ Restauration depuis data_backup.json")
            return safe_load_json(BACKUP_FILE, {"matches": []})
        return {"matches": []}

def save_data(data):
    """
    Sauvegarde data.json avec backup préalable.
    """
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                current = json.load(f)
            with open(BACKUP_FILE, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Impossible de créer le backup: {e}")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("💾 Données sauvegardées dans data.json")

def normalize_score(value):
    if value in (-1, "-1", None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return None

def is_finished_status(status_group, status_text, home_score=None, away_score=None):
    st = str(status_text or "").lower().strip()

    # jamais considéré terminé
    if st in ("postponed", "suspended", "cancelled"):
        return False

    # si l'API dit terminé, on exige quand même des scores valides
    if str(status_group) == "4":
        return home_score is not None and away_score is not None

    return (
        ("ended" in st or "finished" in st or "terminé" in st or st == "ft")
        and home_score is not None
        and away_score is not None
    )

def is_live_status(status_text):
    st = str(status_text or "").lower()
    return (
        "inprogress" in st or
        "live" in st or
        "en cours" in st
    )

def parse_date_yyyy_mm_dd(s):
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except Exception:
        return None

def date_from_match(match):
    d = parse_date_yyyy_mm_dd(match.get("date"))
    if d:
        return d
    ev = match.get("event_date") or match.get("start_time")
    return parse_date_yyyy_mm_dd(ev)

def compute_verified_double(match):
    pred = match.get("prediction") or {}
    dc = pred.get("double_chance")
    hs = match.get("home_score")
    aas = match.get("away_score")

    if hs is None or aas is None:
        return False

    if dc == "1X":
        return hs >= aas
    if dc == "X2":
        return aas >= hs
    return False

def fetch_games(date):
    """Récupère les matchs d'une journée via le client SportData robuste."""
    result = fetch_sportdata_games(date, date, timeout=30)

    if not result.ok:
        print(
            f"❌ Réponse SportData invalide pour {date}: {result.reason} "
            f"| endpoint={result.endpoint} | clés={result.payload_keys}"
        )
        return None

    print(
        f"   ℹ️ SportData valide via clé #{result.key_index} "
        f"et endpoint {result.endpoint}"
    )
    return result.games

def choose_dates_to_fetch(matches, max_days=7):
    """
    Choisit les dates utiles à rafraîchir :
    - matchs non terminés
    - matchs des 2 derniers jours (score tardif possible)
    """
    if not isinstance(matches, list) or not matches:
        return [today, today - timedelta(days=1), today - timedelta(days=2)]

    date_set = set()

    for m in matches:
        d = date_from_match(m)
        if not d:
            continue

        finished = bool(m.get("is_finished", False))
        days_diff = (today - d).days

        if (not finished) or (0 <= days_diff <= 2):
            date_set.add(d)

    if not date_set:
        return [today, today - timedelta(days=1), today - timedelta(days=2)]

    dates_sorted = sorted(date_set, reverse=True)[:max_days]
    return sorted(dates_sorted, reverse=False)

def main():
    data = load_data()
    matches = data.get("matches", [])

    if not isinstance(matches, list):
        matches = []
        data["matches"] = matches

    print(f"📦 Matchs dans data.json : {len(matches)}")

    days_to_fetch = choose_dates_to_fetch(matches, max_days=7)
    print(f"📅 Dates à rafraîchir (max 7) : {[str(d) for d in days_to_fetch]}")

    all_games = []
    valid_api_days = 0
    invalid_api_days = 0

    for day in days_to_fetch:
        print(f"➡️ Récupération des matchs du {day}...")
        games = fetch_games(day)

        if games is None:
            invalid_api_days += 1
            continue

        valid_api_days += 1
        print(f"   → {len(games)} matchs")
        all_games.extend(games)

    if valid_api_days == 0:
        print("❌ Aucune réponse SportData valide. data.json n'est pas modifié.")
        return 1

    if not all_games:
        print(
            "⚠️ Réponses valides mais aucun match récupéré. "
            "data.json n'est pas modifié."
        )
        return 0

    scores_dict = {}
    for g in all_games:
        gid = str(g.get("id", "")).strip()
        if not gid:
            continue

        home = g.get("homeCompetitor", {}) or {}
        away = g.get("awayCompetitor", {}) or {}

        home_score = normalize_score(home.get("score"))
        away_score = normalize_score(away.get("score"))
        status_text = g.get("statusText", "")
        status_group = g.get("statusGroup")

        scores_dict[gid] = {
            "home_score": home_score,
            "away_score": away_score,
            "status": status_text,
            "status_group": status_group,
            "is_finished": is_finished_status(status_group, status_text, home_score, away_score)
        }

    matched_in_api = sum(1 for m in matches if str(m.get("id", "")).strip() in scores_dict)
    print(f"🔎 Matchs de data.json retrouvés dans l’API : {matched_in_api}")

    updated = 0
    finished_count = 0
    live_count = 0
    validated_changed = 0

    for match in matches:
        gid = str(match.get("id", "")).strip()
        if gid not in scores_dict:
            continue

        new = scores_dict[gid]

        old_home = match.get("home_score")
        old_away = match.get("away_score")
        old_status = match.get("status")
        old_finished = bool(match.get("is_finished", False))
        old_verified = bool(match.get("verified_double", False))

        changed = (
            old_home != new["home_score"] or
            old_away != new["away_score"] or
            old_status != new["status"] or
            old_finished != new["is_finished"]
        )

        if changed:
            match["home_score"] = new["home_score"]
            match["away_score"] = new["away_score"]
            match["status"] = new["status"]
            match["is_finished"] = new["is_finished"]

            if match.get("is_finished") and match.get("home_score") is not None and match.get("away_score") is not None:
                new_verified = compute_verified_double(match)
                if new_verified != old_verified:
                    match["verified_double"] = new_verified
                    validated_changed += 1
                    changed = True

            if changed:
                updated += 1

            if new["is_finished"]:
                finished_count += 1
            elif is_live_status(new["status"]):
                live_count += 1

    if updated > 0:
        save_data(data)
    else:
        print("ℹ️ Aucune modification détectée.")

    print("\n📊 RÉSUMÉ")
    print("------------")
    print(f"Matchs API analysés : {len(all_games)}")
    print(f"Matchs data.json retrouvés dans l’API : {matched_in_api}")
    print(f"Matchs mis à jour : {updated}")
    print(f"Matchs terminés (parmi ceux retrouvés) : {finished_count}")
    print(f"Matchs en direct : {live_count}")
    print(f"Validations recalculées (verified_double) : {validated_changed}")
    print("✅ Mise à jour terminée.")

if __name__ == "__main__":
    raise SystemExit(main() or 0)
