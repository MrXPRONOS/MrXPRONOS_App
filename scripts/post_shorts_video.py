#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
post_shorts_video.py - Mr XPRONOS

Publie daily_pronos_shorts.mp4 sur plusieurs plateformes après la génération vidéo.

Plateformes supportées :
- Facebook Page : upload direct du fichier local via Meta Graph Video API
- Instagram Reels : nécessite une URL vidéo publique (ou upload Supabase public)
- Threads : nécessite une URL vidéo publique (ou upload Supabase public)
- TikTok : upload direct via Content Posting API, si app/token autorisés
- YouTube Shorts : upload direct via YouTube Data API avec refresh token OAuth

Usage GitHub Actions :
python scripts/post_shorts_video.py --video daily_pronos_shorts.mp4 --platforms facebook,youtube

Pour Instagram/Threads, fournissez PUBLIC_VIDEO_URL ou configurez Supabase Storage public :
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_BUCKET
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

GRAPH_VERSION = os.getenv("GRAPH_API_VERSION", "v25.0")
ROOT_DIR = Path.cwd()

DEFAULT_CAPTION = (
    "Voici les pronos du jour ⚽\n"
    "Analyse rapide • 18+ • Joue responsablement.\n\n"
    "#football #pronostic #pronosdujour #mrxpronos"
)
DEFAULT_TITLE = "Pronos du jour - Mr XPRONOS"
DEFAULT_DESCRIPTION = (
    "Voici les pronos du jour Mr XPRONOS. "
    "Analyse rapide, 18+ et joue responsablement."
)


@dataclass
class PublishResult:
    platform: str
    ok: bool
    message: str
    data: Optional[Dict[str, Any]] = None


def log(msg: str) -> None:
    print(msg, flush=True)


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    if value is None:
        return None
    value = str(value).strip()
    return value if value else default


def require_env(names: List[str]) -> Tuple[bool, str]:
    missing = [n for n in names if not env(n)]
    if missing:
        return False, "Variables manquantes: " + ", ".join(missing)
    return True, ""


def read_json_response(resp: requests.Response) -> Dict[str, Any]:
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text[:1000]}


def request_or_raise(method: str, url: str, **kwargs) -> Dict[str, Any]:
    timeout = kwargs.pop("timeout", 180)
    resp = requests.request(method, url, timeout=timeout, **kwargs)
    data = read_json_response(resp)
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code} sur {url}: {data}")
    return data


def absolute_path(path: str | Path) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT_DIR / p
    return p.resolve()


def make_caption(user_caption: Optional[str]) -> str:
    return user_caption or env("POST_CAPTION") or DEFAULT_CAPTION


def make_title(user_title: Optional[str]) -> str:
    return user_title or env("POST_TITLE") or DEFAULT_TITLE


def make_description(user_description: Optional[str]) -> str:
    return user_description or env("POST_DESCRIPTION") or DEFAULT_DESCRIPTION


# =====================================================
# PUBLIC HOSTING OPTIONNEL : SUPABASE STORAGE
# =====================================================
def upload_to_supabase_public(video_path: Path) -> str:
    """
    Upload la vidéo dans un bucket Supabase public et retourne l'URL publique.
    Requis : SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_BUCKET.
    """
    ok, msg = require_env(["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_BUCKET"])
    if not ok:
        raise RuntimeError(msg)

    supabase_url = env("SUPABASE_URL", "").rstrip("/")
    service_key = env("SUPABASE_SERVICE_ROLE_KEY", "")
    bucket = env("SUPABASE_BUCKET", "videos")

    date_part = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    object_name = env("SUPABASE_OBJECT_NAME") or f"shorts/{date_part}/{int(time.time())}-{video_path.name}"
    object_name_q = quote(object_name, safe="/")

    upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{object_name_q}"
    public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{object_name_q}"

    mime = mimetypes.guess_type(str(video_path))[0] or "video/mp4"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
        "Content-Type": mime,
        "x-upsert": "true",
    }

    log(f"☁️ Upload Supabase Storage : {bucket}/{object_name}")
    with open(video_path, "rb") as f:
        resp = requests.post(upload_url, headers=headers, data=f, timeout=600)

    if resp.status_code >= 400:
        raise RuntimeError(f"Erreur upload Supabase HTTP {resp.status_code}: {resp.text[:1000]}")

    log(f"✅ URL publique vidéo : {public_url}")
    return public_url


