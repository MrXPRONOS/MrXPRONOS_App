#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_testimonials.py - Génère des témoignages via Mistral en utilisant des prénoms et noms de famille africains.
Évite les doublons et produit des témoignages courts et variés.
"""

import os
import json
import requests
import re
import random

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
TESTIMONIALS_FILE = "testimonials.json"
MAX_TESTIMONIALS = 5

# Listes de prénoms et noms africains (fournies par l'utilisateur)
AFRICAN_FIRST_NAMES = [
    "Aminata", "Fatou", "Moussa", "Amadou", "Khadija", "Ibrahim", "Aisha", "Oumar", "Mariam", "Seydou",
    "Fanta", "Boubacar", "Rokia", "Drissa", "Salimata", "Mamadou", "Adama", "Djeneba", "Lassina", "Kadiatou",
    "Souleymane", "Bintou", "Modibo", "Awa", "Youssouf", "Hawa", "Tidiane", "Oumou", "Cheick", "Fatoumata",
    "Mahamadou", "Ramatou", "Sékou", "Nana", "Karim", "Aïssatou", "Mamoudou", "Kankou", "Balla", "Maimouna",
    "Ibrahima", "Diarra", "Samba", "Nagnouma", "Fodé", "Kadidia", "Lamine", "Massa", "Néné", "Ousmane",
    "Penda", "Salif", "Ténin", "Yacouba", "Zara", "Baba", "Doussou", "Fousseni", "Gaoussou", "Haby",
    "Issa", "Koumba", "Lalla", "Mody", "Nabou", "Oumy", "Pape", "Rama", "Sidy", "Tata",
    "Yoro", "Zeynab", "Ali", "Bassirou", "Coumba", "Demba", "El hadji", "Fama", "Gora", "Hélène",
    "Idrissa", "Jacques", "Kani", "Léa", "Mansour", "Nafi", "Pascal", "Ramatoulaye", "Saïdou", "Thierno",
    "Umu", "Vieux", "Waly", "Xavier", "Yaya", "Zalika", "Abdoulaye", "Bintou", "Chaka", "Diouf",
    "Anta", "Bineta", "Coumba", "Diara", "Fama", "Gnagna", "Henri", "Ina", "Jeanne", "Khadim",
    "Lambert", "Maguette", "Ndeye", "Ousseynou", "Philippe", "Rokhaya", "Sokhna", "Thiaba", "Victorine", "Woury",
    "Yacine", "Zara", "Arona", "Babacar", "Cheikh", "Diarra", "Elhadj", "Fatim", "Gorgui", "Habib",
    "Ibou", "Jean", "Khaly", "Lamine", "Mame", "Ngor", "Omar", "Pape", "Ramata", "Serigne",
    "Tamsir", "Viviane", "Waly", "Younousse", "Zeyna", "Aboubacar", "Baila", "Cire", "Djibril", "Elie",
    "Fily", "Gnakale", "Hamed", "Isha", "Jacob", "Kaba", "Lanciné", "Mamby", "Noumoukè", "Oumou",
    "Péguy", "Rokia", "Sia", "Tigui", "Ulysse", "Victoire", "Wassa", "Youssou", "Zena", "Almamy",
    "Bakary", "Chérif", "Djéné", "Emmanuel", "Fifi", "Gnakpa", "Hamidou", "Ibra", "Joseph", "Kadiatou",
    "Lamine", "Mariame", "Naminata", "Ousmane", "Pascal", "Rahimi", "Saliou", "Tiémoko", "Urbain", "Vamoussa",
    "Wahab", "Yao", "Zongo", "Aïcha", "Baba", "Cédric", "Djakaridja", "Eugénie", "Fodé", "Guy",
    "Haby", "Inza", "Jacob", "Kokou", "Laure", "Massa", "Nadia", "Ollo", "Pélagie", "Rokia",
    "Sita", "Tché", "Ursule", "Véronique", "Wendy", "Yvette", "Zita", "Adja", "Bi", "César",
    "Dani", "Elysée", "Flore", "Gérard", "Huguette", "Ismaël", "Juliette", "Koffi", "Lucien", "Michel",
    "Narcisse", "Odile", "Patrice", "Quentin", "Rosalie", "Sébastien", "Thérèse", "Urbain", "Valérie", "William",
    "Xénia", "Yannick", "Zacharie", "Ablawa", "Bénoît", "Cécile", "David", "Edwige", "Fabrice", "Gisèle",
    "Honoré", "Irène", "Jules", "Karine", "Laurent", "Mireille", "Norbert", "Olivier", "Pierrette", "Quitterie",
    "Rachel", "Sylvain", "Thierry", "Ulrich", "Viviane", "Wilfried", "Xavier", "Yolande", "Zéphirin", "Assitan",
    "Boukary", "Clémence", "Dramane", "Esther", "Ferdinand", "Germaine", "Hervé", "Ignace", "Joséphine", "Kassoum",
    "Lucie", "Marcel", "Nestor", "Odette", "Prisca", "Régine", "Suzanne", "Toussaint", "Ursule", "Victorin",
    "Wendpanga", "Yacinthe", "Zénabou", "Ablawa", "Barnabé", "Clarisse", "Désiré", "Eulalie", "Félicité", "Grégoire",
    "Hortense", "Isidore", "Julienne", "Kouassi", "Léopold", "Mélanie", "Narcisse", "Olympe", "Philomène", "Quentin",
    "Rufin", "Siméon", "Timothée", "Ursule", "Valentin", "Wilfried", "Xavière", "Yvette", "Zachée", "Anastasie",
    "Blaise", "Chantal", "Denis", "Émilie", "Firmin", "Gaston", "Hilaire", "Irma", "Jacqueline", "Kylian",
    "Léonce", "Monique", "Nadège", "Oswald", "Paulette", "Roland", "Solange", "Théophile", "Urbain", "Véronique",
    "William", "Yann", "Zita", "Ablaye", "Boubacar", "Coumba", "Demba", "Elhadji", "Fatima", "Gora",
    "Hamady", "Ibrahima", "Jean", "Khadim", "Lamine", "Mamadou", "Nafissatou", "Oumar", "Penda", "Rokhaya"
]

AFRICAN_LAST_NAMES = [
    "Traoré", "Diallo", "Koné", "Cissé", "Sow", "Diop", "Ba", "Ndiaye", "Fall", "Sall",
    "Camara", "Keita", "Touré", "Kone", "Sissoko", "Coulibaly", "Sacko", "Dembélé", "Bamba", "Sangaré",
    "Ouattara", "Zongo", "Kabore", "Sawadogo", "Ouedraogo", "Yaméogo", "Tiemtore", "Bonkoungou", "Ilboudo", "Kinda",
    "Mensah", "Adebayor", "Ofori", "Asare", "Agyemang", "Owusu", "Boateng", "Appiah", "Asamoah", "Toure",
    "Diaby", "Kante", "Soumahoro", "Fofana", "Kouyate", "Sako", "Diarra", "Sissoko", "Aboubakar", "Mohamed",
    "Ali", "Hassan", "Omar", "Ahmed", "Ibrahim", "Youssef", "Mahmoud", "Salah", "Nkosi", "Okonkwo",
    "Okafor", "Nnamdi", "Chukwu", "Eze", "Nwachukwu", "Onyeka", "Ike", "Obi", "Mbeki", "Ndlovu",
    "Khuzwayo", "Zuma", "Dlamini", "Nkosi", "Botha", "Van der Merwe", "Jansen", "Petersen", "Mutombo", "Mukendi",
    "Tshimanga", "Kalala", "Mbuyi", "Kabasele", "Lubamba", "Kazadi", "Mpoyo", "Ntumba", "Mwanza", "Chanda",
    "Banda", "Phiri", "Mwale", "Tembo", "Zulu", "Mumba", "Mwila", "Simfukwe", "Kipchoge", "Kiprop",
    "Kipyegon", "Cheruiyot", "Kipruto", "Jepchirchir", "Chepkoech", "Kipchumba", "Kiprotich", "Jepkosgei", "Kipkemoi", "Chebet",
    "Kipngetich", "Jepchumba", "Kipkurui", "Chepkwony", "Kiprono", "Jepkemboi", "Kipkoech", "Cherotich", "Kiprop", "Jepkemei",
    "Kiprugut", "Chepchirchir", "Kipserem", "Jepchirchir", "Kipchirchir", "Chepkemoi", "Kiprotich", "Jepkorir", "Kipngeno", "Chepkwemoi",
    "Mokgadi", "Tau", "Masilela", "Mokoena", "Ndlovu", "Zikalala", "Khumalo", "Sibiya", "Mkhize", "Mthembu",
    "Buthelezi", "Ngcobo", "Zwane", "Mabuza", "Maseko", "Shongwe", "Masango", "Mahlangu", "Nkambule", "Mamba",
    "Dlamini", "Ginindza", "Mavuso", "Motsa", "Simelane", "Nxumalo", "Masuku", "Mkhonta", "Shabangu", "Mamba",
    "Konaté", "Diabaté", "Sangaré", "Coulibaly", "Doumbia", "Touré", "Sissoko", "Keita", "Diarra", "Fofana",
    "Sako", "Kanté", "Maiga", "Samake", "Traoré", "Dembélé", "Bagayoko", "Sidibé", "Cissoko", "Bamba",
    "Kouyaté", "Soumah", "Camara", "Condé", "Sylla", "Sow", "Barry", "Bah", "Diallo", "Balde",
    "Mane", "Seck", "Dieng", "Gueye", "Mbaye", "Niang", "Thiam", "Diouf", "Sarr", "Faye",
    "Ndour", "Kane", "Ndao", "Diagne", "Fall", "Wade", "Diop", "Ciss", "Ka", "Sène",
    "Mbodj", "Pouye", "Samb", "Ba", "Ly", "Ndiaye", "Sall", "Sy", "Touré", "Diakité",
    "Sissoko", "Kone", "Traore", "Keita", "Camara", "Diallo", "Sow", "Bah", "Barry", "Balde",
    "Mane", "Seck", "Dieng", "Gueye", "Mbaye", "Niang", "Thiam", "Diouf", "Sarr", "Faye",
    "Ndour", "Kane", "Ndao", "Diagne", "Fall", "Wade", "Diop", "Ciss", "Ka", "Sène",
    "Mbodj", "Pouye", "Samb", "Ba", "Ly", "Ndiaye", "Sall", "Sy", "Touré", "Diakité",
    "Konaté", "Diabaté", "Sangaré", "Coulibaly", "Doumbia", "Touré", "Sissoko", "Keita", "Diarra", "Fofana",
    "Sako", "Kanté", "Maiga", "Samake", "Traoré", "Dembélé", "Bagayoko", "Sidibé", "Cissoko", "Bamba",
    "Kouyaté", "Soumah", "Camara", "Condé", "Sylla", "Sow", "Barry", "Bah", "Diallo", "Balde",
    "Mane", "Seck", "Dieng", "Gueye", "Mbaye", "Niang", "Thiam", "Diouf", "Sarr", "Faye",
    "Ndour", "Kane", "Ndao", "Diagne", "Fall", "Wade", "Diop", "Ciss", "Ka", "Sène",
    "Mbodj", "Pouye", "Samb", "Ba", "Ly", "Ndiaye", "Sall", "Sy", "Touré", "Diakité"
]

def generate_testimonial_prompt(first_name, last_name):
    """Génère un prompt pour un témoignage avec un nom spécifique."""
    prompt = f"""En tant que client satisfait de Mr XPRONOS, un site de pronostics sportifs, rédige un témoignage court et authentique (2-3 phrases) en français.
