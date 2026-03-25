#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import hashlib
import random
from datetime import datetime
from difflib import SequenceMatcher

OUT_FILE = "evergreen_topics.json"
TARGET_COUNT = 500
SEED = 20260325

# Mots à éviter (promesses trompeuses)
BANNED_WORDS = {"garanti", "100%", "assuré", "certain", "impossible de perdre"}

BOOKMAKERS = ["1xBet", "1win", "Betwinner", "Melbet", "Linebet", "Betclic"]
FCFA_AMOUNTS = ["1 000", "2 000", "3 000", "5 000", "10 000", "20 000", "50 000", "100 000"]

NUMBERS = [3, 5, 7, 9, 10, 11, 12, 13]

# Stopwords pour réduire les faux "doublons" (similarité)
STOPWORDS = {
    "de", "du", "des", "la", "le", "les", "un", "une", "et", "ou", "pour", "sur", "en",
    "avec", "sans", "dans", "ton", "ta", "tes", "mon", "ma", "mes", "au", "aux",
    "comment", "pourquoi", "quand", "quoi", "ce", "cette", "ces", "plus", "moins",
    "version", "guide", "méthode", "checklist", "liste", "plan", "rapide", "facile"
}

FAMILIES = {
    "bankroll": [
        "Bankroll en FCFA", "Gestion de bankroll", "Plan de mise", "Stop-loss / Take-profit",
        "Fractionnement des mises", "Routine du parieur", "Anti-tilt"
    ],
    "analyse_match": [
        "Analyse de match", "Forme récente", "H2H intelligent", "Motivation / enjeu",
        "Domicile / extérieur", "Lecture des cotes", "Match piège"
    ],
    "markets": [
        "Double chance (1X/X2)", "DNB (Draw No Bet)", "BTTS", "Over/Under 2.5",
        "Over 1.5 / Under 3.5", "Handicap asiatique", "Mi-temps / fin de match"
    ],
    "value": [
        "Value bet", "Probabilité implicite", "Marge bookmaker", "Baisse de cote",
        "Cote trop belle", "Comparer les bookmakers"
    ],
    "live": [
        "Paris live", "Over live", "BTTS live", "Cashout", "Favori mené", "Carton rouge (live)"
    ],
    "bonus": [
        "Bonus de bienvenue", "Wagering / rollover", "Conditions bonus", "XPVIP",
        "Bonus + discipline", "Retrait bonus"
    ],
    "bookmakers": [
        "Choisir un bookmaker", "Dépôt / retrait", "Compte limité", "Comparatif bookmakers",
        "Cotes & marchés", "Parier sur mobile"
    ],
    "psychology": [
        "Psychologie du parieur", "Biais cognitifs", "Séries (gains/pertes)", "Discipline",
        "FeelinG vs analyse", "Gestion émotion"
    ],
    "combos": [
        "Combinés", "Tickets prudents", "Erreurs combinés", "Combos value", "Limiter le risque"
    ],
}

# "Hooks" : formulations qui donnent envie de cliquer
HOOKS = [
    "La méthode simple (et réaliste)",
    "Le plan clair en {minutes} minutes",
    "La check-list avant de parier",
    "Les {n} erreurs qui te coûtent cher",
    "Le guide {year} pour éviter les pièges",
    "Ce que la plupart des parieurs oublient",
    "Le framework Mr XPRONOS (ultra pratique)",
    "Le mini-plan sur {days} jours",
    "La version ‘FCFA’ (petites mises)",
    "La version ‘FCFA’ (grosses mises)",
    "Avant de cliquer : lis ça",
    "Stop : ne fais plus cette erreur",
]

BENEFITS = [
    "pour jouer plus propre",
    "pour réduire le risque",
    "pour éviter les paris impulsifs",
    "pour gagner en régularité",
    "pour sécuriser tes mises",
    "pour mieux choisir tes matchs",
    "pour comprendre les cotes",
    "pour éviter les matchs pièges",
]

# Patterns CTR premium (beaucoup de variations)
PATTERNS = [
    "{topic} : {hook} — {benefit}",
    "{hook} : {topic} (exemples en FCFA)",
    "{topic} : {hook} (avec tableau + exemples FCFA)",
    "{topic} : {n} règles à suivre (sinon tu vas souffrir)",
    "{topic} : {n} signaux fiables + {n2} pièges à éviter",
    "{topic} : plan {days} jours en FCFA (discipline + limites)",
    "Parier en FCFA : {topic} — {hook}",
    "{topic} : ce que tu dois vérifier en {minutes} minutes",
    "{topic} : le guide anti-erreurs (spécial débutants)",
    "{topic} : le guide anti-pièges (niveau intermédiaire)",
    "{topic} : comment choisir vite (sans ‘feeling’)",
    "{topic} : stratégie prudente + exemple {amount} FCFA",
    "{topic} : stratégie modérée + exemple {amount} FCFA",
    "{topic} : quand jouer / quand éviter (ultra clair)",
    "{topic} : comment éviter la ruine en {days} jours",
    "{topic} : {hook} (spécial Afrique francophone)",
]

