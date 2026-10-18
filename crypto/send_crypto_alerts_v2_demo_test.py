"""Test d'envoi #04 : démo identifiée, vers @predict_mrxp SEULEMENT.

Ce programme n'envoie jamais d'alerte fictive sous l'apparence d'une alerte réelle.
Le payload JSON doit correspondre EXACTEMENT à la maquette officielle du repo.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests

from crypto.export_alerts_v2 import demo_data
from scripts.telegram_test_guard import validate_test_channel

DATA = Path("crypto/generated/test/alerts_v2_demo.json")
IMAGE = Path("crypto/generated/test/alerts_v2_demo.png")


def validate_demo_payload(payload: dict) -> None:
    if not isinstance(payload, dict) or payload != demo_data():
        raise RuntimeError("Démo non conforme à la maquette autorisée : envoi annulé")
    if payload["status"] != "demo" or payload["is_demo"] is not True:
        raise RuntimeError("Données non marquées SIMULATION : envoi annulé")


def main() -> None:
    if not DATA.is_file() or not IMAGE.is_file() or IMAGE.stat().st_size < 10_000:
        raise RuntimeError("Maquette ou image d'essai absente : envoi annulé")
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    validate_demo_payload(payload)
    token = (os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    # Guard compares actual chat username/type and verifies bot posting permissions.
    verified = validate_test_channel("@predict_mrxp", token)
    caption = (
        "🧪 TEST VISUEL #04 — SIMULATION, DONNÉES FICTIVES\n"
        "Cette image sert UNIQUEMENT à vérifier le design et l'envoi Telegram.\n"
        "BTC, prix, pourcentage, courbe et palier sont INVENTÉS pour ce test.\n"
        "🚫 AUCUNE ALERTE RÉELLE — NE PAS UTILISER POUR TRADER.\n"
        "Canal de test Mr XPRONOS @predict_mrxp."
    )
    with IMAGE.open("rb") as image:
        try:
            response = requests.post(
                "https://api.telegram.org/bot" + token + "/sendPhoto",
                data={"chat_id": verified["chat_id"], "caption": caption},
                files={"photo": (IMAGE.name, image, "image/png")},
                timeout=(10, 90),
            )
            response.raise_for_status()
        except requests.RequestException:
            raise RuntimeError("Réponse Telegram incertaine : pas de renvoi automatique") from None
    answer = response.json()
    if answer.get("ok") is not True:
        raise RuntimeError("Telegram a refusé la maquette #04")
    print("ALERTS_V2_DEMO_TEST_PUBLISHED", answer.get("result", {}).get("message_id"),
          "destination", verified["username"])


if __name__ == "__main__":
    main()
