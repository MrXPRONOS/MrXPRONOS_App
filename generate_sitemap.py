#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_sitemap.py - Génère sitemap.xml et sitemap.txt avec priorités SEO
Améliorations:
- URLs articles en article.html?slug=...
- ignore les articles inactive (active=false)
- lastmod par article (date/published_at), sinon today
- URL racine avec slash final
"""

import json
import os
from datetime import datetime

BASE_URL = "https://mrxpronos.github.io/MrXPRONOS_App/"

STATIC_PAGES = {
    "": {"priority": "1.0", "freq": "daily"},  # Accueil
    "pronos.html": {"priority": "0.9", "freq": "daily"},
    "historique.html": {"priority": "0.8", "freq": "weekly"},
    "blog.html": {"priority": "0.8", "freq": "weekly"},
    "conseils.html": {"priority": "0.7", "freq": "monthly"},
    "infos.html": {"priority": "0.6", "freq": "monthly"},
    "bonus.html": {"priority": "0.6", "freq": "monthly"},
    "contact.html": {"priority": "0.5", "freq": "yearly"},
}

def safe_lastmod(date_str: str, fallback: str) -> str:
    if not date_str:
        return fallback
    try:
        return str(date_str)[:10]
    except Exception:
        return fallback

def generate_sitemap():
    urls = []
    today = datetime.utcnow().date().isoformat()

    # Pages statiques
    for page, meta in STATIC_PAGES.items():
        loc = BASE_URL if page == "" else f"{BASE_URL}{page}"
        urls.append({
            "loc": loc,
            "priority": meta["priority"],
            "freq": meta["freq"],
            "lastmod": today
        })

    # Articles depuis articles.json
    articles = []
    if os.path.exists("articles.json"):
        try:
            with open("articles.json", "r", encoding="utf-8") as f:
                content = f.read().strip()
            articles = json.loads(content) if content else []
        except Exception:
            articles = []

    if isinstance(articles, list):
        for article in articles:
            if not isinstance(article, dict):
                continue
            if article.get("active") is False:
                continue

            slug = (article.get("slug") or "").strip()
            if not slug:
                continue

            lastmod = safe_lastmod(article.get("date") or article.get("published_at"), today)

            urls.append({
                "loc": f"{BASE_URL}article.html?slug={slug}",
                "priority": "0.6",
                "freq": "monthly",
                "lastmod": lastmod
            })

    # Écriture sitemap.xml
    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for url in urls:
            f.write("  <url>\n")
            f.write(f"    <loc>{url['loc']}</loc>\n")
            f.write(f"    <lastmod>{url['lastmod']}</lastmod>\n")
            f.write(f"    <changefreq>{url['freq']}</changefreq>\n")
            f.write(f"    <priority>{url['priority']}</priority>\n")
            f.write("  </url>\n")
        f.write("</urlset>\n")

    print("✅ sitemap.xml généré")

    # Écriture sitemap.txt
    with open("sitemap.txt", "w", encoding="utf-8") as f:
        for url in urls:
            f.write(url["loc"] + "\n")

    print("✅ sitemap.txt généré")

if __name__ == "__main__":
    generate_sitemap()