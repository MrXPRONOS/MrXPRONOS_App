#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_testimonials.py - Génère 3 témoignages aléatoires via Mistral
et les sauvegarde dans testimonials.json.
À exécuter quotidiennement.  
"""

import os
import json
import requests
import re

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise ValueError("La variable MISTRAL_API_KEY n'est pas définie")

def generate_testimonials():
    prompt = """Génère 3 témoignages de clients satisfaits de Mr XPRONOS, un site de pronostics sportifs. Pour chaque témoignage, donne un prénom (français) et un commentaire court (2-3 phrases). Les commentaires doivent être positifs et variés. Réponds au format JSON comme suit :
[
  {"name": "Prénom", "text": "Commentaire"},
  ...
]
Uniquement le JSON, sans texte avant ni après."""
    
    response = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "mistral-large-latest",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.8,
            "max_tokens": 500
        },
        timeout=30
    )
    response.raise_for_status()
    content = response.json()['choices'][0]['message']['content']
    match = re.search(r'\[.*\]', content, re.DOTALL)
    if match:
        testimonials = json.loads(match.group())
    else:
        # Fallback
        testimonials = [
            {"name": "Jean", "text": "Grâce à Mr XPRONOS, j'ai multiplié mes gains par 3 en un mois !"},
            {"name": "Marie", "text": "Les pronostics VIP sont incroyablement précis. Je recommande !"},
            {"name": "Thomas", "text": "Le système de partage permet d'accéder à des analyses de qualité gratuitement."}
        ]
    return testimonials

def main():
    print("📝 Génération des témoignages...")
    testimonials = generate_testimonials()
    with open('testimonials.json', 'w', encoding='utf-8') as f:
        json.dump(testimonials, f, indent=2, ensure_ascii=False)
    print(f"✅ {len(testimonials)} témoignages sauvegardés dans testimonials.json")

if __name__ == "__main__":
    main()