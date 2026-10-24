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
- Bluesky : upload MP4 natif, anti-doublon Supabase, même campagne que les autres plateformes

Usage GitHub Actions :
python scripts/post_shorts_video.py --video daily_pronos_shorts.mp4 --platforms facebook,youtube

Pour Instagram/Threads, fournissez PUBLIC_VIDEO_URL ou configurez Supabase Storage public :
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_BUCKET
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
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
    """Return an externally readable MP4 URL; never silently fall back to Supabase."""
    if explicit_url:
        return explicit_url
    if env("PUBLIC_VIDEO_URL"):
        return env("PUBLIC_VIDEO_URL")
    from neon_public_media import upload_public_media
    stamp = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    digest = hashlib.sha256(video_path.read_bytes()).hexdigest()[:24]
    key = f"shorts/{stamp}/{digest}.mp4"
    return upload_public_media(video_path, key)


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

    media_id=payload.get("id") if isinstance(payload,dict) else None
    return PublishResult(platform, bool(media_id),
        f"Facebook {'OK' if media_id else 'sans identifiant de publication'}: {payload}",payload)


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

    media_id=publish_payload.get("id") if isinstance(publish_payload,dict) else None
    return PublishResult(platform, bool(media_id),
        f"Instagram {'OK' if media_id else 'sans identifiant de publication'}: {publish_payload}",publish_payload)


# =====================================================
# THREADS
# =====================================================
def wait_threads_container(container_id: str, token: str, max_wait_sec: int = 300) -> None:
    """Wait for Threads to finish processing a video, never publish an invalid container."""
    url = f"https://graph.threads.net/v1.0/{container_id}"
    deadline = time.monotonic() + max_wait_sec
    while time.monotonic() < deadline:
        payload = request_or_raise(
            "GET", url,
            params={"fields": "status,error_message", "access_token": token},
            timeout=60,
        )
        status = str(payload.get("status") or "").upper()
        log(f"⏳ Threads container {container_id}: {status or 'UNKNOWN'}")
        if status == "FINISHED":
            return
        if status in {"ERROR", "EXPIRED", "PUBLISHED"}:
            reason = str(payload.get("error_message") or "")[:160]
            raise RuntimeError(f"Threads container {status}. {reason}")
        if status != "IN_PROGRESS":
            raise RuntimeError(f"Statut du container Threads inattendu: {status}")
        time.sleep(min(10, max(0, deadline - time.monotonic())))
    raise TimeoutError("Threads: container vidéo pas prêt avant expiration du délai")


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

    # La vidéo doit avoir le statut FINISHED avant publication. Un délai fixe
    # de 20 secondes n'est pas fiable pour le traitement média chez Meta.
    wait_threads_container(creation_id, token)

    log("📤 Publication Threads...")
    publish_url = f"https://graph.threads.net/v1.0/{user_id}/threads_publish"
    publish_payload = request_or_raise(
        "POST",
        publish_url,
        data={"creation_id": creation_id, "access_token": token},
        timeout=180,
    )

    media_id=publish_payload.get("id") if isinstance(publish_payload,dict) else None
    return PublishResult(platform, bool(media_id),
        f"Threads {'OK' if media_id else 'sans identifiant de publication'}: {publish_payload}",publish_payload)


# =====================================================
# TIKTOK CONTENT POSTING API
# =====================================================
def tiktok_api_response(response: requests.Response) -> tuple[Dict[str, Any], Optional[str]]:
    """Parse TikTok API reply; never expose access tokens or returned upload URLs."""
    try:
        data = response.json()
    except ValueError:
        return {}, f"HTTP {response.status_code}, réponse non JSON"
    error = data.get("error") or {}
    code = str(error.get("code") or "ok") if isinstance(error, dict) else str(error)
    if response.status_code >= 400 or code not in ("ok", "0"):
        return {}, f"HTTP {response.status_code}, code {code[:90]}"
    return data, None


