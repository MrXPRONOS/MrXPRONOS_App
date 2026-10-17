"""N°4: envoi d'un SEUL aperçu d'alerte réelle sur @predict_mrxp, jamais ailleurs.

Aucune donnée fictive. Le franchissement instantané du seuil n'est pas affirmé.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import requests
from crypto.export_alerts_v2 import threshold
from scripts.telegram_test_guard import validate_test_channel


def main():
    path = Path("crypto/generated/test/alerts_v2.png")
    input_file = Path("crypto/generated/test/alerts_v2_data.json")
    if not input_file.is_file():
        raise RuntimeError("Données réelles absentes : aucun envoi")
    data = json.loads(input_file.read_text(encoding="utf-8"))
    if data.get("status") == "no_alert":
        print("ALERTS_V2_NO_ALERT_NO_SEND")
        return
    if data.get("status") != "real_alert" or data.get("is_demo") is not False:
        raise RuntimeError("Envoi interdit : exemple fictif/non validé")
    row = data.get("row") or {}
    change = float(row["change"])
    if (row.get("symbol") not in {"BTC", "ETH", "SOL", "BNB", "XRP"}
        or not math.isfinite(change) or threshold(change) < 5
        or threshold(change) != int(row["level"])
        or not isinstance(row.get("sparkline"), list)
        or len(row["sparkline"]) < 12):
        raise RuntimeError("Alerte non validée : aucun envoi")
    if not path.is_file() or path.stat().st_size < 10_000:
        raise RuntimeError("Affiche premium absente ou incomplète")
    token = (os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    verified = validate_test_channel("@predict_mrxp", token)
    side = "hausse" if change > 0 else "baisse"
    caption = (
        "🧪 TEST PUBLICATION 04 — ALERTE CRYPTO\n"
        f"{row['symbol']} : {side} {change:+.2f} % sur 24 h\n"
        f"Palier observé : {'+' if change > 0 else '-'}{int(row['level'])} %\n"
        f"Source : {data['provider']} • Courbe réelle 48 h\n"
        "⚠️ Observation glissante sur 24 h, pas la preuve d'un franchissement à l'instant.\n"
        "Canal de test uniquement. Aucun conseil d'investissement."
    )
    with path.open("rb") as image:
        try:
            response = requests.post("https://api.telegram.org/bot" + token + "/sendPhoto",
                data={"chat_id": verified["chat_id"], "caption": caption},
                files={"photo": (path.name, image, "image/png")}, timeout=(10, 90))
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError("Envoi Telegram incertain : aucun renvoi automatique") from exc
    reply = response.json()
    if not reply.get("ok"):
        raise RuntimeError("Telegram a refusé l'image n°4")
    print("ALERTS_V2_TEST_PUBLISHED", reply.get("result", {}).get("message_id"))


if __name__ == "__main__":
    main()