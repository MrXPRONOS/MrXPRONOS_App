#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_testimonials.py - Génère des témoignages via Mistral avec des noms des listes fournies.
"""

import os
import json
import requests
import re
import random

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
TESTIMONIALS_FILE = "testimonials.json"
MAX_TESTIMONIALS = 5

# Listes fournies (à copier depuis le message)
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

def load_previous_testimonials():
    if os.path.exists(TESTIMONIALS_FILE):
        with open(TESTIMONIALS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_testimonials(testimonials):
    with open(TESTIMONIALS_FILE, 'w', encoding='utf-8') as f:
        json.dump(testimonials, f, indent=2, ensure_ascii=False)

def generate_one_testimonial(first_name, last_name):
    prompt = f"""Génère un témoignage de client satisfait de Mr XPRONOS, un site de pronostics sportifs.
Le client s'appelle {first_name} {last_name}. Écris un commentaire court (2-3 phrases) positif et varié.
Réponds uniquement avec le texte du témoignage, sans guillemets ni mention du nom."""
    try:
        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "mistral-large-latest",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 200
            },
            timeout=30
        )
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content'].strip()
        # Nettoyer si nécessaire
        return content
    except Exception as e:
        print(f"⚠️ Erreur lors de la génération pour {first_name} {last_name}: {e}")
        return None

def main():
    print("📝 Génération des témoignages...")
    previous = load_previous_testimonials()
    # On va générer MAX_TESTIMONIALS nouveaux témoignages
    new_testimonials = []
    used_names = set()  # pour éviter les doublons dans la même session
    for _ in range(MAX_TESTIMONIALS):
        # Choisir un prénom et un nom aléatoires
        first = random.choice(africanFirstNames)
        last = random.choice(africanLastNames)
        full = f"{first} {last}"
        # Éviter les doublons (optionnel)
        while full in used_names:
            first = random.choice(africanFirstNames)
            last = random.choice(africanLastNames)
            full = f"{first} {last}"
        used_names.add(full)
        print(f"   Génération pour {full}...")
        text = generate_one_testimonial(first, last)
        if text:
            new_testimonials.append({"name": full, "text": text})
        else:
            # Fallback : on prend un témoignage par défaut avec ce nom
            default_text = f"Grâce à Mr XPRONOS, j'ai considérablement amélioré mes gains. Les analyses sont très précises et je recommande vivement !"
            new_testimonials.append({"name": full, "text": default_text})

    # On sauvegarde les nouveaux témoignages (on peut choisir de remplacer ou fusionner)
    # Ici on remplace complètement pour avoir des témoignages frais à chaque exécution
    save_testimonials(new_testimonials)
    print(f"✅ {len(new_testimonials)} témoignages générés et sauvegardés.")

if __name__ == "__main__":
    main()