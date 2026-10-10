#!/usr/bin/env python3
"""Génère six aperçus déterministes pour vérifier les coordonnées des templates."""
from __future__ import annotations

import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import programme_styles
import template_cards as tc

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/mrxpronos-template-previews")
OUT.mkdir(parents=True, exist_ok=True)

# Aucun réseau pendant la CI de prévisualisation.
fake_logo = Image.new("RGBA", (180, 120), (255, 255, 255, 255))
fake_photo = Image.new("RGB", (922, 372), (40, 70, 110))
programme_styles.load_logo = lambda url, max_px=100: fake_logo.copy()
tc.remote_photo = lambda url, size: fake_photo.copy()

logo = "https://preview/logo.png"

payloads = {
    "programme": {
        "day": "10/10/2026",
        "matches": [
            {"home": "Manchester United", "away": "Tottenham Hotspur", "time": "16h30", "home_logo": logo, "away_logo": logo},
            {"home": "Paris Saint-Germain", "away": "Olympique de Marseille", "time": "18h45", "home_logo": logo, "away_logo": logo},
            {"home": "Borussia Mönchengladbach", "away": "Jagiellonia Białystok", "time": "19h00", "home_logo": logo, "away_logo": logo},
            {"home": "Real Madrid", "away": "Villarreal", "time": "20h00", "home_logo": logo, "away_logo": logo},
            {"home": "Inter Milan", "away": "AC Milan", "time": "21h00", "home_logo": logo, "away_logo": logo},
        ],
    },
    "avant_match": {
        "day": "10/10/2026",
        "home": "Real Madrid",
        "away": "Villarreal",
        "time": "19h00",
        "home_logo": logo,
        "away_logo": logo,
        "home_form": "D • V • V • V • D | 9/15 pts",
        "away_form": "V • V • D • D • D | 6/15 pts",
    },
    "resultat": {
        "day": "10/10/2026",
        "home": "Manchester United",
        "away": "Tottenham Hotspur",
        "scores": (12, 10),
        "home_logo": logo,
        "away_logo": logo,
    },
    "statistique": {
        "day": "10/10/2026",
        "home": "Manchester United",
        "away": "Tottenham Hotspur",
        "scores": (5, 1),
        "home_logo": logo,
        "away_logo": logo,
        "stat_value": "75%",
        "stat_label": "TIRS CADRÉS",
    },
    "flash": {
        "day": "10/10/2026",
        "title": "Le Portugal annonce officiellement le retour de Cristiano Ronaldo pour les prochaines rencontres",
        "source": "Foot Mercato",
        "summary": "Une actualité volontairement longue permet de vérifier que le résumé reste dans les trois lignes prévues par le template sans recouvrir les éléments graphiques voisins.",
        "image_url": "https://preview/photo.jpg",
    },
    "sondage": {
        "day": "10/10/2026",
        "image_question": "Paris Saint-Germain vs Manchester City : qui va gagner cette grande affiche ?",
        "image_options": ["Paris Saint-Germain", "Match nul", "Manchester City"],
        "home_logo": logo,
        "away_logo": logo,
    },
}

for category, payload in payloads.items():
    image = tc.render(category, payload)
    path = OUT / f"{category}.png"
    image.save(path, "PNG", optimize=True)
    print("PREVIEW_OK", category, path, path.stat().st_size)
