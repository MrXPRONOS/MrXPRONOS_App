#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dedicated social-only publication for tomorrow's Dixon-Coles Top10.

Uses proven platform adapters without editing or invoking any Telegram workflows.
Each platform/day has a distinct D1 reservation, preventing accidental reposts.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo

import requests

from d1_publication_ledger import D1Ledger
import post_shorts_video as social

LOME = ZoneInfo("Africa/Lome")
DEFAULT_PLATFORMS = "facebook,youtube,instagram,threads,bluesky"
PUBLIC_BUCKET = "videos"


def validate_manifest(manifest: dict, video: Path, now: datetime | None = None) -> str:
    now = now or datetime.now(LOME)
    target = str(manifest.get("target") or "")
    try:
        parsed = date.fromisoformat(target)
    except ValueError as error:
        raise ValueError("Date cible invalide") from error
    if parsed != now.date() + timedelta(days=1):
        raise ValueError("Publication limitée aux pronostics de demain à Lomé")
    if (manifest.get("schema") != "mrx-dixon-coles-social-top10-v1"
            or manifest.get("status") != "READY"
            or manifest.get("ready_for_video") is not True
            or manifest.get("count") != 10
            or manifest.get("telegram_username") != "@mr_xpronos"):
        raise ValueError("Manifeste Top10 incomplet ou non conforme")
    if video.suffix.lower() != ".mp4" or not video.is_file():
        raise ValueError("MP4 social manquant")
    size = video.stat().st_size
    if size < 100_000 or size > 24 * 1024 * 1024:
        raise ValueError("MP4 hors limites")
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    if digest != manifest.get("sha256"):
        raise ValueError("Le MP4 ne correspond pas au manifeste vérifié")
    return target


def build_copy(target: str) -> tuple[str, str, str]:
    day = date.fromisoformat(target).strftime("%d/%m/%Y")
    title = f"10 scores exacts possibles pour le {day} | Mr XPRONOS"
    description = (
        f"10 rencontres du {day}, prévisions statistiques Dixon-Coles "
        "(scores possibles, jamais garantis). "
        "Telegram : @mr_xpronos. 18+ • Joue responsablement. #Shorts"
    )
    caption = (
        f"⚽ 10 scores exacts possibles pour demain ({day})\n"
        "📲 Rejoins-nous sur Telegram pour plus de coupons\n"
        "Compte Telegram : Mr XPRONOS • @mr_xpronos\n"
        "Prévisions statistiques, pas de résultat garanti. 18+ • Joue responsablement.\n"
        "#football #scoreexact #pronostics #mrxpronos"
    )
    return title, description, caption


def public_url(video: Path, target: str) -> str:
    """Upload to the pre-existing *public* videos bucket only, never make a new bucket."""
    base = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    secret = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or "").strip()
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".supabase.co"):
        raise RuntimeError("SUPABASE_URL HTTPS du projet requise")
    if not secret:
        raise RuntimeError("Clé serveur Supabase manquante")
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    key = f"shorts/dixon-coles-social/{target}/{digest[:24]}.mp4"
    public = f"{base}/storage/v1/object/public/{PUBLIC_BUCKET}/{quote(key, safe='/')}"
    upload = f"{base}/storage/v1/object/{PUBLIC_BUCKET}/{quote(key, safe='/')}"

    def already_public() -> bool:
        try:
            probe = requests.get(public, headers={"Range": "bytes=0-0"}, timeout=20, stream=True)
            try:
                return probe.status_code in (200, 206) and (
                    "video/" in (probe.headers.get("content-type") or "").lower())
            finally:
                probe.close()
        except requests.RequestException:
            return False

    if already_public():
        return public
    headers = {
        "apikey": secret, "Authorization": "Bearer " + secret,
        "Content-Type": "video/mp4", "x-upsert": "false",
    }
    with video.open("rb") as stream:
        reply = requests.post(upload, headers=headers, data=stream, timeout=180)
    # A duplicate immutable SHA object is fine only if independently verifiable.
    if reply.status_code not in (200, 201, 409):
        raise RuntimeError(f"Upload vidéo Supabase rejeté (HTTP {reply.status_code})")
    if not already_public():
        raise RuntimeError("Le MP4 Supabase n'est pas accessible publiquement")
    return public


