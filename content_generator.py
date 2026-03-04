#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
content_generator.py - Génère des articles de blog et conseils via l'API Mistral.
Ajoute la génération d'images avec fallback : Mistral -> Pixazo -> Lorem Picsum.
Style d'image : dessin 2D attractif (illustration colorée).
"""

import os
import json
import requests
import uuid
import time
import random
from datetime import datetime
from mistralai import Mistral
from mistralai.models import ToolFileChunk

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
PIXAZO_API_KEY = os.environ.get("PIXAZO_API_KEY")

if not MISTRAL_API_KEY:
    raise ValueError("La variable MISTRAL_API_KEY n'est pas définie")

client = Mistral(api_key=MISTRAL_API_KEY)

PIXAZO_API_URL = "https://gateway.pixazo.ai/getImage/v1/getSDXLImage"

DATA_FILE = "data.json"
ARTICLES_FILE = "articles.json"
CONSEILS_FILE = "conseils.json"

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

def generate_image_mistral(prompt, prefix):
    """Génère une image via l'API Mistral (image_generation)."""
    try:
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
        response = client.beta.conversations.start(
            agent_id=agent.id,
            inputs=prompt
        )
        for output in response.outputs:
            if output.type == "message.output":
                for chunk in output.content:
                    if isinstance(chunk, ToolFileChunk):
                        file_id = chunk.file_id
                        file_bytes = client.files.download(file_id=file_id).read()
                        filename = f"assets/images/{prefix}-{uuid.uuid4().hex[:8]}.png"
                        os.makedirs("assets/images", exist_ok=True)
                        with open(filename, "wb") as f:
                            f.write(file_bytes)
                        return filename
        return None
    except Exception as e:
        print(f"   ❌ Erreur Mistral image: {e}")
        return None

def generate_image_pixazo(prompt, prefix):
    """Génère une image via l'API Pixazo (Stable Diffusion XL)."""
    if not PIXAZO_API_KEY:
        return None
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "Ocp-Apim-Subscription-Key": PIXAZO_API_KEY
    }
    payload = {
        "prompt": prompt,
        "negative_prompt": "Low-quality, blurry, distorted, ugly, bad anatomy, extra limbs, watermark, text, cartoon",
        "height": 768,
        "width": 768,
        "num_steps": 20,
        "guidance_scale": 7,
        "seed": random.randint(1, 1000000)
    }
    try:
        print(f"      📡 Tentative Pixazo...")
        response = requests.post(PIXAZO_API_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        image_url = data.get("imageUrl")
        if image_url:
            img_response = requests.get(image_url, timeout=30)
            img_response.raise_for_status()
            filename = f"assets/images/{prefix}-{uuid.uuid4().hex[:8]}.png"
            os.makedirs("assets/images", exist_ok=True)
            with open(filename, "wb") as f:
                f.write(img_response.content)
            return filename
        return None
    except Exception as e:
        print(f"      ❌ Erreur Pixazo: {e}")
        return None

def get_fallback_image_url(topic="football"):
    """Retourne une image de fallback (Lorem Picsum)."""
    seed = random.randint(1, 1000)
    return f"https://picsum.photos/seed/{seed}/768/400?grayscale"

def generate_image_with_fallback(prompt, prefix, subject="football"):
    """
    Tente de générer une image avec Mistral, puis Pixazo, puis fallback.
    """
    print(f"      📡 Tentative Mistral...")
    img = generate_image_mistral(prompt, prefix)
    if img:
        return img

    if PIXAZO_API_KEY:
        img = generate_image_pixazo(prompt, prefix)
        if img:
            return img

    print(f"      ℹ️ Utilisation du fallback Lorem Picsum")
    return get_fallback_image_url(subject)

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
    if not matches:
        return []
    popular = []
    other = []
    for m in matches:
        league_name = m['league']
        if any(pop in league_name for pop in POPULAR_LEAGUES) or league_name in POPULAR_LEAGUES:
            popular.append(m)
        else:
            other.append(m)
    random.shuffle(popular)
    random.shuffle(other)
    selected = popular[:count]
    if len(selected) < count:
        selected += other[:count - len(selected)]
    return selected

def call_mistral(prompt, temperature=0.7, max_tokens=2000):
    API_URL = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "mistral-large-latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    try:
        resp = requests.post(API_URL, headers=headers, json=data, timeout=120)
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"❌ Erreur Mistral texte: {e}")
        return None

def generate_blog_article(match):
    home_team = match['home_team']
    away_team = match['away_team']
    league = match['league']
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
    articles = []
    if os.path.exists(ARTICLES_FILE):
        try:
            with open(ARTICLES_FILE, 'r', encoding='utf-8') as f:
                content_data = f.read().strip()
                if content_data:
                    articles = json.loads(content_data)
                else:
                    articles = []
        except (json.JSONDecodeError, IOError):
            articles = []
    else:
        articles = []

    lines = content.strip().split('\n')
    title = lines[0].replace('#', '').strip() if lines else "Article sans titre"
    slug = title.lower()
    slug = ''.join(c if c.isalnum() else '-' for c in slug)
    slug = '-'.join(filter(None, slug.split('-')))

    # Prompt pour image 2D attractive
    image_prompt = f"High-quality 2D illustration, vibrant colors, attractive style, football match scene: {match['home_team']} vs {match['away_team']} in the {match['league']} championship. Dynamic action, players in motion, stylized design, clean lines, appealing to fans."
    image_url = generate_image_with_fallback(image_prompt, prefix="article", subject="football")

    new = {
        "slug": slug[:100],
        "title": title,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "author": "Mr XPRONOS",
        "excerpt": content[:200] + "...",
        "content": content,
        "match": f"{match['home_team']} vs {match['away_team']}",
        "league": match['league'],
        "image_url": image_url
    }
    articles.insert(0, new)
    articles = articles[:50]
    with open(ARTICLES_FILE, 'w', encoding='utf-8') as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
    print(f"✅ Article sauvegardé : {title[:50]}... (image: {image_url})")

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
        except (json.JSONDecodeError, IOError):
            conseils = []
    else:
        conseils = []

    lines = content.strip().split('\n')
    title = lines[0].replace('#', '').strip() if lines else "Conseil"

    # Prompt pour image 2D attractive
    image_prompt = f"High-quality 2D illustration, vibrant colors, attractive style, illustrating a sports betting tip: {title}. A stylized character giving advice, with sports elements like a football and odds in the background, clean lines, appealing design."
    image_url = generate_image_with_fallback(image_prompt, prefix="conseil", subject="betting")

    new = {
        "title": title,
        "content": content,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "image_url": image_url
    }
    conseils.insert(0, new)
    conseils = conseils[:100]
    with open(CONSEILS_FILE, 'w', encoding='utf-8') as f:
        # Correction : indent=2 (et non indent-2)
        json.dump(conseils, f, indent=2, ensure_ascii=False)
    print(f"✅ Conseil sauvegardé : {title[:50]}... (image: {image_url})")

def main():
    print("="*60)
    print("🚀 GÉNÉRATION DE CONTENU IA (Mistral + images 2D attractives)")
    print("="*60)

    today_matches = load_today_matches()
    if not today_matches:
        print("📝 Aucun match aujourd'hui dans data.json")
    else:
        featured = get_most_popular_matches(today_matches, count=2)
        print(f"\n📝 Génération de {len(featured)} articles sur les matchs du jour...")
        for i, m in enumerate(featured, 1):
            print(f"   Article {i}: {m['home_team']} vs {m['away_team']} ({m['league']})")
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