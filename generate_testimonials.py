#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_testimonials.py - Génère des témoignages (courts + variés) via Mistral.

Améliorations vs version initiale :
- Longueur STRICTE : 1-2 phrases, 90-180 caractères (coupe propre + validation)
- Anti-répétition : déduplication par similarité (SequenceMatcher)
- Angles variés (H2H, discipline, LIVE, clarté, bankroll…)
- max_tokens réduit (réduit les textes trop longs)
- Fallbacks templatisés (variations + moins répétitifs)
"""

import os
import json
import random
import re
import time
import requests
from difflib import SequenceMatcher
from typing import Optional, List, Dict

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise ValueError("La variable MISTRAL_API_KEY n'est pas définie")

TESTIMONIALS_FILE = "testimonials.json"
MAX_TESTIMONIALS = int(os.environ.get("MAX_TESTIMONIALS", "5"))

# Contraintes de forme
MAX_SENTENCES = 2
MIN_CHARS = 90
MAX_CHARS = 180

# Anti-duplication
SIM_SEQ_THRESHOLD = 0.86

BANNED_WORDS = [
    "garanti", "100%", "assuré", "sûr", "certain", "impossible de perdre",
    "jamais perdre", "no risk", "sans risque"
]

ANGLES = [
    "focus: analyses H2H, bénéfice: je sélectionne mieux mes matchs",
    "focus: discipline et gestion de bankroll, bénéfice: je mise plus propre",
    "focus: coupons simples, bénéfice: je fais moins d’erreurs",
    "focus: clarté des explications, bénéfice: je comprends le pourquoi du prono",
    "focus: régularité, bénéfice: je joue moins mais mieux",
    "focus: LIVE VIP, bénéfice: meilleur timing sur corners/tirs/fautes",
]

# Listes de prénoms / noms (tes listes originales gardées)
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
    "Umu", "Vieux", "Waly", "Xavier", "Yaya", "Zalika", "Abdoulaye", "Chaka", "Diouf"
]

africanLastNames = [
    "Traoré", "Diallo", "Koné", "Cissé", "Sow", "Diop", "Ba", "Ndiaye", "Fall", "Sall",
    "Camara", "Keita", "Touré", "Sissoko", "Coulibaly", "Sacko", "Dembélé", "Bamba", "Sangaré",
    "Ouattara", "Zongo", "Kabore", "Sawadogo", "Ouedraogo", "Mensah", "Adebayor", "Owusu", "Boateng",
    "Diaby", "Kante", "Fofana", "Kouyate", "Diarra", "Aboubakar", "Mohamed", "Hassan", "Omar", "Ahmed",
    "Nkosi", "Okonkwo", "Okafor", "Eze", "Onyeka", "Obi", "Mbeki", "Ndlovu", "Zuma", "Dlamini",
    "Mutombo", "Mukendi", "Kabasele", "Kazadi", "Chanda", "Banda", "Phiri", "Tembo", "Zulu",
    "Kipchoge", "Kiprop"
]

african_cities = [
    "Dakar", "Abidjan", "Bamako", "Ouagadougou", "Niamey", "Conakry", "Cotonou", "Lomé", "Accra", "Lagos",
    "Kinshasa", "Douala", "Yaoundé", "Libreville", "Nairobi", "Kampala", "Kigali",
    "Johannesburg", "Luanda", "Antananarivo", "Le Caire", "Casablanca", "Tunis", "Alger"
]


def load_previous_testimonials() -> List[dict]:
    if os.path.exists(TESTIMONIALS_FILE):
        try:
            with open(TESTIMONIALS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def save_testimonials(testimonials: List[dict]) -> None:
    with open(TESTIMONIALS_FILE, "w", encoding="utf-8") as f:
        json.dump(testimonials, f, indent=2, ensure_ascii=False)


def call_mistral(prompt: str, retries: int = 2, temperature: float = 1.0, max_tokens: int = 90) -> Optional[str]:
    API_URL = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "mistral-large-latest",
        "messages": [
            {"role": "system", "content": "Tu écris des témoignages très courts, naturels, sans promesses mensongères."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    for attempt in range(retries + 1):
        try:
            resp = requests.post(API_URL, headers=headers, json=data, timeout=30)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            return content
        except Exception as e:
            print(f"■■ Tentative {attempt+1}/{retries+1} échouée : {e}")
            if attempt == retries:
                return None
            time.sleep(0.8)
    return None


def contains_banned(text: str) -> bool:
    low = (text or "").lower()
    return any(w in low for w in BANNED_WORDS)


def too_similar(a: str, b: str) -> bool:
    a = (a or "").lower().strip()
    b = (b or "").lower().strip()
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= SIM_SEQ_THRESHOLD


def is_duplicate_text(text: str, existing_texts: List[str]) -> bool:
    for t in existing_texts:
        if too_similar(text, t):
            return True
    return False


def generate_testimonial_prompt(first_name: str, last_name: str, city: str, angle: str) -> str:
    banned = "Interdit: garanti, 100%, sûr, certain, impossible de perdre."
    return f"""
