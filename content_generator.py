#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
content_generator.py - VERSION FINALE AVEC TOUTES LES AMÉLIORATIONS
Mistral JSON + logos/bannières TheSportsDB + ligues populaires
"""

import os
import json
import requests
import random
from datetime import datetime

try:
    from slugify import slugify
except ImportError:
    print("⚠️ Installation de python-slugify...")
    os.system("pip install python-slugify")
    from slugify import slugify

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY manquante")

DATA_FILE = "data.json"
ARTICLES_FILE = "articles.json"

POPULAR_LEAGUES = [
    "Premier League",
    "LaLiga",
    "Serie A",
    "Bundesliga",
    "Ligue 1",
    "Championship",
    "Eredivisie",
    "Primeira Liga",
    "Super Lig",
    "MLS"
]

def load_today_matches():
    if not os.path.exists(DATA_FILE):
        print(f"❌ Fichier {DATA_FILE} introuvable")
        return []
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    matches = data.get("matches", [])
    if not matches:
        return []
    today = datetime.now().date()
    today_matches = []
    for m in matches:
        try:
            event_date = datetime.fromisoformat(m['event_date'].replace('Z', '+00:00')).date()
            if event_date == today:
                today_matches.append(m)
        except:
            continue
    return today_matches

def get_most_popular_matches(matches, count=2):
    """Priorité aux grandes ligues"""
    popular = [m for m in matches if any(l in m['league'] for l in POPULAR_LEAGUES)]
    other = [m for m in matches if m not in popular]
    return (popular + other)[:count]

def call_mistral(prompt):
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "mistral-large-latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 3000,
        "response_format": {"type": "json_object"}
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=120)
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"❌ Erreur Mistral: {e}")
        return None

def generate_blog_article(match):
    home_team = match['home_team']
    away_team = match['away_team']
    league = match['league']
    date = match['event_date']

    prompt = f"""Tu es un journaliste sportif expert pour Mr XPRONOS. Rédige un article de blog complet et engageant en français sur le match suivant. Réponds UNIQUEMENT au format JSON valide avec les champs "title", "excerpt", "content".

Match : {home_team} vs {away_team}
Compétition : {league}
Date : {date}

L'article doit contenir :
- Un titre accrocheur (format H1)
- Une introduction
- L'analyse des forces en présence
- Les statistiques clés
- Les confrontations directes historiques
- Les joueurs à suivre
- Un pronostic argumenté
- Une conclusion

Style : professionnel mais accessible, avec passion.
Longueur : environ 800 mots pour le contenu complet.
L'excerpt doit être un résumé de 150-200 caractères.
Le titre doit être court et percutant.

Format de réponse JSON attendu :
{{
  "title": "Le titre de l'article",
  "excerpt": "Le résumé court",
  "content": "Le contenu complet de l'article en HTML (avec balises <h2>, <p>, etc.)"
}}
"""
    response = call_mistral(prompt)
    if response:
        try:
            article_data = json.loads(response)
            if "title" in article_data and "content" in article_data:
                return article_data
        except json.JSONDecodeError:
            print("   ⚠️ Réponse Mistral non JSON, tentative de récupération...")
            lines = response.strip().split('\n')
            title = lines[0].replace('#', '').strip() if lines else "Article"
            content = response
            excerpt = content[:200] + "..."
            return {"title": title, "excerpt": excerpt, "content": content}
    return None

def save_article(match, article_data):
    articles = []
    if os.path.exists(ARTICLES_FILE):
        with open(ARTICLES_FILE, 'r', encoding='utf-8') as f:
            articles = json.load(f)

    # Sécurité JSON
    if not all(k in article_data for k in ("title", "excerpt", "content")):
        article_data["excerpt"] = article_data.get("content", "")[:200] + "..."

    # Générer un slug unique
    base_slug = slugify(article_data["title"])
    slug = base_slug
    counter = 1
    while any(a["slug"] == slug for a in articles):
        slug = f"{base_slug}-{counter}"
        counter += 1

    # Utiliser la bannière TheSportsDB si disponible, sinon image aléatoire
    image_url = match.get("tsdb_banner") or f"https://picsum.photos/seed/{random.randint(1,9999)}/768/400"

    new_article = {
        "slug": slug,
        "title": article_data["title"],
        "date": datetime.now().strftime("%Y-%m-%d"),
        "author": "Mr XPRONOS",
        "excerpt": article_data["excerpt"],
        "content": article_data["content"],
        "match": f"{match['home_team']} vs {match['away_team']}",
        "league": match["league"],
        "image_url": image_url
    }

    # Insérer en tête et limiter à 50 articles
    articles.insert(0, new_article)
    articles = articles[:50]

    with open(ARTICLES_FILE, 'w', encoding='utf-8') as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)

    print(f"✅ Article sauvegardé : {new_article['title'][:60]}... (slug: {slug})")

def main():
    print("="*60)
    print("🚀 GÉNÉRATION DE CONTENU IA (Mistral + images TheSportsDB)")
    print("="*60)

    today_matches = load_today_matches()
    if not today_matches:
        print("📝 Aucun match aujourd'hui dans data.json")
        return

    featured = get_most_popular_matches(today_matches, count=2)
    print(f"\n📝 Génération de {len(featured)} articles sur les matchs du jour...")

    for i, m in enumerate(featured, 1):
        print(f"   Article {i}: {m['home_team']} vs {m['away_team']} ({m['league']})")
        article = generate_blog_article(m)
        if article:
            save_article(m, article)

    print("\n✅ Génération terminée")

if __name__ == "__main__":
    main()