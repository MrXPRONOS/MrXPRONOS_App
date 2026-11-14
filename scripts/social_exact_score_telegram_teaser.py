#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teaser Telegram pour les videos Dixon-Coles deja publiees.

AUCUN score n'est dessine dans l'image ou la legende. Les liens directs ne
proviennent que de recus sociaux confirmes, jamais de pages de profil.
En mode test, l'unique canal autorise est @predict_mrxp.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
LOME = ZoneInfo("Africa/Lome")
TEST_CHANNEL = "@predict_mrxp"
LABELS = {
    "youtube": "▶️ YouTube", "facebook": "📘 Facebook",
    "instagram": "📸 Instagram", "threads": "🧵 Threads",
    "bluesky": "🦋 Bluesky",
}
ORDER = tuple(LABELS)
CANVAS = (1200, 1600)
BG = (7, 17, 34)
TEAL = (53, 229, 207)
WHITE = (244, 250, 255)
SUBTLE = (169, 190, 204)


def font(size: int, bold: bool = True):
    paths = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf") if bold else (
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",)
    for path in paths:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.truetype("DejaVuSans.ttf", size)


def trim(draw, value, face, width):
    value = str(value or "").strip()
    if draw.textbbox((0, 0), value, font=face)[2] <= width:
        return value
    while value and draw.textbbox((0, 0), value + "…", font=face)[2] > width:
        value = value[:-1]
    return value + "…" if value else "—"


def date_label(target: str) -> str:
    d = date.fromisoformat(target)
    months = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
              "août", "septembre", "octobre", "novembre", "décembre")
    return f"{d.day} {months[d.month - 1]} {d.year}"


def check_inputs(manifest: dict, predictions: dict) -> list:
    if not isinstance(manifest, dict) or not isinstance(predictions, dict):
        raise ValueError("Manifest et predictions obligatoires")
    target = manifest.get("target")
    date.fromisoformat(target)
    n = manifest.get("count")
    if (type(n) is not int or not 1 <= n <= 10
            or manifest.get("ready_for_video") is not True
            or manifest.get("status") != "READY"
            or predictions.get("date_local_africa_lome") != target
            or predictions.get("ready_for_video") is not True):
        raise ValueError("Selection sociale incoherente ou non validee")
    rows = predictions.get("selected")
    if not isinstance(rows, list) or len(rows) != n:
        raise ValueError("Nombre de rencontres incompatible")
    ids = [str(row.get("id") or "") for row in rows if isinstance(row, dict)]
    if len(ids) != n or any(not i for i in ids) or len(set(ids)) != n:
        raise ValueError("IDs de rencontres invalides")
    if isinstance(manifest.get("match_ids"), list) and manifest["match_ids"] != ids:
        raise ValueError("Rencontres et manifeste ne correspondent pas")
    for row in rows:
        if not row.get("home") or not row.get("away"):
            raise ValueError("Equipe absente du teaser")
    return rows


def safe_link(platform: str, value: str) -> str | None:
    if not isinstance(value, str) or len(value) > 500:
        return None
    parsed = urlsplit(value.strip())
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or parsed.port is not None or parsed.query and platform != "facebook"
            or parsed.fragment):
        return None
    host = (parsed.hostname or "").lower()
    path = parsed.path
    valid = {
        "youtube": host in ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be") and
                   (path.startswith("/shorts/") or path.startswith("/watch") or host == "youtu.be"),
        "facebook": host in ("facebook.com", "www.facebook.com", "m.facebook.com", "fb.watch") and
                    (path.startswith("/watch/") or path.startswith("/reel/") or "/videos/" in path or host == "fb.watch"),
        "instagram": host in ("instagram.com", "www.instagram.com") and
                     (path.startswith("/reel/") or path.startswith("/p/")),
        "threads": host in ("threads.net", "www.threads.net", "threads.com", "www.threads.com") and "/post/" in path,
        "bluesky": host == "bsky.app" and "/post/" in path,
    }
    # A watch URL may include ?v=... but reject every other query key.
    if platform == "facebook" and parsed.query and not re.fullmatch(r"v=[0-9]{5,30}", parsed.query):
        return None
    return value.strip() if valid.get(platform, False) else None


def graph_permalink(platform: str, identity: str, get=requests.get) -> str | None:
    if not identity.isdigit():
        return None
    if platform == "instagram":
        base = "https://graph.facebook.com/v24.0/" + identity
        token = os.getenv("META_ACCESS_TOKEN", "")
        field = "permalink"
    elif platform == "threads":
        base = "https://graph.threads.net/v1.0/" + identity
        token = os.getenv("THREADS_ACCESS_TOKEN", "")
        field = "permalink"
    elif platform == "facebook":
        base = "https://graph.facebook.com/v24.0/" + identity
        token = os.getenv("META_PAGE_ACCESS_TOKEN", "")
        field = "permalink_url"
    else:
        return None
    if not token:
        return None
    try:
        resp = get(base, params={"fields": field, "access_token": token}, timeout=(7, 15))
        if resp.status_code != 200:
            return None
        result = resp.json()
        return safe_link(platform, result.get(field))
    except (requests.RequestException, ValueError, TypeError):
        return None


