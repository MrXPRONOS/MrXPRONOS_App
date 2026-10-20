#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a vertical short from the exact BSD V2 Telegram coupon renderer.

Important:
- Coupon PNGs are produced by bsd_v2_card.render().
- The bookmaker strip is added by bsd_v2_telegram_banner.attach_banner().
- Coupon pixels are NOT redesigned or cropped.
- The complete coupon may be uniformly scaled down to fit social safe zones;
  width and height always use the same scale factor, so there is no stretching.
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
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bsd"))

from bsd.bsd_h2h import _utc
from bsd.bsd_v2_card import render as render_telegram_coupon
from bsd.bsd_v2_estimated_odds import valid_standalone_prediction
from bsd.bsd_v2_telegram_banner import attach_banner
from bsd.bsd_v2_telegram import partner_pack
from shorts_video_fx import LOOP_TAIL_SECONDS, card_zoom, scene_duration, synthesize_soundtrack

UTC = timezone.utc
W, H = 1080, 1920
MAX_MATCHES = 5
VALID_STATUS = {"notstarted", "upcoming"}
LEDGER_DEFAULT = "shorts_video_coupon"
DAY_SPLIT_HOUR_UTC = 15
VIDEO_BACKGROUND = ROOT / "assets" / "images" / "mrxpronos-video-background.jpg"
HEADER_LOGO = ROOT / "assets" / "images" / "mrxpronos-logo-maquette.png"


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
    # All verified BSD V2 odds providers are eligible. Preserve the existing
    # source/estimated flag checks and never admit a model observation
    # or an unverified price as if it were a bookmaker coupon.
    if not valid_standalone_prediction(pick):
        return False
    return True


def _canonical_event_id(value):
    """Normalize ledger refs like evening:bsd:123 or bsd:123 to 123."""
    text = str(value or "").strip()
    if ":bsd:" in text:
        return text.rsplit(":bsd:", 1)[1]
    if text.startswith("bsd:"):
        return text[4:]
    return text.rsplit(":", 1)[-1]


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
        raise RuntimeError("SUPABASE_URL et une clé serveur obligatoires pour éviter les doublons en production")
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
    return {_canonical_event_id(row.get("ref_id")) for row in rows if row.get("ref_id")}


def _daily_video_already_claimed(now):
    """Vérifie le verrou quotidien, qui empêche une deuxième vidéo."""
    base=(os.getenv("SUPABASE_URL") or "").rstrip("/")
    key=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or ""
    if not base or not key:
        raise RuntimeError("Supabase obligatoire pour limiter les vidéos à une par jour")
    res=requests.get(base+"/rest/v1/telegram_sent",
        params={"select":"ref_id","kind":"eq.shorts_video_daily_guard",
                "ref_id":"eq.one_daily_video",
                "ref_date":"eq."+now.date().isoformat(),"limit":"1"},
        headers=_ledger_headers(key),timeout=30)
    res.raise_for_status()
    rows=res.json()
    if not isinstance(rows,list):
        raise RuntimeError("Registre des vidéos quotidiennes invalide")
    return bool(rows)


def select_matches(data, slot: str, now: datetime, *, limit=MAX_MATCHES, ledger_kind=LEDGER_DEFAULT):
    matches = data.get("matches") or []
    if not isinstance(matches, list):
        raise RuntimeError("Liste de matchs BSD invalide")

    if slot == "preview":
        candidates = [m for m in matches if _valid_match(m, now)]
        # Video priority: strongest available price first, then kickoff.
        candidates.sort(key=lambda m: (
            -float((m.get("prediction") or {}).get("odds") or 0),
            _event_dt(m),
            str(m.get("id") or ""),
        ))
        return candidates[:limit], "preview"

    target = _target_date(slot, now)
    if _daily_video_already_claimed(now):
        print("SHORTS_DAILY_ALREADY_SENT",now.date().isoformat())
        return [],target
    already = _already_sent_ids(target, ledger_kind)

    candidates = []
    for match in matches:
        if not _valid_match(match, now):
            continue
        dt = _event_dt(match)
        if dt.date().isoformat() != target:
            continue
        event_id = _canonical_event_id(match.get("id") or match.get("source_event_id") or "")
        if event_id in already:
            continue

        # Le mode matin couvre TOUS les matchs restants du jour :
        # aucune coupure à 15 h pour ne pas perdre les rencontres matinales.
        # Les anciens déclenchements manuels evening restent compatibles,
        # mais le verrou journalier interdit deux vidéos le même jour.
        candidates.append(match)

    # Within the target day, prefer higher odds first; kickoff breaks ties.
    candidates.sort(key=lambda m: (
        -float((m.get("prediction") or {}).get("odds") or 0),
        _event_dt(m),
        str(m.get("id") or ""),
    ))
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


