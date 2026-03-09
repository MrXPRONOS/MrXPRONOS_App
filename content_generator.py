#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
content_generator.py - Générateur de contenu IA pour Mr XPRONOS
Version avec génération d'images via Mistral (priorité) et Pixazo (fallback).
Aucune image ne signifie aucun article ni conseil publié.
"""

import os
import json
import requests
import random
import uuid
import re
from datetime import datetime

# =======================================================
# CONFIGURATION
# =======================================================
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
PIXAZO_API_KEY = os.environ.get("PIXAZO_API_KEY")

if not MISTRAL_API_KEY:
    raise ValueError("La variable MISTRAL_API_KEY n'est pas définie")

DATA_FILE = "data.json"
ARTICLES_FILE = "articles.json"
CONSEILS_FILE = "conseils.json"

POPULAR_LEAGUES = [
    "Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1",
    "Eredivisie", "Primeira Liga", "Super Lig", "Russian Premier League",
    "MLS", "Brasileirão", "Liga Profesional", "Jupiler Pro League",
    "Super League", "Championship", "Liga Portugal", "Trendyol Super Lig"
]

# =======================================================
# FONCTIONS DE GÉNÉRATION D'IMAGES VIA MISTRAL
# =======================================================
from mistralai import Mistral

mistral_client = Mistral(api_key=MISTRAL_API_KEY)

# Créer un agent de génération d'images (une seule fois)
def create_image_agent():
    try:
        agent = mistral_client.beta.agents.create(
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
        print("✅ Agent de génération d'images Mistral créé")
        return agent.id
    except Exception as e:
        print(f"❌ Erreur création agent Mistral: {e}")
        return None

IMAGE_AGENT_ID = create_image_agent()

def generate_image_mistral(prompt):
    """Génère une image via l'API Mistral (agent)."""
    if not IMAGE_AGENT_ID:
        return None
    try:
        response = mistral_client.beta.conversations.start(
            agent_id=IMAGE_AGENT_ID,
            inputs=prompt
        )
        # Parcourir les outputs pour récupérer le fichier image
        for output in response.outputs:
            if output.type == "message.output":
                for chunk in output.content:
                    if chunk.type == "tool_file" and chunk.tool == "image_generation":
                        file_id = chunk.file_id
                        # Télécharger le fichier
                        file_bytes = mistral_client.files.download(file_id=file_id).read()
                        filename = f"assets/images/article-{uuid.uuid4().hex[:8]}.png"
                        os.makedirs("assets/images", exist_ok=True)
                        with open(filename, "wb") as f:
                            f.write(file_bytes)
                        print(f"      ✅ Image générée via Mistral: {filename}")
                        return filename
        print("      ⚠️ Aucune image trouvée dans la réponse Mistral")
        return None
    except Exception as e:
        print(f"      ❌ Erreur génération image Mistral: {e}")
        return None

# =======================================================
# FONCTIONS DE GÉNÉRATION D'IMAGES VIA PIXAZO (fallback)
# =======================================================
def generate_image_pixazo(prompt):
    """Génère une image via l'API Pixazo."""
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
        response = requests.post(
            "https://gateway.pixazo.ai/getImage/v1/getSDXLImage",
            json=payload, headers=headers, timeout=60
        )
        response.raise_for_status()
        data = response.json()
        image_url = data.get("imageUrl")
        if image_url:
            img_response = requests.get(image_url, timeout=30)
            img_response.raise_for_status()
            filename = f"assets/images/article-{uuid.uuid4().hex[:8]}.png"
            os.makedirs("assets/images", exist_ok=True)
            with open(filename, "wb") as f:
                f.write(img_response.content)
            print(f"      ✅ Image générée via Pixazo: {filename}")
            return filename
        return None
    except Exception as e:
        print(f"      ❌ Erreur Pixazo: {e}")
        return None

def generate_image_with_fallback(prompt):
    """Essaie Mistral puis Pixazo. Retourne None si les deux échouent."""
    img = generate_image_mistral(prompt)
    if img:
        return img
    img = generate_image_pixazo(prompt)
    if img:
        return img
    print("      ❌ Aucune image générée (Mistral et Pixazo ont échoué)")
    return None

# =======================================================
# FONCTIONS DE GÉNÉRATION DE TEXTE (Mistral avec retry)
# =======================================================
def call_mistral(prompt, temperature=0.7, max_tokens=2000, retries=2):
    """Appelle l'API Mistral pour du texte avec retry."""
    from mistralai import Mistral
    client = Mistral(api_key=MISTRAL_API_KEY)
    for attempt in range(retries + 1):
        try:
            response = client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"⚠️ Tentative {attempt+1}/{retries+1} échouée : {e}")
            if attempt == retries:
                return None
    return None

def extract_excerpt(text, length=150):
    """Nettoie le Markdown et extrait un extrait propre."""
    clean = re.sub(r'#', '', text)
    clean = re.sub(r'\n+', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean)
    return clean[:length] + "..."

def reading_time(text):
    """Calcule le temps de lecture en minutes (200 mots/min)."""
    words = len(text.split())
    return max(1, round(words / 200))

def is_duplicate(title, articles):
    """Vérifie si un article avec un titre similaire existe déjà."""
    for a in articles:
        if title.lower() in a["title"].lower():
            return True
    return False

def load_today_matches():
    """Charge les matchs du jour depuis data.json."""
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

