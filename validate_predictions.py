import os
import requests
from datetime import datetime, timedelta, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
BSD_API_TOKEN = os.environ["BSD_API_TOKEN"]

BSD_BASE = "https://sports.bzzoiro.com/api"
HEADERS_SB = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
HEADERS_BSD = {
    "Authorization": f"Token {BSD_API_TOKEN}"
}

def fetch_bsd(endpoint, params=None):
    res = requests.get(f"{BSD_BASE}{endpoint}", headers=HEADERS_BSD, params=params, timeout=30)
    res.raise_for_status()
    return res.json()

def supabase_select_predictions():
    url = f"{SUPABASE_URL}/rest/v1/live_predictions"
    params = {
        "select": "*",
        "validated": "eq.false",
        "order": "created_at.desc"
    }
    res = requests.get(url, headers=HEADERS_SB, params=params, timeout=30)
    res.raise_for_status()
    return res.json()

def supabase_update_prediction(pred_id, outcome):
    url = f"{SUPABASE_URL}/rest/v1/live_predictions?id=eq.{pred_id}"
    payload = {
        "validated": True,
        "outcome": outcome,
        "validated_at": datetime.now(timezone.utc).isoformat()
    }
    res = requests.patch(url, headers=HEADERS_SB, json=payload, timeout=30)
    res.raise_for_status()

def supabase_insert_notification(message, prediction_id):
    url = f"{SUPABASE_URL}/rest/v1/notifications"
    payload = {
        "user_id": "all",
        "type": "prediction_validated",
        "title": "Pronostic validé",
        "message": message,
        "priority": "normal",
        "read": False,
        "related_prediction_id": prediction_id
    }
    res = requests.post(url, headers=HEADERS_SB, json=payload, timeout=30)
    res.raise_for_status()

def main():
    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=2)).date().isoformat()
    date_to = now.date().isoformat()

    events = fetch_bsd("/events/", {
        "date_from": date_from,
        "date_to": date_to,
        "status": "finished"
    }).get("results", [])

    finished_by_id = {str(m["id"]): m for m in events}
    predictions = supabase_select_predictions()

    for pred in predictions:
        match = finished_by_id.get(str(pred["match_id"]))
        if not match:
            continue

        stats = match.get("live_stats") or {}
        home = stats.get("home") or {}
        away = stats.get("away") or {}

        outcome = False
        pred_type = pred.get("prediction_type")
        threshold = float(pred.get("threshold") or 0)

        if pred_type == "total_shots":
            total = (home.get("total_shots") or 0) + (away.get("total_shots") or 0)
            outcome = total > threshold
        elif pred_type == "total_corners":
            total = (home.get("corner_kicks") or 0) + (away.get("corner_kicks") or 0)
            outcome = total > threshold
        elif pred_type == "total_fouls":
            total = (home.get("fouls") or 0) + (away.get("fouls") or 0)
            outcome = total > threshold

        result = "success" if outcome else "failure"
        supabase_update_prediction(pred["id"], result)

        msg = f'{pred["match_name"]} : {pred_type} - {"✅ réussi" if outcome else "❌ échoué"}'
        supabase_insert_notification(msg, pred["id"])

    print("Validation terminée.")

if __name__ == "__main__":
    main()