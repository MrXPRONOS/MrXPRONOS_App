#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_testimonials.py - Génère des témoignages réalistes via Mistral avec retry, nettoyage et enrichissement (notes, villes).
Utilise les listes de prénoms et noms africains fournies.
"""

import os
import json
import random
import re
import requests

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise ValueError("La variable MISTRAL_API_KEY n'est pas définie")

TESTIMONIALS_FILE = "testimonials.json"
MAX_TESTIMONIALS = 5  # Nombre de témoignages à générer

# Listes de prénoms et noms africains (environ 100 chacun, mais tu peux étendre)
africanFirstNames = [
    "Aminata", "Fatou", "Moussa", "Amadou", "Khadija", "Ibrahim", "Aisha", "Oumar", "Mariam", "Seydou",
    "Fanta", "Boubacar", "Rokia", "Drissa", "Salimata", "Mamadou", "Adama", "Djeneba", "Lassina", "Kadiatou",
    "Souleymane", "Bintou", "Modibo", "Awa", "Youssouf", "Hawa", "Tidiane", "Oumou", "Cheick", "Fatoumata",
    "Mahamadou", "Ramatou", "Sékou", "Nana", "Karim", "Aïssatou", "Mamoudou", "Kankou", "Balla", "Maimouna",
    "Ibrahima", "Diarra", "Samba", "Nagnouma", "Fodé", "Kadidia", "Lamine", "Massa", "Néné", "Ousmane",
    "Penda", "Salif", "Ténin", "Yacouba", "Zara", "Baba", "Doussou", "Fousseni", "Gaoussou", "Haby",
    "Issa", "Koumba", "Lalla", "Mody", "Nabou", "Oumy", "Pape", "Rama", "Sidy", "Tata",
    "Yoro", "Zeynab", "Ali", "Bassirou", "Coumba", "Demba", "El hadji", "Fama", "Gora", "Hélène",
    "Idrissa", "Jacques", "Kani", "Léa", "Mansour", "Nafi", "Pascal", "Ramatoulaye", "Saïdou", "Thierno",
    "Umu", "Vieux", "Waly", "Xavier", "Yaya", "Zalika", "Abdoulaye", "Bintou", "Chaka", "Diouf"
]

africanLastNames = [
    "Traoré", "Diallo", "Koné", "Cissé", "Sow", "Diop", "Ba", "Ndiaye", "Fall", "Sall",
    "Camara", "Keita", "Touré", "Kone", "Sissoko", "Coulibaly", "Sacko", "Dembélé", "Bamba", "Sangaré",
    "Ouattara", "Zongo", "Kabore", "Sawadogo", "Ouedraogo", "Yaméogo", "Tiemtore", "Bonkoungou", "Ilboudo", "Kinda",
    "Mensah", "Adebayor", "Ofori", "Asare", "Agyemang", "Owusu", "Boateng", "Appiah", "Asamoah", "Toure",
    "Diaby", "Kante", "Soumahoro", "Fofana", "Kouyate", "Sako", "Diarra", "Sissoko", "Aboubakar", "Mohamed",
    "Ali", "Hassan", "Omar", "Ahmed", "Ibrahim", "Youssef", "Mahmoud", "Salah", "Nkosi", "Okonkwo",
    "Okafor", "Nnamdi", "Chukwu", "Eze", "Nwachukwu", "Onyeka", "Ike", "Obi", "Mbeki", "Ndlovu",
    "Khuzwayo", "Zuma", "Dlamini", "Nkosi", "Botha", "Van der Merwe", "Jansen", "Petersen", "Mutombo", "Mukendi",
    "Tshimanga", "Kalala", "Mbuyi", "Kabasele", "Lubamba", "Kazadi", "Mpoyo", "Ntumba", "Mwanza", "Chanda",
    "Banda", "Phiri", "Mwale", "Tembo", "Zulu", "Mumba", "Mwila", "Simfukwe", "Kipchoge", "Kiprop"
]

# Villes africaines pour crédibilité
african_cities = [
    "Dakar", "Abidjan", "Bamako", "Ouagadougou", "Niamey", "Conakry", "Cotonou", "Lomé", "Accra", "Lagos",
    "Kinshasa", "Brazzaville", "Douala", "Yaoundé", "Libreville", "Nairobi", "Dar es Salaam", "Kampala", "Kigali", "Bujumbura",
    "Johannesburg", "Le Cap", "Durban", "Luanda", "Maputo", "Harare", "Lusaka", "Antananarivo", "Le Caire", "Casablanca",
    "Tunis", "Alger", "Tripoli", "Nouakchott", "Khartoum", "Addis-Abeba", "Mogadiscio", "Djibouti", "Moroni", "Victoria"
]

def load_previous_testimonials():
    if os.path.exists(TESTIMONIALS_FILE):
        with open(TESTIMONIALS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_testimonials(testimonials):
    with open(TESTIMONIALS_FILE, 'w', encoding='utf-8') as f:
        json.dump(testimonials, f, indent=2, ensure_ascii=False)

def call_mistral(prompt, retries=2):
    """Appelle l'API Mistral avec retry et gestion d'erreur."""
    API_URL = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "mistral-large-latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,
        "max_tokens": 150
    }
    for attempt in range(retries + 1):
        try:
            resp = requests.post(API_URL, headers=headers, json=data, timeout=30)
            resp.raise_for_status()
            content = resp.json()['choices'][0]['message']['content'].strip()
            return content
        except Exception as e:
            print(f"⚠️ Tentative {attempt+1}/{retries+1} échouée : {e}")
            if attempt == retries:
                return None
            continue
    return None

def generate_testimonial_prompt(first_name, last_name):
    return f"""Génère un témoignage court (2-3 phrases maximum) pour un site de pronostics sportifs appelé Mr XPRONOS. 
