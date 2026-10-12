#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fetch_foot_news.py - Récupère les dernières actualités football depuis un flux RSS,
(optionnel) traduit en français et les sauvegarde dans footnews.json.
"""

import os
import json
import feedparser
import logging
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from deep_translator import GoogleTranslator

# Configuration
RSS_FEED = os.getenv("FOOTBALL_RSS_FEED", "https://madeinfoot.ouest-france.fr/flux/rss_news.php")
NEWS_FILE = "footnews.json"
MAX_ARTICLES = int(os.getenv("MAX_ARTICLES", "20"))

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
    lang = (feed_language or "").lower()
    if lang.startswith("fr"):
        return False
    return looks_english(text)

def translate_text(text: str, dest: str = "fr", feed_language: str = "") -> str:
    if not text:
        return ""
    if not should_translate(text, feed_language):
        return text

    last_error = None
    for attempt in range(1, TRANSLATION_RETRIES + 1):
        try:
            translated = GoogleTranslator(source="auto", target=dest).translate(text)
            if translated and translated.strip():
                translated = translated.strip()
                # Ne jamais republier silencieusement un texte encore clairement anglais.
                if not looks_english(translated):
                    return translated
                logger.warning("Traduction encore détectée en anglais (tentative %s/%s)", attempt, TRANSLATION_RETRIES)
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

def fetch_news():
    logger.info(f"Récupération du flux : {RSS_FEED}")

    feed = feedparser.parse(RSS_FEED)
    if feed.bozo:
        logger.warning(f"Erreur de parsing : {feed.bozo_exception}")

    feed_language = str(feed.feed.get("language") or "").strip()
    logger.info("Langue déclarée du flux: %s | mode traduction: %s", feed_language or "inconnue", TRANSLATION_MODE)

    articles = []
    for entry in feed.entries[:MAX_ARTICLES]:
        title = entry.get("title", "")
        link = entry.get("link", "")

        # MadeInFoot utilise <description> (feedparser le map souvent sur summary)
        summary_raw = entry.get("summary", "") or entry.get("description", "")
        summary = clean_html(summary_raw)

        published = to_iso_date(entry)
        image_url = extract_image_url(entry)

        translated_title = translate_text(title, feed_language=feed_language)
        translated_summary = translate_text(summary, feed_language=feed_language)

        # Si un flux anglais n'a pas pu être traduit, on préfère ignorer l'article
        # plutôt que de casser l'expérience francophone du site.
        if not translated_title:
            logger.warning("Article ignoré: titre non francisé: %s", title[:120])
            continue
        if summary and not translated_summary:
            logger.warning("Article ignoré: résumé non francisé: %s", title[:120])
            continue

        articles.append({
            "title": translated_title,
            "summary": translated_summary,
            "link": link,
            "published": published,
            "image": image_url
        })

    logger.info("%s articles francophones récupérés", len(articles))
    return articles

def save_news(articles):
    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
    logger.info(f"Articles sauvegardés dans {NEWS_FILE}")

def main():
    articles = fetch_news()
    if articles:
        save_news(articles)
    else:
        logger.warning("Aucun article récupéré.")

if __name__ == "__main__":
    main()