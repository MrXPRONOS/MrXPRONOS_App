"""Fail-closed validation of REAL crypto chart samples. No generated price history."""
from __future__ import annotations

import math
from datetime import datetime, timezone

UTC = timezone.utc
VALID_SOURCES = frozenset({"CryptoCompare", "Coinbase", "CoinGecko"})


def validate_timed_history(samples, now=None):
    """Return hourly-ish closes only when actual timestamps cover >=36h, end <=3h ago."""
    now = now or datetime.now(UTC)
    if len(samples) < 36:
        raise ValueError("Less than 36 authentic candles")
    points, times = [], []
    for stamp, close in samples:
        value = float(close)
        ts = float(stamp)
        if not math.isfinite(value) or value <= 0 or not math.isfinite(ts):
            raise ValueError("Invalid chart candle")
        times.append(ts)
        points.append(value)
    if any(b <= a or b - a > 3 * 3600 for a, b in zip(times, times[1:])):
        raise ValueError("Duplicate, nonchronological or sparse candle timestamps")
    if times[-1] - times[0] < 36 * 3600:
        raise ValueError("Historical price series spans less than 36 hours")
    age = now.timestamp() - times[-1]
    if not -300 <= age <= 3 * 3600:
        raise ValueError("Last historical candle stale or in the future")
    if max(points) <= min(points):
        raise ValueError("Flat history: no verified price movement")
    return points


def chart_signature(points):
    """Scale-invariant: catches accidental reuse of ONE curve for different coins."""
    if not isinstance(points, list) or len(points) < 36:
        raise ValueError("A minimum of 36 recorded chart values is required")
    values = [float(p) for p in points]
    if any(not math.isfinite(p) or p <= 0 for p in values):
        raise ValueError("Invalid chart value")
    first = values[0]
    relative = tuple(round((v / first - 1) * 1_000_000, 4) for v in values)
    if len(set(relative)) < 4:
        raise ValueError("Historical line contains no useful verified movement")
    return relative


def validate_distinct_charts(rows, require_source=False):
    """Reject *exact duplicate normalized histories*, not genuinely correlated markets."""
    names, shapes = set(), set()
    for row in rows:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol or symbol in names:
            raise ValueError("Repeated or missing crypto symbol")
        names.add(symbol)
        series = row.get("sparkline")
        signature = chart_signature(series)
        if signature in shapes:
            raise ValueError("The same historical chart has been assigned to several assets")
        shapes.add(signature)
        if require_source and row.get("sparkline_source") not in VALID_SOURCES:
            raise ValueError("Unattributed historical source")
    return True
