#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-time recovery of the 2026-10-18 coupon video on Threads only.

Checks account, source video, previous posts and API publish result.
No token printing, no posts to other platforms, no blind retry after failure.
"""
from __future__ import annotations

import json
import os
import sys
from urllib.parse import urlparse

import requests

from scripts.post_shorts_video import post_threads

CAPTION = (
    "⚽ Pronostics du 18 octobre 2026 — 4 sélections Mr XPRONOS.\n"
    "Retrouve nos analyses et coupons sur Telegram : @mr_xpronos\n"
    "18+ • Joue responsablement.\n"
    "#football #pronostic #mrxpronos"
)
UNIQUE_TEXT = "Pronostics du 18 octobre 2026 — 4 sélections Mr XPRONOS."
EXPECTED_USERNAME = "mr_xpronos"
BASE = "https://graph.threads.net/v1.0"


def api_get(path: str, token: str, *, params: dict | None = None) -> dict:
    r = requests.get(BASE + path, params=params,
                     headers={"Authorization": "Bearer " + token}, timeout=45)
    if not r.ok:
        code = None
        try:
            code = r.json().get("error", {}).get("code")
        except ValueError:
            pass
        raise RuntimeError(f"Threads GET {path} HTTP {r.status_code}, error_code={code}")
    result = r.json()
    if not isinstance(result, dict):
        raise RuntimeError("Réponse Threads non JSON objet")
    return result


def verify_existing_posts(token: str) -> dict | None:
    # Fail closed if timeline cannot be queried, to prevent duplicate public posts.
    payload = api_get("/me/threads", token, params={
        "fields": "id,text,permalink,timestamp,media_type", "limit": "50"
    })
    for item in payload.get("data") or []:
        if UNIQUE_TEXT in str(item.get("text") or ""):
            return item
    return None


def main() -> int:
    token = (os.getenv("THREADS_ACCESS_TOKEN") or "").strip()
    expected_id = (os.getenv("THREADS_USER_ID") or "").strip()
    url = (os.getenv("THREADS_RECOVERY_VIDEO_URL") or "").strip()
    if not token or not expected_id or not url:
        raise RuntimeError("THREADS_ACCESS_TOKEN / THREADS_USER_ID / video URL manquant")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "nhwafcpndlufzzxexikh.supabase.co":
        raise RuntimeError("Source vidéo invalide: domaine ou schéma inattendu")

    profile = api_get("/me", token, params={"fields": "id,username"})
    if str(profile.get("id") or "") != expected_id:
        raise RuntimeError("Compte Threads incohérent avec THREADS_USER_ID")
    username = str(profile.get("username") or "").strip().lstrip("@").lower()
    if username != EXPECTED_USERNAME:
        raise RuntimeError("Compte Threads incorrect: aucun post envoyé")
    print("THREADS_RECOVERY_ACCOUNT_OK", username, flush=True)

    previous = verify_existing_posts(token)
    if previous:
        print("THREADS_RECOVERY_ALREADY_PUBLISHED", json.dumps({
            "id": previous.get("id"), "permalink": previous.get("permalink")
        }), flush=True)
        return 0

    # Meta fetches the video by public URL, ensure that it actually exists.
    head = requests.head(url, timeout=30, allow_redirects=True)
    if head.status_code != 200:
        raise RuntimeError(f"Source MP4 inaccessible: HTTP {head.status_code}")
    print("THREADS_RECOVERY_VIDEO_ACCESSIBLE", head.status_code,
          head.headers.get("content-length", "unknown"), flush=True)

    posted = post_threads(url, CAPTION)
    if not posted.ok:
        raise RuntimeError("Publication vidéo Threads impossible: " + posted.message)
    post_id = str((posted.data or {}).get("id") or "")
    if not post_id:
        raise RuntimeError("Publication Threads sans identifiant: vérifier directement le compte")

    print("THREADS_RECOVERY_PUBLISH_ACK", post_id, flush=True)
    media = api_get("/" + post_id, token,
                    params={"fields": "id,permalink,media_type,text"})
    if str(media.get("id")) != post_id:
        raise RuntimeError("Identifiant renvoyé par Threads incohérent")
    if str(media.get("media_type") or "").upper() not in ("VIDEO", "CAROUSEL_ALBUM"):
        raise RuntimeError(f"Média publié avec mauvais type: {media.get('media_type')}")
    print("THREADS_RECOVERY_PUBLISHED", json.dumps({
        "id": post_id, "permalink": media.get("permalink"),
        "media_type": media.get("media_type")
    }, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (requests.RequestException, RuntimeError) as e:
        print("::error::" + str(e).replace(
            os.getenv("THREADS_ACCESS_TOKEN") or "__NON_TOKEN__", "***"), file=sys.stderr)
        sys.exit(1)
