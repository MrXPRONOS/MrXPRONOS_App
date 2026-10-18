"""Canal de test exclusivement : publication n°05 Fear & Greed avec VRAIES données."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from crypto.export_fear_v2 import classification, parse_history
from scripts.telegram_test_guard import validate_test_channel

DATA = Path("crypto/generated/test/fear_v2_data.json")
IMAGE = Path("crypto/generated/test/fear_v2.png")


def validate_publication(payload: dict) -> None:
    if not isinstance(payload, dict) or payload.get("status") != "real_data" or payload.get("is_demo") is not False:
        raise ValueError("Seules les données réelles Fear & Greed sont publiables")
    if payload.get("provider") != "Alternative.me":
        raise ValueError("Source non vérifiée")
    observed = datetime.fromisoformat(str(payload["observed_at"]))
    if observed.tzinfo is None:
        raise ValueError("Timestamp sans fuseau horaire")
    # Réappliquer toutes les validations sur les données présentes dans le JSON.
    rows=payload.get("history")
    if not isinstance(rows, list) or len(rows) != 7:
        raise ValueError("Historique journalier réel incomplet")
    records={"metadata":{"error":None}, "data":[{"value":r["value"],"timestamp":str(int(datetime.fromisoformat(r["timestamp"]).timestamp()))} for r in rows]}
    checked=parse_history(records,now=datetime.now(timezone.utc))
    if (int(payload.get("score",-1)) != checked["score"] or
        payload.get("classification") != classification(checked["score"]) or
        payload.get("observed_at") != checked["observed_at"] or
        payload.get("delta_1d") != checked["delta_1d"] or
        payload.get("delta_6d") != checked["delta_6d"] or
        payload.get("history") != checked["history"]):
        raise ValueError("Données ou horodatages modifiés : publication annulée")


def main() -> None:
    if not DATA.is_file() or not IMAGE.is_file() or IMAGE.stat().st_size < 10_000:
        raise RuntimeError("Fichier Fear & Greed V2 réel absent : aucun envoi")
    payload=json.loads(DATA.read_text(encoding="utf-8"))
    validate_publication(payload)
    token=(os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    verified=validate_test_channel("@predict_mrxp", token)
    dt=datetime.fromisoformat(payload["observed_at"]).astimezone(timezone.utc)
    caption=(
        "🧪 TEST RÉEL #05 — FEAR & GREED CRYPTO\n"
        f"Indice : {payload['score']}/100 — {payload['classification'].lower()}\n"
        f"Variation depuis la veille : {payload['delta_1d']:+d} points\n"
        f"Mesuré le {dt.strftime('%d/%m/%Y')} (UTC).\n"
        "Historique : sept mesures quotidiennes réelles.\n"
        "Source : Alternative.me — Crypto Fear & Greed Index.\n"
        "⚠️ Indicateur de sentiment, pas un conseil ni un signal d'achat/vente."
    )
    with IMAGE.open("rb") as image:
        try:
            response=requests.post(
                "https://api.telegram.org/bot" + token + "/sendPhoto",
                data={"chat_id":verified["chat_id"], "caption":caption},
                files={"photo": (IMAGE.name,image,"image/png")}, timeout=(10,90))
            response.raise_for_status()
        except requests.RequestException:
            raise RuntimeError("Envoi Telegram incertain : ne pas retenter automatiquement") from None
    result=response.json()
    if result.get("ok") is not True:
        raise RuntimeError("Publication Fear & Greed refusée par Telegram")
    print("FEAR_V2_TEST_PUBLISHED", result.get("result",{}).get("message_id"),"destination",verified["username"])


if __name__ == "__main__":
    main()