def _eased_x(t, duration, card_width, enter=0.34, leave=0.34):
    """Enter from right, hold centered, then exit left."""
    def smooth(v):
        v = max(0.0, min(1.0, v))
        return v * v * (3.0 - 2.0 * v)

    center_x = int((W - card_width) / 2)
    if t < enter:
        p = smooth(t / enter)
        return int(W + (center_x - W) * p)
    if t > duration - leave:
        p = smooth((t - (duration - leave)) / leave)
        return int(center_x + (-card_width - center_x) * p)
    return center_x


def _fit_card_size(source_w: int, source_h: int, max_w: int = 940, max_h: int = 1210):
    """Fit inside the social-safe coupon area with one uniform scale factor."""
    if source_w <= 0 or source_h <= 0:
        raise RuntimeError("Dimensions coupon invalides")
    scale = min(max_w / source_w, max_h / source_h, 1.0)
    return int(round(source_w * scale)), int(round(source_h * scale))


def _make_card_shadow(card_width: int, card_height: int, out: Path):
    """External shadow/glow only. The Telegram coupon pixels stay untouched."""
    pad = 54
    layer = Image.new("RGBA", (card_width + pad * 2, card_height + pad * 2), (0, 0, 0, 0))

    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (pad, pad + 12, pad + card_width, pad + 12 + card_height),
        radius=26,
        fill=(0, 0, 0, 165),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    layer = Image.alpha_composite(layer, shadow)

    glow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle(
        (pad - 3, pad - 3, pad + card_width + 3, pad + card_height + 3),
        radius=26,
        outline=(39, 133, 255, 105),
        width=8,
    )
    glow = glow.filter(ImageFilter.GaussianBlur(14))
    layer = Image.alpha_composite(layer, glow)
    layer.save(out)
    return pad


def _overlay_png(index: int, total: int, out: Path):
    """Minimal safe-zone UI; Telegram coupon artwork remains untouched."""
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # Brand header kept away from the right-side social UI column.
    if HEADER_LOGO.is_file():
        try:
            logo = Image.open(HEADER_LOGO).convert("RGBA")
            logo.thumbnail((160, 54), Image.Resampling.LANCZOS)
            canvas.alpha_composite(logo, (48, 26))
        except Exception:
            pass
    title = "PRONOS DU JOUR"
    hf = _font(26, True)
    hb = draw.textbbox((0, 0), title, font=hf)
    safe_right = 900
    draw.text((safe_right - (hb[2] - hb[0]), 38), title, font=hf, fill=(244, 249, 255, 245))

    # Counter + one progress system only: old dots/hint were deliberately removed.
    counter = f"{index + 1:02d} / {total:02d}"
    cf = _font(28, True)
    draw.text((92, 1315), counter, font=cf, fill=(248, 251, 255, 255))
    progress_ratio = (index + 1) / max(total, 1)
    bar_x1, bar_y1, bar_x2, bar_y2 = 285, 1331, 900, 1341
    draw.rounded_rectangle((bar_x1, bar_y1, bar_x2, bar_y2), radius=5, fill=(255, 255, 255, 48))
    fill_x = bar_x1 + int((bar_x2 - bar_x1) * progress_ratio)
    draw.rounded_rectangle((bar_x1, bar_y1, fill_x, bar_y2), radius=5, fill=(76, 174, 255, 245))

    # Minimal Telegram CTA: no large box, safely above bottom platform controls.
    draw.line((92, 1390, 900, 1390), fill=(255, 255, 255, 38), width=2)
    icon_x, icon_y, icon_r = 92, 1422, 25
    draw.ellipse((icon_x, icon_y, icon_x + icon_r * 2, icon_y + icon_r * 2),
                 fill=(48, 163, 255, 230))
    draw.polygon(
        [(icon_x + 13, icon_y + 24), (icon_x + 39, icon_y + 13), (icon_x + 29, icon_y + 38)],
        fill=(255, 255, 255, 255),
    )
    draw.text((158, 1413), "PLUS DE PRONOSTICS", font=_font(22, False),
              fill=(193, 210, 226, 245))
    draw.text((158, 1444), "@mr_xpronos", font=_font(31, True),
              fill=(247, 251, 255, 255))

    canvas.save(out)


def _card_position(t: float, duration: float, width: int, height: int, y: int):
    zoom = card_zoom(t, duration)
    x = _eased_x(t, duration, width) - int((width * zoom - width) / 2)
    yy = y - int((height * zoom - height) / 2)
    return x, yy


def _shadow_position(t: float, duration: float, card_width: int, card_height: int, pad: int, y: int):
    zoom = card_zoom(t, duration)
    sw = card_width + 2 * pad
    sh = card_height + 2 * pad
    x = _eased_x(t, duration, card_width) - pad - int((sw * zoom - sw) / 2)
    yy = y - pad - int((sh * zoom - sh) / 2)
    return x, yy


