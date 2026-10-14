#!/usr/bin/env python3
"""Génère les 7 aperçus production Mr XPRONOS: 4 premium + 3 génériques."""
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
fake_logo = Image.new("RGBA", (220, 160), (255, 255, 255, 255))
programme_styles.load_logo = lambda url, max_px=100: fake_logo.copy()

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
        "scores": (4, 2),
        "source": "BSD V2",
        "home_logo": logo,
        "away_logo": logo,
    },
    "composition": {
        "home": "Borussia Mönchengladbach",
        "away": "Club Atlético de Madrid",
        "competition": "UEFA Champions League",
        "time": "20h45",
        "source": "ESPN",
        "home_logo": logo,
        "away_logo": logo,
        "home_players": [
            "Moritz Nicolas", "Joe Scally", "Nico Elvedi", "Kevin Diks",
            "Luca Netz", "Rocco Reitz", "Julian Weigl", "Franck Honorat",
            "Alassane Pléa", "Robin Hack", "Tim Kleindienst",
        ],
        "away_players": [
            "Jan Oblak", "Nahuel Molina", "José María Giménez", "Robin Le Normand",
            "Javi Galán", "Marcos Llorente", "Koke", "Pablo Barrios",
            "Antoine Griezmann", "Julián Álvarez", "Alexander Sørloth",
        ],
    },
    # 3 familles génériques.
    "goal": {
        "home": "Arsenal",
        "away": "Chelsea",
        "home_logo": logo,
        "away_logo": logo,
    },
    "absence_confirmee": {
        "team": "Paris Saint-Germain",
        "team_logo": logo,
        "league": "Ligue 1",
    },
    "quiz": {
        "headline": "Quel joueur détient ce record historique en Ligue des champions ?",
        "meta": "QUIZ FOOT",
    },
}

for category, payload in payloads.items():
    image = tc.render(category, payload)
    path = OUT / f"{category}.png"
    image.save(path, "PNG", optimize=True)
    print("PREVIEW_OK", category, path, image.size, path.stat().st_size)