def generate_blog_article(match):
    """Génère un article complet avec SEO, FAQ et métadonnées."""
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
8. Une section "Conseil de pari Mr XPRONOS" avec le pari recommandé
9. Une section FAQ avec 3 questions fréquentes sur ce match
10. Une conclusion

Ajoute aussi :
- Une meta description SEO de 150 caractères maximum
- 5 mots-clés SEO (séparés par des virgules)

Style : professionnel mais accessible, avec une touche de passion pour le sport.
Longueur : environ 800 mots.
Inclus des sous-titres (H2) pour structurer l'article.
Le ton doit correspondre à la marque Mr XPRONOS : expert, fiable, moderne.
L'auteur est "Mr XPRONOS".

Génère l'article en français uniquement.
À la fin, ajoute une ligne spéciale avec le format suivant :
META_DESCRIPTION: votre meta description
MOTS_CLES: mot1, mot2, mot3, mot4, mot5
"""
    return call_mistral(prompt, temperature=0.8, max_tokens=3000)

def generate_tip():
    """Génère un conseil."""
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

def parse_meta_from_article(content):
    """Extrait la meta description et les mots-clés du contenu."""
    meta_desc = ""
    mots_cles = ""
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        if line.startswith("META_DESCRIPTION:"):
            meta_desc = line.replace("META_DESCRIPTION:", "").strip()
        elif line.startswith("MOTS_CLES:"):
            mots_cles = line.replace("MOTS_CLES:", "").strip()
        else:
            new_lines.append(line)
    cleaned_content = "\n".join(new_lines)
    return cleaned_content, meta_desc, mots_cles

# =======================================================
# SAUVEGARDE AVEC ANTI-DUPLICATION ET MÉTADONNÉES
# =======================================================

def load_existing_articles():
    if os.path.exists(ARTICLES_FILE):
        try:
            with open(ARTICLES_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
                else:
                    return []
        except (json.JSONDecodeError, IOError):
            return []
    return []

def save_article(content, match):
    articles = load_existing_articles()

    content, meta_desc, mots_cles = parse_meta_from_article(content)
    lines = content.strip().split('\n')
    title = lines[0].replace('#', '').strip() if lines else "Article sans titre"

    if is_duplicate(title, articles):
        print(f"⚠️ Article avec titre similaire détecté, on ignore.")
        return

    base_slug = title.lower()
    base_slug = re.sub(r'[^a-z0-9]+', '-', base_slug).strip('-')
    slug = base_slug
    existing_slugs = [a["slug"] for a in articles]
    if slug in existing_slugs:
        slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

    # Construction du prompt pour l'image incluant les noms des équipes
    image_prompt = f"Football match: {match['home_team']} vs {match['away_team']} in the {match['league']}. Dynamic action, players in motion, stadium atmosphere, high quality, realistic style."
    image_url = generate_image_with_fallback(image_prompt)

    if not image_url:
        print(f"❌ Impossible de générer une image pour l'article '{title[:50]}...' -> article non sauvegardé")
        return

    read_time = reading_time(content)
    excerpt = extract_excerpt(content, 150)

    new = {
        "slug": slug,
        "title": title,
        "date": datetime.utcnow().isoformat() + "Z",
        "author": "Mr XPRONOS",
        "reading_time": read_time,
        "excerpt": excerpt,
        "meta_description": meta_desc or excerpt[:150],
        "keywords": mots_cles or "pronostic, analyse, football, paris sportifs",
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

def load_existing_conseils():
    if os.path.exists(CONSEILS_FILE):
        try:
            with open(CONSEILS_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
                else:
                    return []
        except (json.JSONDecodeError, IOError):
            return []
    return []

def save_tip(content):
    conseils = load_existing_conseils()
    lines = content.strip().split('\n')
    title = lines[0].replace('#', '').strip() if lines else "Conseil"

    # Générer l'image
    image_prompt = f"Sports betting tip: {title}. A stylized character giving advice, with football elements, high quality illustration."
    image_url = generate_image_with_fallback(image_prompt)

    if not image_url:
        print(f"❌ Impossible de générer une image pour le conseil '{title[:50]}...' -> conseil non sauvegardé")
        return

    read_time = reading_time(content)
    excerpt = extract_excerpt(content, 120)

    new = {
        "title": title,
        "content": content,
        "date": datetime.utcnow().isoformat() + "Z",
        "reading_time": read_time,
        "excerpt": excerpt,
        "image_url": image_url
    }
    conseils.insert(0, new)
    conseils = conseils[:100]
    with open(CONSEILS_FILE, 'w', encoding='utf-8') as f:
        json.dump(conseils, f, indent=2, ensure_ascii=False)
    print(f"✅ Conseil sauvegardé : {title[:50]}... (image: {image_url})")

# =======================================================
# MAIN
# =======================================================
def main():
    print("="*60)
    print("🚀 GÉNÉRATION DE CONTENU IA (avec images Mistral + Pixazo)")
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
            else:
                print(f"❌ Échec de génération du texte pour {m['home_team']} vs {m['away_team']}")

    print(f"\n💡 Génération de 3 conseils...")
    for i in range(3):
        print(f"   Conseil {i+1}")
        tip = generate_tip()
        if tip:
            save_tip(tip)
        else:
            print(f"❌ Échec de génération du texte pour le conseil {i+1}")

    print("\n✅ Génération terminée")

if __name__ == "__main__":
    main()