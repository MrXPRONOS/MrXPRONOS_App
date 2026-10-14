#!/usr/bin/env python3
"""Publish three real-data Mr XPRONOS preview cards to @predict_mrxp ONLY.

Default is dry-run. There is no production route in this script.
"""
from __future__ import annotations

import argparse
import html
import io
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont
from telegram_test_guard import validate_test_channel

TEST_USERNAME = "predict_mrxp"
PUBLIC_SITE = "https://mrxpronos.github.io/MrXPRONOS_App/live.html"
SOURCE_NAMES = ("espn", "sportscore", "thesportsdb", "openligadb")
COLORS = {"navy": "#061522", "panel": "#102738", "gold": "#f1c55a",
          "white": "#f7f9fc", "muted": "#b8c5d0", "teal": "#50e3c2"}


def utc_now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def font(size, bold=False):
    paths = (["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if bold
             else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def wrap_text(draw, value, face, max_width):
    lines = []
    for para in str(value).split("\n"):
        words = para.split()
        if not words:
            lines.append("")
            continue
        line = ""
        for word in words:
            trial = (line + " " + word).strip()
            if draw.textlength(trial, font=face) <= max_width:
                line = trial
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
    return lines


def render_card(title, kicker, lines):
    im = Image.new("RGB", (1080, 1080), COLORS["navy"])
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((50, 45, 1030, 1034), radius=45,
                        fill=COLORS["panel"], outline="#254356", width=3)
    d.rounded_rectangle((94, 98, 400, 152), radius=22, fill=COLORS["gold"])
    d.text((114, 109), "Mr XPRONOS   |   TEST", font=font(22, True), fill=COLORS["navy"])
    d.text((95, 215), title, font=font(54, True), fill=COLORS["white"])
    d.text((98, 312), kicker, font=font(27), fill=COLORS["gold"])
    d.line((95, 383, 982, 383), fill="#345064", width=2)
    y = 439
    for i, content in enumerate(lines[:7]):
        body_font = font(29 if len(str(content)) > 52 else 33, i == 0)
        for line in wrap_text(d, content, body_font, 845)[:3]:
            if y > 904:
                break
            d.text((104, y), line, font=body_font,
                   fill=COLORS["white"] if i == 0 else COLORS["muted"])
            y += 48
        y += 21
    d.line((98, 959, 980, 959), fill=COLORS["gold"], width=2)
    d.text((103, 976), "Aperçu technique • canal de test uniquement",
           font=font(19), fill=COLORS["muted"])
    out = io.BytesIO()
    im.save(out, format="PNG", optimize=True)
    return out.getvalue()


def get_rows(table, params):
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    token = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base.startswith("https://") or not token:
        raise RuntimeError("Secrets Supabase requis pour des publications fondées sur les données.")
    try:
        r = requests.get(
            base + "/rest/v1/" + table, params=params,
            headers={"apikey": token, "Authorization": "Bearer " + token,
                     "Accept": "application/json"},
            timeout=(7, 20),
        )
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list):
            raise ValueError("Expected array")
        return data
    except (requests.RequestException, ValueError) as error:
        # Never show an authenticated request URL or server payload.
        raise RuntimeError("Lecture Supabase impossible pour " + table) from None


def nf(value, fallback="—"):
    return fallback if value is None else str(value)


def pair_total(stats, name):
    if not isinstance(stats, dict):
        return None
    totals = stats.get("totals")
    value = totals.get(name) if isinstance(totals, dict) else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return None


def posts_from_database():
    now = utc_now()
    since = iso(now - timedelta(hours=2))
    recent = get_rows("live_stats_sources", {
        "select": "source_name,updated_at", "updated_at": "gte." + since,
        "order": "updated_at.desc", "limit": "1000",
    })
    counts = Counter(row.get("source_name") for row in recent)
    source_lines = [
        f"{name.upper()} : {counts[name]} enregistrement(s) sur 2 h"
        for name in SOURCE_NAMES
    ]
    source_text = "\n".join(f"• {name.upper()} : {counts[name]}" for name in SOURCE_NAMES)
    health = {
        "title": "ÉTAT DES SOURCES",
        "kicker": "Bilan API • données Supabase",
        "lines": ["4 connecteurs surveillés", *source_lines],
        "caption": "<b>🧪 TEST 1/3 — SOURCES FOOT</b>\n\n"
                   "Enregistrements actualisés sur les 2 dernières heures :\n"
                   + html.escape(source_text) +
                   "\n\nCe compteur mesure les écritures en base, pas la couverture mondiale."
                   "\n\n<i>Test technique • 18+ • Joue responsablement.</i>",
    }

    merged = get_rows("live_stats_merged", {
        "select": "home_team,away_team,home_score,away_score,minute,is_live,is_finished,merged_stats,sources_used,updated_at",
        "is_live": "eq.true", "updated_at": "gte." + iso(now - timedelta(minutes=15)),
        "order": "updated_at.desc", "limit": "8",
    })
    match = next((m for m in merged if not m.get("is_finished")), None)
    if match:
        home = nf(match.get("home_team"))
        away = nf(match.get("away_team"))
        minute = match.get("minute") or 0
        minute_label = f"{minute}'" if isinstance(minute, (int, float)) and minute > 0 else "Non communiquée"
        score = f"{nf(match.get('home_score'))} - {nf(match.get('away_score'))}"
        sources = match.get("sources_used")
        source_label = ", ".join(str(s) for s in sources) if isinstance(sources, list) else "Non précisée"
        corners = pair_total(match.get("merged_stats"), "corners")
        shots = pair_total(match.get("merged_stats"), "total_shots")
        lines = [f"{home}  VS  {away}", f"Score : {score}",
                 f"Minute : {minute_label}", f"Corners : {nf(corners, 'indisponibles')}",
                 f"Tirs : {nf(shots, 'indisponibles')}", "Sources : " + source_label]
        caption = (
            "<b>🧪 TEST 2/3 — MATCH LIVE</b>\n\n"
            f"<b>{html.escape(home)} — {html.escape(away)}</b>\n"
            f"⚽ Score : {html.escape(score)}\n"
            f"⏱ Minute : {html.escape(minute_label)}\n"
            f"🚩 Corners : {html.escape(nf(corners, 'indisponibles'))}\n"
            f"🎯 Tirs : {html.escape(nf(shots, 'indisponibles'))}\n"
            f"📡 Source(s) : {html.escape(source_label)}\n\n"
            "Données observées, pas un conseil de pari.\n"
            "<i>18+ • Joue responsablement.</i>"
        )
    else:
        lines = ["Aucune rencontre en direct", "avec mise à jour récente",
                 "et statut vérifié dans le cache.",
                 "Le moteur ne doit pas inventer de match."]
        caption = (
            "<b>🧪 TEST 2/3 — MATCH LIVE</b>\n\n"
            "Aucun match récent et confirmé dans le cache fusionné au moment du test.\n"
            "Les informations manquantes ne sont pas inventées."
        )
    live_post = {
        "title": "SUIVI EN DIRECT",
        "kicker": "Aperçu • données du moteur LIVE",
        "lines": lines, "caption": caption,
    }

    history = get_rows("live_predictions", {
        "select": "match_name,prediction_type,threshold,signal_minute,signal_value,outcome,validated,created_at,final_value",
        "validated": "eq.true",
        "created_at": "gte." + iso(now - timedelta(days=2)),
        "order": "created_at.desc", "limit": "12",
    })
    finished = next((p for p in history if p.get("outcome") in ("success", "failure")), None)
    if finished:
        result = "RÉUSSI" if finished["outcome"] == "success" else "ÉCHOUÉ"
        title = nf(finished.get("match_name"))
        kind = nf(finished.get("prediction_type"))
        threshold = nf(finished.get("threshold"))
        date = nf(finished.get("created_at"), "")[:16].replace("T", " ")
        post_lines = [title, f"Marché : {kind}", f"Seuil : {threshold}",
                      f"Verdict : {result}", f"Signal initial : {date} UTC",
                      "EXEMPLE HISTORIQUE, PAS UN SIGNAL ACTUEL"]
        caption = (
            "<b>🧪 TEST 3/3 — PRONOSTIC HISTORIQUE</b>\n\n"
            f"⚽ {html.escape(title)}\n"
            f"🎯 {html.escape(kind)} — seuil {html.escape(threshold)}\n"
            f"🏁 Résultat observé : <b>{result}</b>\n"
            f"📅 Signal enregistré : {html.escape(date)} UTC\n\n"
            "⚠️ Exemple clôturé ; ne pas interpréter comme une nouvelle opportunité.\n"
            "<i>18+ • Les résultats passés ne préjugent pas des résultats futurs.</i>"
        )
    else:
        post_lines = ["Aucun pronostic historique vérifié",
                      "disponible sur les dernières 48 h.",
                      "Le système attend des données suffisantes.",
                      "Aucun seuil ni cote n'est inventé."]
        caption = (
            "<b>🧪 TEST 3/3 — CONTRÔLE DES PRONOSTICS</b>\n\n"
            "Pas d'exemple historique vérifié disponible sur les dernières 48 h.\n"
            "En l'absence de minute et statistiques fiables, le moteur s'abstient.\n"
            "<i>18+ • Joue responsablement.</i>"
        )
    prediction_post = {"title": "QUALITÉ DES SIGNAUX", "kicker": "Bilan de contrôle",
                       "lines": post_lines, "caption": caption}
    return [health, live_post, prediction_post]


def send_photo(token, chat_id, index, post):
    img = render_card(post["title"], post["kicker"], post["lines"])
    markup = {"inline_keyboard": [[{"text": "Voir les matchs et signaux LIVE", "url": PUBLIC_SITE}]]}
    try:
        response = requests.post(
            "https://api.telegram.org/bot" + token + "/sendPhoto",
            data={"chat_id": str(chat_id), "caption": post["caption"],
                  "parse_mode": "HTML", "reply_markup": json.dumps(markup)},
            files={"photo": (f"test_mrxpronos_{index}.png", img, "image/png")},
            timeout=(8, 30),
        )
        result = response.json()
    except (requests.RequestException, ValueError):
        raise RuntimeError(f"Envoi Telegram {index} impossible (réseau/API)") from None
    if not response.ok or not result.get("ok") or not result.get("result", {}).get("message_id"):
        raise RuntimeError(f"Telegram a refusé la publication {index}; vérifier les journaux sécurisés.")
    message_id = result["result"]["message_id"]
    return {"number": index, "message_id": message_id,
            "link": f"https://t.me/{TEST_USERNAME}/{message_id}", "title": post["title"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true", help="Real sends to approved TEST channel only")
    parser.add_argument("--receipt", default="telegram_test_receipt.json")
    args = parser.parse_args()
    posts = posts_from_database()
    receipt = {"channel": "@" + TEST_USERNAME, "mode": "publish" if args.publish else "dry-run",
               "created_at": iso(utc_now()), "items": [], "intended": len(posts)}
    if args.publish:
        token = os.getenv("FOOTBALL_NEWS_BOT_TOKEN", "").strip()
        secret_chat = os.getenv("TELEGRAM_TEST_CHAT_ID", "").strip()
        if not token or not secret_chat:
            raise RuntimeError("Bot ou canal test manquant. Aucun repli production.")
        guard = validate_test_channel(secret_chat, token)
        if guard.get("username") != TEST_USERNAME or not guard.get("can_post"):
            raise RuntimeError("Canal test non autorisé")
        for index, post in enumerate(posts, start=1):
            result = send_photo(token, guard["chat_id"], index, post)
            receipt["items"].append(result)
            print("TEST_TELEGRAM_POST", json.dumps(result, ensure_ascii=False))
            Path(args.receipt).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    else:
        print("DRY_RUN_ONLY", json.dumps([
            {"title": p["title"], "caption": p["caption"]} for p in posts
        ], ensure_ascii=False, indent=2))
    Path(args.receipt).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # No credential or authenticated HTTP URL in exception output.
        print("::error::" + str(error), file=sys.stderr)
        sys.exit(1)