def post_tiktok(video_path: Path, caption: str) -> PublishResult:
    platform = "tiktok"
    # TikTok Direct Post requires app audit, creator-facing metadata/consent UX,
    # and compliant content. Never auto-post sports betting coupons.
    if env("TIKTOK_DIRECT_POST_ENABLED", "false").lower() != "true":
        return PublishResult(platform, False,
            "Publication désactivée: valider TikTok Direct Post, le consentement "
            "de chaque créateur et la conformité des contenus avant activation.")
    if env("TIKTOK_PER_VIDEO_CONSENT", "false").lower() != "true":
        return PublishResult(platform, False, "Consentement explicite du créateur requis pour cette vidéo.")
    ok, msg = require_env(["TIKTOK_ACCESS_TOKEN"])
    if not ok:
        return PublishResult(platform, False, msg)

    token = env("TIKTOK_ACCESS_TOKEN")
    privacy = env("TIKTOK_PRIVACY_LEVEL")
    if not privacy:
        return PublishResult(platform, False, "Le créateur doit choisir explicitement TIKTOK_PRIVACY_LEVEL.")
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json; charset=UTF-8"}

    creator_info_url = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
    try:
        info_resp = requests.post(creator_info_url, headers=headers, json={}, timeout=45)
    except requests.RequestException as exc:
        return PublishResult(platform, False, "Creator info indisponible: " + type(exc).__name__)
    info, error = tiktok_api_response(info_resp)
    if error:
        return PublishResult(platform, False, "TikTok creator_info: " + error)
    creator = info.get("data") or {}
    options = creator.get("privacy_level_options") or []
    if privacy not in options:
        return PublishResult(platform, False, "Confidentialité non autorisée pour ce créateur: "
                             + ", ".join(options))

    try:
        size = video_path.stat().st_size
    except OSError:
        return PublishResult(platform, False, "Vidéo absente ou inaccessible")
    if not 0 < size <= 64 * 1024 * 1024:
        return PublishResult(platform, False, "Vidéo hors limites pour upload TikTok en un seul chunk.")

    # TikTok requires video duration <= max_video_post_duration_sec from creator_info.
    import subprocess
    try:
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "default=nokey=1:noprint_wrappers=1", str(video_path)],
                               capture_output=True, text=True, timeout=25, check=True)
        duration = float(probe.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return PublishResult(platform, False, "Durée vidéo impossible à vérifier avec ffprobe.")
    allowed_duration = creator.get("max_video_post_duration_sec")
    if not isinstance(allowed_duration, (int, float)) or duration > allowed_duration:
        return PublishResult(platform, False, f"Durée vidéo {duration:.1f}s hors limite TikTok.")

    payload = {
        "post_info": {
            "title": caption[:2200],
            "privacy_level": privacy,
            "disable_duet": creator.get("duet_disabled") or env("TIKTOK_DISABLE_DUET", "true") != "false",
            "disable_comment": creator.get("comment_disabled") or env("TIKTOK_DISABLE_COMMENT", "true") != "false",
            "disable_stitch": creator.get("stitch_disabled") or env("TIKTOK_DISABLE_STITCH", "true") != "false",
            "video_cover_timestamp_ms": min(1000, int(duration * 1000)),
        },
        "source_info": {
            "source": "FILE_UPLOAD", "video_size": size,
            "chunk_size": size, "total_chunk_count": 1,
        },
    }

    try:
        init_resp = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            headers=headers, json=payload, timeout=90)
    except requests.RequestException as exc:
        return PublishResult(platform, False, "TikTok init réseau: " + type(exc).__name__)
    init, error = tiktok_api_response(init_resp)
    if error:
        return PublishResult(platform, False, "TikTok init: " + error)
    from urllib.parse import urlsplit
    data = init.get("data") or {}
    upload_url, publish_id = data.get("upload_url"), data.get("publish_id")
    parsed = urlsplit(str(upload_url or ""))
    if parsed.scheme != "https" or parsed.hostname != "open-upload.tiktokapis.com":
        return PublishResult(platform, False, "TikTok upload URL absente ou inattendue.")
    if not publish_id:
        return PublishResult(platform, False, "TikTok publish_id absent.")

    log("📤 Upload TikTok (créateur et confidentialité vérifiés)...")
    try:
        with open(video_path, "rb") as f:
            upload_resp = requests.put(upload_url,
                headers={"Content-Type": "video/mp4", "Content-Length": str(size),
                         "Content-Range": f"bytes 0-{size-1}/{size}"},
                data=f, timeout=300)
    except requests.RequestException as exc:
        return PublishResult(platform, False,
                             "TikTok upload ambigu, vérifier publish_id avant tout nouvel essai: "
                             + type(exc).__name__, {"publish_id": publish_id})
    if upload_resp.status_code >= 400:
        return PublishResult(platform, False,
            "TikTok upload HTTP " + str(upload_resp.status_code), {"publish_id": publish_id})

    # Upload success is NOT publication success. TikTok processes and moderates later.
    status_url = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
    for _ in range(8):
        time.sleep(10)
        try:
            response = requests.post(status_url, headers=headers,
                                     json={"publish_id": publish_id}, timeout=30)
        except requests.RequestException:
            continue
        info, status_error = tiktok_api_response(response)
        if status_error:
            return PublishResult(platform, False,
                "TikTok statut: " + status_error, {"publish_id": publish_id})
        record = info.get("data") or {}
        status = str(record.get("status") or "").upper()
        if status == "PUBLISH_COMPLETE":
            return PublishResult(platform, True, "TikTok publication confirmée",
                                 {"publish_id": publish_id, "status": status,
                                  "post_ids": record.get("publicaly_available_post_id") or []})
        if status == "FAILED":
            return PublishResult(platform, False,
                "TikTok publication refusée: " + str(record.get("fail_reason") or "unknown")[:100],
                {"publish_id": publish_id, "status": status})
    return PublishResult(platform, False,
        "TikTok upload terminé mais publication encore en cours. "
        "Consulter status/fetch avant toute nouvelle tentative.",
        {"publish_id": publish_id, "status": "PROCESSING"})


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
        return PublishResult(platform, bool(video_id), 
            f"YouTube OK: https://youtube.com/watch?v={video_id}" if video_id
            else "YouTube: réponse sans identifiant vidéo", response)

    except Exception as e:
        # HttpError est converti en message lisible.
        return PublishResult(platform, False, f"YouTube erreur: {e}")