BONUS_PATTERNS = [
    "Bonus {bookmaker} + XPVIP : {hook} (wagering expliqué + exemple FCFA)",
    "XPVIP chez {bookmaker} : {n} erreurs qui bloquent ton retrait (et comment éviter)",
    "Bonus de bienvenue : {hook} — comment l’utiliser sans te piéger",
    "Wagering/Rollover : {hook} (exemple {amount} FCFA + plan {days} jours)",
    "{bookmaker} : comment utiliser XPVIP intelligemment (sans promesse, juste méthode)",
]

def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:90] or "topic"

def uniq_id(title: str) -> str:
    h = hashlib.sha1(title.encode("utf-8")).hexdigest()[:10]
    return f"{slugify(title)[:60]}-{h}"

def tokenize(text: str) -> set:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    tokens = [t for t in tokens if t not in STOPWORDS]
    return set(tokens)

def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    uni = len(a | b)
    return inter / uni if uni else 0.0

def too_similar(title: str, used_titles: list, jac_th=0.62, seq_th=0.87) -> bool:
    tset = tokenize(title)
    for prev in used_titles[-250:]:  # compare sur une fenêtre pour vitesse
        if not prev:
            continue
        pset = tokenize(prev)
        if jaccard(tset, pset) >= jac_th:
            return True
        if SequenceMatcher(None, title[:140], prev[:140]).ratio() >= seq_th:
            return True
    return False

def contains_banned(title: str) -> bool:
    low = title.lower()
    return any(w in low for w in BANNED_WORDS)

def pick_hook():
    return random.choice(HOOKS).format(
        n=random.choice(NUMBERS),
        year=2026,
        days=random.choice([7, 10, 14, 21, 30]),
        minutes=random.choice([7, 10, 12, 15]),
    )

def build_title(family: str) -> str:
    topic = random.choice(FAMILIES[family])

    n = random.choice(NUMBERS)
    n2 = random.choice([3, 5, 7, 9])
    days = random.choice([7, 10, 14, 21, 30])
    minutes = random.choice([7, 10, 12, 15])
    amount = random.choice(FCFA_AMOUNTS)
    benefit = random.choice(BENEFITS)
    hook = pick_hook()

    if family == "bonus":
        bookmaker = random.choice(BOOKMAKERS)
        pattern = random.choice(BONUS_PATTERNS)
        title = pattern.format(
            bookmaker=bookmaker,
            hook=hook,
            n=n,
            days=days,
            minutes=minutes,
            amount=amount,
            benefit=benefit,
        )
    else:
        pattern = random.choice(PATTERNS)
        title = pattern.format(
            topic=topic,
            hook=hook,
            n=n,
            n2=n2,
            days=days,
            minutes=minutes,
            amount=amount,
            benefit=benefit,
        )

    # Nettoyage léger des répétitions de ponctuation
    title = re.sub(r"\s+", " ", title).strip()
    title = title.replace("— —", "—")
    return title

def build_angle(family: str, title: str) -> str:
    """
    Angle = instructions pour l'IA ensuite (tableau, checklist, FCFA, prudence, etc.)
    """
    base = [
        f"Famille={family}",
        "Ton: expert, clair, moderne, sans promesse 'garanti'",
        "Inclure des exemples chiffrés en FCFA",
        "Inclure une checklist OU un tableau (Markdown) selon le sujet",
        "Inclure une section 'Erreurs à éviter'",
        "Inclure un mini paragraphe 'Conseil Mr XPRONOS' (prudence)",
        "Maillage interne: lien vers pronos.html, bonus.html, live.html",
    ]
    if family in ("bonus", "bookmakers"):
        base += [
            "Expliquer conditions bonus/KYC/retraits de manière réaliste",
            "Mentionner XPVIP sans exagérer",
        ]
    if family == "live":
        base += [
            "Inclure règles de timing (minute), limites de volume et stop-loss live",
        ]
    if family == "combos":
        base += [
            "Insister sur la limite de matchs et la gestion du risque (FCFA)",
        ]
    return " | ".join(base)

def main():
    random.seed(SEED)

    topics = []
    used_titles = []
    used_normalized = set()

    family_keys = list(FAMILIES.keys())

    attempts = 0
    max_attempts = TARGET_COUNT * 40  # marge pour éviter boucle infinie

    while len(topics) < TARGET_COUNT and attempts < max_attempts:
        attempts += 1

        # équilibrage familles (bonus un peu plus fréquent)
        family = random.choice(family_keys + (["bonus"] * 2))

        title = build_title(family)

        # garde-fous
        if contains_banned(title):
            continue

        norm = re.sub(r"\d+", "", title.lower())
        norm = re.sub(r"[^a-z]+", " ", norm).strip()
        if norm in used_normalized:
            continue

        if too_similar(title, used_titles):
            continue

        used_normalized.add(norm)
        used_titles.append(title)

        topics.append({
            "id": uniq_id(title),
            "family": family,
            "title_template": title,
            "angle": build_angle(family, title)
        })

    topics.sort(key=lambda x: (x["family"], x["title_template"]))

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "count": len(topics),
        "topics": topics
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"✅ {OUT_FILE} généré avec {len(topics)} topics (tentatives={attempts})")

    # aperçu
    print("\n--- APERÇU (20 titres) ---")
    for t in topics[:20]:
        print("-", t["title_template"])

if __name__ == "__main__":
    main()