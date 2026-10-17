"""Publication 04 — alertes de variation glissante 24 h.

Le test réel utilise uniquement les données vérifiées du fournisseur marché.
L'aperçu offline est explicitement fictif, jamais envoyable par le script Telegram.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

WATCH = ("BTC", "ETH", "SOL", "BNB", "XRP")
ROOT = Path("crypto/generated/test")
DEMO_FILE = ROOT / "alerts_v2_demo.json"
LIVE_FILE = ROOT / "alerts_v2_data.json"


def threshold(change: float) -> int:
    """Plus haut palier de 5 % sur la variation glissante 24 h."""
    value = float(change)
    if not math.isfinite(value) or abs(value) > 5000:
        raise ValueError("Variation 24 h absente ou invalide")
    return int(math.floor((abs(value) + 1e-9) / 5)) * 5


def select_alert(rows: list[dict]) -> dict | None:
    """Choisit le plus gros seuil observé parmi BTC/ETH/SOL/BNB/XRP.

    On n'annonce PAS le franchissement instantané : un simple snapshot de
    variation 24 h ne prouve pas la seconde de franchissement.
    """
    by_symbol = {}
    for row in sorted(rows, key=lambda r: int(r.get("rank") or 999999)):
        symbol = str(row.get("symbol") or "").upper()
        if symbol not in WATCH or symbol in by_symbol:
            continue
        if not (1 <= int(row.get("rank") or 0) <= 100):
            continue
        try:
            price = float(row["price"])
            change = float(row["change"])
            level = threshold(change)
            if not (math.isfinite(price) and price > 0):
                continue
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if level >= 5:
            by_symbol[symbol] = {**row, "symbol": symbol, "level": level,
                                  "direction": "up" if change > 0 else "down"}
    return max(by_symbol.values(), key=lambda r: (r["level"], abs(r["change"]), -WATCH.index(r["symbol"])), default=None)


def demo_data() -> dict:
    """Exemple purement graphique ; jamais considéré comme réel."""
    changes = [-0.8, -1.5, -2, -3, -3.8, -4.4, -4, -5, -5.4, -6.1,
               -5.7, -6.5, -7.3, -7.1, -8.0, -9.2, -9.0, -10.4]
    base = 42000.0
    series = [round(base * (1 + v / 100), 2) for v in changes]
    return {"status": "demo", "is_demo": True, "timestamp": "2026-10-17T12:00:00+00:00",
            "provider": "SIMULATION", "row": {"symbol": "BTC", "name": "Bitcoin", "price": series[-1],
            "change": -10.4, "level": 10, "direction": "down", "sparkline": series}}


def export_demo():
    ROOT.mkdir(parents=True, exist_ok=True)
    DEMO_FILE.write_text(json.dumps(demo_data(), ensure_ascii=False), encoding="utf-8")
    print("ALERTS_V2_DEMO_READY", DEMO_FILE)


def export_live():
    from crypto.publish_crypto_1_5 import market
    from crypto.test_channel_premium import get_sparkline
    rows, provider = market()
    selected = select_alert(rows)
    payload = {"timestamp": datetime.now(timezone.utc).isoformat(), "provider": provider,
               "status": "no_alert", "is_demo": False, "row": None}
    if selected:
        series = get_sparkline(selected["symbol"])
        if (not isinstance(series, list) or len(series) < 12 or
            any(not math.isfinite(float(v)) or float(v) <= 0 for v in series)):
            raise RuntimeError("Historique réel 48 h insuffisant : aucune alerte publiée")
        selected["sparkline"] = series
        payload.update(status="real_alert", row=selected)
        print("ALERT_REAL_24H", selected["symbol"], selected["change"],
              "palier", selected["level"], "source", provider)
    else:
        print("ALERTS_V2_NO_ACTIVE_THRESHOLD: pas d'alerte Telegram")
    ROOT.mkdir(parents=True, exist_ok=True)
    LIVE_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print("ALERTS_V2_REAL_DATA", LIVE_FILE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Maquette fictive uniquement, aucun réseau")
    options = parser.parse_args()
    export_demo() if options.demo else export_live()


if __name__ == "__main__":
    main()