def links_from_receipts(report: list, manifest: dict) -> dict:
    if not isinstance(report, list):
        raise ValueError("Rapport de publication invalide")
    found = {}
    for row in report:
        if not isinstance(row, dict):
            continue
        platform = row.get("platform")
        if platform not in ORDER or platform in found or row.get("ok") is not True:
            continue
        if any(row.get(key) != manifest.get(source) for key, source in (
            ("target", "target"), ("count", "count"),
            ("publication_mode", "publication_mode"), ("video_sha256", "sha256"))):
            continue
        info = row.get("data")
        identity = str((info or {}).get("id") or "").strip() if isinstance(info, dict) else ""
        if not identity:
            continue
        direct = safe_link(platform, info.get("url")) if isinstance(info, dict) else None
        if not direct and platform == "youtube" and re.fullmatch(r"[a-zA-Z0-9_-]{11}", identity):
            direct = "https://www.youtube.com/shorts/" + identity
        if not direct and platform == "bluesky" and identity.startswith("at://"):
            handle = os.getenv("BLUESKY_HANDLE", "").strip().lstrip("@")
            key = identity.rsplit("/", 1)[-1]
            if re.fullmatch(r"[a-zA-Z0-9.\-]{3,100}", handle) and re.fullmatch(r"[a-zA-Z0-9]+", key):
                direct = "https://bsky.app/profile/" + handle + "/post/" + key
        if not direct and platform in ("facebook", "instagram", "threads"):
            direct = graph_permalink(platform, identity)
        if not direct and platform == "facebook" and re.fullmatch(r"[0-9]{5,30}", identity):
            direct = "https://www.facebook.com/watch/?v=" + identity
        if direct and safe_link(platform, direct):
            found[platform] = direct
    return {name: found[name] for name in ORDER if name in found}


def keyboard(links: dict) -> dict:
    items = [{"text": LABELS[name], "url": links[name]} for name in ORDER if name in links]
    return {"inline_keyboard": [items[i:i + 2] for i in range(0, len(items), 2)]}


def logo_image(url: str | None, size=58):
    if not url:
        return None
    parsed = urlsplit(str(url))
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    try:
        result = requests.get(url, timeout=(5, 12), stream=True, allow_redirects=True)
        if result.status_code != 200 or not result.headers.get("content-type", "").lower().startswith("image/"):
            result.close()
            return None
        data = BytesIO()
        for chunk in result.iter_content(65536):
            data.write(chunk)
            if data.tell() > 1_500_000:
                result.close()
                return None
        result.close()
        image = Image.open(BytesIO(data.getvalue())).convert("RGBA")
        image.thumbnail((size, size))
        return image
    except (OSError, requests.RequestException, ValueError):
        return None


