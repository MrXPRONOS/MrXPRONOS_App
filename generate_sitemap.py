#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_sitemap.py - Génère sitemap.xml et sitemap.txt avec priorités SEO
"""

import json
import os
from datetime import datetime

BASE_URL = "https://mrxpronos.github.io/MrXPRONOS_App"

# Priorités et fréquences pour chaque page statique
STATIC_PAGES = {
    "": {"priority": "1.0", "freq": "daily"},          # Accueil
    "pronos.html": {"priority": "0.9", "freq": "daily"},
    "historique.html": {"priority": "0.8", "freq": "weekly"},
    "blog.html": {"priority": "0.8", "freq": "weekly"},
    "conseils.html": {"priority": "0.7", "freq": "monthly"},
    "infos.html": {"priority": "0.6", "freq": "monthly"},
    "bonus.html": {"priority": "0.6", "freq": "monthly"},
    "contact.html": {"priority": "0.5", "freq": "yearly"}
}

def generate_sitemap():
    urls = []
    today = datetime.utcnow().date().isoformat()  # Date du jour pour lastmod

    # Pages statiques
    for page, data in STATIC_PAGES.items():
        loc = BASE_URL if page == "" else f"{BASE_URL}/{page}"
        urls.append({
            "loc": loc,
            "priority": data["priority"],
            "freq": data["freq"]
        })

    # Articles depuis articles.json
    if os.path.exists("articles.json"):
        with open("articles.json", "r", encoding="utf-8") as f:
            articles = json.load(f)
            for article in articles:
                urls.append({
                    "loc": f"{BASE_URL}/article.html?slug={article['slug']}",
                    "priority": "0.6",
                    "freq": "monthly"
                })

    # Écriture du sitemap XML
    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for url in urls:
            f.write("  <url>\n")
            f.write(f"    <loc>{url['loc']}</loc>\n")
            f.write(f"    <lastmod>{today}</lastmod>\n")
            f.write(f"    <changefreq>{url['freq']}</changefreq>\n")
            f.write(f"    <priority>{url['priority']}</priority>\n")
            f.write("  </url>\n")
        f.write("</urlset>\n")
    print("✅ sitemap.xml généré")

    # Écriture du sitemap texte
    with open("sitemap.txt", "w", encoding="utf-8") as f:
        for url in urls:
            f.write(url["loc"] + "\n")
    print("✅ sitemap.txt généré")

if __name__ == "__main__":
    generate_sitemap()