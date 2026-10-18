"""Prepare publication 03: top-five REAL crypto losses, five REAL 48h curves.
No fake data. Publishing is a separate, test-only operation.
"""
from __future__ import annotations
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from crypto.publish_crypto_1_5 import market, movers, fear_index
from crypto.free_coin_logos import enrich_with_logos
from crypto.test_channel_premium import get_sparkline, get_global_metrics

OUT = Path("crypto/generated/test/losers_v2_data.json")

def validate_losers(rows):
    if len(rows) != 5:
        raise ValueError("Exactly five real losers required")
    if any(not math.isfinite(float(r["price"])) or float(r["price"]) <= 0
           or not math.isfinite(float(r["change"])) or float(r["change"]) >= 0
           or int(r["rank"]) < 1 or int(r["rank"]) > 100
           or float(r["volume"]) < 1_000_000 for r in rows):
        raise ValueError("Losers must have negative changes, valid price/rank/volume")
    if any(float(rows[i]["change"]) < float(rows[i-1]["change"]) for i in range(1, 5)):
        raise ValueError("Losers must be ranked by biggest percentage drop")
    if len({r["symbol"] for r in rows}) != 5:
        raise ValueError("Duplicate symbols in top-five losers")
    return rows

def main():
    rows, provider = market()
    chosen = validate_losers(movers(rows, "down"))
    for row in chosen:
        series = get_sparkline(row["symbol"])
        if not series or len(series) < 12 or any(
            not math.isfinite(float(v)) or float(v) <= 0 for v in series
        ):
            raise RuntimeError("Real 48h price history missing for " + row["symbol"] +
                               "; do not invent a chart or publish")
        row["sparkline"] = series
    metrics = get_global_metrics()
    chosen[0].update(metrics)
    try:
        score, observed = fear_index()
        chosen[0]["fear_greed"] = score
        print("FEAR_GREED_REAL", score, observed.isoformat())
    except (RuntimeError, ValueError, TypeError):
        chosen[0]["fear_greed"] = None
        print("FEAR_GREED_UNAVAILABLE (render as N/D)")
    enrich_with_logos(chosen)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": provider, "rows": chosen,
    }, ensure_ascii=False), encoding="utf-8")
    print("LOSERS_V2_READY", OUT, [(r["symbol"], r["change"]) for r in chosen])
    print("LOSERS_V2_REAL_CHARTS", len(chosen), "/ 5")

if __name__ == "__main__":
    main()
