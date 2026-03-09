#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_testimonials.py - Génère 3 témoignages aléatoires via Mistral
et les ajoute en tête de testimonials.json (conserve les 10 plus récents).
Version améliorée avec fallback sur les anciens témoignages.
"""

import os
import json
import requests
import re

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise ValueError("La variable MISTRAL_API_KEY n'est pas définie")

TESTIMONIALS_FILE = 'testimonials.json'
MAX_TESTIMONIALS = 10

def load_existing_testimonials():
    """Charge les témoignages existants depuis le fichier JSON."""
    if os.path.exists(TESTIMONIALS_FILE):
        try:
            with open(TESTIMONIALS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            print("⚠️ Fichier testimonials.json corrompu, on repart de zéro.")
            return []
    return []

def save_testimonials(testimonials):
    """Sauvegarde la liste des témoignages (tronquée à MAX_TESTIMONIALS)."""
    with open(TESTIMONIALS_FILE, 'w', encoding='utf-8') as f:
        json.dump(testimonials[:MAX_TESTIMONIALS], f, indent=2, ensure_ascii=False)

def generate_new_testimonials():
    """Appelle l'API Mistral pour générer 3 nouveaux témoignages."""
    prompt = """Génère 3 témoignages de clients satisfaits de Mr XPRONOS, un site de pronostics sportifs. Pour chaque témoignage, donne un prénom (français) et un commentaire court (2-3 phrases). Les commentaires doivent être positifs et variés. Réponds au format JSON comme suit :
[
  {"name": "Prénom", "text": "Commentaire"},
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
                "max_tokens": 500
            },
            timeout=30
        )
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            new_testimonials = json.loads(match.group())
            # Vérification minimale de structure
            if isinstance(new_testimonials, list) and len(new_testimonials) == 3:
                for t in new_testimonials:
                    if not isinstance(t, dict) or 'name' not in t or 'text' not in t:
                        raise ValueError("Format de témoignage invalide")
                return new_testimonials
        raise ValueError("Aucun JSON valide trouvé dans la réponse")
    except Exception as e:
        print(f"❌ Erreur lors de la génération des témoignages: {e}")
        return None

def main():
    print("📝 Génération des témoignages...")
    existing = load_existing_testimonials()
    new_ones = generate_new_testimonials()
    
    if new_ones:
        # Ajouter les nouveaux en tête de liste
        updated = new_ones + existing
        print(f"✅ {len(new_ones)} nouveaux témoignages générés.")
    else:
        # Fallback : garder les existants
        updated = existing
        print("⚠️ Utilisation des anciens témoignages (fallback).")
    
    save_testimonials(updated)
    print(f"💾 {len(updated[:MAX_TESTIMONIALS])} témoignages sauvegardés dans {TESTIMONIALS_FILE}")

if __name__ == "__main__":
    main()