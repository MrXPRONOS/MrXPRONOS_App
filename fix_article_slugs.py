#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fix_article_slugs.py

Corrige les slugs de :
- articles.json
- conseils.json

Fonctionnalités :
- supprime proprement les accents (é -> e, ó -> o, ü -> u)
- normalise les caractères spéciaux
- évite les doublons de slug
- crée des backups avant modification
"""

import os
import re
import json
import shutil
import unicodedata
from datetime import datetime

ARTICLES_FILE = "articles.json"
CONSEILS_FILE = "conseils.json"

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return json.loads(content) if content else default
    except Exception as e:
        print(f"⚠️ Impossible de lire {path}: {e}")
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def backup_file(path):
    if not os.path.exists(path):
        return None
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{path}.bak-{timestamp}"
    shutil.copy2(path, backup_path)
    print(f"💾 Backup créé: {backup_path}")
    return backup_path

def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:90] or "post"

def make_unique_slug(base_slug: str, used_slugs: set) -> str:
    slug = base_slug or "post"
    if slug not in used_slugs:
        used_slugs.add(slug)
        return slug

    i = 2
    while True:
        candidate = f"{slug}-{i}"
        if candidate not in used_slugs:
            used_slugs.add(candidate)
            return candidate
        i += 1

def fix_articles():
    articles = load_json(ARTICLES_FILE, [])
    if not isinstance(articles, list):
        print("⚠️ articles.json invalide")
        return

    backup_file(ARTICLES_FILE)

    used_slugs = set()
    updated = 0

    for article in articles:
        if not isinstance(article, dict):
            continue

        title = article.get("title") or article.get("match") or "article"
        old_slug = (article.get("slug") or "").strip()
        new_slug_base = slugify(title)
        new_slug = make_unique_slug(new_slug_base, used_slugs)

        if old_slug != new_slug:
            article["slug"] = new_slug
            updated += 1
            print(f"📰 Article: {old_slug or '(vide)'} -> {new_slug}")

    save_json(ARTICLES_FILE, articles)
    print(f"✅ articles.json mis à jour ({updated} slug(s) corrigé(s))")

def fix_conseils():
    conseils = load_json(CONSEILS_FILE, [])
    if not isinstance(conseils, list):
        print("⚠️ conseils.json invalide")
        return

    backup_file(CONSEILS_FILE)

    used_slugs = set()
    updated = 0

    for conseil in conseils:
        if not isinstance(conseil, dict):
            continue

        title = conseil.get("title") or "conseil"
        old_slug = (conseil.get("slug") or "").strip()
        new_slug_base = slugify(title)
        new_slug = make_unique_slug(new_slug_base, used_slugs)

        if old_slug != new_slug:
            conseil["slug"] = new_slug
            updated += 1
            print(f"💡 Conseil: {old_slug or '(vide)'} -> {new_slug}")

    save_json(CONSEILS_FILE, conseils)
    print(f"✅ conseils.json mis à jour ({updated} slug(s) corrigé(s))")

def main():
    print("=" * 60)
    print("🔧 CORRECTION DES SLUGS (articles + conseils)")
    print("=" * 60)

    fix_articles()
    print("-" * 60)
    fix_conseils()

    print("=" * 60)
    print("✅ Terminé.")
    print("=" * 60)

if __name__ == "__main__":
    main()
    