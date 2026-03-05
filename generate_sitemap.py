#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_sitemap.py - Génère le sitemap.xml à partir des pages statiques et des articles.
Exécution quotidienne. 
"""

import json
from datetime import datetime

BASE_URL = "https://mrxpronos.github.io/MrXPRONOS_App"  # À modifier si nécessaire

def generate_sitemap():
    urls = []

    # Pages statiques
    static_pages = [
        "",
        "index.html",
        "pronos.html",
        "historique.html",
        "blog.html",
        "conseils.html",
        "infos.html",
        "bonus.html",
        "contact.html"
    ]
    for page in static_pages:
        urls.append(f"{BASE_URL}/{page}")

    # Articles
    try:
        with open("articles.json", "r", encoding="utf-8") as f:
            articles = json.load(f)
            for article in articles:
                urls.append(f"{BASE_URL}/article.html?slug={article['slug']}")
    except FileNotFoundError:
        pass

    # Écriture du sitemap
    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for url in urls:
            f.write('  <url>\n')
            f.write(f'    <loc>{url}</loc>\n')
            f.write(f'    <lastmod>{datetime.now().date()}</lastmod>\n')
            f.write('    <changefreq>weekly</changefreq>\n')
            f.write('    <priority>0.8</priority>\n')
            f.write('  </url>\n')
        f.write('</urlset>\n')
    print("✅ sitemap.xml généré")

if __name__ == "__main__":
    generate_sitemap()