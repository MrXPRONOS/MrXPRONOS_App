#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ajoute les matchs d'hier au cache global sans confondre erreur API et journée vide.
"""

import json
import os
from datetime import datetime, timedelta, timezone

from sportdata_api import fetch_games

CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")
UTC = timezone.utc
YESTERDAY = datetime.now(UTC).date() - timedelta(days=1)


def extract_match_info(game):
    start_time = game.get("startTime")
    home = game.get("homeCompetitor", {}) or {}
    away = game.get("awayCompetitor", {}) or {}

    home_score = home.get("score")
    away_score = away.get("score")
    if home_score == -1:
        home_score = None
    if away_score == -1:
        away_score = None

    status_group = game.get("statusGroup")
    status_text = game.get("statusText")

    return {
        "id": game.get("id"),
        "start_time": start_time,
        "home_team": home.get("name", ""),
        "away_team": away.get("name", ""),
        "home_score": home_score,
        "away_score": away_score,
        "status_group": status_group,
        "status_text": status_text,
        "is_finished": (
            str(status_group) == "4"
            and home_score is not None
            and away_score is not None
        ),
        "competition": game.get("competitionDisplayName", ""),
    }


def load_existing():
    if not os.path.exists(CACHE_FILE):
        return []
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as exc:
        print(f"ERREUR lecture {CACHE_FILE}: {exc}")
        raise


def save(matches):
    os.makedirs(CACHE_DIR, exist_ok=True)
    temp_file = CACHE_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)
    os.replace(temp_file, CACHE_FILE)


def main() -> int:
    print(f"📅 Mise à jour du cache avec les matchs du {YESTERDAY}")

    result = fetch_games(YESTERDAY, YESTERDAY)
    if not result.ok:
        print(
            "❌ SportData invalide. Le cache n'est pas modifié.\n"
            f"   Raison: {result.reason}\n"
            f"   Endpoint: {result.endpoint}\n"
            f"   Clés JSON: {result.payload_keys}"
        )
        return 1

    games = result.games
    print(
        f"   → {len(games)} matchs trouvés "
        f"(endpoint={result.endpoint}, clé=#{result.key_index})"
    )

    if not games:
        print("⚠️ Réponse valide mais aucun match pour cette journée.")
        return 0

    new_matches = [extract_match_info(g) for g in games]
    all_matches = load_existing()
    existing_ids = {
        str(m.get("id"))
        for m in all_matches
        if isinstance(m, dict) and m.get("id") is not None
    }

    to_add = [
        m for m in new_matches
        if m.get("id") is not None and str(m["id"]) not in existing_ids
    ]
    print(f"   → {len(to_add)} nouveaux matchs à ajouter")

    if not to_add:
        print("✅ Cache déjà à jour.")
        return 0

    all_matches.extend(to_add)
    save(all_matches)
    print(f"✅ Cache mis à jour : maintenant {len(all_matches)} matchs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