def recorded_receipt(ledger: D1Ledger, kind: str, ref: str, day: str) -> dict | None:
    rows = ledger.query(
        "SELECT delivery_status,validation_details FROM telegram_sent "
        "WHERE kind=? AND ref_id=? AND ref_date=? LIMIT 1",
        (kind, ref, day)).get("results") or []
    if not rows:
        return None
    row = rows[0]
    try:
        info = json.loads(row.get("validation_details") or "{}")
    except (ValueError, TypeError):
        info = {}
    if row.get("delivery_status") == "sent" and isinstance(info.get("id"), str) and info["id"]:
        return {"status": "sent", "id": info["id"]}
    return {"status": "unconfirmed"}


def set_receipt(ledger: D1Ledger, kind: str, ref: str, day: str, provider_id: str) -> None:
    receipt = json.dumps({"id": provider_id}, ensure_ascii=False)
    row = ledger.query(
        "UPDATE telegram_sent SET delivery_status='sent', published_at=?, validation_details=? "
        "WHERE kind=? AND ref_id=? AND ref_date=? AND delivery_status='reserved'",
        (datetime.now(LOME).isoformat(), receipt, kind, ref, day))
    if (row.get("meta") or {}).get("changes") != 1:
        raise RuntimeError("Publication faite mais preuve D1 non confirmée")


def dispatch(platform: str, video: Path, url: str | None,
             title: str, description: str, caption: str):
    return {
        "facebook": lambda: social.post_facebook_page(video, caption),
        "youtube": lambda: social.post_youtube(video, title, description),
        "instagram": lambda: social.post_instagram_reel(url, caption),
        "threads": lambda: social.post_threads(url, caption),
        "bluesky": lambda: social.post_bluesky_video(video, caption, title),
        "tiktok": lambda: social.post_tiktok(video, caption),
    }[platform]()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--platforms", default=os.getenv("POST_PLATFORMS", DEFAULT_PLATFORMS))
    p.add_argument("--report", type=Path, default=Path("social_exact_scores_out/social_post_results.json"))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    target = validate_manifest(manifest, args.video)
    platforms = social.parse_platforms(args.platforms)
    if not platforms:
        raise ValueError("Aucun réseau social demandé")
    title, description, caption = build_copy(target)
    if args.dry_run:
        print("SOCIAL_EXACT_SCORE_PREVIEW", json.dumps({
            "target": target, "platforms": platforms, "title": title,
            "description": description, "caption": caption}, ensure_ascii=False))
        return 0

    # Persistent claims must be available before performing ANY social upload.
    ledger = D1Ledger()
    ref = "tomorrow-top10"
    url = None
    url_error = None
    if set(platforms) & {"instagram", "threads"}:
        try:
            url = public_url(args.video, target)
        except Exception as exc:
            url_error = type(exc).__name__ + ": " + str(exc)
            print("SOCIAL_EXACT_PUBLIC_VIDEO_NOT_READY", url_error, flush=True)

    results = []
    args.report.parent.mkdir(parents=True, exist_ok=True)
    for platform in platforms:
        kind = "dcscore_social_top10_" + platform
        row = {"platform": platform, "ok": False, "message": "", "data": {}}
        try:
            existing = recorded_receipt(ledger, kind, ref, target)
            if existing and existing["status"] == "sent":
                row.update(ok=True, message="Déjà publié : preuve D1", data={"id": existing["id"]})
            elif existing:
                row["message"] = "Publication précédente incertaine; envoi bloqué contre doublon"
            elif platform in ("instagram", "threads") and url_error:
                row["message"] = "Vidéo publique non disponible : " + url_error
            elif ledger.claim(kind, ref, target):
                try:
                    response = dispatch(platform, args.video, url, title, description, caption)
                except Exception as exc:
                    row["message"] = "Envoi ambigu : " + type(exc).__name__ + "; vérification manuelle requise"
                else:
                    provider_id = response.data.get("id") if isinstance(response.data, dict) else None
                    if response.ok and provider_id:
                        set_receipt(ledger, kind, ref, target, str(provider_id))
                        row.update(ok=True, message=response.message,
                                   data={"id": str(provider_id)})
                    else:
                        # Do NOT release the claim: an upload timeout can already be published.
                        row["message"] = response.message or "Publication non confirmée"
            else:
                row["message"] = "Réservation D1 concurrente; publication bloquée"
        except Exception as exc:
            row["message"] = "Échec de sécurité : " + type(exc).__name__
        results.append(row)
        args.report.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(("SOCIAL_EXACT_POST_OK " if row["ok"] else "SOCIAL_EXACT_POST_FAILED ")
              + platform + " : " + row["message"], flush=True)
    return 0 if all(r["ok"] for r in results) and len(results) == len(platforms) else 1


if __name__ == "__main__":
    raise SystemExit(main())