def resolve_public_url(video_path: Path, explicit_url: Optional[str]) -> Optional[str]:
    if explicit_url:
        return explicit_url
    if env("PUBLIC_VIDEO_URL"):
        return env("PUBLIC_VIDEO_URL")
    # Si Supabase est configuré, on crée automatiquement une URL publique.
    if env("SUPABASE_URL") and env("SUPABASE_SERVICE_ROLE_KEY") and env("SUPABASE_BUCKET"):
        return upload_to_supabase_public(video_path)
    return None


# =====================================================
# FACEBOOK PAGE
# =====================================================
def post_facebook_page(video_path: Path, caption: str) -> PublishResult:
    platform = "facebook"
    ok, msg = require_env(["META_PAGE_ID", "META_PAGE_ACCESS_TOKEN"])
    if not ok:
        return PublishResult(platform, False, msg)

    page_id = env("META_PAGE_ID")
    token = env("META_PAGE_ACCESS_TOKEN")
    url = f"https://graph-video.facebook.com/{GRAPH_VERSION}/{page_id}/videos"

    data = {
        "access_token": token,
        "description": caption,
        "published": "true",
    }

    log("📤 Publication Facebook Page...")
    with open(video_path, "rb") as f:
        files = {"source": (video_path.name, f, "video/mp4")}
        resp = requests.post(url, data=data, files=files, timeout=900)

    payload = read_json_response(resp)
    if resp.status_code >= 400:
        return PublishResult(platform, False, f"HTTP {resp.status_code}: {payload}", payload)

    return PublishResult(platform, True, f"Facebook OK: {payload}", payload)


# =====================================================
# INSTAGRAM REELS
# =====================================================
def wait_instagram_container(container_id: str, token: str, max_wait_sec: int = 300) -> None:
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{container_id}"
    started = time.time()
    while time.time() - started < max_wait_sec:
        data = request_or_raise(
            "GET",
            url,
            params={"fields": "status_code,status", "access_token": token},
            timeout=60,
        )
        status = str(data.get("status_code", "")).upper()
        log(f"⏳ Instagram container {container_id}: {status or data}")
        if status in {"FINISHED", "PUBLISHED"}:
            return
        if status == "ERROR":
            raise RuntimeError(f"Container Instagram en erreur: {data}")
        time.sleep(10)
    raise TimeoutError("Instagram: délai dépassé pendant le traitement du container")


def post_instagram_reel(public_video_url: Optional[str], caption: str) -> PublishResult:
    platform = "instagram"
    ok, msg = require_env(["IG_USER_ID", "META_ACCESS_TOKEN"])
    if not ok:
        return PublishResult(platform, False, msg)
    if not public_video_url:
        return PublishResult(
            platform,
            False,
            "PUBLIC_VIDEO_URL requis pour Instagram Reels, ou configure Supabase Storage public.",
        )

    ig_user_id = env("IG_USER_ID")
    token = env("META_ACCESS_TOKEN")

    log("📤 Création container Instagram Reels...")
    create_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{ig_user_id}/media"
    create_payload = request_or_raise(
        "POST",
        create_url,
        data={
            "media_type": "REELS",
            "video_url": public_video_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": token,
        },
        timeout=180,
    )

    container_id = create_payload.get("id")
    if not container_id:
        return PublishResult(platform, False, f"Container Instagram sans id: {create_payload}", create_payload)

    wait_instagram_container(container_id, token)

    log("📤 Publication Instagram Reels...")
    publish_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{ig_user_id}/media_publish"
    publish_payload = request_or_raise(
        "POST",
        publish_url,
        data={"creation_id": container_id, "access_token": token},
        timeout=180,
    )

    return PublishResult(platform, True, f"Instagram OK: {publish_payload}", publish_payload)


