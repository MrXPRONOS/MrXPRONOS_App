#!/usr/bin/env python3
"""Moteur commun d'actualités football pour le site Infos Foot et Telegram Actu Foot.

Le moteur utilise uniquement des flux RSS/publics sans API payante.
Il n'invente aucune information : le contenu publié vient des champs fournis par
le flux (titre, description, date, média, lien) et des métadonnées publiques de
l'article (og:image / og:description) lorsque le flux est incomplet.
"""
from __future__ import annotations

import html
import io
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
MEDIA_DIR = ROOT / "assets" / "images" / "footnews"
SITE_BASE = "https://mrxpronos.github.io/MrXPRONOS_App/"

# Flux publics gratuits. Aucune clé API n'est nécessaire.
DEFAULT_FREE_FEEDS = (
    "https://madeinfoot.ouest-france.fr/flux/rss_news.php",
    "https://www.footmercato.net/flux-rss",
    "https://www.france24.com/fr/tag/football/rss",
    "https://www.rfi.fr/fr/tag/football/rss",
    "https://www.rfi.fr/fr/afrique-foot/rss",
    "https://www.franceinfo.fr/sports/foot.rss",
    "https://www.onzemondial.com/rss/index.html",
    "http://rss.maxifoot.com/football-general.xml",
    "https://www.sofoot.com/rss",
)


@dataclass(frozen=True)
class SourceProfile:
    name: str
    priority: int
    region: str = "international"


SOURCE_PROFILES = {
    "madeinfoot.ouest-france.fr": SourceProfile("MadeInFoot", 88),
    "footmercato.net": SourceProfile("Foot Mercato", 92),
    "www.footmercato.net": SourceProfile("Foot Mercato", 92),
    "france24.com": SourceProfile("France 24", 83),
    "www.france24.com": SourceProfile("France 24", 83),
    "rfi.fr": SourceProfile("RFI", 86, "afrique"),
    "www.rfi.fr": SourceProfile("RFI", 86, "afrique"),
    "franceinfo.fr": SourceProfile("Franceinfo", 82),
    "www.franceinfo.fr": SourceProfile("Franceinfo", 82),
    "onzemondial.com": SourceProfile("Onze Mondial", 80),
    "www.onzemondial.com": SourceProfile("Onze Mondial", 80),
    "rss.maxifoot.com": SourceProfile("Maxifoot", 78),
    "maxifoot.fr": SourceProfile("Maxifoot", 78),
    "www.maxifoot.fr": SourceProfile("Maxifoot", 78),
    "sofoot.com": SourceProfile("So Foot", 77),
    "www.sofoot.com": SourceProfile("So Foot", 77),
}

CATEGORY_RULES = (
    ("Officiel", (
        "officiel", "official", "communiqué", "communique", "annonce officielle",
        "a annoncé", "a annonce", "nommé", "nomme", "prolonge jusqu", "prolongation officialisée",
    )),
    ("Blessures", (
        "blessure", "blessé", "blesse", "forfait", "indisponible", "absent", "opéré",
        "opere", "touché", "touche", "suspendu", "suspension",
    )),
    ("Mercato", (
        "mercato", "transfert", "recrut", "signature", "signe ", "prêt ", "prete ",
        "accord", "offre pour", "négoci", "negoci", "clause", "prolong", "départ",
        "depart", "arrivée", "arrivee",
    )),
    ("Déclarations", (
        "déclare", "declare", "conférence de presse", "conference de presse", "répond",
        "repond", "explique", "confie", "assure", "selon lui", "a indiqué", "a indique",
        "estime", "avoue", "prévient", "previent", "encense", "critique",
    )),
    ("Convocations", (
        "convoqué", "convoque", "convocation", "liste de", "groupe pour", "sélectionné",
        "selectionne", "retenu pour", "appelé", "appele",
    )),
    ("Polémique", (
        "polémique", "polemique", "scandale", "controverse", "tension", "incident",
        "sanction", "accus", "colère", "colere", "attaque ", "recadre",
    )),
    ("Afrique", (
        "afrique", "caf ", " can ", "afcon", "sénégal", "senegal", "togo", "maroc",
        "algérie", "algerie", "tunisie", "côte d'ivoire", "cote d'ivoire", "ghana",
        "nigeria", "cameroun", "mali", "burkina",
    )),
    ("Matchs", (
        "match", "score", "victoire", "défaite", "defaite", "nul ", "but ", "mi-temps",
        "composition", "compo", "onze de départ", "coup d'envoi", "qualifié", "qualifie",
    )),
    ("Compétitions", (
        "champions league", "ligue des champions", "europa league", "conference league",
        "coupe du monde", "mondial", "premier league", "ligue 1", "liga", "serie a",
        "bundesliga",
    )),
)

CATEGORY_EMOJI = {
    "Officiel": "✅",
    "Blessures": "🚑",
    "Mercato": "🚨",
    "Déclarations": "🗣️",
    "Convocations": "📋",
    "Polémique": "🔥",
    "Afrique": "🌍",
    "Matchs": "⚽",
    "Compétitions": "🏆",
    "Actualité": "🚨",
}


