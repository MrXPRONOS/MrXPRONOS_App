#!/usr/bin/env python3
"""Prepare a *reviewed, non-betting* football video for Snapchat Spotlight.

This program NEVER calls Snapchat, stores credentials, or claims publication.
Human review of the actual video is required before running it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import requests

SUPABASE_HOST = "nhwafcpndlufzzxexikh.supabase.co"
ALLOWED_PREFIX = "/storage/v1/object/public/videos/snapchat/"
MAX_DOWNLOAD_BYTES = 150 * 1024 * 1024
REVIEW_CONFIRMATION = "football-only-reviewed-no-betting"
BLOCKED_METADATA = re.compile(
    r"(?:1xbet|betwinner|bookmaker|pari[s]? sportif[s]?|casino|"
    r"code promo|bonus de pari|sportsbook|pronostic[s]? de pari|"
    r"cote[s]? (?:de pari|boost[eé]e[s]?)|https?://|"
    r"t\.me/|bit\.ly/)",
    re.IGNORECASE,
)


class PreparationError(Exception):
    pass


def run_command(args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=180)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise PreparationError(f"Échec du traitement média : {type(exc).__name__}") from None


def video_metadata(path: Path) -> dict:
    probe = run_command(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                         "-of", "json", str(path)])
    try:
        info = json.loads(probe.stdout)
        video = next(s for s in info["streams"] if s.get("codec_type") == "video")
        duration = float((info.get("format") or {}).get("duration") or 0)
        return {
            "width": int(video["width"]), "height": int(video["height"]),
            "duration": duration, "codec": video.get("codec_name"),
            "has_audio": any(s.get("codec_type") == "audio" for s in info["streams"]),
        }
    except (KeyError, ValueError, StopIteration, TypeError) as exc:
        raise PreparationError("Métadonnées vidéo absentes ou incorrectes") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def check_title(title: str) -> str:
    title = title.strip()
    if not 3 <= len(title) <= 130:
        raise PreparationError("Le titre doit contenir entre 3 et 130 caractères")
    if BLOCKED_METADATA.search(title):
        raise PreparationError("Titre à revoir : promotion de paris, bookmaker ou lien interdit")
    return title


def parse_source_url(value: str) -> str:
    target = urlsplit(value.strip())
    path = unquote(target.path)
    if (target.scheme != "https" or target.hostname != SUPABASE_HOST
            or target.port is not None or target.username or target.password
            or target.query or target.fragment or not path.startswith(ALLOWED_PREFIX)
            or ".." in path or "\\" in path
            or not path.lower().endswith(".mp4")
            or len(value) > 1500):
        raise PreparationError("URL invalide : utiliser une URL publique Supabase dans videos/snapchat/*.mp4")
    return value.strip()


def download_video(source_url: str, dest: Path) -> None:
    url = parse_source_url(source_url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(url, timeout=(10, 90), stream=True, allow_redirects=False) as resp:
            if resp.status_code != 200:
                raise PreparationError(f"Source vidéo indisponible (HTTP {resp.status_code})")
            if int(resp.headers.get("Content-Length", "0") or 0) > MAX_DOWNLOAD_BYTES:
                raise PreparationError("Vidéo source trop volumineuse")
            size = 0
            with dest.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=256 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > MAX_DOWNLOAD_BYTES:
                        raise PreparationError("La vidéo dépasse 150 Mo")
                    f.write(chunk)
            if size < 1024:
                raise PreparationError("Vidéo source vide ou trop courte en octets")
    except requests.RequestException as exc:
        raise PreparationError("Téléchargement impossible : " + type(exc).__name__) from None


def prepare(src: Path, out_dir: Path, title: str, review_confirmation: str) -> dict:
    if review_confirmation != REVIEW_CONFIRMATION:
        raise PreparationError("Revue humaine obligatoire : confirmer football-only-reviewed-no-betting")
    title = check_title(title)
    if not src.is_file() or src.stat().st_size < 1024:
        raise PreparationError("Fichier vidéo source manquant ou vide")
    if src.resolve().is_relative_to(out_dir.resolve()):
        raise PreparationError("Le fichier d'entrée doit être hors du dossier de sortie")

    metadata = video_metadata(src)
    if not 5 <= metadata["duration"] <= 59.8:
        raise PreparationError("Snapchat Spotlight : durée source entre 5 et 59,8 secondes requise")
    if metadata["width"] < 540 or metadata["height"] < 960:
        raise PreparationError("Snapchat Spotlight : source verticale au moins 540x960 requise")
    aspect = metadata["width"] / metadata["height"]
    if not 0.50 <= aspect <= 0.70:
        raise PreparationError("Source non verticale : fournir une vidéo 9:16 sans déformation")
    if src.stat().st_size > MAX_DOWNLOAD_BYTES:
        raise PreparationError("Source trop volumineuse")

    out_dir.mkdir(parents=True, exist_ok=True)
    result = out_dir / "mrxpronos_snapchat_spotlight.mp4"
    filters = ("scale=1080:1920:force_original_aspect_ratio=decrease,"
               "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
               "setsar=1,fps=30,format=yuv420p")
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
           "-i", str(src), "-map", "0:v:0", "-map", "0:a:0?",
           "-vf", filters, "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "23", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
           str(result)]
    run_command(cmd)
    ready = video_metadata(result)
    if (ready["width"], ready["height"], ready["codec"]) != (1080, 1920, "h264"):
        raise PreparationError("Échec de validation du fichier MP4 final")
    if not 5 <= ready["duration"] <= 60:
        raise PreparationError("Durée du fichier final hors limites Snapchat")

    caption = f"{title}\n#Football #ActuFoot #MrXPRONOS"
    manifest = {
        "status": "READY_FOR_HUMAN_UPLOAD_ONLY",
        "published": False,
        "platform": "snapchat_spotlight",
        "title": title,
        "caption": caption,
        "format": {"container": "mp4", "codec": ready["codec"],
                   "width": ready["width"], "height": ready["height"],
                   "duration_sec": round(ready["duration"], 2)},
        "video_filename": result.name,
        "video_sha256": sha256_file(result),
        "review": ("L'opérateur déclare avoir inspecté toute la vidéo et exclu "
                   "les marques de bookmakers, cotes, coupons et redirections vers les paris."),
        "upload_url": "https://profile.snapchat.com/",
        "note": "Le fichier est prêt. Il n'a pas été publié automatiquement.",
    }
    (out_dir / "snapchat_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "LIRE_AVANT_PUBLICATION.txt").write_text(
        "MR XPRONOS — SNAPCHAT SPOTLIGHT\n\n"
        "1. Inspecter le MP4 final pour vérifier l'absence de liens, de cotes, "
        "de codes promo et de logos de sites de paris.\n"
        "2. Ouvrir https://profile.snapchat.com/ et se connecter au profil public.\n"
        "3. Charger mrxpronos_snapchat_spotlight.mp4 puis sélectionner Spotlight Snaps.\n"
        "4. Ajouter la description proposée dans snapchat_manifest.json.\n"
        "5. Accepter les conditions, puis publier ou programmer depuis l'interface Snapchat.\n"
        "6. Vérifier l'état de modération et les vues dans les Insights du profil.\n\n"
        "ATTENTION : GitHub n'a effectué AUCUNE publication Snapchat.\n",
        encoding="utf-8"
    )
    return manifest


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--video", type=Path)
    p.add_argument("--source-url", default="")
    p.add_argument("--out-dir", type=Path, default=Path("snapchat_ready"))
    p.add_argument("--title", required=True)
    p.add_argument("--review-confirmation", default="")
    args = p.parse_args()
    if bool(args.video) == bool(args.source_url):
        print("::error::Donner exactement --video ou --source-url", file=sys.stderr)
        return 2
    try:
        src = args.video
        if args.source_url:
            src = Path("snapchat_input/source.mp4")
            download_video(args.source_url, src)
        result = prepare(src, args.out_dir, args.title, args.review_confirmation)
        print("SNAPCHAT_PACKAGE_READY", json.dumps(
            {"status": result["status"], "seconds": result["format"]["duration_sec"],
             "video_sha256": result["video_sha256"][:16]},
            ensure_ascii=False), flush=True)
    except PreparationError as exc:
        print("::error::" + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
