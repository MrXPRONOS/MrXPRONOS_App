#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
auto_train.py - Entraînement quotidien du modèle ML
Version finale alignée avec :
- ml_model.py
- dataset structuré
- historique dédupliqué
- qualité des exemples
"""

import os
import json
from datetime import datetime
from ml_model import train_model

DATA_FILE = "data.json"
HISTORY_DIR = "history"
TRAINING_DATASET_FILE = "training_dataset.jsonl"


def load_json_file(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json_file(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_daily_snapshot(data):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(HISTORY_DIR, f"matches_{today}.json")
    save_json_file(path, data)
    print(f"✅ Snapshot sauvegardé : {path}")


def load_all_history():
    if not os.path.exists(HISTORY_DIR):
        return []

    merged = {}
    for file in sorted(os.listdir(HISTORY_DIR)):
        if not file.endswith(".json"):
            continue
        path = os.path.join(HISTORY_DIR, file)
        try:
            data = load_json_file(path, {})
            matches = data.get("matches", [])
            if not isinstance(matches, list):
                continue

            for m in matches:
                if not isinstance(m, dict):
                    continue
                mid = str(m.get("id", "")).strip()
                if not mid:
                    continue

                existing = merged.get(mid)
                if existing is None:
                    merged[mid] = m
                else:
                    if m.get("is_finished") and not existing.get("is_finished"):
                        merged[mid] = m
                    elif m.get("is_finished") == existing.get("is_finished"):
                        merged[mid] = m
        except Exception as e:
            print(f"⚠️ Erreur lecture {file}: {e}")

    return list(merged.values())


def clean_old_files(days=30):
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
                print(f"🗑️ Ancien fichier supprimé : {file}")
        except Exception as e:
            print(f"⚠️ Erreur nettoyage {file}: {e}")


def compute_example_quality(match: dict) -> int:
    score = 0

    if match.get("is_finished"):
        score += 25
    if match.get("home_score") is not None and match.get("away_score") is not None:
        score += 20
    if match.get("prediction"):
        score += 15
    if match.get("odds"):
        score += 10
    if match.get("home_form"):
        score += 10
    if match.get("away_form"):
        score += 10
    if match.get("h2h_analysis"):
        score += 5
    if match.get("final_score") is not None:
        score += 5

    if match.get("category") in ("pro", "vip"):
        score += 5

    league = (match.get("league") or "").lower()
    if any(x in league for x in ["friendly", "u19", "u21", "women", "reserve"]):
        score -= 20

    return max(0, min(score, 100))


def is_trainable_match(match: dict) -> bool:
    if not isinstance(match, dict):
        return False

    if not match.get("is_finished"):
        return False

    if match.get("home_score") is None or match.get("away_score") is None:
        return False

    pred = match.get("prediction", {})
    if not pred:
        return False

    if pred.get("double_chance") not in ("1X", "X2"):
        return False

    return compute_example_quality(match) >= 60


def extract_training_row(match: dict):
    if not is_trainable_match(match):
        return None

    pred = match.get("prediction", {})
    h2h = match.get("h2h_analysis", {}) or {}
    home_form = match.get("home_form", {}) or {}
    away_form = match.get("away_form", {}) or {}

    dc = pred.get("double_chance")
    home_score = match.get("home_score")
    away_score = match.get("away_score")

    if dc == "1X":
        label = 1 if home_score >= away_score else 0
    elif dc == "X2":
        label = 1 if away_score >= home_score else 0
    else:
        return None

    return {
        "id": str(match.get("id")),
        "date": match.get("date"),
        "league": match.get("league"),
        "category": match.get("category"),
        "double_chance": dc,
        "confidence": pred.get("confidence", 0),
        "xpronos_score": match.get("xpronos_score", 0),
        "final_score": match.get("final_score", 0),
        "value_bet": 1 if match.get("value_bet") else 0,
        "used_poisson_fallback": 1 if match.get("used_poisson_fallback") else 0,
        "h2h_total_matches": h2h.get("total_matches", 0),
        "home_dominance": h2h.get("home_dominance", 0),
        "away_dominance": h2h.get("away_dominance", 0),
        "draw_rate": h2h.get("draw_rate", 0),
        "home_form_score": home_form.get("form_score", 0),
        "away_form_score": away_form.get("form_score", 0),
        "home_goals_for": home_form.get("goals_for", 0),
        "away_goals_for": away_form.get("goals_for", 0),
        "home_goals_against": home_form.get("goals_against", 0),
        "away_goals_against": away_form.get("goals_against", 0),
        "quality_score": compute_example_quality(match),
        "label": label,
    }


def load_existing_training_ids() -> set:
    if not os.path.exists(TRAINING_DATASET_FILE):
        return set()

    ids = set()
    try:
        with open(TRAINING_DATASET_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    if row.get("id"):
                        ids.add(str(row["id"]))
                except Exception:
                    continue
    except Exception:
        pass

    return ids


def append_training_rows(rows: list):
    if not rows:
        return 0

    with open(TRAINING_DATASET_FILE, "a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def load_training_dataset() -> list:
    rows = []
    if not os.path.exists(TRAINING_DATASET_FILE):
        return rows

    try:
        with open(TRAINING_DATASET_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    rows.append(row)
                except Exception:
                    continue
    except Exception:
        pass

    return rows


def main():
    print("=" * 60)
    print("🚀 Entraînement automatique ML FINAL")
    print("=" * 60)

    if not os.path.exists(DATA_FILE):
        print("❌ data.json introuvable")
        return

    current_data = load_json_file(DATA_FILE, None)
    if not current_data:
        print("❌ Impossible de lire data.json")
        return

    save_daily_snapshot(current_data)

    history_matches = load_all_history()
    print(f"📂 Historique dédupliqué : {len(history_matches)} matchs")

    trainable_rows = []
    for m in history_matches:
        row = extract_training_row(m)
        if row:
            trainable_rows.append(row)

    print(f"🎯 Exemples trainables extraits : {len(trainable_rows)}")

    existing_ids = load_existing_training_ids()
    new_rows = [r for r in trainable_rows if str(r["id"]) not in existing_ids]

    added = append_training_rows(new_rows)
    print(f"➕ Nouveaux exemples ajoutés au dataset : {added}")

    dataset = load_training_dataset()
    print(f"📊 Dataset ML total : {len(dataset)} lignes")

    filtered_dataset = [r for r in dataset if r.get("quality_score", 0) >= 60]
    print(f"🧪 Dataset après filtre qualité : {len(filtered_dataset)} lignes")

    try:
        model = train_model(filtered_dataset)
    except Exception as e:
        print(f"❌ Erreur entraînement : {e}")
        model = None

    if model:
        print("✅ Modèle entraîné et sauvegardé")
    else:
        print("⚠️ Modèle non entraîné (données insuffisantes ou erreur)")

    clean_old_files()
    print("✅ Nettoyage terminé")


if __name__ == "__main__":
    main()