def strip_accents(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()


def compact_spaces(value: str) -> str:
    return re.sub(r"[ \t\r\f\v]+", " ", value or "").strip()


def clean_rich_text(raw: str) -> str:
    """Nettoie le HTML RSS en conservant les séparations de paragraphes."""
    if not raw:
        return ""
    text = html.unescape(str(raw))
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?i)</(?:div|li|h[1-6])\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    lines = [compact_spaces(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def normalize_title(value: str) -> str:
    value = strip_accents(value).lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def source_profile(feed_url: str, feed_title: str = "") -> SourceProfile:
    host = (urlparse(feed_url).hostname or "").lower()
    if host in SOURCE_PROFILES:
        profile = SOURCE_PROFILES[host]
        if host.endswith("rfi.fr") and "afrique" in feed_url:
            return SourceProfile("RFI Afrique Foot", 90, "afrique")
        return profile
    label = compact_spaces(feed_title)[:70] or host or "Source football"
    return SourceProfile(label, 70)


def classify_news(title: str, text: str, feed_url: str = "") -> tuple[str, int]:
    corpus = strip_accents(f"{title} {text}").lower()
    scores: dict[str, int] = {}
    for category, words in CATEGORY_RULES:
        hits = sum(1 for word in words if strip_accents(word).lower() in corpus)
        if hits:
            scores[category] = hits
    if "rfi.fr/fr/afrique-foot/" in feed_url:
        scores["Afrique"] = scores.get("Afrique", 0) + 2
    category = max(scores, key=lambda name: (scores[name], name)) if scores else "Actualité"
    editorial_score = 1 + min(3, max(scores.values(), default=0))
    if len(text) >= 180:
        editorial_score += 1
    return category, editorial_score


def sentence_list(text: str) -> list[str]:
    value = re.sub(r"\s*\n+\s*", " ", text or "").strip()
    if not value:
        return []
    parts = re.split(r"(?<=[.!?…])\s+(?=[A-ZÀÂÇÉÈÊËÎÏÔÙÛÜŸŒ0-9«“])", value)
    return [compact_spaces(part) for part in parts if compact_spaces(part)]


def short_summary(text: str, max_chars: int = 380) -> str:
    sentences = sentence_list(text)
    if not sentences:
        return ""
    selected: list[str] = []
    for sentence in sentences[:3]:
        candidate = " ".join(selected + [sentence]).strip()
        if selected and len(candidate) > max_chars:
            break
        selected.append(sentence)
        if len(candidate) >= 180:
            break
    result = " ".join(selected).strip()
    if len(result) > max_chars:
        result = result[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    return result


def key_points(text: str, limit: int = 4) -> list[str]:
    out: list[str] = []
    seen = set()
    for sentence in sentence_list(text):
        clean = sentence.strip(" •-\t")
        key = normalize_title(clean)
        if len(clean) < 35 or not key or key in seen:
            continue
        seen.add(key)
        out.append(clean[:260].rstrip())
        if len(out) >= limit:
            break
    return out


def paragraphs(text: str) -> list[str]:
    """Transforme la description du flux en paragraphes lisibles, sans ajouter de faits."""
    raw_blocks = [compact_spaces(x) for x in re.split(r"\n{2,}", text or "") if compact_spaces(x)]
    if len(raw_blocks) > 1:
        return raw_blocks[:8]
    sentences = sentence_list(text)
    if not sentences:
        return []
    blocks, current = [], []
    for sentence in sentences:
        current.append(sentence)
        if len(" ".join(current)) >= 360 or len(current) >= 3:
            blocks.append(" ".join(current))
            current = []
    if current:
        blocks.append(" ".join(current))
    return blocks[:8]


def feed_entry_text(entry) -> str:
    candidates = [
        entry.get("summary"),
        entry.get("description"),
    ]
    content = entry.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                candidates.append(item.get("value"))
    cleaned = [clean_rich_text(x) for x in candidates if x]
    # Conserver le texte le plus informatif fourni par le RSS.
    return max(cleaned, key=len, default="")


def extract_entry_image(entry) -> str:
    for enc in entry.get("enclosures") or []:
        if not isinstance(enc, dict):
            continue
        url = enc.get("href") or enc.get("url")
        typ = str(enc.get("type") or "").lower()
        if url and (typ.startswith("image/") or re.search(r"\.(?:jpe?g|png|webp)(?:\?|$)", url, re.I)):
            return str(url)
    for key in ("media_content", "media_thumbnail"):
        items = entry.get(key) or []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("url"):
                    return str(item["url"])
    raw = str(entry.get("summary") or entry.get("description") or "")
    match = re.search(r'<img[^>]+src=["\']([^"\']+)', raw, re.I)
    return html.unescape(match.group(1)).strip() if match else ""


def fetch_open_graph(session: requests.Session, url: str, timeout: int = 18) -> dict[str, str]:
    """Fallback métadonnées : aucune extraction du corps complet de l'article."""
    try:
        response = session.get(
            url,
            timeout=(7, timeout),
            headers={"User-Agent": "Mozilla/5.0 (compatible; MrXPRONOS-NewsBot/3.0; +https://mrxpronos.github.io/MrXPRONOS_App/)"},
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException:
        return {}
    page = response.text[:1_500_000]
    result: dict[str, str] = {}
    patterns = {
        "image": (
            r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::secure_url)?["\']',
            r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)',
        ),
        "description": (
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']',
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
        ),
    }
    for field, rules in patterns.items():
        for pattern in rules:
            match = re.search(pattern, page, re.I)
            if match:
                value = html.unescape(match.group(1)).strip()
                if value:
                    result[field] = value
                    break
    return result


def _background_cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def prepare_real_image(raw: bytes, out: Path, size: tuple[int, int] = (1200, 675)) -> str:
    """Rend l'image source en 16:9. Fond flou quand un crop brutal couperait trop l'image."""
    with Image.open(io.BytesIO(raw)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    if image.width < 180 or image.height < 120:
        raise ValueError("image source trop petite")

    target_ratio = size[0] / size[1]
    ratio = image.width / image.height
    # Un écart supérieur à ~24 % utilise contain + arrière-plan flouté.
    if ratio < target_ratio * 0.76 or ratio > target_ratio * 1.24:
        background = _background_cover(image, size).filter(ImageFilter.GaussianBlur(34))
        overlay = Image.new("RGB", size, (0, 0, 0))
        overlay.putalpha if False else None
        # Légère assombrissement pour que l'image centrale soit bien lisible.
        dark = Image.new("RGB", size, (18, 22, 26))
        background = Image.blend(background, dark, 0.24)
        foreground = ImageOps.contain(image, (size[0] - 56, size[1] - 34), method=Image.Resampling.LANCZOS)
        x = (size[0] - foreground.width) // 2
        y = (size[1] - foreground.height) // 2
        background.paste(foreground, (x, y))
        rendered = background
        mode = "blur-contain"
    else:
        rendered = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.46))
        mode = "smart-crop"

    out.parent.mkdir(parents=True, exist_ok=True)
    rendered.save(out, "WEBP", quality=88, method=6)
    return mode


def download_real_image(
    session: requests.Session,
    url: str,
    slug: str,
    *,
    root: Path = ROOT,
    timeout: int = 22,
) -> tuple[str, str]:
    if not url.startswith(("https://", "http://")):
        return "", ""
    try:
        response = session.get(
            url,
            timeout=(7, timeout),
            headers={"User-Agent": "Mozilla/5.0 MrXPRONOS-NewsBot/3.0", "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"},
            stream=True,
            allow_redirects=True,
        )
        response.raise_for_status()
        content_type = str(response.headers.get("content-type") or "").lower()
        if "image/" not in content_type:
            return "", ""
        raw = bytearray()
        for chunk in response.iter_content(65536):
            raw.extend(chunk)
            if len(raw) > 12_000_000:
                raise ValueError("image source supérieure à 12 Mo")
    except (requests.RequestException, ValueError):
        return "", ""

    relative = Path("assets") / "images" / "footnews" / f"{slug}.webp"
    absolute = root / relative
    try:
        mode = prepare_real_image(bytes(raw), absolute)
        return relative.as_posix(), mode
    except (OSError, ValueError):
        try:
            absolute.unlink(missing_ok=True)
        except OSError:
            pass
        return "", ""


def site_url(slug: str) -> str:
    return SITE_BASE + "infos.html?news=" + slug


def build_news_record(
    *,
    slug: str,
    title: str,
    body: str,
    link: str,
    published: str,
    source: SourceProfile,
    feed_url: str,
    image_path: str,
    source_image: str,
    image_mode: str,
    category: str,
    editorial_score: int,
) -> dict:
    body = clean_rich_text(body)
    short = short_summary(body)
    points = key_points(body)
    article_blocks = paragraphs(body)
    return {
        "slug": slug,
        "title": compact_spaces(title),
        "summary": short,
        "summary_short": short,
        "content": body,
        "paragraphs": article_blocks,
        "key_points": points,
        "telegram_summary": short_summary(body, 330),
        "link": link,
        "source_url": link,
        "site_url": site_url(slug),
        "published": published,
        "image": image_path,
        "source_image": source_image,
        "image_origin": "source" if image_path else "missing",
        "image_layout": image_mode,
        "source": source.name,
        "source_priority": source.priority,
        "source_region": source.region,
        "source_feed": feed_url,
        "category": category,
        "category_emoji": CATEGORY_EMOJI.get(category, "🚨"),
        "editorial_score": editorial_score,
    }


def cleanup_orphan_images(records: list[dict], root: Path = ROOT) -> int:
    folder = root / "assets" / "images" / "footnews"
    if not folder.exists():
        return 0
    keep = {
        str((root / str(item.get("image") or "")).resolve())
        for item in records
        if str(item.get("image") or "").startswith("assets/images/footnews/")
    }
    removed = 0
    for path in folder.glob("*.webp"):
        if str(path.resolve()) not in keep:
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return removed