def draw_logo(image, d, logo_url, x, y, team):
    d.ellipse((x, y, x + 66, y + 66), fill=(25, 48, 69))
    logo = logo_image(logo_url, 56)
    if logo is not None:
        image.paste(logo, (x + (66 - logo.width) // 2, y + (66 - logo.height) // 2), logo)
    else:
        initials = "".join(w[0] for w in str(team).split()[:2]).upper()[:2] or "FC"
        d.text((x + 33, y + 33), initials, font=font(18), fill=WHITE, anchor="mm")


def render(image_path: Path, manifest: dict, predictions: dict, *, test=False) -> Path:
    rows = check_inputs(manifest, predictions)
    target = manifest["target"]
    n = len(rows)
    image = Image.new("RGB", CANVAS, BG)
    d = ImageDraw.Draw(image)
    # Neon brand, inspired by the existing Dixon-Coles social render.
    d.rounded_rectangle((38, 37, 1162, 110), radius=27, fill=(16, 39, 58))
    d.text((67, 73), "Mr XPRONOS", font=font(40), fill=WHITE, anchor="lm")
    d.text((1137, 74), "EXACT SCORE", font=font(22), fill=TEAL, anchor="rm")
    if test:
        heading = "APERÇU TEST — SCORES MASQUÉS"
    else:
        heading = "LES TOP SCORES EXACTS DE DEMAIN"
    d.text((40, 158), heading, font=font(41), fill=WHITE)
    d.text((42, 226), f"{n} MATCH{'S' if n > 1 else ''} · {date_label(target).upper()}",
           font=font(30), fill=TEAL)
    d.text((42, 282), "Les rencontres sont ici. Les scores sont dans les vidéos.",
           font=font(26, False), fill=SUBTLE)
    top = 357
    for i, match in enumerate(rows):
        col, row = i % 2, i // 2
        x = 40 + col * 574
        y = top + row * 220
        d.rounded_rectangle((x, y, x + 542, y + 206), radius=24, fill=(17, 35, 55),
                            outline=(36, 77, 87), width=2)
        d.text((x + 22, y + 29), f"{i + 1:02d}", font=font(26), fill=TEAL, anchor="lm")
        league = trim(d, match.get("league") or "Football", font(21, False), 418)
        d.text((x + 88, y + 29), league, font=font(21, False), fill=SUBTLE, anchor="lm")
        for j, (side, name_key) in enumerate((("home", "home_logo_url"), ("away", "away_logo_url"))):
            yy = y + 57 + j * 69
            team = str(match.get(side) or "")
            draw_logo(image, d, match.get(name_key), x + 24, yy, team)
            face = font(27)
            d.text((x + 107, yy + 33), trim(d, team, face, 405), font=face,
                   fill=WHITE, anchor="lm")
        d.rounded_rectangle((x + 392, y + 161, x + 521, y + 194),
                            radius=10, fill=(35, 74, 80))
        d.text((x + 457, y + 178), "—  :  —", font=font(23), fill=TEAL, anchor="mm")
    d.line((42, 1498, 1158, 1498), fill=(39, 96, 102), width=2)
    d.text((600, 1537), "DÉCOUVRE LES SCORES SUR NOS RÉSEAUX SOCIAUX",
           font=font(23), fill=WHITE, anchor="mm")
    d.text((600, 1574), "Pronostics statistiques, jamais garantis · 18+ · Joue responsablement",
           font=font(17, False), fill=SUBTLE, anchor="mm")
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(image_path, "PNG", optimize=True)
    return image_path


def make_caption(manifest, links, *, test=False):
    n = manifest["count"]
    day = date_label(manifest["target"])
    if test:
        return ("🧪 TEST VISUEL — Mr XPRONOS\n"
                f"⚽ Aperçu de {n} rencontre(s) du {day}, scores masqués.\n"
                "🔎 Vérifie le visuel et les boutons ci-dessous. "
                "Les liens disponibles ouvrent les vidéos déjà publiées.\n"
                "18+ · Joue responsablement.")
    return (f"⚽ LES {n} SCORES EXACTS POSSIBLES DE DEMAIN — {day}\n\n"
            "👀 Découvre les matchs sélectionnés sur l'image. "
            "Les pronostics sont volontairement masqués !\n\n"
            "🎬 Clique sur un bouton ci-dessous pour voir les scores dans nos vidéos.\n"
            "📊 Prévisions statistiques, jamais garanties. 18+ · Joue responsablement.")


def send_test(image: Path, caption: str, links: dict, *, token: str, chat: str):
    from telegram_test_guard import validate_test_channel
    dest = validate_test_channel(chat, token)
    with image.open("rb") as stream:
        try:
            response = requests.post(
                "https://api.telegram.org/bot" + token + "/sendPhoto",
                data={"chat_id": dest["chat_id"], "caption": caption,
                      "reply_markup": json.dumps(keyboard(links), ensure_ascii=False)},
                files={"photo": (image.name, stream, "image/png")}, timeout=(10, 100))
        except requests.RequestException:
            raise RuntimeError("Envoi Telegram incertain, ne pas relancer automatiquement") from None
    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError("Réponse Telegram non JSON") from None
    message = payload.get("result") or {}
    if (response.status_code != 200 or payload.get("ok") is not True
            or not isinstance(message.get("message_id"), int)
            or (message.get("chat") or {}).get("id") != dest["chat_id"]):
        raise RuntimeError("Telegram n'a pas confirme l'envoi dans le canal de test")
    return {"message_id": message["message_id"],
            "url": "https://t.me/predict_mrxp/" + str(message["message_id"]),
            "buttons": list(links), "target": dest["username"]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--predictions", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--receipt", type=Path)
    p.add_argument("--mode", choices=("test",), default="test")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--dedupe", action="store_true",
                   help="Reserve one Telegram teaser per target day in the existing D1 ledger")
    args = p.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf8"))
    predictions = json.loads(args.predictions.read_text(encoding="utf8"))
    report = json.loads(args.report.read_text(encoding="utf8"))
    rows = check_inputs(manifest, predictions)
    links = links_from_receipts(report, manifest)
    if not links:
        print("TEASER_SKIPPED no verified video permalink; no Telegram message")
        return 0
    render(args.image, manifest, predictions, test=True)
    caption = make_caption(manifest, links, test=True)
    print("TEASER_READY", json.dumps({"target": manifest["target"], "matches": len(rows),
            "buttons": list(links), "image": str(args.image), "mode": args.mode}))
    if args.dry_run:
        return 0
    token = (os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    chat = (os.getenv("TELEGRAM_TEST_CHAT_ID") or TEST_CHANNEL).strip()
    if not token:
        raise RuntimeError("FOOTBALL_NEWS_BOT_TOKEN manquant")
    ledger = None
    if args.dedupe:
        from d1_publication_ledger import D1Ledger
        ledger = D1Ledger()
        if not ledger.claim("dcscore_social_teaser_test", "tomorrow-social-video", manifest["target"]):
            print("TEASER_ALREADY_SENT", manifest["target"])
            return 0
    receipt = send_test(args.image, caption, links, token=token, chat=chat)
    if ledger:
        ledger.mark("dcscore_social_teaser_test", "tomorrow-social-video",
                    manifest["target"], message_id=receipt["message_id"])
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("TEASER_TEST_SENT", json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        # Never print the Telegram API URL: it contains a bot token.
        print("TEASER_ERROR", type(error).__name__, str(error), file=sys.stderr)
        raise SystemExit(1)
