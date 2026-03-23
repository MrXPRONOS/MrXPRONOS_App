#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ml_model.py - Entraînement et prédiction du modèle Random Forest
Version améliorée et compatible avec :
- ancien format {ml_features, ml_label}
- nouveau format dataset structuré
"""

import os
import json
import joblib
import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

MODEL_FILE = "model.pkl"
MODEL_META_FILE = "model_meta.json"

MIN_TRAIN_SAMPLES = 20

# Ordre fixe des features pour le nouveau dataset structuré
FEATURE_ORDER = [
    "confidence",
    "xpronos_score",
    "final_score",
    "value_bet",
    "used_poisson_fallback",
    "h2h_total_matches",
    "home_dominance",
    "away_dominance",
    "draw_rate",
    "home_form_score",
    "away_form_score",
    "home_goals_for",
    "away_goals_for",
    "home_goals_against",
    "away_goals_against",
    "quality_score",
]


def to_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def save_model_meta(meta: dict):
    try:
        with open(MODEL_META_FILE, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Impossible de sauvegarder les métadonnées du modèle: {e}")


def load_model_meta():
    if not os.path.exists(MODEL_META_FILE):
        return {}
    try:
        with open(MODEL_META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def extract_features_and_label(match: dict):
    """
    Supporte 2 formats :

    1) Ancien format :
       {
         "is_finished": True,
         "ml_features": {...},
         "ml_label": 0/1
       }

    2) Nouveau format structuré :
       {
         "confidence": ...,
         "xpronos_score": ...,
         ...
         "label": 0/1
       }
    """

    if not isinstance(match, dict):
        return None, None

    # ------------------------------------------
    # ANCIEN FORMAT
    # ------------------------------------------
    if "ml_features" in match:
        if not match.get("is_finished"):
            return None, None

        f = match.get("ml_features")
        if not isinstance(f, dict):
            return None, None

        features = [
            to_float(f.get("home_form")),
            to_float(f.get("away_form")),
            to_float(f.get("h2h_home")),
            to_float(f.get("h2h_away")),
            to_float(f.get("draw_rate")),
            to_float(f.get("elo_diff")),
            to_float(f.get("xg_diff")),
            to_float(f.get("odds_home")),
            to_float(f.get("odds_away")),
            to_float(f.get("confidence")),
            to_float(f.get("ensemble_dc")),
        ]

        label = int(match.get("ml_label", 0))
        return features, label

    # ------------------------------------------
    # NOUVEAU FORMAT
    # ------------------------------------------
    if "label" in match:
        features = [to_float(match.get(name, 0)) for name in FEATURE_ORDER]
        label = int(match.get("label", 0))
        return features, label

    return None, None


def train_model(matches):
    """
    Entraîne un RandomForestClassifier.
    Compatible ancien et nouveau format de dataset.
    """
    X = []
    y = []

    for m in matches:
        features, label = extract_features_and_label(m)
        if features is None:
            continue
        X.append(features)
        y.append(label)

    if len(X) < MIN_TRAIN_SAMPLES:
        print(f"⚠️ Pas assez de données pour l'entraînement (< {MIN_TRAIN_SAMPLES} exemples)")
        return None

    X = np.array(X, dtype=float)
    y = np.array(y, dtype=int)

    unique_labels = np.unique(y)
    if len(unique_labels) < 2:
        print("⚠️ Impossible d'entraîner: une seule classe présente dans les labels")
        return None

    try:
        X_train, X_valid, y_train, y_valid = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
    except Exception:
        # fallback si stratify échoue
        X_train, X_valid, y_train, y_valid = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_split=4,
        min_samples_leaf=2,
        random_state=42,
        class_weight="balanced"
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_valid)
    acc = accuracy_score(y_valid, y_pred)

    joblib.dump(model, MODEL_FILE)

    meta = {
        "trained_at": os.path.getmtime(MODEL_FILE),
        "samples_total": int(len(X)),
        "samples_train": int(len(X_train)),
        "samples_valid": int(len(X_valid)),
        "accuracy": round(float(acc), 4),
        "feature_order": FEATURE_ORDER,
        "model_type": "RandomForestClassifier",
    }
    save_model_meta(meta)

    print("✅ Modèle entraîné et sauvegardé")
    print(f"📊 Accuracy validation: {acc:.3f}")
    print(f"📦 Exemples: train={len(X_train)}, valid={len(X_valid)}")

    return model


def load_model():
    """
    Charge le modèle sauvegardé, ou retourne None.
    """
    try:
        return joblib.load(MODEL_FILE)
    except Exception:
        return None


def predict_proba(model, features):
    """
    Retourne la probabilité de succès (classe 1).
    Si le modèle est absent ou si problème, retourne 0.5
    """
    if model is None:
        return 0.5

    try:
        arr = [to_float(x, 0.0) for x in features]
        proba = model.predict_proba([arr])[0]
        if len(proba) < 2:
            return 0.5
        return float(proba[1])
    except Exception:
        return 0.5


def build_feature_vector_from_row(row: dict):
    """
    Construit un vecteur de features à partir d'une ligne du nouveau dataset structuré.
    """
    return [to_float(row.get(name, 0)) for name in FEATURE_ORDER]


def get_feature_order():
    return FEATURE_ORDER