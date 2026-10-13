#!/usr/bin/env python3
"""Moteur 5 — Médias / Viral pour Actu Foot.

But:
- fabriquer des animations ORIGINALES Mr XPRONOS à partir de données vérifiées;
- utiliser éventuellement un fond externe uniquement si sa réutilisation est
  explicitement compatible (Wikimedia Commons filtré par licence, ou Pexels /
  Pixabay avec clé gratuite);
- conserver l'attribution dans le post Telegram.

Aucune vidéo YouTube/TikTok/X n'est téléchargée ou republiée.
"""
from __future__ import annotations

import html
import io
import math
import os
import re
import tempfile
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from football_stats_engine import daily_insight

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
PEXELS_API = "https://api.pexels.com/v1/search"
PIXABAY_API = "https://pixabay.com/api/"
USER_AGENT = "MrXPRONOS-Viral/1.0 (+https://mrxpronos.github.io/MrXPRONOS_App/)"

ALLOWED_COMMONS_LICENSE_MARKERS = (
    "cc0",
    "public domain",
    "pd-",
    "cc by",
    "cc-by",
    "cc by-sa",
    "cc-by-sa",
    "creative commons attribution",
)

W = H = 640
FRAMES = 20
FRAME_MS = 140


def plain(value: Any, limit: int = 260) -> str:
    value = re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))
    return re.sub(r"\s+", " ", value).strip()[:limit].rstrip()


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", plain(value, 200))
    text = text.encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def moment(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def score(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def team_name(event: dict, side: str) -> str:
    value = event.get(side + "_team")
    if isinstance(value, dict):
        value = value.get("name") or value.get("displayName")
    return plain(value, 54)


def league_name(event: dict) -> str:
    for key in ("league_name", "competition_name", "tournament_name", "league"):
        value = event.get(key)
        if isinstance(value, dict):
            value = value.get("name")
        text = plain(value, 70)
        if text and text.casefold() not in {"football", "soccer"}:
            return text
    return "Football"


def final_score(event: dict) -> tuple[int, int] | None:
    status = plain(event.get("status"), 24).casefold()
    if status not in {"finished", "ft", "full_time"}:
        return None
    home = score(event.get("home_score"))
    away = score(event.get("away_score"))
    return (home, away) if home is not None and away is not None else None


def _meta_value(meta: dict, key: str) -> str:
    value = meta.get(key)
    if isinstance(value, dict):
        value = value.get("value")
    return plain(value, 500)


def _commons_license_allowed(meta: dict) -> bool:
    nonfree = _meta_value(meta, "NonFree").casefold()
    if nonfree in {"true", "1", "yes"}:
        return False
    restrictions = _meta_value(meta, "Restrictions")
    if restrictions:
        return False
    license_name = _meta_value(meta, "LicenseShortName").casefold()
    if not license_name:
        return False
    return any(marker in license_name for marker in ALLOWED_COMMONS_LICENSE_MARKERS)


def fetch_commons_image(session: requests.Session, query: str) -> dict:
    """Recherche un fond générique football et vérifie sa licence fichier par fichier."""
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": "6",
        "gsrsearch": query,
        "gsrlimit": "10",
        "prop": "imageinfo",
        "iiprop": "url|mime|extmetadata",
        "iiurlwidth": "1280",
        "iiextmetadatafilter": (
            "LicenseShortName|LicenseUrl|Artist|Credit|Attribution|"
            "AttributionRequired|NonFree|Restrictions|ObjectName"
        ),
        "origin": "*",
    }
    try:
        response = session.get(
            COMMONS_API, params=params, headers={"User-Agent": USER_AGENT}, timeout=(7, 22)
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return {}

    pages = (payload.get("query") or {}).get("pages") if isinstance(payload, dict) else {}
    if not isinstance(pages, dict):
        return {}

    candidates = []
    for page in pages.values():
        if not isinstance(page, dict):
            continue
        title = plain(page.get("title"), 180)
        infos = page.get("imageinfo")
        info = infos[0] if isinstance(infos, list) and infos and isinstance(infos[0], dict) else {}
        mime = plain(info.get("mime"), 40).lower()
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        meta = info.get("extmetadata") if isinstance(info.get("extmetadata"), dict) else {}
        if not _commons_license_allowed(meta):
            continue
        url = plain(info.get("thumburl") or info.get("url"), 1000)
        if not url.startswith("https://"):
            continue
        license_name = _meta_value(meta, "LicenseShortName")
        license_url = _meta_value(meta, "LicenseUrl")
        attribution = (
            _meta_value(meta, "Attribution")
            or _meta_value(meta, "Artist")
            or _meta_value(meta, "Credit")
            or "Wikimedia Commons contributor"
        )
        # Préférence aux images dont le titre évoque bien pelouse/stade/football.
        match_score = sum(
            1 for token in ("football", "soccer", "stadium", "pitch", "field", "grass")
            if token in _norm(title)
        )
        candidates.append((match_score, title, {
            "provider": "Wikimedia Commons",
            "url": url,
            "page_url": "https://commons.wikimedia.org/wiki/" + quote(title.replace(" ", "_"), safe=":_()"),
            "credit": attribution,
            "license": license_name,
            "license_url": license_url,
        }))
    if not candidates:
        return {}
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]


def fetch_pexels_image(session: requests.Session, query: str) -> dict:
    key = (os.getenv("PEXELS_API_KEY") or "").strip()
    if not key:
        return {}
    try:
        response = session.get(
            PEXELS_API,
            params={"query": query, "orientation": "landscape", "per_page": "12"},
            headers={"Authorization": key, "User-Agent": USER_AGENT},
            timeout=(7, 22),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return {}
    photos = payload.get("photos") if isinstance(payload, dict) else None
    if not isinstance(photos, list):
        return {}
    for photo in photos:
        if not isinstance(photo, dict):
            continue
        src = photo.get("src") if isinstance(photo.get("src"), dict) else {}
        url = plain(src.get("large2x") or src.get("large"), 1000)
        page = plain(photo.get("url"), 1000)
        photographer = plain(photo.get("photographer"), 100)
        if url.startswith("https://") and page.startswith("https://"):
            return {
                "provider": "Pexels",
                "url": url,
                "page_url": page,
                "credit": photographer or "Pexels contributor",
                "license": "Pexels License",
                "license_url": "https://www.pexels.com/license/",
            }
    return {}


def fetch_pixabay_image(session: requests.Session, query: str) -> dict:
    key = (os.getenv("PIXABAY_API_KEY") or "").strip()
    if not key:
        return {}
    try:
        response = session.get(
            PIXABAY_API,
            params={
                "key": key,
                "q": query,
                "image_type": "photo",
                "orientation": "horizontal",
                "category": "sports",
                "safesearch": "true",
                "per_page": "12",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=(7, 22),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return {}
    hits = payload.get("hits") if isinstance(payload, dict) else None
    if not isinstance(hits, list):
        return {}
    for item in hits:
        if not isinstance(item, dict):
            continue
        url = plain(item.get("largeImageURL") or item.get("webformatURL"), 1000)
        page = plain(item.get("pageURL"), 1000)
        author = plain(item.get("user"), 100)
        tags = _norm(item.get("tags"))
        # Éviter les résultats manifestement hors football malgré le mot-clé.
        if not any(word in tags for word in ("football", "soccer", "stadium", "ball", "pitch")):
            continue
        if url.startswith("https://") and page.startswith("https://"):
            return {
                "provider": "Pixabay",
                "url": url,
                "page_url": page,
                "credit": author or "Pixabay contributor",
                "license": "Pixabay Content License",
                "license_url": "https://pixabay.com/service/license-summary/",
            }
    return {}


def choose_licensed_background(session: requests.Session, query: str) -> dict:
    """Priorité au sans-clé; les autres fournisseurs sont des renforts optionnels."""
    if (os.getenv("VIRAL_EXTERNAL_MEDIA") or "1").strip() == "0":
        return {}
    providers = (
        lambda: fetch_commons_image(session, query),
        lambda: fetch_pexels_image(session, query),
        lambda: fetch_pixabay_image(session, query),
    )
    for provider in providers:
        media = provider()
        if media:
            return media
    return {}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "C:/Windows/Fonts/arialbd.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "C:/Windows/Fonts/arial.ttf"]
    )
    for candidate in candidates:
        try:
            if Path(candidate).is_file():
                return ImageFont.truetype(candidate, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _wrap(text: str, font: ImageFont.ImageFont, width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = plain(text, 500).split()
    lines, current = [], ""
    for word in words:
        trial = (current + " " + word).strip()
        box = draw.textbbox((0, 0), trial, font=font)
        if box[2] - box[0] <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _smart_trim(value: Any, limit: int) -> str:
    text = plain(value, max(limit * 2, limit + 20))
    if len(text) <= limit:
        return text
    cut = text[: max(1, limit - 1)].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0].rstrip()
    return (cut or text[: max(1, limit - 1)]).rstrip(" .,;:-") + "…"


def _line_height(draw: ImageDraw.ImageDraw, line: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), line or "Ag", font=font)
    return max(1, box[3] - box[1])


def _fit_text_layout(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    max_width: int,
    max_height: int,
    max_lines: int,
    max_size: int,
    min_size: int,
    bold: bool = False,
    gap: int = 8,
) -> tuple[ImageFont.ImageFont, list[str], int]:
    clean = plain(text, 500)
    if not clean:
        font = _font(min_size, bold)
        return font, [], min_size

    for size in range(max_size, min_size - 1, -1):
        font = _font(size, bold)
        lines = _wrap(clean, font, max_width, draw)
        if not lines or len(lines) > max_lines:
            continue
        total = sum(_line_height(draw, line, font) for line in lines)
        total += gap * max(0, len(lines) - 1)
        if total <= max_height:
            return font, lines, size

    font = _font(min_size, bold)
    lines = _wrap(clean, font, max_width, draw)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        final = lines[-1]
        while final:
            candidate = final.rstrip(" .,:;-") + "…"
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                lines[-1] = candidate
                break
            final = final[:-1].rstrip()
        if not final:
            lines[-1] = "…"
    return font, lines, min_size


def _draw_text_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    *,
    max_size: int,
    min_size: int,
    max_lines: int,
    bold: bool = False,
    fill=(255, 255, 255, 255),
    gap: int = 8,
    align: str = "left",
) -> int:
    x0, y0, x1, y1 = box
    font, lines, _ = _fit_text_layout(
        draw,
        text,
        max_width=max(1, x1 - x0),
        max_height=max(1, y1 - y0),
        max_lines=max_lines,
        max_size=max_size,
        min_size=min_size,
        bold=bold,
        gap=gap,
    )
    y = y0
    for line in lines:
        line_box = draw.textbbox((0, 0), line, font=font)
        width = line_box[2] - line_box[0]
        if align == "center":
            x = x0 + max(0, (x1 - x0 - width) / 2)
        elif align == "right":
            x = x1 - width
        else:
            x = x0
        draw.text((x, y), line, font=font, fill=fill)
        y += _line_height(draw, line, font) + gap
    return y


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    *,
    size: int,
    bold: bool = False,
    fill=(255, 255, 255),
    max_width: int = 540,
    max_lines: int = 3,
    gap: int = 8,
) -> int:
    return _draw_text_box(
        draw,
        text,
        ((W - max_width) // 2, y, (W + max_width) // 2, H - 70),
        max_size=size,
        min_size=max(14, size - 12),
        max_lines=max_lines,
        bold=bold,
        fill=fill,
        gap=gap,
        align="center",
    )


def _gradient_frame(progress: float) -> Image.Image:
    image = Image.new("RGB", (W, H), "#061421")
    draw = ImageDraw.Draw(image)
    for y in range(H):
        t = y / max(1, H - 1)
        r = int(5 + 15 * t + 8 * progress)
        g = int(18 + 18 * t)
        b = int(31 + 20 * t)
        draw.line((0, y, W, y), fill=(r, g, b))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    radius = 180 + int(35 * math.sin(progress * math.pi))
    gd.ellipse(
        (W // 2 - radius, 70 - radius // 2, W // 2 + radius, 70 + radius * 3 // 2),
        fill=(224, 166, 54, 42),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(45))
    return Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")


def _load_background(session: requests.Session, media: dict) -> Image.Image | None:
    url = plain(media.get("url"), 1000)
    if not url.startswith("https://"):
        return None
    try:
        response = session.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"},
            timeout=(7, 28),
        )
        response.raise_for_status()
        if "image/" not in str(response.headers.get("content-type") or "").lower():
            return None
        raw = response.content
        if len(raw) > 14_000_000:
            return None
        with Image.open(io.BytesIO(raw)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
        return ImageOps.fit(image, (W, H), Image.Resampling.LANCZOS)
    except (requests.RequestException, OSError, ValueError):
        return None


def _base_frame(session: requests.Session, media: dict, progress: float) -> Image.Image:
    background = _load_background(session, media) if media else None
    if background is None:
        return _gradient_frame(progress)

    # Pan/zoom très léger, puis assombrissement fort: le stock n'est jamais publié
    # tel quel et sert uniquement de matière visuelle à une création Mr XPRONOS.
    zoom = 1.00 + 0.035 * progress
    size = (int(W * zoom), int(H * zoom))
    scaled = background.resize(size, Image.Resampling.LANCZOS)
    left = max(0, (scaled.width - W) // 2 + int(8 * math.sin(progress * math.pi)))
    top = max(0, (scaled.height - H) // 2)
    frame = scaled.crop((left, top, left + W, top + H))
    dark = Image.new("RGB", (W, H), "#04101b")
    frame = Image.blend(frame, dark, 0.58)
    return frame


def _brand(draw: ImageDraw.ImageDraw) -> None:
    draw.rounded_rectangle(
        (30, 26, 205, 70),
        radius=14,
        fill=(5, 18, 30, 235),
        outline=(231, 183, 73, 235),
        width=2,
    )
    draw.text((48, 39), "MR XPRONOS", font=_font(18, True), fill=(248, 226, 172))
    draw.text(
        (W - 32, 42),
        "ACTU FOOT",
        font=_font(14, True),
        fill=(184, 201, 214),
        anchor="ra",
    )


def _source_pill(draw: ImageDraw.ImageDraw, source: str, y: int) -> None:
    source = _smart_trim(source or "Source vérifiée", 34)
    label_font = _font(11, True)
    value_font = _font(15, True)
    draw.text((60, y), "SOURCE", font=label_font, fill=(135, 153, 168, 255))
    box = draw.textbbox((0, 0), source, font=value_font)
    width = min(250, max(118, box[2] - box[0] + 34))
    draw.rounded_rectangle(
        (60, y + 22, 60 + width, y + 58),
        radius=12,
        fill=(231, 183, 73, 28),
        outline=(231, 183, 73, 95),
        width=1,
    )
    draw.text((76, y + 31), source, font=value_font, fill=(245, 218, 158, 255))


def render_animation(
    payload: dict,
    output: str | Path,
    session: requests.Session,
) -> Path:
    """Produit un GIF carré premium, lisible et compatible Telegram.

    L'animation porte une seule idée forte. Le contexte détaillé reste dans la
    légende Telegram au lieu d'être répété en petit dans la vidéo.
    """
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    media = payload.get("media") if isinstance(payload.get("media"), dict) else {}
    frames: list[Image.Image] = []
    kind = plain(payload.get("kind"), 40)

    # Pour une news, un fond générique peut induire en erreur. On privilégie
    # donc le fond graphique de marque. Matchs et stats peuvent garder un fond
    # licencié fortement assombri.
    downloaded = None
    if media and kind != "news_pulse":
        downloaded = _load_background(session, media)

    for index in range(FRAMES):
        progress = index / max(1, FRAMES - 1)
        if downloaded is not None:
            zoom = 1.02 + 0.025 * progress
            scaled = downloaded.resize(
                (int(W * zoom), int(H * zoom)),
                Image.Resampling.LANCZOS,
            )
            left = max(0, (scaled.width - W) // 2 + int(5 * math.sin(progress * math.pi)))
            top = max(0, (scaled.height - H) // 2)
            frame = scaled.crop((left, top, left + W, top + H))
            frame = frame.filter(ImageFilter.GaussianBlur(1.1))
            frame = Image.blend(frame, Image.new("RGB", (W, H), "#061420"), 0.72)
        else:
            frame = _gradient_frame(progress)

        draw = ImageDraw.Draw(frame, "RGBA")
        _brand(draw)

        fade = min(1.0, max(0.0, progress * 3.4))
        alpha = int(255 * fade)
        gold = (237, 188, 76, alpha)
        white = (255, 255, 255, alpha)
        muted = (184, 201, 214, int(235 * fade))
        panel = (2, 11, 19, int(224 * fade))

        accent_w = 18 + int(30 * min(1.0, progress * 2.4))
        draw.rounded_rectangle((36, 116, 36 + accent_w, 122), radius=3, fill=gold)

        if kind == "news_pulse":
            draw.text((36, 140), "À RETENIR", font=_font(18, True), fill=gold)
            draw.rounded_rectangle(
                (28, 184, W - 28, 520),
                radius=28,
                fill=panel,
                outline=(255, 255, 255, int(22 * fade)),
                width=1,
            )
            display_title = _smart_trim(payload.get("title"), 150)
            _draw_text_box(
                draw,
                display_title,
                (60, 232, W - 58, 410),
                max_size=38,
                min_size=25,
                max_lines=4,
                bold=True,
                fill=white,
                gap=10,
            )
            _source_pill(draw, plain(payload.get("data_source"), 80), 455)

        elif kind == "match_fou":
            draw.text((36, 140), "MATCH FOU", font=_font(18, True), fill=gold)
            draw.rounded_rectangle(
                (28, 184, W - 28, 532),
                radius=28,
                fill=panel,
                outline=(255, 255, 255, int(22 * fade)),
                width=1,
            )
            score_text = plain(payload.get("score"), 24)
            score_font, score_lines, _ = _fit_text_layout(
                draw,
                score_text,
                max_width=500,
                max_height=100,
                max_lines=1,
                max_size=92,
                min_size=64,
                bold=True,
                gap=0,
            )
            score = score_lines[0] if score_lines else score_text
            draw.text((W // 2, 225), score, font=score_font, fill=white, anchor="ma")
            _draw_text_box(
                draw,
                plain(payload.get("home"), 70),
                (64, 335, W - 64, 386),
                max_size=27,
                min_size=20,
                max_lines=2,
                bold=True,
                fill=white,
                gap=6,
                align="center",
            )
            draw.text((W // 2, 405), "—", font=_font(18, True), fill=gold, anchor="ma")
            _draw_text_box(
                draw,
                plain(payload.get("away"), 70),
                (64, 430, W - 64, 480),
                max_size=27,
                min_size=20,
                max_lines=2,
                bold=True,
                fill=white,
                gap=6,
                align="center",
            )
            league = _smart_trim(payload.get("league"), 52)
            draw.text((W // 2, 505), league, font=_font(14, True), fill=muted, anchor="ma")

        else:
            draw.text((36, 140), "STAT À RETENIR", font=_font(18, True), fill=gold)
            draw.rounded_rectangle(
                (28, 184, W - 28, 532),
                radius=28,
                fill=panel,
                outline=(255, 255, 255, int(22 * fade)),
                width=1,
            )
            headline = _smart_trim(payload.get("headline"), 155)
            end_y = _draw_text_box(
                draw,
                headline,
                (60, 224, W - 60, 370),
                max_size=34,
                min_size=23,
                max_lines=4,
                bold=True,
                fill=white,
                gap=9,
            )
            y = max(390, end_y + 12)
            for line in (payload.get("lines") or [])[:2]:
                clean = _smart_trim(line, 72)
                if not clean or y > 490:
                    continue
                draw.rounded_rectangle(
                    (60, y, W - 60, y + 44),
                    radius=14,
                    fill=(255, 255, 255, int(14 * fade)),
                    outline=(231, 183, 73, int(50 * fade)),
                )
                _draw_text_box(
                    draw,
                    clean,
                    (78, y + 10, W - 78, y + 37),
                    max_size=15,
                    min_size=12,
                    max_lines=1,
                    bold=True,
                    fill=muted,
                    gap=0,
                    align="center",
                )
                y += 54

        draw.text(
            (36, H - 64),
            "L’ESSENTIEL. CLAIR. RAPIDE.",
            font=_font(13, True),
            fill=muted,
        )
        draw.rounded_rectangle(
            (36, H - 36, W - 36, H - 32),
            radius=2,
            fill=(255, 255, 255, int(24 * fade)),
        )
        draw.rounded_rectangle(
            (36, H - 36, 36 + int((W - 72) * progress), H - 32),
            radius=2,
            fill=gold,
        )

        frame = frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=112)
        frames.append(frame)

    frames[0].save(
        destination,
        save_all=True,
        append_images=frames[1:],
        optimize=True,
        duration=FRAME_MS,
        loop=0,
        disposal=2,
    )
    if destination.stat().st_size > 14_000_000:
        compact = [
            frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=64)
            for frame in frames[::2]
        ]
        compact[0].save(
            destination,
            save_all=True,
            append_images=compact[1:],
            optimize=True,
            duration=FRAME_MS * 2,
            loop=0,
            disposal=2,
        )
    return destination


def _licensed_media_for_payload(session: requests.Session, kind: str) -> dict:
    if kind == "match_fou":
        query = "association football stadium pitch grass"
    elif kind == "news_pulse":
        query = "football stadium lights pitch"
    else:
        query = "soccer ball football pitch grass"
    return choose_licensed_background(session, query)


def build_viral_payload(
    events: list[dict],
    news: list[dict],
    session: requests.Session,
    now: datetime,
    importance_fn: Callable[[dict], int],
) -> dict | None:
    """Sélectionne au maximum un sujet viral, sans fabriquer de fait."""
    # 1) Résultat spectaculaire et récent.
    spectacular = []
    for event in events:
        result = final_score(event)
        kickoff = moment(event.get("event_date") or event.get("start_time"))
        if result is None or kickoff is None:
            continue
        if not now - timedelta(hours=6) <= kickoff <= now:
            continue
        home, away = team_name(event, "home"), team_name(event, "away")
        if not home or not away:
            continue
        hs, aws = result
        total, margin = hs + aws, abs(hs - aws)
        importance = int(importance_fn(event) or 0)
        if importance <= 0 or not (total >= 4 or margin >= 3):
            continue
        spectacular.append((total * 12 + margin * 8 + importance, kickoff, event, result))
    if spectacular:
        spectacular.sort(key=lambda x: (-x[0], -x[1].timestamp(), str(x[2].get("id") or "")))
        _, _, event, result = spectacular[0]
        hs, aws = result
        payload = {
            "kind": "match_fou",
            "key": f"viral-match:{event.get('id')}:{hs}-{aws}",
            "home": team_name(event, "home"),
            "away": team_name(event, "away"),
            "score": f"{hs} - {aws}",
            "league": league_name(event),
            "caption": (
                f"🔥 <b>MATCH FOU</b>\n\n"
                f"<b>{team_name(event, 'home')} {hs}-{aws} {team_name(event, 'away')}</b>\n"
                f"<i>{league_name(event)}</i>\n\n"
                f"{hs + aws} buts dans cette rencontre. 💬 Quel moment t’a le plus marqué ?"
            ),
            "data_source": "Mr XPRONOS / données match vérifiées",
            "target_url": "https://mrxpronos.github.io/MrXPRONOS_App/live.html",
        }
        payload["media"] = _licensed_media_for_payload(session, payload["kind"])
        return payload

    # 2) News récente à fort score éditorial.
    ranked_news = []
    for item in news:
        if not isinstance(item, dict):
            continue
        published = moment(item.get("published"))
        title = plain(item.get("title"), 240)
        summary = plain(item.get("summary_short") or item.get("summary"), 300)
        if not published or not title or not summary:
            continue
        if now - published > timedelta(hours=14):
            continue
        editorial = int(item.get("editorial_score") or 0)
        if editorial < 4:
            continue
        ranked_news.append((editorial, published, item))
    if ranked_news:
        ranked_news.sort(key=lambda x: (x[0], x[1]), reverse=True)
        item = ranked_news[0][2]
        payload = {
            "kind": "news_pulse",
            "key": "viral-news:" + plain(item.get("slug"), 90),
            "title": plain(item.get("title"), 230),
            "summary": plain(item.get("summary_short") or item.get("summary"), 250),
            "caption": (
                "🚨 <b>À RETENIR</b>\n\n"
                + "<b>" + html.escape(plain(item.get("title"), 240), quote=False) + "</b>\n\n"
                + "<blockquote>" + html.escape(plain(item.get("summary_short") or item.get("summary"), 330), quote=False) + "</blockquote>\n\n"
                + "<i>🗞️ Source : " + html.escape(plain(item.get("source"), 80), quote=False) + "</i>"
            ),
            "data_source": plain(item.get("source"), 80),
            "target_url": plain(item.get("site_url"), 500),
        }
        payload["media"] = {}
        return payload

    # 3) Statistique fiable comme dernier format.
    insight = daily_insight(session, now.date())
    if insight and int(insight.get("confidence") or 0) >= 70:
        payload = {
            "kind": "stat_pulse",
            "key": (
                "viral-stat:" + now.date().isoformat() + ":"
                + plain(insight.get("league_key"), 60) + ":" + plain(insight.get("kind"), 60)
            ),
            "headline": plain(insight.get("headline"), 230),
            "lines": [plain(x, 120) for x in (insight.get("lines") or []) if plain(x, 120)][:3],
            "caption": (
                "📊 <b>STAT QUI CLAQUE</b>\n\n"
                + "<blockquote><b>" + html.escape(plain(insight.get("headline"), 250), quote=False) + "</b></blockquote>\n\n"
                + "<i>Sources : " + html.escape(plain(insight.get("source"), 120), quote=False)
                + " • confiance " + str(int(insight.get("confidence") or 0)) + "%</i>"
            ),
            "data_source": plain(insight.get("source"), 120),
            "target_url": "https://mrxpronos.github.io/MrXPRONOS_App/infos.html",
        }
        payload["media"] = _licensed_media_for_payload(session, payload["kind"])
        return payload

    return None


def media_credit_text(payload: dict) -> str:
    media = payload.get("media") if isinstance(payload.get("media"), dict) else {}
    if not media:
        return ""
    provider = plain(media.get("provider"), 60)
    credit = plain(media.get("credit"), 100)
    license_name = plain(media.get("license"), 80)
    parts = [part for part in (credit, provider, license_name) if part]
    return " • ".join(parts)


def media_credit_url(payload: dict) -> str:
    media = payload.get("media") if isinstance(payload.get("media"), dict) else {}
    return plain(media.get("page_url"), 600)
