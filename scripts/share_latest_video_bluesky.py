#!/usr/bin/env python3
"""Share a verified, already-produced Mr XPRONOS Short natively to Bluesky.

A GitHub Actions run supplies the video artifact and manifest.
Never fabricate a video, expose credentials, or change existing social posts.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import requests
from d1_publication_ledger import D1Ledger


TABLE = "telegram_sent"
SITE = "https://mrxpronos.github.io/MrXPRONOS_App/pronos.html"


def metadata(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    target = str(raw.get("target", "")).strip()
    if not target:
        raise ValueError("Date cible absente du manifeste")
    datetime.strptime(target, "%Y-%m-%d")
    count = int(raw.get("count", 0))
    if count < 1 or count > 15:
        raise ValueError("Nombre de sélections invalide")
    return {"target": target, "count": count, "slot": str(raw.get("slot", ""))}


def build_copy(item: dict) -> str:
    label = "Pronostics de la soirée" if item["slot"] == "morning" else "Première vague des pronostics de demain"
    day = datetime.strptime(item["target"], "%Y-%m-%d").strftime("%d/%m/%Y")
    return (
        f"⚽ {label} | Mr XPRONOS\n"
        f"📅 {day} · {item['count']} sélections football\n"
        f"🔗 {SITE}\n"
        "🔞 18+ · Joue responsablement.\n"
        "#football #pronosdujour #mrxpronos"
    )


def headers(key: str) -> dict:
    return {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "Prefer": "return=representation,resolution=ignore-duplicates",
    }


def claim(session: requests.Session, base: str, key: str, ident: tuple[str, str, str]) -> bool:
    kind, ref_id, ref_date = ident
    response = session.post(
        base.rstrip("/") + "/rest/v1/" + TABLE,
        params={"on_conflict": "kind,ref_id,ref_date"},
        headers=headers(key),
        json={"kind": kind, "ref_id": ref_id, "ref_date": ref_date, "validation_sent": False},
        timeout=35,
    )
    response.raise_for_status()
    result = response.json()
    return isinstance(result, list) and bool(result)


def release(session: requests.Session, base: str, key: str, ident: tuple[str, str, str]) -> None:
    kind, ref_id, ref_date = ident
    response = session.delete(
        base.rstrip("/") + "/rest/v1/" + TABLE,
        params={"kind": "eq." + kind, "ref_id": "eq." + ref_id, "ref_date": "eq." + ref_date},
        headers=headers(key),
        timeout=35,
    )
    response.raise_for_status()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    item = metadata(args.manifest)
    if not args.video.is_file():
        raise FileNotFoundError(f"Vidéo introuvable: {args.video}")
    length = args.video.stat().st_size
    if length < 100_000 or length > 50_000_000:
        raise ValueError(f"Fichier vidéo de taille non prise en charge : {length} bytes")
    if args.video.suffix.lower() != ".mp4":
        raise ValueError("La vidéo doit être un fichier MP4")
    caption = build_copy(item)
    if args.dry_run:
        print("BLUESKY_VIDEO_DRY_RUN", json.dumps({
            "source_run_id": args.source_run_id, "bytes": length,
            "caption": caption}, ensure_ascii=False))
        return 0

    handle = os.getenv("BLUESKY_HANDLE", "").strip().lstrip("@").lower()
    password = os.getenv("BLUESKY_APP_PASSWORD", "").strip()
    if not all((handle, password)):
        raise RuntimeError("Secrets Bluesky non configurés")

    from atproto import Client
    client = Client()
    client.login(handle, password)  # Authenticate before any dedup claim.

    ident = ("bsd_v2_bluesky_video", handle + ":shorts:" + args.source_run_id, item["target"])
    ledger = D1Ledger()
    claimed = ledger.claim(*ident)
    if not claimed:
        print("BLUESKY_VIDEO_ALREADY_POSTED", args.source_run_id)
        return 0

    upload_started = False
    try:
        video = args.video.read_bytes()
        upload_started = True
        # The high-level SDK adds the video embed and uploads the video bytes.
        response = client.send_video(
            text=caption, video=video,
            video_alt=f"Vidéo Mr XPRONOS : {item['count']} pronostics football du {item['target']}",
            langs=["fr"],
        )
    except Exception:
        # Once the upload began a timeout can be ambiguous; retain the claim to
        # prevent unintended duplicate posting. For local preflight failures,
        # release the claim so another workflow attempt is possible.
        if not upload_started:
            ledger.release(*ident)
        raise

    ledger.mark(*ident)
    uri = str(response.uri)
    key = uri.rsplit("/", 1)[-1]
    url = f"https://bsky.app/profile/{handle}/post/{key}"
    print("BLUESKY_VIDEO_PUBLISHED", url)
    output = os.getenv("GITHUB_STEP_SUMMARY")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"### Vidéo Bluesky publiée\n\n{url}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