# =====================================================
# THREADS
# =====================================================
def post_threads(public_video_url: Optional[str], caption: str) -> PublishResult:
    platform = "threads"
    ok, msg = require_env(["THREADS_USER_ID", "THREADS_ACCESS_TOKEN"])
    if not ok:
        return PublishResult(platform, False, msg)
    if not public_video_url:
        return PublishResult(
            platform,
            False,
            "PUBLIC_VIDEO_URL requis pour Threads, ou configure Supabase Storage public.",
        )

    user_id = env("THREADS_USER_ID")
    token = env("THREADS_ACCESS_TOKEN")

    log("📤 Création container Threads...")
    create_url = f"https://graph.threads.net/v1.0/{user_id}/threads"
    create_payload = request_or_raise(
        "POST",
        create_url,
        data={
            "media_type": "VIDEO",
            "video_url": public_video_url,
            "text": caption,
            "access_token": token,
        },
        timeout=180,
    )

    creation_id = create_payload.get("id")
    if not creation_id:
        return PublishResult(platform, False, f"Threads container sans id: {create_payload}", create_payload)

    # Petit délai pour laisser Meta traiter la vidéo.
    time.sleep(int(env("THREADS_PUBLISH_DELAY", "20")))

    log("📤 Publication Threads...")
    publish_url = f"https://graph.threads.net/v1.0/{user_id}/threads_publish"
    publish_payload = request_or_raise(
        "POST",
        publish_url,
        data={"creation_id": creation_id, "access_token": token},
        timeout=180,
    )

    return PublishResult(platform, True, f"Threads OK: {publish_payload}", publish_payload)


# =====================================================
# TIKTOK CONTENT POSTING API
# =====================================================
def post_tiktok(video_path: Path, caption: str) -> PublishResult:
    platform = "tiktok"
    ok, msg = require_env(["TIKTOK_ACCESS_TOKEN"])
    if not ok:
        return PublishResult(platform, False, msg)

    token = env("TIKTOK_ACCESS_TOKEN")
    privacy = env("TIKTOK_PRIVACY_LEVEL", "PUBLIC_TO_EVERYONE")
    size = video_path.stat().st_size
    # Upload en 1 chunk pour les shorts. Si la vidéo grossit, on pourra le découper.
    chunk_size = size

    init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    payload = {
        "post_info": {
            "title": caption[:2200],
            "privacy_level": privacy,
            "disable_duet": env("TIKTOK_DISABLE_DUET", "false").lower() == "true",
            "disable_comment": env("TIKTOK_DISABLE_COMMENT", "false").lower() == "true",
            "disable_stitch": env("TIKTOK_DISABLE_STITCH", "false").lower() == "true",
            "video_cover_timestamp_ms": int(env("TIKTOK_COVER_TIMESTAMP_MS", "1000")),
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": chunk_size,
            "total_chunk_count": 1,
        },
    }

    log("📤 Initialisation upload TikTok...")
    init_resp = requests.post(init_url, headers=headers, json=payload, timeout=180)
    init_payload = read_json_response(init_resp)
    if init_resp.status_code >= 400 or init_payload.get("error", {}).get("code") not in (None, "ok"):
        return PublishResult(platform, False, f"TikTok init erreur: {init_payload}", init_payload)

    data = init_payload.get("data") or {}
    upload_url = data.get("upload_url")
    publish_id = data.get("publish_id")
    if not upload_url or not publish_id:
        return PublishResult(platform, False, f"TikTok réponse incomplète: {init_payload}", init_payload)

    log("📤 Upload vidéo TikTok...")
    with open(video_path, "rb") as f:
        upload_headers = {
            "Content-Type": "video/mp4",
            "Content-Length": str(size),
            "Content-Range": f"bytes 0-{size - 1}/{size}",
        }
        upload_resp = requests.put(upload_url, headers=upload_headers, data=f, timeout=900)

    if upload_resp.status_code >= 400:
        return PublishResult(platform, False, f"TikTok upload HTTP {upload_resp.status_code}: {upload_resp.text[:1000]}")

    return PublishResult(platform, True, f"TikTok upload OK, publish_id={publish_id}", {"publish_id": publish_id})


