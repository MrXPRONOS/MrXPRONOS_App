"""Publication 07 — Bilan crypto des 7 derniers jours (sources gratuites).

Périmètre clair : variations 7 jours des COURS, pas de la capitalisation globale.
Capitalisation, dominance et volume 24h sont des instantanés.
Démo isolée : elle ne peut jamais être envoyée sur Telegram.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from crypto.publish_crypto_1_5 import request_json
from crypto.export_dominance_v2 import parse_paprika, parse_coinlore

UTC = timezone.utc
PAPRIKA_TICKERS = "https://api.coinpaprika.com/v1/tickers"
PAPRIKA_GLOBAL = "https://api.coinpaprika.com/v1/global"
LORE_TICKERS = "https://api.coinlore.net/api/tickers/"
LORE_GLOBAL = "https://api.coinlore.net/api/global/"
FEAR_API = "https://api.alternative.me/fng/"
OUT = Path("crypto/generated/test/weekly_v2_data.json")
DEMO_OUT = Path("crypto/generated/test/weekly_v2_demo.json")
STABLE = {"USDT", "USDC", "DAI", "FDUSD", "TUSD", "USDD", "PYUSD", "USDE",
          "USD1", "USDS", "RLUSD", "BUSD", "FRAX", "EURC"}
ALLOWED = {"CoinPaprika", "CoinLore"}


def number(raw, field: str, lo: float, hi: float) -> float:
    if raw is None or isinstance(raw, bool):
        raise ValueError(field + " manquant")
    try:
        v = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(field + " incorrect") from exc
    if not math.isfinite(v) or not lo <= v <= hi:
        raise ValueError(field + " hors limites")
    return v


def stamp(raw, now: datetime, max_hours: int) -> datetime:
    if isinstance(raw, bool) or raw is None:
        raise ValueError("Horodatage source absent")
    try:
        if isinstance(raw, (int, float)) or str(raw).isdigit():
            dt = datetime.fromtimestamp(int(raw), UTC)
        else:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError, OSError) as exc:
        raise ValueError("Date source incorrecte") from exc
    if dt.tzinfo is None or not -300 <= (now - dt).total_seconds() <= max_hours * 3600:
        raise ValueError("Horodatage trop ancien ou futur")
    return dt


def from_paprika(payload, now: datetime):
    if not isinstance(payload, list):
        raise ValueError("Tickers CoinPaprika incorrects")
    output = []
    for r in payload:
        if not isinstance(r, dict) or not isinstance(r.get("quotes"), dict):
            continue
        try:
            rank = int(number(r.get("rank"), "rang", 1, 100))
            q = r["quotes"]["USD"]
            updated = stamp(r.get("last_updated"), now, 3)
            output.append({
                "symbol": str(r["symbol"]).upper().strip(), "rank": rank,
                "price_usd": number(q.get("price"), "prix", 0.000000001, 1e9),
                "change_7d": number(q.get("percent_change_7d"), "7j", -99.99, 5000),
                "volume_24h": number(q.get("volume_24h"), "volume", 0, 1e15),
                "stamp": updated.isoformat(),
            })
        except (ValueError, KeyError, TypeError):
            continue
    return output


def from_lore(payload, now: datetime):
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("Tickers CoinLore incorrects")
    source_time = stamp((payload.get("info") or {}).get("time"), now, 3)
    output = []
    for r in payload["data"]:
        if not isinstance(r, dict):
            continue
        try:
            rank = int(number(r.get("rank"), "rang", 1, 100))
            output.append({
                "symbol": str(r["symbol"]).upper().strip(), "rank": rank,
                "price_usd": number(r.get("price_usd"), "prix", 0.000000001, 1e9),
                "change_7d": number(r.get("percent_change_7d"), "7j", -99.99, 5000),
                "volume_24h": number(r.get("volume24"), "volume", 0, 1e15),
                "stamp": source_time.isoformat(),
            })
        except (ValueError, KeyError, TypeError):
            continue
    return output


def select_assets(rows: list) -> dict:
    unique = {}
    for row in sorted(rows, key=lambda r: r["rank"]):
        sym = row.get("symbol", "")
        if sym and sym not in unique:
            unique[sym] = row
    if len(unique) < 40 or not all(s in unique for s in ("BTC", "ETH")):
        raise ValueError("Marché ou actifs majeurs incomplets")
    eligible = [r for r in unique.values() if r["symbol"] not in STABLE
                and r["volume_24h"] >= 1_000_000 and r["symbol"] not in ("BTC", "ETH")]
    if len(eligible) < 6:
        raise ValueError("Pas assez de cryptos liquides pour le classement")
    up = sorted(eligible, key=lambda r: (-r["change_7d"], r["rank"]))[:3]
    down = sorted(eligible, key=lambda r: (r["change_7d"], r["rank"]))[:3]
    if len({r["symbol"] for r in up + down}) < 6:
        raise ValueError("Chevauchement classement hebdomadaire")
    short = lambda r: {"symbol": r["symbol"], "change_7d": r["change_7d"]}
    return {
        "btc": {"symbol": "BTC", "price_usd": unique["BTC"]["price_usd"],
                "change_7d": unique["BTC"]["change_7d"]},
        "eth": {"symbol": "ETH", "price_usd": unique["ETH"]["price_usd"],
                "change_7d": unique["ETH"]["change_7d"]},
        "winners": [short(r) for r in up], "losers": [short(r) for r in down],
    }


def parse_fear(payload, now: datetime) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("Fear & Greed non disponible")
    if not isinstance(payload.get("metadata"), dict) or payload["metadata"].get("error"):
        raise ValueError("Erreur du fournisseur Fear & Greed")
    days = {}
    for r in payload["data"]:
        if not isinstance(r, dict):
            raise ValueError("Mesure Fear & Greed invalide")
        score = int(number(r.get("value"), "sentiment", 0, 100))
        time = stamp(r.get("timestamp"), now, 24 * 30)
        day = time.date().isoformat()
        if day in days and days[day]["score"] != score:
            raise ValueError("Valeurs de sentiment contradictoires")
        days[day] = {"date": day, "score": score, "timestamp": time.isoformat()}
    ordered = [days[k] for k in sorted(days)][-8:]
    if len(ordered) != 8:
        raise ValueError("Huit mesures quotidiennes requises pour calculer 7 jours")
    for a, b in zip(ordered, ordered[1:]):
        if (datetime.fromisoformat(b["date"]) - datetime.fromisoformat(a["date"])).days != 1:
            raise ValueError("Jour manquant dans les mesures")
    stamp(ordered[-1]["timestamp"], now, 48)
    return {
        "score": ordered[-1]["score"], "delta_7d": ordered[-1]["score"] - ordered[0]["score"],
        "history": [{"date": r["date"], "score": r["score"]} for r in ordered],
        "observed_at": ordered[-1]["timestamp"],
    }


def build_report(provider: str, rows: list, global_stats: dict, fear: dict, now: datetime) -> dict:
    if provider not in ALLOWED:
        raise ValueError("Source de marché interdite")
    assets = select_assets(rows)
    # La couverture des fournisseurs n'est pas forcément identique.
    return {
        "status": "real_data", "is_demo": False, "provider": provider,
        "market_source": PAPRIKA_GLOBAL if provider == "CoinPaprika" else LORE_GLOBAL,
        "fear_source": "Alternative.me", "collected_at": now.isoformat(),
        "period": "7 derniers jours (glissants)", "market_cap_usd": global_stats["market_cap_usd"],
        "volume_24h_usd": global_stats["volume_24h_usd"],
        "btc_dominance_pct": global_stats["btc_dominance_pct"],
        "market_source_updated_at": global_stats["source_updated_at"],
        "btc": assets["btc"], "eth": assets["eth"],
        "winners": assets["winners"], "losers": assets["losers"], "fear": fear,
    }


def validate_real(report: dict, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    if report.get("status") != "real_data" or report.get("is_demo") is not False:
        raise ValueError("Publication fictive interdite")
    provider = report.get("provider")
    if provider not in ALLOWED or report.get("fear_source") != "Alternative.me":
        raise ValueError("Fournisseur non approuvé")
    expected_url = PAPRIKA_GLOBAL if provider == "CoinPaprika" else LORE_GLOBAL
    if report.get("market_source") != expected_url:
        raise ValueError("Source non cohérente")
    stamp(report.get("collected_at"), now, 1)
    if provider == "CoinPaprika":
        stamp(report.get("market_source_updated_at"), now, 6)
    elif report.get("market_source_updated_at") is not None:
        raise ValueError("CoinLore ne fournit pas d'heure de mesure")
    number(report.get("market_cap_usd"), "capitalisation", 1e6, 1e16)
    number(report.get("volume_24h_usd"), "volume", 1, 1e15)
    number(report.get("btc_dominance_pct"), "dominance", 0.01, 99.99)
    for ticker in ("btc", "eth"):
        r = report.get(ticker)
        if not isinstance(r, dict) or r.get("symbol") != ticker.upper():
            raise ValueError("Actif majeur manquant")
        number(r.get("price_usd"), "prix", 0.000000001, 1e9)
        number(r.get("change_7d"), "variation 7j", -99.99, 5000)
    symbols = []
    for typ in ("winners", "losers"):
        items = report.get(typ)
        if not isinstance(items, list) or len(items) != 3:
            raise ValueError("Classement incomplet")
        for row in items:
            if not isinstance(row, dict) or not isinstance(row.get("symbol"), str) or not row["symbol"]:
                raise ValueError("Crypto non identifiable")
            if row["symbol"] in STABLE or row["symbol"] in ("BTC", "ETH"):
                raise ValueError("Actif exclu")
            number(row.get("change_7d"), "variation", -99.99, 5000)
            symbols.append(row["symbol"])
        vals = [r["change_7d"] for r in items]
        if vals != sorted(vals, reverse=(typ == "winners")):
            raise ValueError("Classement mal ordonné")
    if len(set(symbols)) != 6:
        raise ValueError("Crypto répétée dans le classement")
    f = report.get("fear")
    if not isinstance(f, dict):
        raise ValueError("Sentiment manquant")
    stamp(f.get("observed_at"), now, 48)
    h = f.get("history")
    if not isinstance(h, list) or len(h) != 8:
        raise ValueError("Historique de sentiment incomplet")
    for entry in h:
        if not isinstance(entry, dict):
            raise ValueError("Historique de sentiment incorrect")
        datetime.fromisoformat(entry["date"])
        if int(number(entry.get("score"), "score", 0, 100)) != entry["score"]:
            raise ValueError("Score non entier")
    for a, b in zip(h, h[1:]):
        if (datetime.fromisoformat(b["date"]) - datetime.fromisoformat(a["date"])).days != 1:
            raise ValueError("Historique avec date manquante")
    if f.get("score") != h[-1]["score"] or f.get("delta_7d") != h[-1]["score"] - h[0]["score"]:
        raise ValueError("Sentiment incohérent")
    if datetime.fromisoformat(f["observed_at"]).date().isoformat() != h[-1]["date"]:
        raise ValueError("Date sentiment incohérente")


def demo_report() -> dict:
    now = datetime(2026, 10, 18, 9, 17, tzinfo=UTC)
    def row(s, n): return {"symbol": s, "rank": n, "price_usd": 150+n,
                            "change_7d": 20-n*1.5, "volume_24h": 50000000,
                            "stamp": now.isoformat()}
    rows = [row("BTC", 1), row("ETH", 2)] + [row("COIN"+str(n), n) for n in range(3, 55)]
    rows[0]["price_usd"] = 92000
    rows[1]["price_usd"] = 3600
    values = [41, 44, 48, 50, 56, 52, 58, 55]
    history = [{"date": (now.date()-timedelta(days=7-i)).isoformat(), "score": v}
               for i, v in enumerate(values)]
    fear = {"score": 55, "delta_7d": 14, "history": history,
            "observed_at": now.replace(hour=0).isoformat()}
    report = build_report("CoinPaprika", rows, {
        "market_cap_usd": 3.2e12, "volume_24h_usd": 97e9,
        "btc_dominance_pct": 57.4, "source_updated_at": now.isoformat()}, fear, now)
    report.update(status="demo", is_demo=True, provider="SIMULATION", market_source="")
    return report


def export(demo: bool = False) -> Path:
    if demo:
        report, target = demo_report(), DEMO_OUT
    else:
        now = datetime.now(UTC)
        errors = []
        report = None
        # Un seul fournisseur pour les cours 7j ET pour la capitalisation.
        for name, tickers_url, global_url, parser, stats_parser in (
            ("CoinPaprika", PAPRIKA_TICKERS, PAPRIKA_GLOBAL, from_paprika, parse_paprika),
            ("CoinLore", LORE_TICKERS, LORE_GLOBAL, from_lore, parse_coinlore),
        ):
            try:
                ticker_json = request_json(tickers_url,
                    params={"quotes": "USD"} if name == "CoinPaprika" else {"start": 0, "limit": 100})
                global_json = request_json(global_url)
                rows = parser(ticker_json, now)
                stats = stats_parser(global_json, now)
                fear_json = request_json(FEAR_API, params={"limit": 8, "format": "json"})
                fear = parse_fear(fear_json, now)
                report = build_report(name, rows, stats, fear, now)
                validate_real(report, now)
                break
            except (ValueError, RuntimeError, KeyError, TypeError) as exc:
                errors.append(name + ": " + str(exc))
        if report is None:
            raise RuntimeError("Données réelles insuffisantes : " + "; ".join(errors))
        target = OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("WEEKLY_V2_EXPORTED", report["status"], report["provider"], target)
    return target


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="Générer seulement une maquette fictive")
    args = ap.parse_args()
    export(args.demo)
