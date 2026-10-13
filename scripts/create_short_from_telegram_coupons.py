#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a vertical short from the exact BSD V2 Telegram coupon renderer.

Important:
- Coupon PNGs are produced by bsd_v2_card.render().
- The bookmaker strip is added by bsd_v2_telegram_banner.attach_banner().
- Coupon pixels are NOT redesigned, cropped or rescaled in the video.
- Only the surrounding vertical canvas, staggered movement, progress hint and
  Telegram CTA belong to this video compositor.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bsd"))

from bsd.bsd_h2h import _utc
from bsd.bsd_v2_card import render as render_telegram_coupon
from bsd.bsd_v2_estimated_odds import valid_standalone_prediction
from bsd.bsd_v2_telegram_banner import attach_banner
from bsd.bsd_v2_telegram import partner_pack

UTC = timezone.utc
W, H = 1080, 1920
MAX_MATCHES = 5
VALID_STATUS = {"notstarted", "upcoming"}
LEDGER_DEFAULT = "shorts_video_coupon"


def _font(size: int, bold: bool = False):
    candidates = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    )
    for item in candidates:
        if Path(item).is_file():
            return ImageFont.truetype(item, size)
    return ImageFont.load_default()


def _load_data(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("source") != "bsd" or data.get("model_version") != "bsd-v2-isolated":
        raise RuntimeError("data.json n'est pas une publication BSD V2")
    return data


def _event_dt(match):
    try:
        return _utc(str(match.get("event_date") or ""))
    except (ValueError, TypeError):
        return None


def _target_date(slot: str, now: datetime):
    if slot == "evening":
        return (now.date() + timedelta(days=1)).isoformat()
    if slot == "morning":
        return now.date().isoformat()
    return None


def _valid_match(match, now: datetime, *, require_future=True):
    if not isinstance(match, dict) or match.get("source") != "bsd":
        return False
    if str(match.get("status") or "").lower() not in VALID_STATUS:
        return False
    if match.get("is_finished") is True:
        return False
    if match.get("recommendation_eligible") is not True:
        return False

    # No category discrimination: SIMPLE, PRO and VIP are all eligible.
    category = str(match.get("category") or "").strip().casefold()
    if category not in {"simple", "pro", "vip"}:
        return False

    dt = _event_dt(match)
    if dt is None:
        return False
    if require_future and dt <= now:
        return False

    pick = match.get("prediction") or {}
    if not isinstance(pick, dict):
        return False
    if pick.get("recommendation_eligible") is not True:
        return False
    try:
        odds = float(pick.get("odds"))
    except (TypeError, ValueError):
        return False
    # Video selection follows the generated recommendation pool, not the
    # hourly Telegram >1.50 delivery threshold. The canonical coupon renderer
    # itself accepts verified/estimated BSD prices from 1.20 upward.
    if not math.isfinite(odds) or not (1.20 <= odds <= 100):
        return False
    if str(pick.get("odds_source") or "") not in {
        "bsd_consensus", "bsd_bookmaker", "mrxpronos_model"
    }:
        return False
    return True


def _ledger_headers(key):
    return {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    }


def _already_sent_ids(target_date: str, kind: str):
    base = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or ""
    if not base or not key:
        return set()
    response = requests.get(
        base + "/rest/v1/telegram_sent",
        params={
            "select": "ref_id",
            "kind": "eq." + kind,
            "ref_date": "eq." + target_date,
            "limit": "100",
        },
        headers=_ledger_headers(key),
        timeout=30,
    )
    response.raise_for_status()
    rows = response.json() or []
    return {str(row.get("ref_id") or "").split(":")[-1] for row in rows if row.get("ref_id")}


def select_matches(data, slot: str, now: datetime, *, limit=MAX_MATCHES, ledger_kind=LEDGER_DEFAULT):
    matches = data.get("matches") or []
    if not isinstance(matches, list):
        raise RuntimeError("Liste de matchs BSD invalide")

    if slot == "preview":
        candidates = [m for m in matches if _valid_match(m, now)]
        # Preview uses the nearest future matches, irrespective of calendar day.
        candidates.sort(key=lambda m: (_event_dt(m), str(m.get("id") or "")))
        return candidates[:limit], "preview"

    target = _target_date(slot, now)
    already = _already_sent_ids(target, ledger_kind)

    candidates = []
    for match in matches:
        if not _valid_match(match, now):
            continue
        dt = _event_dt(match)
        if dt.date().isoformat() != target:
            continue
        event_id = str(match.get("id") or match.get("source_event_id") or "")
        if event_id in already:
            continue
        candidates.append(match)

    # Evening naturally prioritizes the earliest matches of tomorrow.
    # Morning takes whatever eligible matches remain unsent later that day.
    candidates.sort(key=lambda m: (_event_dt(m), str(m.get("id") or "")))
    return candidates[:limit], target


def generate_exact_cards(matches, out_dir: Path, now: datetime):
    out_dir.mkdir(parents=True, exist_ok=True)
    pack = partner_pack(now)
    cards = []
    for index, match in enumerate(matches, 1):
        path = out_dir / f"coupon_{index:02d}.png"
        render_telegram_coupon(match, path, now=now, session=requests.Session())
        attach_banner(path, pack=pack)
        cards.append(path)
        print("EXACT_TELEGRAM_COUPON", index, path)
    return cards, pack


def _eased_x(t, duration, enter=0.34, leave=0.34):
    """Enter from right, hold, then exit left."""
    def smooth(v):
        v = max(0.0, min(1.0, v))
        return v * v * (3.0 - 2.0 * v)

    if t < enter:
        p = smooth(t / enter)
        return int(W * (1.0 - p))
    if t > duration - leave:
        p = smooth((t - (duration - leave)) / leave)
        return int(-W * p)
    return 0


def _overlay_png(index: int, total: int, out: Path):
    """CTA + tiny progress cue only; coupon artwork itself remains untouched."""
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # Bottom CTA.
    draw.rounded_rectangle((92, 1607, 988, 1752), radius=36, fill=(5, 18, 31, 230),
                           outline=(255, 255, 255, 34), width=2)
    title = "REJOINS-NOUS SUR TELEGRAM"
    sub = "Plus de pronostics sur @mr_xpronos"
    tf = _font(34, True)
    sf = _font(25, False)
    tw = draw.textbbox((0, 0), title, font=tf)[2]
    sw = draw.textbbox((0, 0), sub, font=sf)[2]
    draw.text(((W - tw) / 2, 1640), title, font=tf, fill=(255, 255, 255, 255))
    draw.text(((W - sw) / 2, 1692), sub, font=sf, fill=(186, 207, 224, 255))

    # Small visual cue that more coupons follow.
    y = 1810
    if total > 1:
        hint = "D’AUTRES PRONOSTICS SUIVENT  ›"
        hf = _font(23, True)
        hw = draw.textbbox((0, 0), hint, font=hf)[2]
        draw.text(((W - hw) / 2, y - 45), hint, font=hf, fill=(198, 213, 225, 235))

    gap = 24
    radius = 8
    total_width = total * radius * 2 + (total - 1) * gap
    x = (W - total_width) / 2
    for i in range(total):
        fill = (255, 255, 255, 255) if i == index else (255, 255, 255, 85)
        draw.ellipse((x, y, x + radius * 2, y + radius * 2), fill=fill)
        x += radius * 2 + gap

    canvas.save(out)


def build_video(cards, output: Path, work_dir: Path):
    # Pillow >= 10 compatibility for MoviePy 1.x resize internals, although the
    # coupon images themselves are never resized here.
    if not hasattr(Image, "ANTIALIAS"):
        Image.ANTIALIAS = Image.Resampling.LANCZOS

    from moviepy.editor import ColorClip, CompositeVideoClip, ImageClip, concatenate_videoclips

    total = len(cards)
    if not total:
        raise RuntimeError("Aucune carte à monter")

    per_card = 3.0 if total <= 2 else 2.6
    coupon_y = 150
    scenes = []

    for idx, card_path in enumerate(cards):
        with Image.open(card_path) as image:
            if image.width != W:
                raise RuntimeError(f"Coupon inattendu: largeur {image.width}, attendu {W}")
            coupon_h = image.height
        if coupon_y + coupon_h >= 1580:
            raise RuntimeError("Coupon Telegram trop haut pour le gabarit vidéo")

        overlay_path = work_dir / f"overlay_{idx+1:02d}.png"
        _overlay_png(idx, total, overlay_path)

        background = ColorClip((W, H), color=(7, 15, 24)).set_duration(per_card)
        coupon = (
            ImageClip(str(card_path))
            .set_duration(per_card)
            .set_position(lambda t, d=per_card: (_eased_x(t, d), coupon_y))
        )
        overlay = ImageClip(str(overlay_path), transparent=True).set_duration(per_card)
        scene = CompositeVideoClip([background, coupon, overlay], size=(W, H)).set_duration(per_card)
        scenes.append(scene)

    # Cards follow each other directly; no intro and no outro.
    final = concatenate_videoclips(scenes, method="compose")
    output.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(output),
        fps=30,
        codec="libx264",
        audio=False,
        preset="medium",
        bitrate="5000k",
        threads=4,
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
        verbose=False,
        logger="bar",
    )
    try:
        final.close()
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data.json")
    parser.add_argument("--slot", choices=("evening", "morning", "preview"), default="preview")
    parser.add_argument("--max", type=int, default=MAX_MATCHES)
    parser.add_argument("--out", default="daily_pronos_coupon_short.mp4")
    parser.add_argument("--work-dir", default="telegram_out/video_coupon_short")
    parser.add_argument("--ledger-kind", default=os.getenv("SHORTS_LEDGER_KIND", LEDGER_DEFAULT))
    args = parser.parse_args()

    now = datetime.now(UTC)
    data = _load_data(Path(args.data))
    max_count = max(1, min(MAX_MATCHES, int(args.max)))
    selected, target = select_matches(
        data, args.slot, now, limit=max_count, ledger_kind=args.ledger_kind
    )

    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    if not selected:
        manifest = {
            "slot": args.slot,
            "target": target,
            "count": 0,
            "generated_at": now.isoformat(),
            "matches": [],
        }
        (work_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("SHORTS_NO_MATCHES", json.dumps(manifest, ensure_ascii=False))
        return 3

    cards, pack = generate_exact_cards(selected, work_dir / "cards", now)
    build_video(cards, Path(args.out), work_dir)

    manifest_matches = []
    for match in selected:
        pick = match.get("prediction") or {}
        manifest_matches.append({
            "id": str(match.get("id") or match.get("source_event_id") or ""),
            "date": str(match.get("date") or _event_dt(match).date().isoformat()),
            "event_date": str(match.get("event_date") or ""),
            "category": str(match.get("category") or ""),
            "home_team": str(match.get("home_team") or ""),
            "away_team": str(match.get("away_team") or ""),
            "selection_key": str(pick.get("selection_key") or ""),
            "odds": pick.get("odds"),
        })

    manifest = {
        "slot": args.slot,
        "target": target,
        "count": len(selected),
        "bookmaker_pack": pack,
        "generated_at": now.isoformat(),
        "ledger_kind": args.ledger_kind,
        "matches": manifest_matches,
    }
    (work_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("SHORTS_COUPON_VIDEO_READY", json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
