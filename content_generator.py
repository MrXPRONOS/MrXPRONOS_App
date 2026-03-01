#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
content_generator.py - Génère des articles de blog et conseils via l'API Mistral.
Exécution quotidienne.
"""

import os
import json
import requests
from datetime import datetime
import random

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise ValueError("La variable MISTRAL_API_KEY n'est pas définie")

MISTRAL_MODEL = "mistral-large-latest"
API_URL = "https://api.mistral.ai/v1/chat/completions"

CACHE_FILE = "cache/all_matches.json"
ARTICLES_FILE = "articles.json"
CONSEILS_FILE = "conseils.json"

def load_matches():
    if not os.path.exists(CACHE_FILE):
        return []
    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_featured_matches(matches, count=5):
    today = datetime.now().date()
    past, upcoming = [], []
    for m in matches:
        try:
            d = datetime.fromisoformat(m['event_date'].replace('Z', '+00:00')).date()
            if d < today:
                past.append(m)
            else:
                upcoming.append(m)
        except:
            continue
    random.shuffle(past)
    random.shuffle(upcoming)
    return (past + upcoming)[:count]

def call_mistral(prompt, temperature=0.7, max_tokens=2000):
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MISTRAL_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    try:
        resp = requests.post(API_URL, headers=headers, json=data, timeout=120)
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"Erreur Mistral: {e}")
        return None

def generate_blog_article(match):
    prompt = f"""En tant que journaliste sportif expert pour Mr XPRONOS, rédige un article de blog complet et engageant en français sur le match suivant :

Match : {match['home_team']} vs {match['away_team']}
Compétition : {match['league']['name']}
Date : {match['event_date']}

L'article doit contenir :
1. Un titre accrocheur (format H1)
2. Une introduction qui plante le décor
3. L'analyse des forces en présence
4. Les statistiques clés des deux équipes
5. Les confrontations directes historiques
6. Les joueurs à suivre
7. Un pronostic argumenté (qui va gagner et pourquoi)
8. Une conclusion

Style : professionnel mais accessible, avec une touche de passion pour le sport.
Longueur : environ 800 mots.
Inclus des sous-titres (H2) pour structurer l'article.
Le ton doit correspondre à la marque Mr XPRONOS : expert, fiable, moderne.

Génère l'article en français uniquement."""
    return call_mistral(prompt, temperature=0.8, max_tokens=2500)

def generate_tip():
    topics = [
        "gestion de bankroll",
        "analyse des cotes",
        "psychologie du parieur",
        "stratégies de mise",
        "erreurs à éviter",
        "comment analyser un match",
        "utilisation des statistiques",
        "paris live vs pré-match"
    ]
    topic = random.choice(topics)
    prompt = f"""En tant qu'expert en paris sportifs pour Mr XPRONOS, rédige un conseil pratique et actionable en français sur le thème : "{topic}".

Le conseil doit inclure :
- Un titre accrocheur
- Une explication claire du concept
- Des exemples concrets
- Des erreurs courantes à éviter
- Une recommandation finale

Style : pédagogique, direct, utile.
Longueur : environ 300 mots.
Le ton doit être celui d'un expert qui partage son savoir.

Génère en français uniquement."""
    return call_mistral(prompt, temperature=0.7, max_tokens=1500)

def save_article(content, match):
    articles = []
    if os.path.exists(ARTICLES_FILE):
        try:
            with open(ARTICLES_FILE, 'r', encoding='utf-8') as f:
                # Vérifier que le fichier n'est pas vide avant de charger
                content_data = f.read().strip()
                if content_data:
                    articles = json.loads(content_data)
                else:
                    articles = []
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Fichier {ARTICLES_FILE} corrompu ou vide, réinitialisation.")
            articles = []
    else:
        articles = []

    lines = content.strip().split('\n')
    title = lines[0].replace('#', '').strip() if lines else "Article sans titre"
    slug = title.lower()
    slug = ''.join(c if c.isalnum() else '-' for c in slug)
    slug = '-'.join(filter(None, slug.split('-')))
    new = {
        "slug": slug[:100],
        "title": title,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "author": "Mr XPRONOS",
        "excerpt": content[:200] + "...",
        "content": content,
        "match": f"{match['home_team']} vs {match['away_team']}",
        "league": match['league']['name']
    }
    articles.insert(0, new)
    articles = articles[:50]
    with open(ARTICLES_FILE, 'w', encoding='utf-8') as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
    print(f"✅ Article sauvegardé : {title}")

def save_tip(content):
    conseils = []
    if os.path.exists(CONSEILS_FILE):
        try:
            with open(CONSEILS_FILE, 'r', encoding='utf-8') as f:
                content_data = f.read().strip()
                if content_data:
                    conseils = json.loads(content_data)
                else:
                    conseils = []
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Fichier {CONSEILS_FILE} corrompu ou vide, réinitialisation.")
            conseils = []
    else:
        conseils = []

    lines = content.strip().split('\n')
    title = lines[0].replace('#', '').strip() if lines else "Conseil"
    new = {
        "title": title,
        "content": content,
        "date": datetime.now().strftime("%Y-%m-%d")
    }
    conseils.insert(0, new)
    conseils = conseils[:100]
    with open(CONSEILS_FILE, 'w', encoding='utf-8') as f:
        json.dump(conseils, f, indent=2, ensure_ascii=False)
    print(f"✅ Conseil sauvegardé : {title}")

def main():
    print("="*60)
    print("🚀 GÉNÉRATION DE CONTENU IA (Mistral)")
    print("="*60)

    matches = load_matches()
    if not matches:
        print("❌ Aucun match dans le cache")
        return

    featured = get_featured_matches(matches, 2)
    print(f"\n📝 Génération de {len(featured)} articles...")
    for i, m in enumerate(featured, 1):
        print(f"   Article {i}: {m['home_team']} vs {m['away_team']}")
        art = generate_blog_article(m)
        if art:
            save_article(art, m)

    print(f"\n💡 Génération de 3 conseils...")
    for i in range(3):
        print(f"   Conseil {i+1}")
        tip = generate_tip()
        if tip:
            save_tip(tip)

    print("\n✅ Génération terminée")

if __name__ == "__main__":
    main()