"""Shared financial plausibility checks preventing USD scaling incidents.

CoinLore /api/global/ total_mcap and total_volume are *USD amounts*.
Never multiply these numbers by 1e9. No provider is entitled to
skip unit sanity, even when its JSON parses successfully.
"""
from __future__ import annotations
import math


def validate_global_usd(market_cap_usd, volume_24h_usd):
    try:
        cap, vol = float(market_cap_usd), float(volume_24h_usd)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Missing global market USD amounts") from exc
    if not math.isfinite(cap) or not math.isfinite(vol):
        raise ValueError("Non-finite global USD values")
    if not 1e11 <= cap <= 1e14:
        raise ValueError("Global USD market cap implausible: suspected wrong units")
    if not 1e9 <= vol <= 1e13 or vol > 3 * cap:
        raise ValueError("Global USD 24h volume implausible: suspected wrong units")
    return cap, vol