Le témoignage doit être écrit à la première personne, avec le prénom "{first_name}" et le nom de famille "{last_name}".
Évite les phrases toutes faites comme "Grâce à Mr XPRONOS" (varie les expressions). Parle de ton expérience personnelle, des résultats obtenus, ou de la qualité des analyses.
Le ton doit être naturel et varié.

Format : Retourne uniquement le texte du témoignage, sans guillemets, sans introduction.
Exemple : "Je suis vraiment impressionné par la précision des pronostics. J'ai gagné plusieurs paris grâce à leurs analyses pointues." - Jean Dupont
Mais ici, on veut seulement le texte, pas le nom (le nom sera ajouté après)."""
    return prompt

def call_mistral(prompt, temperature=0.8, max_tokens=200):
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
        resp = requests.post(API_URL, headers=headers, json=data, timeout=30)
        resp.raise_for_status()
        content = resp.json()['choices'][0]['message']['content'].strip()
        # Nettoyer les guillemets éventuels
        content = content.strip('"').strip("'")
        return content
    except Exception as e:
        print(f"❌ Erreur Mistral: {e}")
        return None

def generate_testimonial(first_name, last_name):
    """Génère un témoignage pour un nom donné, avec fallback."""
    prompt = generate_testimonial_prompt(first_name, last_name)
    text = call_mistral(prompt)
    if text and len(text) > 20:
        return text
    # Fallback si échec
    fallbacks = [
        "Les pronostics sont vraiment fiables, je recommande vivement !",
        "Une analyse très pointue qui m'a permis de mieux comprendre les matchs.",
        "Depuis que je suis Mr XPRONOS, mes gains ont augmenté significativement.",
        "Enfin un site de pronostics qui ne se trompe pas !",
        "Le système de partage est génial, j'ai débloqué des pronostics premium facilement."
    ]
    return random.choice(fallbacks)

def main():
    print("📝 Génération des témoignages...")
    testimonials = []
    used_names = set()

    # Générer MAX_TESTIMONIALS témoignages uniques
    while len(testimonials) < MAX_TESTIMONIALS:
        first = random.choice(AFRICAN_FIRST_NAMES)
        last = random.choice(AFRICAN_LAST_NAMES)
        full_name = f"{first} {last}"
        if full_name in used_names:
            continue
        used_names.add(full_name)
        text = generate_testimonial(first, last)
        testimonials.append({"name": full_name, "text": text})
        print(f"  Généré : {full_name}")

    # Sauvegarde
    with open(TESTIMONIALS_FILE, 'w', encoding='utf-8') as f:
        json.dump(testimonials, f, indent=2, ensure_ascii=False)

    print(f"✅ {len(testimonials)} témoignages sauvegardés dans {TESTIMONIALS_FILE}")

if __name__ == "__main__":
    main()