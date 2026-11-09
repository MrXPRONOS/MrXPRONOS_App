#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent 20:00 social edition of the Dixon-Coles ten-score grid.

The original 2x5 renderer and all existing Telegram/Shorts workflows are
untouched. Never publish partial, demonstration or unverified forecasts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DIXON = ROOT / "dixon-coles"
LOME = ZoneInfo("Africa/Lome")
SIZE = (1080, 1920)
# The original grid's last card is at y=1145/1280; after scaling it ends at
# ~1362, so this panel never covers a score, club crest or team name.
VIDEO_BOX = (90, 25, 840, 1494)
CTA_BOX = (75, 1398, 905, 1567)
SAFE_RIGHT = 920
SAFE_BOTTOM = 1570
CTA_LINES = (
    "Rejoins-nous sur Telegram pour plus de coupons",
    "Compte Telegram : Mr XPRONOS",
    "@mr_xpronos",
)


def check_layout() -> None:
    x, y, width, height = VIDEO_BOX
    left, top, right, bottom = CTA_BOX
    if (width * 16 != height * 9
            or not (0 <= x and 0 <= y and x + width <= SAFE_RIGHT)
            or not (left >= 60 and right <= SAFE_RIGHT and bottom <= SAFE_BOTTOM)
            or not (top > y + (1145 / 1280) * height + 25)):
        raise ValueError("Zone Telegram non sûre ou recouvrant les 10 matchs")
    if len(CTA_LINES) != 3 or not CTA_LINES[-1].startswith("@"):
        raise ValueError("Texte Telegram incomplet")


def font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ):
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.truetype("DejaVuSans.ttf", size)


def fitted_font(draw: ImageDraw.ImageDraw, text: str, maximum: int, start: int) -> ImageFont.FreeTypeFont:
    for size in range(start, 19, -1):
        face = font(size)
        box = draw.textbbox((0, 0), text, font=face)
        if box[2] - box[0] <= maximum:
            return face
    raise ValueError("Texte trop long pour la zone sûre")


def make_cta(output: Path) -> None:
    """Transparent overlay; typography is fully within conservative Shorts/Reels safe area."""
    check_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    d = ImageDraw.Draw(image, "RGBA")
    d.rounded_rectangle(CTA_BOX, radius=28,
                        fill=(7, 23, 44, 244), outline=(53, 229, 207, 190), width=3)
    d.rounded_rectangle((94, 1413, 105, 1550), radius=5, fill=(53, 229, 207, 255))
    positions = (1432, 1483, 1534)
    sizes = (31, 30, 39)
    colors = ((247, 251, 253, 255), (192, 211, 226, 255), (53, 229, 207, 255))
    for line, y, size, color in zip(CTA_LINES, positions, sizes, colors):
        face = fitted_font(d, line, CTA_BOX[2] - CTA_BOX[0] - 105, size)
        d.text((500, y), line, font=face, fill=color, anchor="mm")
    image.save(output, format="PNG")


def verify_ready(report: dict, storyboard: dict, target: str) -> None:
    if (report.get("date_local_africa_lome") != target
            or storyboard.get("date_local_africa_lome") != target
            or report.get("status") != "READY"
            or report.get("ready_for_video") is not True
            or storyboard.get("ready_for_video") is not True
            or report.get("selected_count") != 10
            or storyboard.get("selected_count") != 10
            or len(report.get("selected") or []) != 10
            or len(storyboard.get("clips") or []) != 10):
        raise ValueError("Pas de vidéo sans 10 affiches réelles prêtes, datées et vérifiées")
    identities = [str(row.get("id") or "") for row in report["selected"]]
    if not all(identities) or len(set(identities)) != 10:
        raise ValueError("Dix identifiants réels et distincts obligatoires")
    if storyboard.get("status") != "READY":
        raise ValueError("Storyboard non validé")


