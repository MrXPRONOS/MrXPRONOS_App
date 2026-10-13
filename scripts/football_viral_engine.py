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
import shutil
import subprocess
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

W = H = 1080
FPS = 24
DURATION_SECONDS = 4.0
FRAME_COUNT = int(FPS * DURATION_SECONDS)


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


def _phase(progress: float, start: float, end: float) -> float:
    if end <= start:
        return 1.0 if progress >= end else 0.0
    return max(0.0, min(1.0, (progress - start) / (end - start)))


def _ease_out_cubic(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1.0 - (1.0 - value) ** 3


def _ease_out_back(value: float) -> float:
    value = max(0.0, min(1.0, value))
    c1 = 1.70158
    c3 = c1 + 1.0
    return 1.0 + c3 * (value - 1.0) ** 3 + c1 * (value - 1.0) ** 2


_EMOJI_CACHE: dict[tuple[str, int], Image.Image] = {}


def _emoji_tile(symbol: str, target_px: int) -> Image.Image:
    """Rend un emoji couleur haute définition avec fallback sans dépendance externe."""
    key = (symbol, target_px)
    cached = _EMOJI_CACHE.get(key)
    if cached is not None:
        return cached.copy()

    source = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
    d = ImageDraw.Draw(source)
    emoji_font = Path("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf")
    rendered = False
    if emoji_font.is_file():
        try:
            face = ImageFont.truetype(str(emoji_font), 109)
            d.text((90, 88), symbol, font=face, anchor="mm", embedded_color=True)
            rendered = True
        except (OSError, ValueError):
            pass
    if not rendered:
        face = _font(108, True)
        d.text((90, 90), symbol, font=face, fill=(248, 202, 92, 255), anchor="mm")

    bbox = source.getbbox()
    if bbox:
        source = source.crop(bbox)
    source.thumbnail((target_px, target_px), Image.Resampling.LANCZOS)
    _EMOJI_CACHE[key] = source.copy()
    return source


def _paste_center(
    image: Image.Image,
    overlay: Image.Image,
    center: tuple[int, int],
    *,
    opacity: float = 1.0,
) -> None:
    layer = overlay.copy()
    if opacity < 0.999:
        alpha = layer.getchannel("A").point(
            lambda px: int(px * max(0.0, min(1.0, opacity)))
        )
        layer.putalpha(alpha)
    image.paste(
        layer,
        (center[0] - layer.width // 2, center[1] - layer.height // 2),
        layer,
    )


def _gradient_frame(progress: float) -> Image.Image:
    image = Image.new("RGB", (W, H), "#061522")
    draw = ImageDraw.Draw(image)
    for y in range(H):
        t = y / max(1, H - 1)
        r = int(4 + 8 * t)
        g = int(18 + 18 * t)
        b = int(31 + 28 * t)
        draw.line((0, y, W, y), fill=(r, g, b))

    glows = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glows)
    pulse = 0.5 + 0.5 * math.sin(progress * math.pi * 2)
    gx = int(W * (0.22 + 0.08 * math.sin(progress * math.pi * 2)))
    gy = int(H * 0.18)
    radius = 280 + int(45 * pulse)
    gd.ellipse(
        (gx - radius, gy - radius, gx + radius, gy + radius),
        fill=(241, 187, 69, 58),
    )
    bx = int(W * (0.83 - 0.05 * math.sin(progress * math.pi * 2)))
    by = int(H * 0.70)
    br = 360
    gd.ellipse(
        (bx - br, by - br, bx + br, by + br),
        fill=(18, 112, 181, 44),
    )
    glows = glows.filter(ImageFilter.GaussianBlur(105))
    image = Image.alpha_composite(image.convert("RGBA"), glows).convert("RGB")

    line_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(line_layer)
    offset = int(progress * 110)
    for x in range(-260, W + 260, 170):
        ld.line(
            (x + offset, H, x + 360 + offset, 0),
            fill=(255, 255, 255, 10),
            width=2,
        )
    return Image.alpha_composite(image.convert("RGBA"), line_layer).convert("RGB")


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


def _base_frame(downloaded: Image.Image | None, progress: float) -> Image.Image:
    if downloaded is None:
        return _gradient_frame(progress)

    zoom = 1.03 + 0.045 * progress
    size = (int(W * zoom), int(H * zoom))
    scaled = downloaded.resize(size, Image.Resampling.LANCZOS)
    left = max(0, (scaled.width - W) // 2 + int(14 * math.sin(progress * math.pi)))
    top = max(0, (scaled.height - H) // 2)
    frame = scaled.crop((left, top, left + W, top + H))
    frame = frame.filter(ImageFilter.GaussianBlur(1.4))
    dark = Image.new("RGB", (W, H), "#04101b")
    return Image.blend(frame, dark, 0.66)


def _brand(draw: ImageDraw.ImageDraw, alpha: int = 255) -> None:
    draw.rounded_rectangle(
        (54, 48, 352, 122),
        radius=26,
        fill=(4, 17, 29, int(225 * alpha / 255)),
        outline=(238, 188, 72, alpha),
        width=3,
    )
    draw.text(
        (82, 71),
        "MR XPRONOS",
        font=_font(29, True),
        fill=(252, 232, 180, alpha),
    )
    draw.text(
        (W - 58, 84),
        "ACTU FOOT",
        font=_font(24, True),
        fill=(199, 214, 226, alpha),
        anchor="ra",
    )


def _source_pill(draw: ImageDraw.ImageDraw, source: str, y: int, alpha: int) -> None:
    source = _smart_trim(source or "Source vérifiée", 38)
    label_font = _font(18, True)
    value_font = _font(25, True)
    draw.text((116, y), "SOURCE VÉRIFIÉE", font=label_font, fill=(142, 165, 182, alpha))
    box = draw.textbbox((0, 0), source, font=value_font)
    width = min(430, max(205, box[2] - box[0] + 58))
    draw.rounded_rectangle(
        (116, y + 34, 116 + width, y + 90),
        radius=20,
        fill=(238, 188, 72, int(34 * alpha / 255)),
        outline=(238, 188, 72, int(125 * alpha / 255)),
        width=2,
    )
    draw.text((143, y + 48), source, font=value_font, fill=(250, 226, 167, alpha))


def _draw_sparks(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    progress: float,
    alpha: int,
) -> None:
    cx, cy = center
    for index, angle in enumerate((0.15, 1.0, 1.8, 2.65, 3.45, 4.25, 5.15)):
        phase = progress * math.pi * 2 + index * 0.7
        distance = 112 + 20 * math.sin(phase)
        x = cx + math.cos(angle) * distance
        y = cy + math.sin(angle) * distance
        radius = 4 + (index % 3) * 2
        color = (
            (244, 193, 75, int(alpha * 0.85))
            if index % 2 == 0
            else (91, 181, 238, int(alpha * 0.62))
        )
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)


def _render_frame(
    payload: dict,
    progress: float,
    downloaded: Image.Image | None = None,
) -> Image.Image:
    kind = plain(payload.get("kind"), 40)
    frame = _base_frame(downloaded, progress)
    draw = ImageDraw.Draw(frame, "RGBA")

    entry = _ease_out_cubic(_phase(progress, 0.0, 0.18))
    content_entry = _ease_out_cubic(_phase(progress, 0.08, 0.28))
    alpha = max(0, min(255, int(255 * entry)))
    content_alpha = max(0, min(255, int(255 * content_entry)))
    gold = (241, 193, 76, content_alpha)
    white = (255, 255, 255, content_alpha)
    muted = (187, 207, 222, int(235 * content_alpha / 255))

    _brand(draw, alpha)

    emoji_symbol = {"news_pulse": "🚨", "match_fou": "🔥", "stat_pulse": "📊"}.get(kind, "⚡")
    section = {
        "news_pulse": "À RETENIR",
        "match_fou": "MATCH FOU",
        "stat_pulse": "STAT QUI CLAQUE",
    }.get(kind, "MOMENT VIRAL")
    kicker = {
        "news_pulse": "NEWS FOOT",
        "match_fou": "ÇA A EXPLOSÉ",
        "stat_pulse": "LE CHIFFRE DU JOUR",
    }.get(kind, "S5 • VIRAL")

    bounce = _ease_out_back(_phase(progress, 0.02, 0.24))
    pulse = 1.0 + 0.035 * math.sin(progress * math.pi * 5)
    emoji_size = max(70, int(188 * max(0.55, bounce) * pulse))
    emoji_center = (170, 252)
    halo_r = int(112 + 8 * math.sin(progress * math.pi * 4))
    draw.ellipse(
        (
            emoji_center[0] - halo_r,
            emoji_center[1] - halo_r,
            emoji_center[0] + halo_r,
            emoji_center[1] + halo_r,
        ),
        fill=(238, 188, 72, int(22 * alpha / 255)),
        outline=(238, 188, 72, int(88 * alpha / 255)),
        width=3,
    )
    _draw_sparks(draw, emoji_center, progress, alpha)
    _paste_center(
        frame,
        _emoji_tile(emoji_symbol, emoji_size),
        (emoji_center[0], emoji_center[1] - int((1.0 - min(1.0, bounce)) * 30)),
        opacity=entry,
    )

    draw.text((306, 190), kicker, font=_font(22, True), fill=muted)
    draw.text((306, 224), section, font=_font(46, True), fill=gold)
    accent_width = int(350 * _ease_out_cubic(_phase(progress, 0.10, 0.40)))
    draw.rounded_rectangle(
        (306, 292, 306 + accent_width, 300),
        radius=4,
        fill=(241, 193, 76, content_alpha),
    )

    panel_shift = int((1.0 - content_entry) * 55)
    panel = (58, 354 + panel_shift, W - 58, 878 + panel_shift)
    shadow = (panel[0] + 10, panel[1] + 14, panel[2] + 10, panel[3] + 14)
    draw.rounded_rectangle(shadow, radius=40, fill=(0, 0, 0, int(80 * content_alpha / 255)))
    draw.rounded_rectangle(
        panel,
        radius=40,
        fill=(2, 13, 23, int(220 * content_alpha / 255)),
        outline=(255, 255, 255, int(30 * content_alpha / 255)),
        width=2,
    )
    draw.rounded_rectangle(
        (panel[0] + 2, panel[1] + 2, panel[0] + 12, panel[3] - 2),
        radius=5,
        fill=(241, 193, 76, int(220 * content_alpha / 255)),
    )

    if kind == "news_pulse":
        title = _smart_trim(payload.get("title"), 148)
        _draw_text_box(
            draw,
            title,
            (112, 422 + panel_shift, W - 104, 704 + panel_shift),
            max_size=66,
            min_size=43,
            max_lines=4,
            bold=True,
            fill=white,
            gap=13,
        )
        # Accent visuel secondaire, sans répéter le résumé dans la vidéo.
        bolt = _emoji_tile("⚡", 86)
        _paste_center(frame, bolt, (W - 155, 786 + panel_shift), opacity=content_entry * 0.82)
        _source_pill(
            draw,
            plain(payload.get("data_source"), 80),
            732 + panel_shift,
            content_alpha,
        )

    elif kind == "match_fou":
        score_text = plain(payload.get("score"), 24)
        score_font, score_lines, _ = _fit_text_layout(
            draw,
            score_text,
            max_width=720,
            max_height=175,
            max_lines=1,
            max_size=160,
            min_size=112,
            bold=True,
            gap=0,
        )
        score = score_lines[0] if score_lines else score_text
        score_scale = 1.0 + 0.025 * math.sin(progress * math.pi * 6)
        score_layer = Image.new("RGBA", (900, 220), (0, 0, 0, 0))
        sd = ImageDraw.Draw(score_layer)
        sd.text(
            (450, 100),
            score,
            font=score_font,
            fill=(255, 255, 255, content_alpha),
            anchor="mm",
            stroke_width=2,
            stroke_fill=(241, 193, 76, int(95 * content_alpha / 255)),
        )
        if abs(score_scale - 1.0) > 0.002:
            score_layer = score_layer.resize(
                (int(score_layer.width * score_scale), int(score_layer.height * score_scale)),
                Image.Resampling.LANCZOS,
            )
        _paste_center(frame, score_layer, (W // 2, 470 + panel_shift), opacity=content_entry)

        _draw_text_box(
            draw,
            plain(payload.get("home"), 70),
            (120, 566 + panel_shift, W - 120, 632 + panel_shift),
            max_size=43,
            min_size=31,
            max_lines=1,
            bold=True,
            fill=white,
            gap=0,
            align="center",
        )
        draw.text(
            (W // 2, 657 + panel_shift),
            "VS",
            font=_font(26, True),
            fill=gold,
            anchor="ma",
        )
        _draw_text_box(
            draw,
            plain(payload.get("away"), 70),
            (120, 690 + panel_shift, W - 120, 756 + panel_shift),
            max_size=43,
            min_size=31,
            max_lines=1,
            bold=True,
            fill=white,
            gap=0,
            align="center",
        )
        league = _smart_trim(payload.get("league"), 58)
        draw.text(
            (W // 2, 815 + panel_shift),
            league,
            font=_font(25, True),
            fill=muted,
            anchor="ma",
        )

    else:
        headline = _smart_trim(payload.get("headline"), 150)
        end_y = _draw_text_box(
            draw,
            headline,
            (112, 414 + panel_shift, W - 112, 660 + panel_shift),
            max_size=59,
            min_size=40,
            max_lines=4,
            bold=True,
            fill=white,
            gap=12,
            align="left",
        )
        y = max(690 + panel_shift, end_y + 18)
        for line in (payload.get("lines") or [])[:2]:
            clean_line = _smart_trim(line, 76)
            if not clean_line or y > 804 + panel_shift:
                continue
            draw.rounded_rectangle(
                (112, y, W - 112, y + 58),
                radius=20,
                fill=(255, 255, 255, int(18 * content_alpha / 255)),
                outline=(241, 193, 76, int(72 * content_alpha / 255)),
                width=2,
            )
            _draw_text_box(
                draw,
                clean_line,
                (140, y + 12, W - 140, y + 48),
                max_size=25,
                min_size=20,
                max_lines=1,
                bold=True,
                fill=muted,
                gap=0,
                align="center",
            )
            y += 72

    footer_alpha = int(230 * _phase(progress, 0.20, 0.45))
    draw.text(
        (58, H - 102),
        "MR XPRONOS • L’ESSENTIEL DU FOOT, EN MOUVEMENT.",
        font=_font(20, True),
        fill=(190, 207, 220, footer_alpha),
    )
    draw.text(
        (W - 58, H - 102),
        "18+ • JEU RESPONSABLE",
        font=_font(17, True),
        fill=(139, 158, 173, footer_alpha),
        anchor="ra",
    )
    draw.rounded_rectangle(
        (58, H - 58, W - 58, H - 48),
        radius=5,
        fill=(255, 255, 255, int(25 * footer_alpha / 255)),
    )
    draw.rounded_rectangle(
        (58, H - 58, 58 + int((W - 116) * progress), H - 48),
        radius=5,
        fill=(241, 193, 76, footer_alpha),
    )

    return frame.convert("RGB")


def _ffmpeg_executable() -> str:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg  # type: ignore
        executable = imageio_ffmpeg.get_ffmpeg_exe()
        if executable:
            return executable
    except (ImportError, OSError):
        pass
    raise RuntimeError(
        "FFmpeg est requis pour S5 Viral HD. Installer ffmpeg ou imageio-ffmpeg."
    )


def _encode_mp4(frame_dir: Path, destination: Path, *, crf: int = 16) -> None:
    command = [
        _ffmpeg_executable(),
        "-y",
        "-loglevel", "error",
        "-framerate", str(FPS),
        "-i", str(frame_dir / "frame_%04d.png"),
        "-c:v", "libx264",
        "-preset", "medium",
        "-tune", "animation",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        str(destination),
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError("Encodage S5 MP4 impossible: " + result.stderr[-500:])


def render_animation(
    payload: dict,
    output: str | Path,
    session: requests.Session,
) -> Path:
    """Produit une animation MP4 native 1080x1080, pensée pour Telegram.

    Le MP4 évite la conversion GIF -> petite vidéo qui dégradait fortement le
    rendu. Le texte détaillé reste dans la légende; la vidéo garde un seul hook
    lisible, de grands éléments visuels et des effets légers.
    """
    destination = Path(output)
    if destination.suffix.casefold() != ".mp4":
        raise ValueError("S5 Viral HD doit être rendu en .mp4")
    destination.parent.mkdir(parents=True, exist_ok=True)

    media = payload.get("media") if isinstance(payload.get("media"), dict) else {}
    kind = plain(payload.get("kind"), 40)
    downloaded = None
    if media and kind != "news_pulse":
        downloaded = _load_background(session, media)

    with tempfile.TemporaryDirectory(prefix="mrxpronos-s5-frames-") as tmp:
        frame_dir = Path(tmp)
        for index in range(FRAME_COUNT):
            progress = index / max(1, FRAME_COUNT - 1)
            frame = _render_frame(payload, progress, downloaded)
            frame.save(
                frame_dir / f"frame_{index:04d}.png",
                format="PNG",
                optimize=False,
                compress_level=2,
            )
        _encode_mp4(frame_dir, destination, crf=16)

        # Telegram accepte largement cette taille, mais on conserve une marge
        # de sécurité si un fond photo très détaillé fait gonfler le fichier.
        if destination.stat().st_size > 45_000_000:
            _encode_mp4(frame_dir, destination, crf=20)

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
