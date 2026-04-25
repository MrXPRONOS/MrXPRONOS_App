import os
import glob
import json
import time
import argparse
import requests
from datetime import datetime, timedelta, timezone

UTC = timezone.utc

# Telegram
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SITE_URL = os.environ.get("SITE_URL", "https://mrxpronos.github.io/MrXPRONOS_App/")
MORE_URL = os.environ.get("MORE_URL", SITE_URL + "pronos.html")
HIST_URL = os.environ.get("HIST_URL", SITE_URL + "historique.html")

# Files
OUT_DIR = os.environ.get("OUT_DIR", "telegram_out")

# Supabase (service role recommandé)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

def require_telegram():
    if not TOKEN or not CHAT_ID:
        raise SystemExit("Secrets manquants: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")

def require_supabase():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise SystemExit("Secrets manquants: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY (service role)")

def sb_headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }

# --------------------- Telegram helpers ---------------------
def send_message(text: str, buttons=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }
    if buttons:
        payload["reply_markup"] = json.dumps({"inline_keyboard": buttons})
    r = requests.post(url, data=payload, timeout=60)
    if not r.ok:
        print("Telegram message error:", r.status_code, r.text)
    r.raise_for_status()

def send_photo(photo_path: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    keyboard = {
        "inline_keyboard": [
            [{"text": "Voir plus de coupons", "url": MORE_URL}],
            [{"text": "Ouvrir le site", "url": SITE_URL}],
        ]
    }
    with open(photo_path, "rb") as f:
        r = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "caption": caption,
                "reply_markup": json.dumps(keyboard),
            },
            files={"photo": f},
            timeout=120
        )
    if not r.ok:
        print("Telegram photo error:", r.status_code, r.text)
    r.raise_for_status()

# --------------------- Supabase helpers ---------------------
def sb_log_sent(match_id: str, date_str: str):
    url = f"{SUPABASE_URL}/rest/v1/telegram_sent?on_conflict=kind,ref_id,ref_date"
    payload = {
        "kind": "daily_simple",
        "ref_id": str(match_id),
        "ref_date": date_str,
        "validation_sent": False
    }
    r = requests.post(url, headers=sb_headers(), json=payload, timeout=30)
    if not r.ok:
        print("Supabase log error:", r.status_code, r.text)
    r.raise_for_status()

def sb_fetch_to_validate(date_str: str):
    url = f"{SUPABASE_URL}/rest/v1/telegram_sent"
    params = {
        "select": "id,ref_id",
        "kind": f"eq.daily_simple",
        "ref_date": f"eq.{date_str}",
        "validation_sent": "eq.false",
        "order": "sent_at.asc",
        "limit": "30",
    }
    r = requests.get(url, headers=sb_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json() or []

def sb_get_pronostic(match_id: str, date_str: str):
    url = f"{SUPABASE_URL}/rest/v1/pronostics"
    params = {
        "select": "match,prediction,home_score,away_score,verified_double,is_finished",
        "match_id": f"eq.{match_id}",
        "date": f"eq.{date_str}",
        "limit": "1",
    }
    r = requests.get(url, headers=sb_headers(), params=params, timeout=30)
    r.raise_for_status()
    rows = r.json() or []
    return rows[0] if rows else None

def sb_mark_validated(ids):
    for _id in ids:
        url = f"{SUPABASE_URL}/rest/v1/telegram_sent?id=eq.{_id}"
        r = requests.patch(url, headers=sb_headers(), json={"validation_sent": True}, timeout=30)
        r.raise_for_status()

# --------------------- Manifest ---------------------
def load_manifest():
    p = os.path.join(OUT_DIR, "manifest.json")
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

# ============================================================
# MODE 1 : Send today coupons + log in Supabase
# ============================================================
def send_today():
    require_telegram()
    require_supabase()

    files = sorted(glob.glob(os.path.join(OUT_DIR, "*.png")))
    if not files:
        send_message("Coupons SIMPLE du jour : aucun match trouvé.")
        return

    manifest = load_manifest()
    if not manifest or not manifest.get("matches"):
        raise SystemExit("manifest.json manquant/invalide. (export_simple_coupons doit le créer)")

    date_str = manifest.get("date") or datetime.now(UTC).strftime("%Y-%m-%d")
    matches = manifest["matches"]

    intro = f"Coupons SIMPLE du {date_str} (UTC)\nPlus de coupons fiables : {MORE_URL}"
    send_message(intro, buttons=[[{"text": "Voir plus de coupons", "url": MORE_URL}]])

    n = min(len(files), len(matches))
    for idx in range(n):
        match_id = matches[idx]["match_id"]
        send_photo(files[idx], caption="")
        sb_log_sent(match_id, date_str)
        time.sleep(0.7)

    send_message(f"Fin des coupons SIMPLE du {date_str}.\nVoir plus : {MORE_URL}")

# ============================================================
# MODE 2 : Validate yesterday coupons and send results
# ============================================================
def validate_yesterday():
    require_telegram()
    require_supabase()

    yday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    rows = sb_fetch_to_validate(yday)
    if not rows:
        print("■ Rien à valider pour hier.")
        return

    validated_lines = []
    ids_to_mark = []
    finished = 0
    wins = 0

    for x in rows:
        match_id = str(x["ref_id"])
        pr = sb_get_pronostic(match_id, yday)
        if not pr:
            continue

        if not pr.get("is_finished"):
            continue

        finished += 1
        ok = bool(pr.get("verified_double"))
        if ok:
            wins += 1

        score = "-"
        if pr.get("home_score") is not None and pr.get("away_score") is not None:
            score = f'{pr["home_score"]}-{pr["away_score"]}'

        validated_lines.append(
            f'• {pr.get("match","")} — {pr.get("prediction","-")} — {score} — {"✅ Validé" if ok else "❌ Échoué"}'
        )
        ids_to_mark.append(x["id"])

    if not validated_lines:
        print("■ Aucun match terminé parmi ceux à valider (on réessaiera au prochain cron).")
        return

    text = (
        f"📌 Validation des coupons SIMPLE du {yday}\n\n"
        + "\n".join(validated_lines)
        + f"\n\nBilan : {wins}/{finished} ✅"
    )

    send_message(
        text,
        buttons=[
            [{"text": "Voir l’historique", "url": HIST_URL}],
            [{"text": "Voir plus de coupons", "url": MORE_URL}],
        ],
    )

    sb_mark_validated(ids_to_mark)
    print(f"■ Validation envoyée. Lignes marquées: {len(ids_to_mark)}")

# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["send-today", "validate-yesterday"], required=True)
    args = parser.parse_args()

    if args.mode == "send-today":
        send_today()
    elif args.mode == "validate-yesterday":
        validate_yesterday()

if __name__ == "__main__":
    main()