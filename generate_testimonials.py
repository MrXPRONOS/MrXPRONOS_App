#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_testimonials.py - Génère des témoignages via Mistral avec fallback sur les anciens.
"""

import os
import json
import requests
import re

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
TESTIMONIALS_FILE = "testimonials.json"
MAX_TESTIMONIALS = 5

def load_previous_testimonials():
    if os.path.exists(TESTIMONIALS_FILE):
        with open(TESTIMONIALS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_testimonials(testimonials):
    with open(TESTIMONIALS_FILE, 'w', encoding='utf-8') as f:
        json.dump(testimonials, f, indent=2, ensure_ascii=False)

def generate_new_testimonials():
    prompt = f"""Génère {MAX_TESTIMONIALS} témoignages de clients satisfaits de Mr XPRONOS, un site de pronostics sportifs. Pour chaque témoignage, donne un prénom (français) et un commentaire court (2-3 phrases). Les commentaires doivent être positifs et variés. Réponds au format JSON comme suit :
[
  {{"name": "Prénom", "text": "Commentaire"}},
  ...
]
Uniquement le JSON, sans texte avant ni après."""
    try:
        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "mistral-large-latest",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 800
            },
            timeout=30
        )
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            new_testimonials = json.loads(match.group())
            # Limiter à MAX_TESTIMONIALS
            return new_testimonials[:MAX_TESTIMONIALS]
    except Exception as e:
        print(f"⚠️ Erreur lors de la génération: {e}")
    return None

def main():
    print("📝 Génération des témoignages...")
    previous = load_previous_testimonials()
    new = generate_new_testimonials()
    if new:
        # On garde les nouveaux, mais on peut aussi fusionner avec les anciens pour varier
        # Ici on remplace complètement
        save_testimonials(new)
        print(f"✅ {len(new)} témoignages générés et sauvegardés.")
    else:
        # Fallback : on garde les anciens
        if previous:
            print(f"⚠️ Utilisation des {len(previous)} témoignages précédents.")
            # On peut éventuellement les remélanger ou les laisser tels quels
        else:
            # Fallback ultime : témoignages par défaut
            default = [
                {"name": "Jean", "text": "Grâce à Mr XPRONOS, j'ai multiplié mes gains par 3 en un mois !"},
                {"name": "Marie", "text": "Les pronostics VIP sont incroyablement précis. Je recommande !"},
                {"name": "Thomas", "text": "Le système de partage permet d'accéder à des analyses de qualité gratuitement."}
            ]
            save_testimonials(default)
            print("✅ Témoignages par défaut sauvegardés.")

if __name__ == "__main__":
    main()