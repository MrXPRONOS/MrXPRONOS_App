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

# Flux MadeInFoot = déjà FR => traduction off par défaut
ENABLE_TRANSLATION = os.getenv("ENABLE_TRANSLATION", "0") == "1"

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

def translate_text(text: str, dest: str = "fr") -> str:
    if not text:
        return ""
    if not ENABLE_TRANSLATION:
        return text
    try:
        return GoogleTranslator(source="auto", target=dest).translate(text)
    except Exception as e:
        logger.error(f"Erreur de traduction : {e}")
        return text

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

    articles = []
    for entry in feed.entries[:MAX_ARTICLES]:
        title = entry.get("title", "")
        link = entry.get("link", "")

        # MadeInFoot utilise <description> (feedparser le map souvent sur summary)
        summary_raw = entry.get("summary", "") or entry.get("description", "")
        summary = clean_html(summary_raw)

        published = to_iso_date(entry)
        image_url = extract_image_url(entry)

        articles.append({
            "title": translate_text(title),
            "summary": translate_text(summary),
            "link": link,
            "published": published,
            "image": image_url
        })

    logger.info(f"{len(articles)} articles récupérés")
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