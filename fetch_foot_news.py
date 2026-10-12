#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fetch_foot_news.py - Récupère les dernières actualités football depuis un flux RSS,
(optionnel) traduit en français et les sauvegarde dans footnews.json.
"""

import os
import json
import feedparser
import requests
import logging
import re
import time
import hashlib
import unicodedata
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from deep_translator import GoogleTranslator

# Configuration
DEFAULT_RSS_FEED = "https://madeinfoot.ouest-france.fr/flux/rss_news.php"
RSS_FEED = (os.getenv("FOOTBALL_RSS_FEED") or DEFAULT_RSS_FEED).strip()
NEWS_FILE = "footnews.json"
MAX_ARTICLES = int(os.getenv("MAX_ARTICLES", "20"))
# Plusieurs flux FR libres à consulter (titres, courts résumés et liens uniquement).
EXTRA_RSS_FEEDS = [x.strip() for x in os.getenv("EXTRA_FOOTBALL_RSS_FEEDS", "https://www.france24.com/fr/tag/football/rss,https://www.footmercato.net/flux-rss").split(",") if x.strip()]
MAX_NEWS_AGE_HOURS = max(12, int(os.getenv("MAX_NEWS_AGE_HOURS", "96")))
RSS_TIMEOUT = max(3, int(os.getenv("RSS_TIMEOUT", "18")))

# Traduction:
# - "auto" (défaut): traduit seulement lorsque le flux / texte n'est pas français.
# - "1"/"true"/"on": force la traduction.
# - "0"/"false"/"off": désactive la traduction.
TRANSLATION_MODE = (os.getenv("ENABLE_TRANSLATION", "auto") or "auto").strip().lower()
TRANSLATION_RETRIES = max(1, int(os.getenv("TRANSLATION_RETRIES", "2")))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def clean_html(raw: str) -> str:
    if not raw:
        return ""
    clean = re.sub(r"<[^>]+>", "", raw)
    return clean.strip()

def to_iso_date(entry) -> str:
    """
    Essaie de sortir une date ISO à partir de published/published_parsed (RSS pubDate).
    """
    # feedparser fournit souvent published_parsed (struct_time)
    if entry.get("published_parsed"):
        try:
            dt = datetime(*entry.published_parsed[:6])
            return dt.isoformat()
        except Exception:
            pass

    raw = entry.get("published") or entry.get("pubDate") or entry.get("updated")
    if raw:
        try:
            return parsedate_to_datetime(raw).isoformat()
        except Exception:
            return str(raw)

    return datetime.now().isoformat()

def _word_hits(text: str, words: set[str]) -> int:
    tokens = re.findall(r"[a-zàâçéèêëîïôûùüÿœ'-]+", (text or "").lower())
    return sum(1 for token in tokens if token in words)

def looks_english(text: str) -> bool:
    """Heuristique légère: suffit pour éviter de republier un flux BBC brut."""
    if not text:
        return False
    en_words = {
        "the", "and", "with", "after", "before", "from", "for", "but", "not",
        "have", "has", "are", "was", "were", "will", "their", "his", "her",
        "who", "what", "how", "why", "against", "during", "player", "players",
        "club", "clubs", "football", "league", "win", "wins", "game", "games"
    }
    fr_words = {
        "le", "la", "les", "des", "du", "de", "et", "avec", "après", "avant",
        "pour", "mais", "pas", "est", "sont", "dans", "leur", "leurs", "qui",
        "que", "quoi", "comment", "contre", "pendant", "joueur", "joueurs",
        "club", "clubs", "football", "ligue", "match", "matchs"
    }
    en = _word_hits(text, en_words)
    fr = _word_hits(text, fr_words)
    return en >= 2 and en > fr

def should_translate(text: str, feed_language: str = "") -> bool:
    mode = TRANSLATION_MODE
    if mode in {"1", "true", "yes", "on", "force"}:
        return True
    if mode in {"0", "false", "no", "off"}:
        return False

    lang = (feed_language or "").strip().lower()
    if lang.startswith("fr"):
        return False
    # Si le flux annonce explicitement une langue non-française (ex: en-gb),
    # on traduit systématiquement, même pour un titre très court.
    if lang:
        return True
    return looks_english(text)

def translate_text(text: str, dest: str = "fr", feed_language: str = "") -> str:
    if not text:
        return ""
    if not should_translate(text, feed_language):
        return text

    last_error = None
    for attempt in range(1, TRANSLATION_RETRIES + 1):
        try:
            # Google limite la fréquence. 0,35 s garde le workflow sous ~3 req/s,
            # bien en dessous de la limite annoncée de 5 req/s.
            time.sleep(0.35 if attempt == 1 else 1.5 * attempt)
            translated = GoogleTranslator(source="auto", target=dest).translate(text)
            if translated and translated.strip():
                translated = translated.strip()
                return translated
        except Exception as e:
            last_error = e
            logger.warning("Erreur de traduction (tentative %s/%s): %s", attempt, TRANSLATION_RETRIES, e)

    if last_error:
        logger.error("Traduction impossible après %s tentative(s): %s", TRANSLATION_RETRIES, last_error)
    return ""

def extract_image_url(entry):
    # MadeInFoot met l'image dans <enclosure url="...">
    if entry.get("enclosures"):
        for enc in entry.enclosures:
            url = enc.get("href") or enc.get("url")
            typ = (enc.get("type") or "").lower()
            if url and (typ.startswith("image/") or url.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))):
                return url

    # Fallbacks génériques (au cas où)
    if "media_content" in entry and entry.media_content:
        return entry.media_content[0].get("url")
    if "media_thumbnail" in entry and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url")

    # Dernier fallback: chercher <img src="..."> dans summary/description
    html = entry.get("summary", "") or entry.get("description", "")
    match = re.search(r'<img[^>]+src="([^">]+)"', html)
    return match.group(1) if match else None

def _normalized_key(title: str) -> str:
    value = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def classify_news(title: str, summary: str) -> tuple[str, int]:
    text = (title + " " + summary).lower()
    categories = [
        ("Mercato", ("transfert", "mercato", "recrut", "signature", "prêt ")),
        ("Afrique", ("afrique", "caf ", "can ", "ligue des champions caf")),
        ("Matchs", ("match", "score", "victoire", "but ", "défaite")),
        ("Compétitions", ("champions league", "ligue des champions", "coupe du monde")),
    ]
    category = next((cat for cat, keywords in categories if any(k in text for k in keywords)), "Actualité")
    score = 2 if category != "Actualité" else 1
    if len(summary) >= 65: score += 1
    return category, score


def fetch_news():
    feeds = [RSS_FEED] + [url for url in EXTRA_RSS_FEEDS if url != RSS_FEED]
    articles, seen_links, seen_titles = [], set(), set()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_NEWS_AGE_HOURS)
    diagnostics = {"feeds": {}, "rejected_stale": 0, "rejected_duplicate": 0}
    for feed_url in feeds:
        logger.info("Récupération du flux : %s", feed_url)
        try:
            response = requests.get(feed_url, timeout=RSS_TIMEOUT, headers={"User-Agent":"MrXPRONOS-NewsBot/2.0 RSS Reader"})
            response.raise_for_status()
            feed = feedparser.parse(response.content)
        except Exception as exc:
            logger.warning("Flux indisponible %s : %s", feed_url, exc)
            diagnostics["feeds"][feed_url] = "unavailable"
            continue
        if not feed.entries:
            logger.warning("Flux vide: %s", feed_url)
            diagnostics["feeds"][feed_url] = "empty"
            continue
        diagnostics["feeds"][feed_url] = len(feed.entries)
        feed_language = str(feed.feed.get("language") or "").strip()
        source = str(feed.feed.get("title") or urlparse(feed_url).netloc)[:90]
        for entry in feed.entries[:max(MAX_ARTICLES, 25)]:
            title = str(entry.get("title") or "").strip()
            link = str(entry.get("link") or "").strip()
            summary = clean_html(entry.get("summary") or entry.get("description") or "")
            if not title or not link.startswith("https://"):
                continue
            norm = _normalized_key(title)
            if not norm or norm in seen_titles or link in seen_links:
                diagnostics["rejected_duplicate"] += 1
                continue
            raw_date = to_iso_date(entry)
            try:
                parsed = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
                if parsed < cutoff or parsed > now + timedelta(hours=3):
                    diagnostics["rejected_stale"] += 1
                    continue
            except (TypeError, ValueError):
                continue
            translated_title = translate_text(title, feed_language=feed_language)
            translated_summary = translate_text(summary, feed_language=feed_language)
            if not translated_title or summary and not translated_summary:
                continue
            if looks_english(translated_title + " " + translated_summary):
                continue
            category,score=classify_news(translated_title,translated_summary)
            seen_links.add(link);seen_titles.add(norm)
            articles.append({
                "slug": hashlib.sha1(link.encode()).hexdigest()[:16],
                "title": translated_title,
                "summary": translated_summary[:380],
                "link": link,
                "published": raw_date,
                "image": "assets/images/preview.jpg",
                "source_image": extract_image_url(entry),
                "source": source,
                "category": category,
                "editorial_score": score
            })
    articles.sort(key=lambda x: (x.get("editorial_score",0),x.get("published","")),reverse=True)
    result=articles[:MAX_ARTICLES]
    logger.info("%s actualités uniques depuis %s flux ; diagnostic %s",len(result),len(feeds),json.dumps(diagnostics,ensure_ascii=False))
    return result

def save_news(articles):
    """Conserve les métadonnées des images locales entre deux actualisations RSS."""
    old_by_link = {}
    try:
        old_data = json.loads(open(NEWS_FILE, encoding="utf-8").read())
        if isinstance(old_data, list):
            old_by_link = {x.get("link"): x for x in old_data if isinstance(x,dict) and x.get("link")}
    except (OSError, ValueError):
        pass
    preservable = ("image_url", "og_image", "social_image", "story_image",
                   "visual_variant", "visual_hash", "visual_format")
    for item in articles:
        previous = old_by_link.get(item["link"]) or {}
        for key in preservable:
            if previous.get(key): item[key] = previous[key]
        if item.get("image_url", "").startswith("assets/images/editorial/"):
            item["image"] = item["image_url"]
    # Le rapport du flux n'est pas diffusé directement; le JSON conserve les liens sources.
    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
        f.write("\n")
    logger.info("%s actualités sauvegardées, images locales préservées",len(articles))

def main():
    articles = fetch_news()
    if articles:
        save_news(articles)
    else:
        logger.warning("Aucun article récupéré.")

if __name__ == "__main__":
    main()