# =====================================================
# YOUTUBE SHORTS
# =====================================================
def post_youtube(video_path: Path, title: str, description: str) -> PublishResult:
    platform = "youtube"
    ok, msg = require_env(["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"])
    if not ok:
        return PublishResult(platform, False, msg)

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from googleapiclient.errors import HttpError
    except Exception as e:
        return PublishResult(
            platform,
            False,
            "Dépendances YouTube manquantes. Installe: google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2. "
            f"Détail: {e}",
        )

    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = Credentials(
        token=None,
        refresh_token=env("YOUTUBE_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=env("YOUTUBE_CLIENT_ID"),
        client_secret=env("YOUTUBE_CLIENT_SECRET"),
        scopes=scopes,
    )

    try:
        creds.refresh(Request())
        youtube = build("youtube", "v3", credentials=creds)
        tags = [x.strip() for x in env("YOUTUBE_TAGS", "football,pronostic,MrXPRONOS,shorts").split(",") if x.strip()]
        privacy = env("YOUTUBE_PRIVACY_STATUS", "public")
        category_id = env("YOUTUBE_CATEGORY_ID", "17")  # Sports

        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        log("📤 Upload YouTube Shorts...")
        response = None
        while response is None:
            _status, response = request.next_chunk()
            if _status:
                log(f"   YouTube upload: {int(_status.progress() * 100)}%")

        video_id = response.get("id")
        return PublishResult(platform, True, f"YouTube OK: https://youtube.com/watch?v={video_id}", response)

    except Exception as e:
        # HttpError est converti en message lisible.
        return PublishResult(platform, False, f"YouTube erreur: {e}")


# =====================================================
# RUNNER
# =====================================================
def parse_platforms(raw: str) -> List[str]:
    if not raw:
        return []
    allowed = {"facebook", "instagram", "threads", "tiktok", "youtube"}
    out = []
    for item in raw.split(","):
        p = item.strip().lower()
        if not p:
            continue
        if p not in allowed:
            raise ValueError(f"Plateforme inconnue: {p}. Autorisées: {sorted(allowed)}")
        if p not in out:
            out.append(p)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Publier la vidéo Mr XPRONOS sur les réseaux sociaux")
    parser.add_argument("--video", default="daily_pronos_shorts.mp4", help="Chemin du fichier MP4")
    parser.add_argument("--platforms", default=env("POST_PLATFORMS", "facebook,instagram,threads,tiktok,youtube"))
    parser.add_argument("--caption", default=None, help="Texte/caption à publier")
    parser.add_argument("--title", default=None, help="Titre YouTube")
    parser.add_argument("--description", default=None, help="Description YouTube")
    parser.add_argument("--public-url", default=None, help="URL publique du MP4 pour Instagram/Threads")
    parser.add_argument("--dry-run", action="store_true", help="Affiche ce qui serait publié sans appeler les API")
    parser.add_argument("--strict", action="store_true", help="Échoue si une plateforme est ignorée ou en erreur")
    args = parser.parse_args()

    video_path = absolute_path(args.video)
    if not video_path.exists():
        log(f"❌ Vidéo introuvable: {video_path}")
        return 1

    platforms = parse_platforms(args.platforms)
    caption = make_caption(args.caption)
    title = make_title(args.title)
    description = make_description(args.description)

    log("=" * 70)
    log("🚀 Publication réseaux sociaux - Mr XPRONOS")
    log(f"Vidéo      : {video_path}")
    log(f"Plateformes: {', '.join(platforms) if platforms else '(aucune)'}")
    log(f"Titre      : {title}")
    log("Caption    :")
    log(caption)
    log("=" * 70)

    if args.dry_run:
        log("🧪 DRY RUN : aucun post ne sera envoyé.")
        return 0

    public_url: Optional[str] = None
    if any(p in platforms for p in ("instagram", "threads")):
        try:
            public_url = resolve_public_url(video_path, args.public_url)
        except Exception as e:
            public_url = None
            log(f"⚠️ Impossible de créer/récupérer l'URL publique: {e}")

    dispatch: Dict[str, Callable[[], PublishResult]] = {
        "facebook": lambda: post_facebook_page(video_path, caption),
        "instagram": lambda: post_instagram_reel(public_url, caption),
        "threads": lambda: post_threads(public_url, caption),
        "tiktok": lambda: post_tiktok(video_path, caption),
        "youtube": lambda: post_youtube(video_path, title, description),
    }

    results: List[PublishResult] = []
    for platform in platforms:
        try:
            result = dispatch[platform]()
        except Exception as e:
            result = PublishResult(platform, False, f"Exception: {e}")
        results.append(result)
        icon = "✅" if result.ok else "❌"
        log(f"{icon} {platform.upper()} : {result.message}")
        if args.strict and not result.ok:
            break

    report_path = ROOT_DIR / "social_post_results.json"
    report = [r.__dict__ for r in results]
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"🧾 Rapport écrit: {report_path}")

    failed = [r for r in results if not r.ok]
    if failed and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
