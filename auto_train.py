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
MODEL_FILE = "model.pkl"


def save_daily_snapshot(data):
    """
    Sauvegarde les matchs du jour dans un fichier journalier.
    """
    os.makedirs(HISTORY_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(HISTORY_DIR, f"matches_{today}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Snapshot sauvegardé : {path}")


def load_all_history():
    """
    Charge tous les matchs historiques depuis les fichiers journaliers.
    """
    all_matches = []
    if not os.path.exists(HISTORY_DIR):
        return []
    for file in os.listdir(HISTORY_DIR):
        if file.endswith(".json"):
            path = os.path.join(HISTORY_DIR, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    all_matches.extend(data.get("matches", []))
            except Exception as e:
                print(f"⚠️ Erreur lecture {file}: {e}")
    return all_matches


def clean_old_files(days=30):
    """
    Supprime les fichiers historiques plus vieux que 'days' jours.
    """
    now = datetime.now()
    for file in os.listdir(HISTORY_DIR):
        if file.endswith(".json"):
            path = os.path.join(HISTORY_DIR, file)
            mod_time = datetime.fromtimestamp(os.path.getmtime(path))
            if (now - mod_time).days > days:
                os.remove(path)
                print(f"🗑️ Supprimé ancien fichier : {file}")


def main():
    print("=" * 60)
    print("🚀 Entraînement automatique du modèle ML")
    print("=" * 60)

    # Vérifier que data.json existe
    if not os.path.exists(DATA_FILE):
        print("❌ data.json introuvable, impossible de créer un snapshot.")
        return

    # Charger le data.json actuel
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        current_data = json.load(f)

    # Sauvegarder le snapshot du jour
    save_daily_snapshot(current_data)

    # Charger tout l'historique
    all_matches = load_all_history()
    print(f"📊 Dataset total : {len(all_matches)} matchs")

    # Entraîner le modèle
    model = train_model(all_matches)
    if model:
        print("✅ Modèle sauvegardé avec succès")
    else:
        print("⚠️ Échec de l'entraînement (données insuffisantes)")

    # Nettoyer les anciens fichiers
    clean_old_files()
    print("✅ Nettoyage terminé")


if __name__ == "__main__":
    main()