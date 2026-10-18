"""Publication n°5 — Fear & Greed premium V2, STRICTEMENT données réelles.

Source : Alternative.me /fng/ (valeurs historiques quotidiennes).
Échoue sans aperçu trompeur lorsque l'indice manque, est périmé ou incomplet.
La maquette de démonstration est isolée du chemin des publications réelles.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from crypto.publish_crypto_1_5 import request_json

UTC = timezone.utc
ENDPOINT = "https://api.alternative.me/fng/"
OUTPUT = Path("crypto/generated/test/fear_v2_data.json")
DEMO_OUTPUT = Path("crypto/generated/test/fear_v2_demo.json")


def classification(value: int) -> str:
    if not isinstance(value, int) or not 0 <= value <= 100:
        raise ValueError("Score Fear & Greed hors 0..100")
    return ("PEUR EXTRÊME" if value <= 24 else
            "PEUR" if value <= 44 else
            "NEUTRE" if value <= 54 else
            "AVIDITÉ" if value <= 74 else "AVIDITÉ EXTRÊME")


def parse_score(value) -> int:
    if isinstance(value, bool):
        raise ValueError("Score invalide")
    if isinstance(value, int):
        n = value
    elif isinstance(value, str) and value.isdigit():
        n = int(value)
    else:
        raise ValueError("Score invalide ou non entier")
    classification(n)
    return n


def parse_history(data: dict, now: datetime | None = None) -> dict:
    """Validation fail-closed ; 7 jours UTC consécutifs, de source officielle.

    Déduplique uniquement les enregistrements parfaitement identiques de jour.
    Une contradiction sur la même journée annule l'envoi.
    """
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("now doit inclure son fuseau horaire")
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ValueError("Réponse Alternative.me invalide")
    metadata = data.get("metadata") or {}
    if not isinstance(metadata, dict) or metadata.get("error"):
        raise ValueError("Alternative.me indique une erreur")
    points = {}
    for item in data["data"]:
        if not isinstance(item, dict):
            raise ValueError("Ligne d'indice invalide")
        score = parse_score(item.get("value"))
        raw_timestamp = item.get("timestamp")
        if isinstance(raw_timestamp, bool) or not str(raw_timestamp).isdigit():
            raise ValueError("Timestamp invalide")
        try:
            date = datetime.fromtimestamp(int(raw_timestamp), UTC)
        except (OSError, OverflowError, ValueError) as exc:
            raise ValueError("Timestamp hors limites") from exc
        if date > now + timedelta(minutes=5):
            raise ValueError("Mesure future invalide")
        key = date.date().isoformat()
        if key in points and points[key]["value"] != score:
            raise ValueError("Valeurs contradictoires pour une même journée")
        points[key] = {"date": key, "value": score, "timestamp": date.isoformat()}
    ordered = sorted(points.values(), key=lambda p: p["date"])
    if len(ordered) < 7:
        raise ValueError("Historique réel de 7 jours absent")
    history = ordered[-7:]
    for prev, item in zip(history, history[1:]):
        previous = datetime.fromisoformat(prev["date"]).date()
        today = datetime.fromisoformat(item["date"]).date()
        if (today - previous).days != 1:
            raise ValueError("Historique non quotidien : ne pas inventer les dates manquantes")
    latest = datetime.fromisoformat(history[-1]["timestamp"])
    age = (now - latest).total_seconds()
    if not -300 <= age <= 48 * 3600:
        raise ValueError("Indice périmé : publication interdite")
    score = history[-1]["value"]
    return {
        "status": "real_data", "is_demo": False,
        "provider": "Alternative.me", "source_url": "https://alternative.me/crypto/fear-and-greed-index/",
        "generated_at": now.isoformat(), "observed_at": latest.isoformat(),
        "score": score, "classification": classification(score),
        "yesterday_score": history[-2]["value"],
        "delta_1d": score - history[-2]["value"],
        "delta_6d": score - history[0]["value"],
        "history": history,
    }


def demo_data() -> dict:
    """Maquette locale strictement fictive, JAMAIS éligible à Telegram."""
    vals = [32, 36, 39, 42, 45, 37, 28]
    dates = ["2026-10-11", "2026-10-12", "2026-10-13", "2026-10-14",
             "2026-10-15", "2026-10-16", "2026-10-17"]
    return {
        "status": "demo", "is_demo": True, "provider": "SIMULATION",
        "source_url": "", "generated_at": "2026-10-17T12:00:00+00:00",
        "observed_at": "2026-10-17T00:00:00+00:00", "score": vals[-1],
        "classification": classification(vals[-1]),
        "yesterday_score": vals[-2], "delta_1d": vals[-1]-vals[-2],
        "delta_6d": vals[-1]-vals[0],
        "history": [{"date": d, "value": v, "timestamp": d+"T00:00:00+00:00"} for d, v in zip(dates, vals)]
    }


def export(demo: bool = False) -> Path:
    if demo:
        result, target = demo_data(), DEMO_OUTPUT
    else:
        payload = request_json(ENDPOINT, params={"limit": 7, "format": "json"})
        result = parse_history(payload)
        target = OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("FEAR_V2_DATA_VALIDATED", result["status"], target,
          "score", result["score"], "date", result["observed_at"],
          "historical_days", len(result["history"]))
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Maquette fictive locale seulement")
    args = parser.parse_args()
    export(args.demo)


if __name__ == "__main__":
    main()