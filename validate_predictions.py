import os
import json
import requests
import argparse
from datetime import datetime, timedelta, timezone

# -------------------------
# ENV (robuste)
# -------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

BSD_API_TOKEN = os.environ.get("BSD_API_TOKEN")  # optionnel si tu ne fais pas le live
BSD_BASE = "https://sports.bzzoiro.com/api"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SITE_URL = os.environ.get("SITE_URL", "https://mrxpronos.github.io/MrXPRONOS_App/")
HIST_URL = os.environ.get("HIST_URL", SITE_URL + "historique.html")
PRONOS_URL = os.environ.get("PRONOS_URL", SITE_URL + "pronos.html")

UTC = timezone.utc

HEADERS_SB = {
    "apikey": SUPABASE_KEY or "",
    "Authorization": f"Bearer {SUPABASE_KEY}" if SUPABASE_KEY else "",
    "Content-Type": "application/json",
}

HEADERS_BSD = {"Authorization": f"Token {BSD_API_TOKEN}"} if BSD_API_TOKEN else {}


# =========================================================
# TELEGRAM HELPERS
# =========================================================
def tg_send_message(text: str, buttons=None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("■■ Telegram secrets manquants, envoi ignoré.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }
    if buttons:
        payload["reply_markup"] = json.dumps({"inline_keyboard": buttons})

    r = requests.post(url, data=payload, timeout=45)
    if not r.ok:
        print("Telegram error status:", r.status_code)
        print("Telegram response:", r.text)
    r.raise_for_status()


# =========================================================
# COUPONS TELEGRAM VALIDATION (J-1)
# =========================================================
def sb_get_telegram_sent_yesterday(kind="daily_simple"):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise SystemExit("Supabase URL/KEY manquants pour valider les coupons Telegram.")

    yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()

    url = f"{SUPABASE_URL}/rest/v1/telegram_sent"
    params = {
        "select": "id,ref_id,ref_date",
        "kind": f"eq.{kind}",
        "ref_date": f"eq.{yesterday}",
        "validation_sent": "eq.false",
        "order": "sent_at.asc",
        "limit": "20",
    }
    r = requests.get(url, headers=HEADERS_SB, params=params, timeout=30)
    r.raise_for_status()
    return yesterday, (r.json() or [])


def sb_get_pronostic(match_id: str, date_str: str):
    url = f"{SUPABASE_URL}/rest/v1/pronostics"
    params = {
        "select": "match,prediction,home_score,away_score,verified_double,is_finished,competition",
        "match_id": f"eq.{match_id}",
        "date": f"eq.{date_str}",
        "limit": "1",
    }
    r = requests.get(url, headers=HEADERS_SB, params=params, timeout=30)
    r.raise_for_status()
    data = r.json() or []
    return data[0] if data else None


def sb_mark_validations_sent(ids):
    # patch ligne par ligne (simple, peu de volume: 5 coupons)
    for _id in ids:
        url = f"{SUPABASE_URL}/rest/v1/telegram_sent?id=eq.{_id}"
        r = requests.patch(url, headers=HEADERS_SB, data=json.dumps({"validation_sent": True}), timeout=30)
        r.raise_for_status()


def validate_telegram_coupons():
    yesterday, rows = sb_get_telegram_sent_yesterday(kind="daily_simple")
    if not rows:
        print("■ Aucun coupon Telegram à valider (yesterday) ou déjà validé.")
        return

    lines = []
    finished = 0
    wins = 0

    for x in rows:
        mid = str(x["ref_id"])
        pr = sb_get_pronostic(mid, yesterday)
        if not pr:
            lines.append(f"• {mid} : introuvable dans pronostics")
            continue

        match_name = pr.get("match") or mid
        dc = pr.get("prediction") or "-"
        is_finished = bool(pr.get("is_finished"))
        ok = bool(pr.get("verified_double"))
        hs, aas = pr.get("home_score"), pr.get("away_score")

        if is_finished:
            finished += 1
            if ok:
                wins += 1
            score = f"{hs}-{aas}" if hs is not None and aas is not None else "-"
            lines.append(f"• {match_name} — {dc} — {score} — {'✅ Validé' if ok else '❌ Échoué'}")
        else:
            lines.append(f"• {match_name} — {dc} — ⏳ pas encore terminé")

    # Si rien n’est fini, on évite de spammer (optionnel)
    if finished == 0:
        print("■ Aucun match terminé parmi les coupons d’hier -> pas d’envoi Telegram.")
        return

    text = (
        f"📌 Validation des coupons SIMPLE du {yesterday}\n\n"
        + "\n".join(lines)
        + f"\n\nBilan (matchs terminés) : {wins}/{finished} ✅"
    )

    tg_send_message(
        text,
        buttons=[
            [{"text": "Voir l’historique", "url": HIST_URL}],
            [{"text": "Voir plus de coupons", "url": PRONOS_URL}],
        ],
    )

    sb_mark_validations_sent([x["id"] for x in rows])
    print("■ Validation Telegram envoyée + marquée.")


# =========================================================
# (TON EXISTANT) LIVE VALIDATION - laissé tel quel
# =========================================================
def fetch_bsd(endpoint, params=None):
    res = requests.get(f"{BSD_BASE}{endpoint}", headers=HEADERS_BSD, params=params, timeout=30)
    res.raise_for_status()
    return res.json()

def supabase_select_predictions():
    url = f"{SUPABASE_URL}/rest/v1/live_predictions"
    params = {"select": "*", "validated": "eq.false", "order": "created_at.desc"}
    res = requests.get(url, headers=HEADERS_SB, params=params, timeout=30)
    res.raise_for_status()
    return res.json()

def supabase_update_prediction(pred_id, outcome):
    url = f"{SUPABASE_URL}/rest/v1/live_predictions?id=eq.{pred_id}"
    payload = {"validated": True, "outcome": outcome, "validated_at": datetime.now(UTC).isoformat()}
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
        "related_prediction_id": prediction_id,
    }
    res = requests.post(url, headers=HEADERS_SB, json=payload, timeout=30)
    res.raise_for_status()

def validate_live_predictions():
    if not BSD_API_TOKEN:
        print("■■ BSD_API_TOKEN manquant -> validation live ignorée.")
        return

    now = datetime.now(UTC)
    date_from = (now - timedelta(days=2)).date().isoformat()
    date_to = now.date().isoformat()

    events = fetch_bsd("/events/", {"date_from": date_from, "date_to": date_to, "status": "finished"}).get("results", [])
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

    print("Validation live terminée.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--coupons", action="store_true", help="Valider les coupons Telegram (J-1)")
    parser.add_argument("--live", action="store_true", help="Valider les prédictions live")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise SystemExit("SUPABASE_URL / SUPABASE_KEY manquants")

    if args.coupons:
        validate_telegram_coupons()

    if args.live:
        validate_live_predictions()

    # Si aucun flag => ne fait rien par défaut (évite surprises)
    if not args.coupons and not args.live:
        print("Aucune action. Utilise --coupons et/ou --live.")


if __name__ == "__main__":
    main()