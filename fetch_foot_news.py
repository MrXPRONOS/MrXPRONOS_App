#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fetch_foot_news.py - Récupère les dernières actualités football depuis un flux RSS,
les traduit en français et les sauvegarde dans footnews.json.
Exécution quotidienne (ou plus fréquente) via GitHub Actions.
"""

import os
import json
import feedparser
import logging
import re
from datetime import datetime
from deep_translator import GoogleTranslator

# Configuration
RSS_FEED = os.getenv("FOOTBALL_RSS_FEED", "https://www.theguardian.com/football/rss")  # À remplacer par un flux valide
NEWS_FILE = "footnews.json"
MAX_ARTICLES = 20  # Nombre max d'articles à conserver

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def clean_html(raw):
    """Supprime les balises HTML basiques."""
    if not raw:
        return ""
    clean = re.sub(r'<[^>]+>', '', raw)
    return clean.strip()

def translate_text(text, dest="fr"):
    """Traduit un texte en français via Google Translate."""
    if not text:
        return ""
    try:
        return GoogleTranslator(source="auto", target=dest).translate(text)
    except Exception as e:
        logger.error(f"Erreur de traduction : {e}")
        return text

def fetch_news():
    """Récupère les articles depuis le flux RSS."""
    logger.info(f"Récupération du flux : {RSS_FEED}")
    feed = feedparser.parse(RSS_FEED)
    if feed.bozo:
        logger.warning(f"Erreur de parsing : {feed.bozo_exception}")
    articles = []
    for entry in feed.entries[:MAX_ARTICLES]:
        # Extraire les champs
        title = entry.get("title", "")
        link = entry.get("link", "")
        published = entry.get("published", datetime.now().isoformat())
        summary = clean_html(entry.get("summary", ""))
        # Traduire titre et résumé
        title_fr = translate_text(title)
        summary_fr = translate_text(summary)
        # Extraire une image (si disponible)
        image_url = None
        if "media_content" in entry:
            image_url = entry.media_content[0].get("url")
        elif "media_thumbnail" in entry:
            image_url = entry.media_thumbnail[0].get("url")
        else:
            # Chercher une image dans le résumé HTML (approximatif)
            match = re.search(r'<img[^>]+src="([^">]+)"', entry.get("summary", ""))
            if match:
                image_url = match.group(1)

        articles.append({
            "title": title_fr,
            "summary": summary_fr,
            "link": link,
            "published": published,
            "image": image_url
        })
    logger.info(f"{len(articles)} articles récupérés")
    return articles

def save_news(articles):
    """Sauvegarde les articles dans un fichier JSON."""
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