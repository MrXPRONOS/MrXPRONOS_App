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
    font = _font(size, bold)
    lines = _wrap(text, font, max_width, draw)[:max_lines]
    cur = y
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        draw.text(((W - (box[2] - box[0])) / 2, cur), line, font=font, fill=fill)
        cur += box[3] - box[1] + gap
    return cur


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
    draw.rounded_rectangle((28, 24, 214, 70), radius=18, fill=(6, 20, 33, 225), outline=(224, 166, 54), width=2)
    draw.text((47, 37), "MR XPRONOS", font=_font(21, True), fill=(244, 216, 151))
    draw.text((W - 30, 39), "ACTU FOOT", font=_font(16, True), fill=(190, 203, 214), anchor="ra")


def render_animation(
    payload: dict,
    output: str | Path,
    session: requests.Session,
) -> Path:
    """Produit un GIF carré original léger, compatible Telegram sendAnimation."""
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    media = payload.get("media") if isinstance(payload.get("media"), dict) else {}
    frames: list[Image.Image] = []
    kind = plain(payload.get("kind"), 40)

    # Le background n'est téléchargé qu'une fois.
    downloaded = _load_background(session, media) if media else None

    for index in range(FRAMES):
        progress = index / max(1, FRAMES - 1)
        if downloaded is not None:
            zoom = 1.00 + 0.035 * progress
            scaled = downloaded.resize((int(W * zoom), int(H * zoom)), Image.Resampling.LANCZOS)
            left = max(0, (scaled.width - W) // 2 + int(7 * math.sin(progress * math.pi)))
            top = max(0, (scaled.height - H) // 2)
            frame = scaled.crop((left, top, left + W, top + H))
            frame = Image.blend(frame, Image.new("RGB", (W, H), "#04101b"), 0.60)
        else:
            frame = _gradient_frame(progress)
        draw = ImageDraw.Draw(frame, "RGBA")
        _brand(draw)

        # Barre de progression / mouvement visuel.
        draw.rounded_rectangle((36, H - 48, W - 36, H - 34), radius=7, fill=(255, 255, 255, 35))
        draw.rounded_rectangle(
            (36, H - 48, 36 + int((W - 72) * progress), H - 34),
            radius=7,
            fill=(224, 166, 54, 235),
        )

        fade = min(1.0, progress * 3.0)
        gold = (244, 201, 104, int(255 * fade))
        white = (255, 255, 255, int(255 * fade))
        muted = (188, 202, 212, int(230 * fade))

        if kind == "match_fou":
            draw.text((W // 2, 112), "🔥 MATCH FOU", font=_font(34, True), fill=gold, anchor="ma")
            score_text = plain(payload.get("score"), 24)
            score_size = 108 + int(10 * math.sin(progress * math.pi))
            draw.text((W // 2, 205), score_text, font=_font(score_size, True), fill=white, anchor="ma")
            _draw_centered(draw, plain(payload.get("home"), 60), 338, size=29, bold=True, fill=white, max_width=510, max_lines=2)
            draw.text((W // 2, 417), "VS", font=_font(18, True), fill=muted, anchor="ma")
            _draw_centered(draw, plain(payload.get("away"), 60), 452, size=29, bold=True, fill=white, max_width=510, max_lines=2)
            draw.text(
                (W // 2, 540),
                plain(payload.get("league"), 75),
                font=_font(17, True), fill=muted, anchor="ma"
            )

        elif kind == "news_pulse":
            draw.text((W // 2, 112), "🚨 À RETENIR", font=_font(32, True), fill=gold, anchor="ma")
            end_y = _draw_centered(
                draw, plain(payload.get("title"), 230), 185,
                size=32, bold=True, fill=white, max_width=550, max_lines=4, gap=10
            )
            summary = plain(payload.get("summary"), 260)
            _draw_centered(
                draw, summary, min(end_y + 28, 420),
                size=20, fill=muted, max_width=520, max_lines=4, gap=8
            )

        else:
            draw.text((W // 2, 112), "📊 STAT QUI CLAQUE", font=_font(30, True), fill=gold, anchor="ma")
            _draw_centered(
                draw, plain(payload.get("headline"), 240), 205,
                size=38, bold=True, fill=white, max_width=550, max_lines=4, gap=10
            )
            y = 430
            for line in (payload.get("lines") or [])[:3]:
                clean = plain(line, 120)
                if not clean:
                    continue
                draw.rounded_rectangle((72, y - 8, W - 72, y + 44), radius=18, fill=(6, 22, 35, 190), outline=(224, 166, 54, 110))
                draw.text((W // 2, y + 7), clean, font=_font(18, True), fill=muted, anchor="ma")
                y += 66

        frame = frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=128)
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
        # Repli compact: moins de couleurs et une image sur deux.
        compact = [frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=64) for frame in frames[::2]]
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
        payload["media"] = _licensed_media_for_payload(session, payload["kind"])
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
