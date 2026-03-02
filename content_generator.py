#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
content_generator.py - Génère des articles de blog et conseils via l'API Mistral.
Ajoute la génération d'images pour illustrer chaque contenu.
Sélectionne les matchs les plus populaires du jour pour les articles.
Gère les rate limits avec retry et backoff.
Exécution quotidienne.
"""

import os
import json
import requests
import uuid
import time
from datetime import datetime, timedelta
import random
from mistralai import Mistral
from mistralai.models import ToolFileChunk

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise ValueError("La variable MISTRAL_API_KEY n'est pas définie")

# Initialisation du client Mistral
client = Mistral(api_key=MISTRAL_API_KEY)

MISTRAL_MODEL = "mistral-large-latest"
API_URL = "https://api.mistral.ai/v1/chat/completions"

CACHE_FILE = "cache/all_matches.json"
ARTICLES_FILE = "articles.json"
CONSEILS_FILE = "conseils.json"

# Liste des ligues les plus populaires (ordre de priorité)
POPULAR_LEAGUES = [
    "Premier League",
    "LaLiga",
    "Serie A",
    "Bundesliga",
    "Ligue 1",
    "Eredivisie",
    "Primeira Liga",
    "Super Lig",
    "Russian Premier League",
    "MLS",
    "Brasileirão",
    "Liga Profesional",
    "Jupiler Pro League",
    "Super League",
    "Championship",
    "Liga Portugal",
    "Trendyol Super Lig"
]

def generate_image_with_retry(prompt, prefix="article", max_retries=3, base_delay=5):
    """
    Tente de générer une image via l'API Mistral avec retry en cas de rate limit.
    Retourne le chemin local de l'image sauvegardée, ou None en cas d'échec.
    """
    for attempt in range(max_retries):
        try:
            # Créer un agent temporaire pour la génération d'image
            agent = client.beta.agents.create(
                model="mistral-medium-2505",
                name="Image Generation Agent",
                description="Agent used to generate images.",
                instructions="Use the image generation tool when you have to create images.",
                tools=[{"type": "image_generation"}],
                completion_args={
                    "temperature": 0.3,
                    "top_p": 0.95,
                }
            )

            # Démarrer une conversation avec le prompt
            response = client.beta.conversations.start(
                agent_id=agent.id,
                inputs=prompt
            )

            # Parcourir les outputs pour trouver le fichier image
            for output in response.outputs:
                if output.type == "message.output":
                    for chunk in output.content:
                        if isinstance(chunk, ToolFileChunk):
                            file_id = chunk.file_id
                            # Télécharger le fichier
                            file_bytes = client.files.download(file_id=file_id).read()
                            # Sauvegarder avec un nom unique
                            filename = f"assets/images/{prefix}-{uuid.uuid4().hex[:8]}.png"
                            os.makedirs("assets/images", exist_ok=True)
                            with open(filename, "wb") as f:
                                f.write(file_bytes)
                            return filename
            return None
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate limit" in error_str.lower():
                delay = base_delay * (2 ** attempt)  # backoff exponentiel
                print(f"   ⚠️ Rate limit atteint, nouvel essai dans {delay}s...")
                time.sleep(delay)
            else:
                print(f"   ❌ Erreur génération image: {e}")
                return None
    print(f"   ❌ Échec après {max_retries} tentatives")
    return None

def get_fallback_image_url():
    """Retourne une image aléatoire de Lorem Picsum en cas d'échec."""
    return f"https://picsum.photos/seed/{random.randint(1,1000)}/800/400"

def load_matches():
    """Charge tous les matchs depuis le cache."""
    if not os.path.exists(CACHE_FILE):
        return []
    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_today_matches(matches):
    """Retourne les matchs qui ont lieu aujourd'hui (dans le fuseau local)."""
    today = datetime.now().date()
    today_matches = []
    for m in matches:
        try:
            # Extraire la date de l'événement (au format ISO)
            event_date = datetime.fromisoformat(m['event_date'].replace('Z', '+00:00')).date()
            if event_date == today:
                today_matches.append(m)
        except:
            continue
    return today_matches

