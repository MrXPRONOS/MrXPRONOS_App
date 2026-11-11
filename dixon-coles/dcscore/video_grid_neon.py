"""Mr XPRONOS neon-stadium edition: independent 2x5 Dixon-Coles score reveal.

Uses user-provided background and transparent PNG title / Telegram banner.
All real match data and authentic crests are validated by the original engine.
No changes to the original video_grid renderer or Telegram workflows.
"""
from __future__ import annotations

import argparse
from datetime import date
from functools import lru_cache
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageOps

from .video_render import (
    W, H, FPS, LogoCache, font, split_names, soundtrack, validate_payload, ease,
)

HERE = Path(__file__).resolve().parents[1]
ASSETS = HERE / "assets" / "social_neon"
STADIUM = ASSETS / "stadium.png"
TITLE = ASSETS / "title.png"
TELEGRAM = ASSETS / "telegram.png"

CARD_X = (23, 368)
CARD_W = 329
CARD_Y0 = 249  # +14px: clear space below the title
CARD_H = 120   # preserve two-line club labels, while gaining footer room
CARD_GAP_Y = 9

# Keep the Telegram artwork centred on the 2x5 grid and off social UI controls.
TELEGRAM_WIDTH = 500
TELEGRAM_X = (W - TELEGRAM_WIDTH) // 2
TELEGRAM_Y = 918

# Compact score badges must stop above all club names (first line at y+87).
SCORE_CENTER_Y = 51
SCORE_HALF_WIDTH = 47
SCORE_HALF_HEIGHT = 21

# Uniform scale for artwork only. Stadium remains 720x1280 untouched.
ARTWORK_SCALE = 0.86
ARTWORK_X = 6
ARTWORK_Y = 36
FIRST_REVEAL = .62
REVEAL_INTERVAL = 1.22
REVEAL_EFFECT = .42
FINAL_HOLD = 3.2
GOLD = (255, 207, 74, 255)
WHITE = (246, 251, 255, 255)
PALE = (184, 208, 230, 255)
BLUE = (30, 181, 253, 255)
MONTHS = ("JAN", "FÉV", "MAR", "AVR", "MAI", "JUN", "JUL", "AOÛ", "SEP", "OCT", "NOV", "DÉC")