Génère UN témoignage en français pour un site de pronostics sportifs appelé Mr XPRONOS.

Contraintes STRICTES :
- 1 à 2 phrases maximum
- entre {MIN_CHARS} et {MAX_CHARS} caractères (espaces compris)
- ton naturel (Afrique francophone), pas trop marketing
- {banned}
- pas de guillemets, pas d’emoji, pas de hashtags
- N'inclus PAS le nom de la personne dans le texte (ni prénom ni nom)

Contexte :
- Ville : {city}
- Angle : {angle}

Réponds uniquement avec le texte du témoignage.
""".strip()


def clean_testimonial(text: str, first_name: str, last_name: str) -> Optional[str]:
    if not text:
        return None

    # Garder une seule ligne (Mistral peut renvoyer plusieurs lignes)
    text = text.strip()
    text = re.sub(r"\s+", " ", text).strip()

    # Supprimer nom/prénom si jamais
    full_name_pattern = re.compile(fr"{re.escape(first_name)}\s*{re.escape(last_name)}", re.IGNORECASE)
    text = full_name_pattern.sub("", text)
    first_name_pattern = re.compile(fr"\b{re.escape(first_name)}\b", re.IGNORECASE)
    last_name_pattern = re.compile(fr"\b{re.escape(last_name)}\b", re.IGNORECASE)
    text = first_name_pattern.sub("", text)
    text = last_name_pattern.sub("", text)

    text = text.strip().strip('"').strip("'").strip()
    text = re.sub(r"\s+", " ", text).strip()

    # Enlever listes/bullets éventuels
    text = re.sub(r"^[-•]+\s*", "", text).strip()

    # Limiter à 2 phrases
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    text = " ".join(sentences[:MAX_SENTENCES]).strip()

    # Coupe à MAX_CHARS proprement
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"

    # Validation longueur
    if len(text) < MIN_CHARS:
        return None

    # Validation anti-promesses
    if contains_banned(text):
        return None

    return text


def fallback_testimonial() -> str:
    days = random.choice([7, 10, 14, 21, 30])
    focus = random.choice([
        "les analyses", "les coupons", "la fiabilité", "les explications", "le live", "la méthode"
    ])
    benefit = random.choice([
        "je choisis mieux mes matchs",
        "je mise plus discipliné",
        "je fais moins de combinés inutiles",
        "je joue moins mais plus propre",
        "je comprends enfin pourquoi je joue",
    ])
    t = random.choice([
        f"Depuis {days} jours je suis {focus}, et {benefit}. C’est simple et ça m’aide vraiment.",
        f"Les pronos sont clairs et {benefit}. Je préfère cette méthode aux paris au hasard.",
        f"Franchement, {focus} font la différence. Maintenant {benefit}.",
    ])
    # Assurer la fenêtre 90-180
    if len(t) > MAX_CHARS:
        t = t[:MAX_CHARS].rsplit(" ", 1)[0] + "…"
    if len(t) < MIN_CHARS:
        t = (t + " Ça change ma façon de jouer.").strip()
    return t


def generate_testimonial(first_name: str, last_name: str, city: str, existing_texts: List[str]) -> str:
    # On tente plusieurs fois avec des angles différents
    for _ in range(4):
        angle = random.choice(ANGLES)
        prompt = generate_testimonial_prompt(first_name, last_name, city, angle)
        raw = call_mistral(prompt, retries=1, temperature=1.0, max_tokens=90)
        cleaned = clean_testimonial(raw or "", first_name, last_name)
        if not cleaned:
            continue
        if is_duplicate_text(cleaned, existing_texts):
            continue
        return cleaned

    # fallback varié
    return fallback_testimonial()


def main():
    print("■ Génération de témoignages (courts + variés)...")

    previous = load_previous_testimonials()
    previous_texts = [t.get("text", "") for t in previous if isinstance(t, dict)]

    used_names = set()
    new_testimonials: List[Dict] = []

    max_attempts = MAX_TESTIMONIALS * 8
    attempts = 0

    while len(new_testimonials) < MAX_TESTIMONIALS and attempts < max_attempts:
        attempts += 1

        first = random.choice(africanFirstNames)
        last = random.choice(africanLastNames)
        full = f"{first} {last}"
        if full in used_names:
            continue
        used_names.add(full)

        city = random.choice(african_cities)

        existing_texts = previous_texts + [t["text"] for t in new_testimonials]
        text = generate_testimonial(first, last, city, existing_texts)
        if not text:
            continue
        if is_duplicate_text(text, existing_texts):
            continue

        # Notes crédibles : 70% 5★, 30% 4★
        rating = 5 if random.random() < 0.70 else 4

        new_testimonials.append({
            "name": full,
            "rating": rating,
            "city": city,
            "text": text
        })

        print(f"■ Généré : {full} ({city}) – {rating}★")

    if new_testimonials:
        save_testimonials(new_testimonials)
        print(f"■ {len(new_testimonials)} témoignages sauvegardés dans {TESTIMONIALS_FILE}")
    else:
        print("■■ Aucun témoignage généré. Conservation de l'ancien fichier si présent.")


if __name__ == "__main__":
    main()