def encode_social(source: Path, overlay: Path, destination: Path) -> None:
    """Never touch the original score-reveal animation or soundtrack."""
    x, y, width, height = VIDEO_BOX
    vf = (f"[0:v]scale={width}:{height}:flags=lanczos,"
          f"pad=1080:1920:{x}:{y}:color=0x071122[center];"
          "[center][1:v]overlay=0:0:shortest=1:format=auto,"
          "format=yuv420p[final]")
    args = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source), "-loop", "1", "-i", str(overlay),
        "-filter_complex", vf, "-map", "[final]", "-map", "0:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-c:a", "copy", "-movflags", "+faststart", "-shortest",
        str(destination),
    ]
    subprocess.run(args, check=True, timeout=420, capture_output=True, text=True)
    metadata = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "json", str(destination)],
        text=True, timeout=30))
    streams = metadata.get("streams") or []
    if not streams or (streams[0].get("width"), streams[0].get("height")) != SIZE:
        raise ValueError("Le MP4 doit être exactement en 1080 x 1920")
    if not 100_000 <= destination.stat().st_size <= 24 * 1024 * 1024:
        raise ValueError("Vidéo absente, trop petite ou dépassant 24 Mio")


def build(*, day: str, source: str, output_dir: Path) -> int:
    check_layout()
    now = datetime.now(LOME)
    target = (now.date() + timedelta(days=1)).isoformat() if day == "tomorrow" else day
    # Prevent accidentally publishing historical footage as tomorrow's forecasts.
    if target != (now.date() + timedelta(days=1)).isoformat():
        raise ValueError("Le pipeline social n'accepte que les matchs de demain à Lomé")
    work = output_dir / target
    work.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(DIXON))
    from dcscore.daily import main as daily_main
    from dcscore.video_grid import render

    outcome = daily_main([
        "--day", target, "--source", source, "--count", "10",
        "--min-team", "4", "--min-importance", "70",
        "--max-staleness-days", "35",
        "--output-dir", str(output_dir / "model"),
    ])
    if outcome:
        raise RuntimeError("Calcul Dixon-Coles interrompu")
    base = output_dir / "model" / target
    report = json.loads((base / "predictions.json").read_text(encoding="utf-8"))
    storyboard = json.loads((base / "video_payload.json").read_text(encoding="utf-8"))
    if not report.get("ready_for_video"):
        (work / "skipped.json").write_text(json.dumps({
            "target": target, "status": report.get("status"),
            "selected": report.get("selected_count"),
            "reasons": report.get("reasons_not_ready", []),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("SOCIAL_EXACT_SCORES_SKIPPED", target, report.get("selected_count"), flush=True)
        return 3

    verify_ready(report, storyboard, target)
    raw_video = work / "grid_original.mp4"
    final_video = work / "social_exact_scores_10.mp4"
    overlay = work / "cta_safe_zone.png"
    render(storyboard, raw_video, fullhd=False, asset_root=str(DIXON))
    make_cta(overlay)
    encode_social(raw_video, overlay, final_video)
    data = {
        "schema": "mrx-dixon-coles-social-top10-v1",
        "target": target,
        "count": 10,
        "source": report.get("source_mode"),
        "status": "READY",
        "ready_for_video": True,
        "video": str(final_video),
        "sha256": hashlib.sha256(final_video.read_bytes()).hexdigest(),
        "telegram_username": "@mr_xpronos",
        "social_safe_zone": {"right": SAFE_RIGHT, "bottom": SAFE_BOTTOM},
    }
    (work / "social_manifest.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SOCIAL_EXACT_SCORES_READY", json.dumps({
        "target": target, "video": str(final_video), "count": 10,
        "bytes": final_video.stat().st_size}, ensure_ascii=False), flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default="tomorrow")
    parser.add_argument("--source", default="espn",
                        choices=["auto", "espn", "football-data", "openfootball", "openligadb"])
    parser.add_argument("--output-dir", type=Path, default=Path("social_exact_scores_out"))
    parser.add_argument("--cta-preview", type=Path,
                        help="Génère uniquement le calque CTA pour vérification hors réseau")
    args = parser.parse_args()
    if args.cta_preview:
        make_cta(args.cta_preview)
        return 0
    return build(day=args.day, source=args.source, output_dir=args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
