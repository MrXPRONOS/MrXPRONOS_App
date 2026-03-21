#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ml_model.py - Entraînement et prédiction du modèle Random Forest
"""

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

MODEL_FILE = "model.pkl"

def train_model(matches):
    """
    Entraîne un modèle Random Forest à partir de l'historique des matchs.
    Chaque match doit contenir 'ml_features' et 'ml_label'.
    """
    X = []
    y = []

    for m in matches:
        if not m.get("is_finished"):
            continue

        f = m.get("ml_features")
        if not f:
            continue

        X.append([
            f["home_form"],
            f["away_form"],
            f["h2h_home"],
            f["h2h_away"],
            f["draw_rate"],
            f["elo_diff"],
            f["xg_diff"],
            f["odds_home"],
            f["odds_away"],
            f["confidence"],
            f["ensemble_dc"]
        ])
        y.append(m.get("ml_label", 0))

    if len(X) < 10:
        print("⚠️ Pas assez de données pour l'entraînement (< 10 matchs)")
        return None

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)

    joblib.dump(model, MODEL_FILE)
    print("✅ Modèle entraîné et sauvegardé")
    return model


def load_model():
    """Charge le modèle sauvegardé, ou retourne None."""
    try:
        return joblib.load(MODEL_FILE)
    except:
        return None


def predict_proba(model, features):
    """Retourne la probabilité de succès (classe 1) pour un ensemble de features."""
    if model is None:
        return 0.5
    proba = model.predict_proba([features])[0]
    return proba[1]  # probabilité de classe 1 (succès)