def _animated_background(ImageClip, duration: float, *, results: bool = False):
    """Slow parallax movement over the premium background."""
    bg_w = 1120
    bg_h = int(round(H * bg_w / W))
    clip = ImageClip(str(VIDEO_BACKGROUND)).resize(newsize=(bg_w, bg_h)).set_duration(duration)
    phase = 0.7 if results else 0.0
    return clip.set_position(
        lambda t: (
            int((W - bg_w) / 2 + 8 * math.sin((t + phase) * 0.55)),
            int((H - bg_h) / 2 + 6 * math.cos((t + phase) * 0.42)),
        )
    )


def build_video(cards, output: Path, work_dir: Path):
    if not hasattr(Image, "ANTIALIAS"):
        Image.ANTIALIAS = Image.Resampling.LANCZOS

    from moviepy.editor import AudioFileClip, CompositeVideoClip, ImageClip, concatenate_videoclips

    total = len(cards)
    if not total:
        raise RuntimeError("Aucune carte à monter")
    if not VIDEO_BACKGROUND.is_file():
        raise RuntimeError(f"Fond vidéo introuvable: {VIDEO_BACKGROUND}")

    durations = [scene_duration(total, idx) for idx in range(total)]
    coupon_y = 105
    target_width = 940
    scenes = []
    last_overlay_path = None

    for idx, card_path in enumerate(cards):
        duration = durations[idx]
        with Image.open(card_path) as image:
            source_w, source_h = image.size
        card_width, card_height = _fit_card_size(source_w, source_h, max_w=target_width, max_h=1210)
        if coupon_y + card_height >= 1360:
            raise RuntimeError("Coupon Telegram trop haut pour la zone vidéo sûre")

        overlay_path = work_dir / f"overlay_{idx+1:02d}.png"
        _overlay_png(idx, total, overlay_path)
        last_overlay_path = overlay_path
        shadow_path = work_dir / f"shadow_{idx+1:02d}.png"
        shadow_pad = _make_card_shadow(card_width, card_height, shadow_path)

        background = _animated_background(ImageClip, duration)
        shadow = (
            ImageClip(str(shadow_path), transparent=True)
            .resize(lambda t, d=duration: card_zoom(t, d))
            .set_duration(duration)
            .set_position(
                lambda t, d=duration, cw=card_width, ch=card_height, p=shadow_pad:
                    _shadow_position(t, d, cw, ch, p, coupon_y)
            )
        )
        coupon = (
            ImageClip(str(card_path))
            .resize(width=card_width)
            .resize(lambda t, d=duration: card_zoom(t, d))
            .set_duration(duration)
            .set_position(
                lambda t, d=duration, cw=card_width, ch=card_height:
                    _card_position(t, d, cw, ch, coupon_y)
            )
        )

        # Decorative next-card sliver; no critical information is placed in the right UI zone.
        next_preview = None
        if idx + 1 < total:
            next_path = cards[idx + 1]
            with Image.open(next_path) as next_image:
                next_w, _ = _fit_card_size(next_image.width, next_image.height,
                                           max_w=target_width, max_h=1210)
            preview_w = int(round(next_w * 0.94))
            next_preview = (
                ImageClip(str(next_path))
                .resize(width=preview_w)
                .set_opacity(0.50)
                .set_duration(duration)
                .set_position((W - 62, coupon_y + 44))
            )

        overlay = ImageClip(str(overlay_path), transparent=True).set_duration(duration)
        layers = [background, shadow, coupon]
        if next_preview is not None:
            layers.append(next_preview)
        layers.append(overlay)
        scenes.append(CompositeVideoClip(layers, size=(W, H)).set_duration(duration))

    # A tiny background-only tail makes the automatic social-media loop feel intentional.
    tail_bg = _animated_background(ImageClip, LOOP_TAIL_SECONDS)
    tail_overlay = ImageClip(str(last_overlay_path), transparent=True).set_duration(LOOP_TAIL_SECONDS)
    scenes.append(CompositeVideoClip([tail_bg, tail_overlay], size=(W, H))
                  .set_duration(LOOP_TAIL_SECONDS))

    final = concatenate_videoclips(scenes, method="compose")

    # Locally generated ambience + whoosh + landing impacts; no external audio/license.
    soundtrack_path = work_dir / "soundtrack.wav"
    synthesize_soundtrack(durations, soundtrack_path, results=False)
    audio = AudioFileClip(str(soundtrack_path)).set_duration(final.duration)
    final = final.set_audio(audio)

    output.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(output),
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        bitrate="5000k",
        threads=4,
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
        verbose=False,
        logger="bar",
    )
    try:
        audio.close()
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
        "window": (
            f"before_{DAY_SPLIT_HOUR_UTC:02d}00_utc"
            if args.slot == "evening"
            else f"from_{DAY_SPLIT_HOUR_UTC:02d}00_utc"
            if args.slot == "morning"
            else "preview"
        ),
        "matches": manifest_matches,
    }
    (work_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("SHORTS_COUPON_VIDEO_READY", json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
