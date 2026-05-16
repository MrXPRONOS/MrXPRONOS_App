#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import glob
import json
import time
import argparse
import requests
import subprocess
from datetime import datetime, timedelta, timezone

UTC = timezone.utc

# Telegram
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SITE_URL = os.environ.get("SITE_URL", "https://mrxpronos.github.io/MrXPRONOS_App/")
MORE_URL = os.environ.get("MORE_URL", SITE_URL + "pronos.html")
HIST_URL = os.environ.get("HIST_URL", SITE_URL + "historique.html")

# Fichiers
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

# --- Helpers Telegram ---
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

# --- Helpers Supabase ---
def sb_log_sent(match_id: str, date_str: str):
    url = f"{SUPABASE_URL}/rest/v1/telegram_sent"
    payload = {
        "kind": "daily_simple",
        "ref_id": str(match_id),
        "ref_date": date_str,
        "validation_sent": False
    }
    # Upsert: on_conflict = kind,ref_id,ref_date
    r = requests.post(
        url,
        headers=sb_headers(),
        json=payload,
        params={"on_conflict": "kind,ref_id,ref_date"},
        timeout=30
    )
    if not r.ok:
        print("Supabase log error:", r.status_code, r.text)
        r.raise_for_status()

def sb_fetch_to_validate(date_str: str):
    """Récupère les IDs des coupons envoyés pour une date donnée, non encore validés."""
    url = f"{SUPABASE_URL}/rest/v1/telegram_sent"
    params = {
        "select": "id,ref_id",
        "kind": "eq.daily_simple",
        "ref_date": f"eq.{date_str}",
        "validation_sent": "eq.false",
        "order": "sent_at.asc",
        "limit": "30",
    }
    r = requests.get(url, headers=sb_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json() or []

def sb_get_pronostic(match_id: str, date_str: str):
    """Récupère un pronostic depuis Supabase."""
    url = f"{SUPABASE_URL}/rest/v1/pronostics"
    params = {
        "select": "match, prediction, home_score, away_score, verified_double, is_finished",
        "match_id": f"eq.{match_id}",
        "date": f"eq.{date_str}",
        "limit": "1",
    }
    r = requests.get(url, headers=sb_headers(), params=params, timeout=30)
    r.raise_for_status()
    rows = r.json() or []
    return rows[0] if rows else None

def sb_mark_validated(ids):
    """Marque les enregistrements comme validés."""
    for _id in ids:
        url = f"{SUPABASE_URL}/rest/v1/telegram_sent?id=eq.{_id}"
        r = requests.patch(url, headers=sb_headers(), json={"validation_sent": True}, timeout=30)
        r.raise_for_status()

# --- Manifest ---
def load_manifest():
    p = os.path.join(OUT_DIR, "manifest.json")
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

# ========== MODE 1 : Envoi des coupons du jour ==========
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
    intro = f"📊 Coupons SIMPLE du {date_str} (UTC)\n🔗 Plus de coupons fiables : {MORE_URL}"
    send_message(intro, buttons=[[{"text": "Voir plus de coupons", "url": MORE_URL}]])

    n = min(len(files), len(matches))
    for idx in range(n):
        match_id = matches[idx]["match_id"]
        send_photo(files[idx], caption="")
        sb_log_sent(match_id, date_str)
        time.sleep(0.7)

    send_message(f"✅ Fin des coupons SIMPLE du {date_str}.\n🔗 Voir plus : {MORE_URL}")

# ========== MODE 2 : Validation des coupons d'hier ==========
def validate_yesterday():
    require_telegram()
    require_supabase()
    export_url = os.environ.get("EXPORT_URL", "http://127.0.0.1:8000/pronos.html")

    yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    rows = sb_fetch_to_validate(yesterday)
    if not rows:
        print("Rien à valider pour hier.")
        # On envoie quand même un récapitulatif ? Optionnel
        send_message(f"📅 Hier ({yesterday}) : aucun coupon à valider.")
        return

    items = []
    pending_lines = []
    finished_count = 0
    wins = 0

    for x in rows:
        match_id = str(x["ref_id"])
        pr = sb_get_pronostic(match_id, yesterday)
        if not pr:
            continue
        match_name = pr.get("match") or match_id
        dc = pr.get("prediction") or "-"

        if not pr.get("is_finished"):
            pending_lines.append(f"⏳ {match_name} - {dc} - en attente")
            continue

        finished_count += 1
        ok = bool(pr.get("verified_double"))
        if ok:
            wins += 1
        hs = pr.get("home_score")
        as_ = pr.get("away_score")
        score = f"{hs}-{as_}" if hs is not None and as_ is not None else "-"

        items.append({
            "telegram_sent_id": x["id"],
            "match_id": match_id,
            "outcome": "win" if ok else "lose",
            "file": f"val_{len(items)+1:02d}.png",
            "caption": f"{'✅' if ok else '❌'} {match_name} - {dc} - {score}"
        })

    if not items:
        print("Aucun match terminé à valider (on réessayera au prochain cron).")
        # Envoi d'un message récapitulatif quand même
        recap = f"📅 Résultats d'hier ({yesterday}) :\nTerminés: 0\nEn attente: {len(pending_lines)}"
        if pending_lines:
            recap += "\n\n⏳ En attente:\n" + "\n".join(pending_lines[:5])
            if len(pending_lines) > 5:
                recap += f"\n... et {len(pending_lines)-5} autres"
        send_message(recap)
        return

    # Écrire validate_list.json pour Playwright
    list_path = os.path.join(OUT_DIR, "validate_list.json")
    with open(list_path, "w", encoding="utf-8") as f:
        json.dump({"date": yesterday, "items": items}, f, ensure_ascii=False, indent=2)

    # Exporter les images des cartes "Hier" correspondant aux match_id
    env = os.environ.copy()
    env["OUT_DIR"] = OUT_DIR
    env["EXPORT_URL"] = export_url
    env["LIST_FILE"] = list_path
    subprocess.run(["node", "scripts/export_validate_cards.mjs"], check=True, env=env)

    # Envoyer les photos une par une avec la légende
    validated_ids = []
    for item in items:
        photo_path = os.path.join(OUT_DIR, item["file"])
        if os.path.exists(photo_path):
            send_photo(photo_path, caption=item["caption"])
            validated_ids.append(item["telegram_sent_id"])
            time.sleep(0.7)
        else:
            print(f"Image manquante : {photo_path}")

    # Marquer comme validé dans Supabase
    if validated_ids:
        sb_mark_validated(validated_ids)

    # Envoyer un récapitulatif final
    total = finished_count
    success_rate = (wins / total * 100) if total > 0 else 0
    recap = f"📊 Bilan d'hier ({yesterday}) :\n✅ {wins} gains / {total} terminés ({success_rate:.1f}%)\n"
    if pending_lines:
        recap += f"\n⏳ Encore {len(pending_lines)} match(s) en attente de résultat."
    send_message(recap)

# ========== MAIN ==========
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