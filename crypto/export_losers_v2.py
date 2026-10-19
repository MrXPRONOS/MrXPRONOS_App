"""Prepare publication 03: top-five REAL crypto losses, five REAL 48h curves.
No fake data. Publishing is a separate, test-only operation.
"""
from __future__ import annotations
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from crypto.publish_crypto_1_5 import market, STABLE, fear_index
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

def select_real_losers(rows, fetch_history=get_sparkline, max_candidates=24):
    """Best five *eligible with verified real 48h history*, not synthetic charts.

    CoinPaprika's top losers can include obscure symbols for which the free
    time-series providers have no coverage. Keep scanning legitimate top-100
    assets in descending loss order instead of aborting after the first miss.
    """
    eligible = []
    unique = set()
    for r in sorted(rows, key=lambda x: float(x.get("change") or 0)):
        symbol = str(r.get("symbol") or "").upper()
        try:
            if (symbol in unique or symbol in STABLE
                    or not 1 <= int(r["rank"]) <= 100
                    or float(r["volume"]) < 1_000_000
                    or float(r["change"]) >= 0 or not math.isfinite(float(r["change"]))
                    or float(r["price"]) <= 0 or not math.isfinite(float(r["price"]))):
                continue
        except (KeyError,TypeError,ValueError,OverflowError):
            continue
        unique.add(symbol)
        eligible.append(r)
    chosen = []
    for row in eligible[:max_candidates]:
        try:
            series = fetch_history(row["symbol"])
            if (not isinstance(series,list) or len(series)<36 or
                    any(not math.isfinite(float(v)) or float(v)<=0 for v in series)
                    or max(series)==min(series)):
                print("LOSER_HISTORY_NOT_AVAILABLE",row["symbol"])
                continue
            chosen.append({**row,"sparkline":series})
            print("LOSER_HISTORY_VERIFIED",row["symbol"],len(series))
            if len(chosen)==5:
                return validate_losers(chosen)
        except (ValueError,TypeError,OverflowError,RuntimeError) as exc:
            print("LOSER_HISTORY_SKIP",row["symbol"],type(exc).__name__)
    raise RuntimeError(
        f"Only {len(chosen)} authentic loser charts across "
        f"{min(max_candidates,len(eligible))} eligible candidates: no publication")


def main():
    rows, provider = market()
    chosen = select_real_losers(rows)
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
