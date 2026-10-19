"""Publication #06 — Dominance BTC / capitalisation globale, sources gratuites.

La maquette --demo ne peut jamais être envoyée. En cas de données
invalides ou périmées, l'export réel s'arrête plutôt que d'inventer.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path

from crypto.publish_crypto_1_5 import request_json
from crypto.financial_sanity import validate_global_usd

UTC = timezone.utc
PAPRIKA_URL = "https://api.coinpaprika.com/v1/global"
COINLORE_URL = "https://api.coinlore.net/api/global/"
REAL_OUTPUT = Path("crypto/generated/test/dominance_v2_data.json")
DEMO_OUTPUT = Path("crypto/generated/test/dominance_v2_demo.json")
PROVIDERS = {"CoinPaprika", "CoinLore"}


def finite_number(value, field: str, *, low: float, high: float) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field}: chiffre manquant")
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"{field}: valeur invalide") from exc
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"{field}: hors limites")
    return result


def normalized(provider: str, market_cap, volume, dominance, change, count,
               now: datetime, source_updated_at: str | None) -> dict:
    if now.tzinfo is None:
        raise ValueError("Horodatage sans fuseau horaire")
    if provider not in PROVIDERS:
        raise ValueError("Source non autorisée")
    cap = finite_number(market_cap, "market_cap_usd", low=1_000_000, high=1e16)
    vol = finite_number(volume, "volume_24h_usd", low=1, high=1e15)
    validate_global_usd(cap, vol)  # shared USD scale guard across #01/#03/#06/#07
    btc = finite_number(dominance, "btc_dominance_pct", low=0.01, high=99.99)
    variation = finite_number(change, "market_cap_change_24h_pct", low=-100, high=100)
    coins = int(finite_number(count, "cryptocurrencies_number", low=1, high=1000000))
    if source_updated_at is not None:
        dt = datetime.fromisoformat(source_updated_at)
        if dt.tzinfo is None or not -300 <= (now - dt).total_seconds() <= 6 * 3600:
            raise ValueError("Mesure fournisseur périmée ou future")
    return {
        "status": "real_data", "is_demo": False,
        "provider": provider,
        "source_url": PAPRIKA_URL if provider == "CoinPaprika" else COINLORE_URL,
        "collected_at": now.astimezone(UTC).isoformat(),
        "source_updated_at": source_updated_at,
        "market_cap_usd": cap,
        "volume_24h_usd": vol,
        "btc_dominance_pct": btc,
        "other_dominance_pct": round(100 - btc, 8),
        "market_cap_change_24h_pct": variation,
        "cryptocurrencies_number": coins,
    }


def parse_paprika(payload, now: datetime) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("CoinPaprika: réponse invalide")
    stamp = payload.get("last_updated")
    if isinstance(stamp, bool) or stamp is None:
        raise ValueError("CoinPaprika: date source manquante")
    try:
        measured = datetime.fromtimestamp(int(stamp), tz=UTC).isoformat()
    except (ValueError, TypeError, OverflowError, OSError) as exc:
        raise ValueError("CoinPaprika: date invalide") from exc
    # CoinPaprika Free renvoie parfois deux variations 24h à zéro simultanément :
    # ce couple peut représenter des champs indisponibles, pas un marché immobile.
    # Ne publions pas 0,00 % comme une mesure certaine ; préférons CoinLore.
    cap_change = payload.get("market_cap_change_24h")
    vol_change = payload.get("volume_24h_change_24h")
    if cap_change is not None and vol_change is not None:
        if (finite_number(cap_change, "market_cap_change_24h", low=-100, high=100) == 0 and
                finite_number(vol_change, "volume_24h_change_24h", low=-100, high=100) == 0):
            raise ValueError("CoinPaprika : variations 24h nulles simultanées, donnée douteuse")
    return normalized("CoinPaprika", payload.get("market_cap_usd"),
                      payload.get("volume_24h_usd"),
                      payload.get("bitcoin_dominance_percentage"),
                      payload.get("market_cap_change_24h"),
                      payload.get("cryptocurrencies_number"), now, measured)


def parse_coinlore(payload, now: datetime) -> dict:
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        raise ValueError("CoinLore: réponse invalide")
    p = payload[0]
    # CoinLore ne fournit pas d'horodatage source sur cet endpoint:
    # la carte affichera l'heure de consultation, PAS l'heure de mesure.
    return normalized("CoinLore", p.get("total_mcap"), p.get("total_volume"),
                      p.get("btc_d"), p.get("mcap_change"), p.get("coins_count"),
                      now, None)


def validate_real(payload: dict, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    if not isinstance(payload, dict) or payload.get("status") != "real_data" or payload.get("is_demo") is not False:
        raise ValueError("La simulation n'est pas publiable")
    dt = datetime.fromisoformat(str(payload.get("collected_at", "")))
    if dt.tzinfo is None or not -300 <= (now - dt).total_seconds() <= 30 * 60:
        raise ValueError("Capture des données trop ancienne")
    recalculated = normalized(payload["provider"], payload["market_cap_usd"],
                payload["volume_24h_usd"], payload["btc_dominance_pct"],
                payload["market_cap_change_24h_pct"],
                payload["cryptocurrencies_number"], dt,
                payload.get("source_updated_at"))
    for field in ("provider", "source_url", "market_cap_usd", "volume_24h_usd",
                  "btc_dominance_pct", "other_dominance_pct",
                  "market_cap_change_24h_pct", "cryptocurrencies_number"):
        if payload.get(field) != recalculated[field]:
            raise ValueError(f"Champ modifié ou incohérent : {field}")


def demo_data() -> dict:
    now = datetime(2026, 10, 17, 12, tzinfo=UTC)
    data = normalized("CoinPaprika", 2_800_000_000_000, 110_000_000_000,
                      57.3, -1.2, 10833, now, now.isoformat())
    data.update(status="demo", is_demo=True, provider="SIMULATION", source_url="")
    return data


def export(*, demo=False):
    if demo:
        data, target = demo_data(), DEMO_OUTPUT
    else:
        now = datetime.now(UTC)
        errors = []
        data = None
        for provider, url, parser in (("CoinPaprika", PAPRIKA_URL, parse_paprika),
                                      ("CoinLore", COINLORE_URL, parse_coinlore)):
            try:
                data = parser(request_json(url), now)
                break
            except (ValueError, RuntimeError, KeyError) as exc:
                errors.append(provider + ": " + str(exc))
        if data is None:
            raise RuntimeError("Aucune donnée mondiale valide : " + "; ".join(errors))
        validate_real(data, now)
        target = REAL_OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DOMINANCE_V2_EXPORTED", data["status"], data["provider"], target)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    export(demo=args.demo)