Le témoignage doit être attribué à {first_name} {last_name}, un client satisfait. 
Le ton doit être naturel et positif, sans être trop formel. 
Le témoignage doit parler de la qualité des pronostics, des analyses ou des résultats obtenus. 
N'inclus PAS le nom de la personne dans le texte (seulement dans l'attribut). 
Ne mets pas de guillemets autour du texte. 
Réponds uniquement avec le texte du témoignage, sans introduction ni conclusion."""

def clean_testimonial(text, first_name, last_name):
    """Nettoie et limite le témoignage à 3 phrases, en supprimant d'éventuelles mentions du nom."""
    # Supprimer le nom complet ou le prénom/nom seuls (sensible à la casse)
    full_name_pattern = re.compile(fr"{re.escape(first_name)}\s*{re.escape(last_name)}", re.IGNORECASE)
    text = full_name_pattern.sub("", text)
    # Supprimer aussi le prénom seul (pour éviter les mentions)
    first_name_pattern = re.compile(fr"\b{re.escape(first_name)}\b", re.IGNORECASE)
    text = first_name_pattern.sub("", text)
    # Supprimer les guillemets superflus
    text = text.strip('"').strip("'").strip()
    # Limiter à 3 phrases (séparateur . ! ?)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    if len(sentences) > 3:
        text = " ".join(sentences[:3])
    return text.strip()

def generate_testimonial(first_name, last_name):
    """Génère un témoignage pour une personne donnée, avec fallback si échec."""
    prompt = generate_testimonial_prompt(first_name, last_name)
    text = call_mistral(prompt)
    if text and len(text) > 20:
        cleaned = clean_testimonial(text, first_name, last_name)
        if cleaned:
            return cleaned
    # Fallbacks variés
    fallbacks = [
        "Les analyses sont vraiment sérieuses. J'ai commencé à gagner régulièrement.",
        "Je ne pensais pas que les pronostics pouvaient être aussi précis.",
        "Les matchs sont très bien analysés et ça fait la différence.",
        "Depuis que je consulte ce site, mes paris sont beaucoup plus réfléchis.",
        "Franchement surpris par la qualité des analyses.",
        "Une fiabilité impressionnante, je recommande vivement.",
        "Grâce à Mr XPRONOS, j'ai enfin compris comment analyser un match.",
        "Les pronostics sont clairs et bien expliqués. Top !",
        "Je suis devenu plus discipliné dans mes paris grâce aux conseils.",
        "Résultats au rendez-vous, je suis conquis."
    ]
    return random.choice(fallbacks)

def main():
    print("📝 Génération de témoignages enrichis...")
    used_names = set()
    new_testimonials = []
    max_attempts = MAX_TESTIMONIALS * 3  # pour éviter boucle infinie
    attempts = 0

    while len(new_testimonials) < MAX_TESTIMONIALS and attempts < max_attempts:
        attempts += 1
        first = random.choice(africanFirstNames)
        last = random.choice(africanLastNames)
        full = f"{first} {last}"
        if full in used_names:
            continue
        used_names.add(full)

        # Générer le texte
        text = generate_testimonial(first, last)
        if not text:
            continue

        # Ajouter note aléatoire (entre 4 et 5 étoiles, crédible)
        rating = random.choice([4, 5]) if random.random() > 0.2 else 5  # 80% de 5, 20% de 4
        # Ajouter ville aléatoire
        city = random.choice(african_cities)

        new_testimonials.append({
            "name": full,
            "rating": rating,
            "city": city,
            "text": text
        })
        print(f"✅ Généré : {full} ({city}) – {rating}⭐")

    if new_testimonials:
        # Option : fusionner avec les anciens ou remplacer ? Ici on remplace pour garder des témoignages frais.
        save_testimonials(new_testimonials)
        print(f"✅ {len(new_testimonials)} témoignages sauvegardés dans {TESTIMONIALS_FILE}")
    else:
        print("❌ Aucun témoignage généré, conservation des anciens si existants.")
        # fallback sur les anciens (si existent) mais on ne fait rien car on n'écrase pas le fichier.

if __name__ == "__main__":
    main()