# =====================================================
# BLUESKY - native video in the same social publishing batch
# =====================================================
def post_bluesky_video(video_path: Path, caption: str, title: str) -> PublishResult:
    platform = "bluesky"
    handle = (env("BLUESKY_HANDLE") or "").lstrip("@").lower()
    password = env("BLUESKY_APP_PASSWORD")
    if not all((handle, password)):
        return PublishResult(platform, False, "Identifiants Bluesky absents")

    size = video_path.stat().st_size
    if not 100_000 <= size <= 50_000_000 or video_path.suffix.lower() != ".mp4":
        return PublishResult(platform, False, "Vidéo MP4 absente ou hors limites Bluesky (100 Ko à 50 Mo)")

    # Content hash guarantees a retry cannot upload the same MP4 twice in one day.
    # Different validation clips from the same GitHub run get different keys.
    data = video_path.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    ref_date = datetime.now(timezone.utc).date().isoformat()
    ident = ("bsd_v2_bluesky_video", handle + ":sha256:" + sha256, ref_date)

    from atproto import Client
    from d1_publication_ledger import D1Ledger

    client = Client()
    client.login(handle, password)  # Verify auth BEFORE creating a dedup reservation.
    ledger = D1Ledger()
    if not ledger.claim(*ident):
        # The existing claim could represent a prior successful upload OR an
        # ambiguous timeout: do not claim unverified publication success.
        return PublishResult(platform, False,
                             "Vidéo déjà réservée sur Bluesky (anti-doublon). Vérifier le post précédent.",
                             {"status": "already_claimed"})

    upload_started = False
    try:
        text = caption.replace("\\n", "\n").strip()[:280]
        upload_started = True
        response = client.send_video(
            text=text,
            video=data,
            video_alt=(title or "Vidéo de football Mr XPRONOS")[:900],
            langs=["fr"],
        )
        uri = str(response.uri)
        if not uri.startswith("at://"):
            raise RuntimeError("Réponse Bluesky sans URI de publication")
    except Exception:
        # Keep reservation after an ambiguous network/upload failure: never
        # automatically send a second video that might already exist.
        if not upload_started:
            ledger.release(*ident)
        raise

    ledger.mark(*ident)
    url = "https://bsky.app/profile/" + handle + "/post/" + uri.rsplit("/", 1)[-1]
    return PublishResult(platform, True, "Bluesky OK: " + url,
                         {"id": uri, "url": url, "status": "published"})


# =====================================================
# RUNNER
# =====================================================
def parse_platforms(raw: str) -> List[str]:
    if not raw:
        return []
    allowed = {"facebook", "instagram", "threads", "tiktok", "youtube", "bluesky"}
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
    parser.add_argument("--platforms", default=env("POST_PLATFORMS", "facebook,youtube,instagram,threads,bluesky"))
    parser.add_argument("--caption", default=None, help="Texte/caption à publier")
    parser.add_argument("--title", default=None, help="Titre YouTube")
    parser.add_argument("--description", default=None, help="Description YouTube")
    parser.add_argument("--public-url", default=None, help="URL publique du MP4 pour Instagram/Threads")
    parser.add_argument("--dry-run", action="store_true", help="Affiche ce qui serait publié sans appeler les API")
    parser.add_argument("--strict", action="store_true", help="Échoue immédiatement à la première erreur")
    parser.add_argument("--require-all", action="store_true", help="Tente toutes les plateformes, puis échoue si l'une manque ou échoue")
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
        "bluesky": lambda: post_bluesky_video(video_path, caption, title),
    }

    def attempt(platform: str) -> PublishResult:
        try:
            return dispatch[platform]()
        except Exception as e:
            return PublishResult(platform, False, f"Exception: {type(e).__name__}: {e}")

    results: List[PublishResult] = []
    if args.strict:
        # Explicit strict mode keeps the historical stop-on-first-error behavior.
        for platform in platforms:
            result = attempt(platform)
            results.append(result)
            log(f"{'✅' if result.ok else '❌'} {platform.upper()} : {result.message}")
            if not result.ok:
                break
    elif platforms:
        # Start uploads together once the common public URL is ready.
        # Preserve requested platform order in the final report.
        with ThreadPoolExecutor(max_workers=min(len(platforms), 6)) as executor:
            futures = {platform: executor.submit(attempt, platform) for platform in platforms}
            for platform in platforms:
                result = futures[platform].result()
                results.append(result)
                log(f"{'✅' if result.ok else '❌'} {platform.upper()} : {result.message}")

    report_path = ROOT_DIR / "social_post_results.json"
    report = [r.__dict__ for r in results]
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"🧾 Rapport écrit: {report_path}")

    failed = [r for r in results if not r.ok]
    if (failed or len(results)!=len(platforms)) and (args.strict or args.require_all):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
