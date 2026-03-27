#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_sitemap.py - Génère sitemap.xml et sitemap.txt avec priorités SEO

Améliorations:
- URLs articles en article.html?slug=...
- URLs conseils en conseil.html?slug=...
- ignore les contenus inactive (active=false)
- lastmod par contenu (date/published_at), sinon today
- URL racine avec slash final
"""

import json
import os
from datetime import datetime

BASE_URL = "https://mrxpronos.github.io/MrXPRONOS_App/"

STATIC_PAGES = {
    "": {"priority": "1.0", "freq": "daily"},
    "pronos.html": {"priority": "0.9", "freq": "daily"},
    "historique.html": {"priority": "0.8", "freq": "weekly"},
    "blog.html": {"priority": "0.8", "freq": "daily"},
    "conseils.html": {"priority": "0.7", "freq": "daily"},
    "infos.html": {"priority": "0.6", "freq": "daily"},
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

def load_json_file(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return json.loads(content) if content else default
    except Exception:
        return default

def append_static_pages(urls, today):
    for page, meta in STATIC_PAGES.items():
        loc = BASE_URL if page == "" else f"{BASE_URL}{page}"
        urls.append({
            "loc": loc,
            "priority": meta["priority"],
            "freq": meta["freq"],
            "lastmod": today
        })

def append_articles(urls, today):
    articles = load_json_file("articles.json", [])
    if not isinstance(articles, list):
        return

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

def append_conseils(urls, today):
    conseils = load_json_file("conseils.json", [])
    if not isinstance(conseils, list):
        return

    for conseil in conseils:
        if not isinstance(conseil, dict):
            continue
        if conseil.get("active") is False:
            continue

        slug = (conseil.get("slug") or "").strip()
        if not slug:
            continue

        lastmod = safe_lastmod(conseil.get("date") or conseil.get("published_at"), today)

        urls.append({
            "loc": f"{BASE_URL}conseil.html?slug={slug}",
            "priority": "0.55",
            "freq": "monthly",
            "lastmod": lastmod
        })

def write_sitemap_xml(urls):
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

def write_sitemap_txt(urls):
    with open("sitemap.txt", "w", encoding="utf-8") as f:
        for url in urls:
            f.write(url["loc"] + "\n")

def generate_sitemap():
    urls = []
    today = datetime.utcnow().date().isoformat()

    append_static_pages(urls, today)
    append_articles(urls, today)
    append_conseils(urls, today)

    write_sitemap_xml(urls)
    write_sitemap_txt(urls)

    print("✅ sitemap.xml généré")
    print("✅ sitemap.txt généré")
    print(f"✅ Total URLs: {len(urls)}")

if __name__ == "__main__":
    generate_sitemap()