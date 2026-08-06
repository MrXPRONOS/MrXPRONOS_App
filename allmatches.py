#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Télécharge l'historique SportData depuis 2024 par petites plages de 3 jours.

L'endpoint /games/allscores peut renvoyer un tableau vide sur les grandes plages.
Ce script respecte donc la recommandation 1 à 3 jours et n'écrase jamais un cache
existant si l'API échoue.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone

from sportdata_api import fetch_games

UTC = timezone.utc
START_DATE = datetime(2024, 1, 1, tzinfo=UTC).date()
END_DATE = datetime.now(UTC).date() - timedelta(days=1)
CHUNK_DAYS = 3

CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "all_matches.json")


def extract_game_info(game):
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
    return {
        "id": game.get("id"),
        "start_time": start_time,
        "home_team": home.get("name", ""),
        "away_team": away.get("name", ""),
        "competition": game.get("competitionDisplayName", ""),
        "home_score": home_score,
        "away_score": away_score,
        "status_group": status_group,
        "status_text": game.get("statusText"),
        "is_finished": (
            str(status_group) == "4"
            and home_score is not None
            and away_score is not None
        ),
    }


def main() -> int:
    print("=" * 70)
    print("TÉLÉCHARGEMENT HISTORIQUE SPORTDATA")
    print(f"Période : {START_DATE} -> {END_DATE}")
    print(f"Taille des plages : {CHUNK_DAYS} jours")
    print("=" * 70)

    by_id = {}
    current = START_DATE
    failed_chunks = 0
    valid_chunks = 0

    while current <= END_DATE:
        chunk_end = min(current + timedelta(days=CHUNK_DAYS - 1), END_DATE)
        print(f"\n📅 {current} -> {chunk_end}")

        result = fetch_games(current, chunk_end, timeout=40)
        if not result.ok:
            failed_chunks += 1
            print(
                f"   ❌ Échec: {result.reason} "
                f"(endpoint={result.endpoint}, clés={result.payload_keys})"
            )
            current = chunk_end + timedelta(days=1)
            time.sleep(0.5)
            continue

        valid_chunks += 1
        print(f"   ✅ {len(result.games)} matchs reçus")

        for game in result.games:
            row = extract_game_info(game)
            if row.get("id") is not None:
                by_id[str(row["id"])] = row

        current = chunk_end + timedelta(days=1)
        time.sleep(0.25)

    if valid_chunks == 0:
        print("❌ Aucune plage valide. Le cache existant reste intact.")
        return 1

    if failed_chunks:
        print(
            f"❌ {failed_chunks} plage(s) ont échoué. "
            "Le cache existant reste intact pour éviter un historique incomplet."
        )
        return 2

    os.makedirs(CACHE_DIR, exist_ok=True)
    temp_file = CACHE_FILE + ".tmp"
    rows = list(by_id.values())

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    os.replace(temp_file, CACHE_FILE)
    print(f"\n💾 {len(rows)} matchs sauvegardés dans {CACHE_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