def get_most_popular_matches(matches, count=2):
    """
    Parmi les matchs du jour, sélectionne ceux appartenant aux ligues les plus populaires.
    Si pas assez, complète avec d'autres matchs du jour.
    """
    today_matches = get_today_matches(matches)
    if not today_matches:
        return []

    # Séparer par popularité de ligue
    popular = []
    other = []
    for m in today_matches:
        league_name = m['league']['name']
        if any(pop in league_name for pop in POPULAR_LEAGUES) or league_name in POPULAR_LEAGUES:
            popular.append(m)
        else:
            other.append(m)

    # Mélanger un peu pour éviter la répétition
    random.shuffle(popular)
    random.shuffle(other)

    # Prendre d'abord les populaires, puis compléter avec les autres
    selected = popular[:count]
    if len(selected) < count:
        selected += other[:count - len(selected)]

    return selected

def call_mistral(prompt, temperature=0.7, max_tokens=2000):
    """Appelle l'API Mistral avec un prompt."""
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
        print(f"❌ Erreur Mistral: {e}")
        return None

def generate_blog_article(match):
    """
    Génère un article de blog pour un match donné, en utilisant toutes les infos disponibles.
    """
    home_team = match['home_team']
    away_team = match['away_team']
    league = match['league']['name']
    date = match['event_date']

    prompt = f"""En tant que journaliste sportif expert pour Mr XPRONOS, rédige un article de blog complet et engageant en français sur le match suivant :

Match : {home_team} vs {away_team}
Compétition : {league}
Date : {date}

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
L'auteur doit être "Mr XPRONOS".

Génère l'article en français uniquement."""
    return call_mistral(prompt, temperature=0.8, max_tokens=2500)

def generate_tip():
    """Génère un conseil court sur un thème aléatoire."""
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
- Une explication claire du concept (environ 100 mots)
- Un exemple concret (50 mots)
- Une recommandation finale (50 mots)

Style : pédagogique, direct, utile.
Longueur totale : environ 200 mots maximum.
Le ton doit être celui d'un expert qui partage son savoir.
L'auteur est "Mr XPRONOS".

Génère en français uniquement."""
    return call_mistral(prompt, temperature=0.7, max_tokens=800)

def save_article(content, match):
    """Sauvegarde un article dans articles.json."""
    articles = []
    if os.path.exists(ARTICLES_FILE):
        try:
            with open(ARTICLES_FILE, 'r', encoding='utf-8') as f:
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

    # Générer une image
    image_prompt = f"Image illustrant le match de football {match['home_team']} vs {match['away_team']} dans le championnat {match['league']['name']}, style sportif dynamique."
    image_url = generate_image_with_retry(image_prompt, prefix="article")
    if not image_url:
        print(f"   ℹ️ Utilisation d'une image de fallback pour l'article {title[:30]}...")
        image_url = get_fallback_image_url()

    new = {
        "slug": slug[:100],
        "title": title,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "author": "Mr XPRONOS",
        "excerpt": content[:200] + "...",
        "content": content,
        "match": f"{match['home_team']} vs {match['away_team']}",
        "league": match['league']['name'],
        "image_url": image_url
    }
    articles.insert(0, new)
    articles = articles[:50]
    with open(ARTICLES_FILE, 'w', encoding='utf-8') as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
    print(f"✅ Article sauvegardé : {title[:50]}... (image: {image_url})")

def save_tip(content):
    """Sauvegarde un conseil dans conseils.json."""
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

    # Générer une image
    image_prompt = f"Image illustrant un conseil de paris sportifs sur le thème : {title}"
    image_url = generate_image_with_retry(image_prompt, prefix="conseil")
    if not image_url:
        print(f"   ℹ️ Utilisation d'une image de fallback pour le conseil {title[:30]}...")
        image_url = get_fallback_image_url()

    new = {
        "title": title,
        "content": content,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "image_url": image_url
    }
    conseils.insert(0, new)
    conseils = conseils[:100]
    with open(CONSEILS_FILE, 'w', encoding='utf-8') as f:
        json.dump(conseils, f, indent=2, ensure_ascii=False)
    print(f"✅ Conseil sauvegardé : {title[:50]}... (image: {image_url})")

def main():
    print("="*60)
    print("🚀 GÉNÉRATION DE CONTENU IA (Mistral + Images)")
    print("="*60)

    matches = load_matches()
    if not matches:
        print("❌ Aucun match dans le cache")
        return

    # Sélectionner les matchs les plus populaires du jour
    featured = get_most_popular_matches(matches, count=2)
    print(f"\n📝 Génération de {len(featured)} articles sur les matchs du jour...")
    for i, m in enumerate(featured, 1):
        print(f"   Article {i}: {m['home_team']} vs {m['away_team']} ({m['league']['name']})")
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