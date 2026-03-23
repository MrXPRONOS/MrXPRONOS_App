#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
auto_train.py - Entraînement quotidien du modèle ML
Sauvegarde l'historique des matchs, nettoie les anciens fichiers.
À exécuter une fois par jour (via cron ou GitHub Actions).
"""

import os
import json
from datetime import datetime
from ml_model import train_model

DATA_FILE = "data.json"
HISTORY_DIR = "history"


def save_daily_snapshot(data):
    """
    Sauvegarde les matchs du jour dans un fichier journalier.
    """
    os.makedirs(HISTORY_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(HISTORY_DIR, f"matches_{today}.json")

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ Snapshot sauvegardé : {path}")
    except Exception as e:
        print(f"❌ Erreur sauvegarde snapshot {path}: {e}")


def load_all_history():
    """
    Charge tous les matchs historiques depuis les fichiers journaliers
    avec déduplication par id.
    """
    all_matches = {}

    if not os.path.exists(HISTORY_DIR):
        return []

    for file in sorted(os.listdir(HISTORY_DIR)):
        if not file.endswith(".json"):
            continue

        path = os.path.join(HISTORY_DIR, file)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            matches = data.get("matches", [])
            if not isinstance(matches, list):
                continue

            for match in matches:
                if not isinstance(match, dict):
                    continue
                match_id = str(match.get("id", "")).strip()
                if match_id:
                    all_matches[match_id] = match

        except Exception as e:
            print(f"⚠️ Erreur lecture {file}: {e}")

    return list(all_matches.values())


def clean_old_files(days=30):
    """
    Supprime les fichiers historiques plus vieux que 'days' jours.
    """
    if not os.path.exists(HISTORY_DIR):
        return

    now = datetime.now()

    for file in os.listdir(HISTORY_DIR):
        if not file.endswith(".json"):
            continue

        path = os.path.join(HISTORY_DIR, file)
        try:
            mod_time = datetime.fromtimestamp(os.path.getmtime(path))
            if (now - mod_time).days > days:
                os.remove(path)
                print(f"🗑️ Supprimé ancien fichier : {file}")
        except Exception as e:
            print(f"⚠️ Impossible de traiter {file}: {e}")


def filter_trainable_matches(matches):
    """
    Garde uniquement les matchs exploitables pour l'entraînement.
    """
    filtered = []
    for m in matches:
        if not isinstance(m, dict):
            continue
        if not m.get("is_finished"):
            continue
        if m.get("home_score") is None or m.get("away_score") is None:
            continue
        filtered.append(m)
    return filtered


def main():
    print("=" * 60)
    print("🚀 Entraînement automatique du modèle ML")
    print("=" * 60)

    if not os.path.exists(DATA_FILE):
        print("❌ data.json introuvable, impossible de créer un snapshot.")
        return

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            current_data = json.load(f)
    except Exception as e:
        print(f"❌ Impossible de lire {DATA_FILE}: {e}")
        return

    save_daily_snapshot(current_data)

    all_matches = load_all_history()
    print(f"📊 Dataset brut total : {len(all_matches)} matchs")

    train_matches = filter_trainable_matches(all_matches)
    print(f"🎯 Matchs exploitables pour entraînement : {len(train_matches)}")

    try:
        model = train_model(train_matches)
    except Exception as e:
        print(f"❌ Erreur entraînement modèle: {e}")
        model = None

    if model:
        print("✅ Modèle sauvegardé avec succès")
    else:
        print("⚠️ Échec de l'entraînement (données insuffisantes ou erreur)")

    clean_old_files()
    print("✅ Nettoyage terminé")


if __name__ == "__main__":
    main()