def positions(n=10):
    if not 1 <= n <= 10:
        raise ValueError("L'édition sociale accepte 1 à 10 affiches vérifiées")
    slots = [(CARD_X[i % 2], CARD_Y0 + (i // 2) * (CARD_H + CARD_GAP_Y)) for i in range(n)]
    if n % 2:
        # Center an isolated last match; never leave the last row lopsided.
        slots[-1] = (round((CARD_X[0] + CARD_X[1]) / 2), slots[-1][1])
    return slots


def check_assets():
    for path in (STADIUM, TITLE, TELEGRAM):
        if not path.is_file():
            raise FileNotFoundError(f"Asset neon absent: {path}")
    with Image.open(TITLE) as title, Image.open(TELEGRAM) as telegram:
        if title.mode != "RGBA" or telegram.mode != "RGBA":
            raise ValueError("Les bandeaux doivent être des PNG transparents")


def _overlay_fit(frame: Image.Image, path: Path, *, width: int, y: int, x: int = 0):
    with Image.open(path) as raw:
        tile = raw.convert("RGBA")
        h = round(tile.height * width / tile.width)
        tile = tile.resize((width, h), Image.Resampling.LANCZOS)
    frame.alpha_composite(tile, (x, y))
    return h


def _draw_calendar_date(frame: Image.Image, target: date):
    # The approved PNG artwork embeds "11 NOV". Replace only the printed
    # date on its white calendar page; crown, tabs and neon design remain.
    draw = ImageDraw.Draw(frame, "RGBA")
    # Coordinates apply to the 704px-wide title PNG positioned at x=8, y=0.
    draw.polygon(((82, 153), (157, 147), (169, 199), (91, 215)),
                 fill=(249, 249, 250, 255))
    draw.text((123, 164), str(target.day), font=font(25, True),
              fill=(4, 9, 15, 255), anchor="mm")
    draw.text((126, 193), MONTHS[target.month - 1], font=font(17, True),
              fill=(4, 9, 15, 255), anchor="mm")


def _team_label(draw, x, y, name):
    """Readable one- or two-line team names on a score card."""
    name = name.upper().replace(" FOOTBALL CLUB", " FC")
    words = name.split()
    lines = [name]
    if len(words) > 1 and len(name) > 12:
        cuts = [(" ".join(words[:i]), " ".join(words[i:])) for i in range(1, len(words))]
        lines = list(min(cuts, key=lambda pair: max(
            draw.textbbox((0, 0), s, font=font(17, True))[2] for s in pair)))
    ys = (y + 94,) if len(lines) == 1 else (y + 87, y + 106)
    for text, line_y in zip(lines, ys):
        sz = 17
        while sz > 11 and draw.textbbox((0, 0), text, font=font(sz, True))[2] > 140:
            sz -= 1
        while len(text) > 2 and draw.textbbox((0, 0), text, font=font(sz, True))[2] > 140:
            text = text[:-2] + "…"
        draw.text((x, line_y), text, font=font(sz, True), fill=WHITE, anchor="mm")


@lru_cache(maxsize=1)
def stadium_background():
    with Image.open(STADIUM) as stadium:
        return ImageOps.fit(stadium.convert("RGB"), (W, H),
                            method=Image.Resampling.LANCZOS,
                            centering=(.52, .50)).convert("RGBA")


def fit_artwork(artwork):
    reduced = artwork.resize((round(W * ARTWORK_SCALE), round(H * ARTWORK_SCALE)),
                             Image.Resampling.LANCZOS)
    frame = stadium_background().copy()
    frame.alpha_composite(reduced, (ARTWORK_X, ARTWORK_Y))
    return frame


def base_frame(payload, clips, logos, preview=False):
    check_assets()
    target = date.fromisoformat(payload["date_local_africa_lome"])
    # No global dark rounded rectangle: cards keep their own dark backing.
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _overlay_fit(base, TITLE, width=704, y=0, x=8)
    _draw_calendar_date(base, target)
    _overlay_fit(base, TELEGRAM, width=TELEGRAM_WIDTH, y=TELEGRAM_Y, x=TELEGRAM_X)

    d = ImageDraw.Draw(base, "RGBA")
    for (x, y), clip, pair in zip(positions(len(clips)), clips, logos):
        # Gold-blue lighting and premium card border, still 2 columns x 5 rows.
        d.rounded_rectangle((x-2, y-2, x+CARD_W+2, y+CARD_H+2),
                            radius=17, fill=(4, 17, 41, 235),
                            outline=(255, 193, 52, 235), width=3)
        d.rounded_rectangle((x+2, y+2, x+CARD_W-2, y+CARD_H-2),
                            radius=14, outline=(30, 173, 240, 165), width=2)
        d.line((x+19, y+4, x+CARD_W-19, y+4), fill=(255, 240, 169, 165), width=2)
        home, away = split_names(clip["headline"])
        for cx, crest in ((x+77, pair[0]), (x+CARD_W-77, pair[1])):
            with_img = crest.image.copy()
            with_img.thumbnail((60, 60), Image.Resampling.LANCZOS)
            base.alpha_composite(with_img, (round(cx-with_img.width/2), y+10))
        _team_label(d, x+76, y, home)
        _team_label(d, x+CARD_W-76, y, away)
    # Below four rows the small count label fits; with nine fixtures it
    # would cover the fifth-row club names, so leave it to the caption.
    if len(clips) <= 8:
        d.rounded_rectangle((270, 860, 450, 890), radius=9,
                            fill=(6, 20, 39, 238), outline=GOLD, width=2)
        d.text((360, 875), f"{len(clips)} MATCHS EN VIDÉO",
               font=font(15, True), fill=GOLD, anchor="mm")
    if preview:
        d.rounded_rectangle((140, 1138, 580, 1172), radius=10, fill=(6, 20, 39, 240))
        d.text((360, 1155), "DÉMONSTRATION · NON OFFICIEL",
               font=font(16, True), fill=GOLD, anchor="mm")
    return base


def _heavy_score(draw, center, label, color, size):
    # Prefer Inter Display Black; strengthen any font fallback with a 1px stroke.
    max_width = SCORE_HALF_WIDTH * 2 - 12
    while size > 14:
        bounds = draw.textbbox((0, 0), label, font=font(size, True), stroke_width=1)
        if bounds[2] - bounds[0] <= max_width:
            break
        size -= 1
    draw.text(center, label, font=font(size, True), fill=color, anchor="mm",
              stroke_width=1, stroke_fill=color)


def draw_score(frame, clip, x, y, elapsed):
    d = ImageDraw.Draw(frame, "RGBA")
    sx = x + CARD_W // 2
    sy = y + SCORE_CENTER_Y
    box = (sx - SCORE_HALF_WIDTH, sy - SCORE_HALF_HEIGHT,
           sx + SCORE_HALF_WIDTH, sy + SCORE_HALF_HEIGHT)
    score = str(clip["display_score"]).replace("-", " : ")
    if elapsed < 0:
        d.rounded_rectangle(box, radius=12, fill=(10, 27, 59, 240),
                            outline=(38, 183, 245, 235), width=2)
        _heavy_score(d, (sx, sy), "— : —", PALE, 19)
        return
    phase = min(1.0, elapsed / REVEAL_EFFECT)
    if phase < .34:
        current = "— : —"
    elif phase < .70:
        current = score.split(" : ")[0] + " : —"
    else:
        current = score
    # Score glints once, synchronized to the original reveal timing.
    shimmer = (1.0 - phase) ** 2
    if shimmer > 0.001:
        d.rounded_rectangle((box[0]-5, box[1]-5, box[2]+5, box[3]+5),
                            radius=15, outline=(34, 200, 255, int(170 * shimmer)), width=4)
    d.rounded_rectangle(box, radius=12,
                        fill=(255, 201, 50, 245) if phase >= .7 else (19, 50, 79, 247),
                        outline=(255, 246, 170, 255), width=2)
    text_color = (11, 22, 39, 255) if phase >= .7 else WHITE
    _heavy_score(d, (sx, sy), current, text_color, 20 + int(2 * ease(phase)))


def compose_frame(base, clips, t, *, starts):
    frame = base.copy()
    for clip, (x, y), start in zip(clips, positions(len(clips)), starts):
        draw_score(frame, clip, x, y, t-start)
    return fit_artwork(frame)


def render(payload, output, *, preview=False, require_real_logos=False,
           fullhd=True, asset_root=".", logo_cache=None, fps=FPS,
           allow_partial_production=False):
    clips = validate_payload(payload, preview=preview,
                             allow_partial_production=allow_partial_production)
    if not 1 <= len(clips) <= 10 or (not allow_partial_production and len(clips)!=10):
        raise ValueError("L'édition sociale stricte exige exactement dix rencontres vérifiées")
    check_assets()
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg absent")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    starts = [FIRST_REVEAL+i*REVEAL_INTERVAL for i in range(len(clips))]
    duration = round(starts[-1]+REVEAL_EFFECT+FINAL_HOLD, 3)
    frames = round(duration*fps)
    with tempfile.TemporaryDirectory(prefix="mrx-neon-social-") as temp:
        cache = LogoCache(logo_cache or Path(temp)/"logos", asset_root, preview)
        logos = [(cache.get(c, "home", i), cache.get(c, "away", i)) for i, c in enumerate(clips, 1)]
        if require_real_logos and (cache.fallback_count or cache.real_count != 2 * len(clips)):
            raise ValueError("Tous les vrais écussons sont exigés pour les équipes : pas de lettres de remplacement")
        base = base_frame(payload, clips, logos, preview)
        soundtrack_file = Path(temp)/"audio.wav"
        soundtrack(soundtrack_file, duration, [0., *starts], volume=.55)
        silent = Path(temp)/"silent.mp4"
        args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                "-pixel_format", "rgb24", "-video_size", f"{W}x{H}", "-framerate", str(fps),
                "-i", "pipe:0", "-c:v", "libx264", "-preset", "veryfast",
                "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", str(silent)]
        encoder = subprocess.Popen(args, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for k in range(frames):
                frame = compose_frame(base, clips, k/fps, starts=starts)
                encoder.stdin.write(frame.convert("RGB").tobytes())
            encoder.stdin.close()
            if encoder.wait(timeout=240):
                raise RuntimeError("FFmpeg encode failed: " +
                                   encoder.stderr.read().decode(errors="replace")[-600:])
        except Exception:
            try:
                encoder.stdin.close()
            except (OSError, ValueError):
                pass
            encoder.kill()
            encoder.wait()
            raise
        mux = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-i", str(silent), "-i", str(soundtrack_file)]
        if fullhd:
            mux += ["-vf", "scale=1080:1920:flags=lanczos",
                    "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p", "-crf", "17"]
        else:
            mux += ["-c:v", "copy"]
        mux += ["-c:a", "aac", "-b:a", "160k", "-shortest",
                "-movflags", "+faststart", str(output)]
        subprocess.run(mux, check=True, timeout=240, capture_output=True)
    return {
        "output": str(output), "format": "neon_stadium_grid_2x5",
        "duration_seconds": duration, "fps": fps, "count": len(clips),
        "resolution": "1080x1920" if fullhd else f"{W}x{H}",
        "real_logo_instances": cache.real_count,
        "placeholder_logo_instances": cache.fallback_count,
        "preview": preview, "size_bytes": output.stat().st_size,
        "telegram_sent": False,
    }


def main():
    p = argparse.ArgumentParser(description="Mr XPRONOS stadium video - verified ten-score reveal")
    p.add_argument("--payload", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--preview", action="store_true")
    p.add_argument("--fullhd", action="store_true")
    args = p.parse_args()
    data = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    result = render(data, args.output, preview=args.preview, fullhd=args.fullhd, asset_root=str(HERE))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
