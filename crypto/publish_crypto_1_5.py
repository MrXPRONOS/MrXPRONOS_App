#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Actu Crypto - premier lot 1/5 : prix, hausses, baisses, alertes, sentiment.

100 % sources gratuites. Même bot que les actus Foot mais chat_id distinct.
Exécuter avec --dry-run pour vérifier sans envoyer de messages.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from crypto.render_premium_cards import render_prices_card, render_movers_card, render_alert_card, render_fear_card

UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / "crypto" / "telegram_state.json"
OUT_DIR = ROOT / "crypto" / "generated"
WATCH = ("BTC", "ETH", "SOL", "BNB", "XRP")
STABLE = {"USDT", "USDC", "DAI", "FDUSD", "TUSD", "USDD", "PYUSD", "USDE", "USD1", "USDS", "RLUSD"}
PAPRIKA = "https://api.coinpaprika.com/v1/tickers"
COINLORE = "https://api.coinlore.net/api/tickers/"
GECKO = "https://api.coingecko.com/api/v3/coins/markets"
FEAR = "https://api.alternative.me/fng/"
TIMEOUT = (8, 30)
LOG = logging.getLogger("actu_crypto")
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "ActuCryptoTelegram/1.0 (data attribution in messages)", "Accept": "application/json"})
TOKEN = (os.getenv("TELEGRAM_ACTU_FOOT_BOT_TOKEN") or os.getenv("ACTU_FOOT_BOT_TOKEN")
         or os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
CHAT = (os.getenv("ACTU_CRYPTO_CHAT_ID") or "").strip()


def request_json(url: str, *, params=None, headers=None):
    """Retry uniquement pour lectures publiques; 429 et erreurs temporaires."""
    for attempt in range(3):
        try:
            r = SESSION.get(url, params=params, headers=headers, timeout=TIMEOUT)
            if r.status_code in (429, 500, 502, 503, 504):
                if attempt < 2:
                    time.sleep(min(2 ** attempt + 1, 8))
                    continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            if attempt == 2:
                raise RuntimeError("Lecture API impossible: " + url.split("?")[0]) from exc
            time.sleep(1 + attempt)
    raise RuntimeError("API non disponible: " + url)


def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def valid_timestamp(raw):
    if not raw:
        return True
    try:
        if isinstance(raw, (int, float)):
            dt = datetime.fromtimestamp(float(raw), UTC)
        else:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
        return -300 <= (datetime.now(UTC) - dt).total_seconds() <= 7200
    except (ValueError, TypeError, OverflowError):
        return False


def clean_row(symbol, name, rank, price, change, volume, timestamp=None):
    price, change, volume = number(price), number(change), number(volume)
    rank = int(number(rank) or 0)
    symbol = str(symbol or "").strip().upper()
    if not symbol or not price or price <= 0 or change is None or abs(change) > 5000:
        return None
    if timestamp and not valid_timestamp(timestamp):
        return None
    return {"symbol": symbol, "name": str(name or symbol), "rank": rank,
            "price": price, "change": change, "volume": volume or 0}


def from_paprika():
    raw = request_json(PAPRIKA, params={"quotes": "USD"})
    if not isinstance(raw, list):
        raise RuntimeError("CoinPaprika: format inattendu")
    rows = []
    for item in raw:
        usd = (item.get("quotes") or {}).get("USD") or {}
        row = clean_row(item.get("symbol"), item.get("name"), item.get("rank"),
                        usd.get("price"), usd.get("percent_change_24h"),
                        usd.get("volume_24h"), item.get("last_updated"))
        if row:
            rows.append(row)
    return rows


def from_coinlore():
    raw = request_json(COINLORE, params={"start": 0, "limit": 100})
    if not isinstance(raw, dict):
        raise RuntimeError("CoinLore: format inattendu")
    if not valid_timestamp((raw.get("info") or {}).get("time")):
        raise RuntimeError("CoinLore: données périmées")
    rows = []
    for item in raw.get("data") or []:
        row = clean_row(item.get("symbol"), item.get("name"), item.get("rank"),
                        item.get("price_usd"), item.get("percent_change_24h"), item.get("volume24"))
        if row:
            rows.append(row)
    return rows


def from_gecko():
    key = (os.getenv("COINGECKO_DEMO_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("Clé CoinGecko gratuite absente")
    raw = request_json(GECKO,
        params={"vs_currency": "usd", "order": "market_cap_desc",
                "per_page": 100, "page": 1, "sparkline": "false"},
        headers={"x-cg-demo-api-key": key})
    if not isinstance(raw, list):
        raise RuntimeError("CoinGecko: format inattendu")
    rows = []
    for item in raw:
        row = clean_row(item.get("symbol"), item.get("name"), item.get("market_cap_rank"),
                        item.get("current_price"), item.get("price_change_percentage_24h"),
                        item.get("total_volume"), item.get("last_updated"))
        if row:
            rows.append(row)
    return rows


def market():
    """Un fournisseur unique par message: ne mélange jamais les variations."""
    for name, fetch in (("CoinPaprika", from_paprika), ("CoinLore", from_coinlore),
                        ("CoinGecko", from_gecko)):
        try:
            rows = fetch()
            symbols = {r["symbol"] for r in rows if 1 <= r["rank"] <= 100}
            if len(rows) >= 40 and all(sym in symbols for sym in WATCH):
                LOG.info("Provider %s: %s coins", name, len(rows))
                return rows, name
            LOG.warning("Provider %s incomplet: %s coins", name, len(rows))
        except (RuntimeError, requests.RequestException) as exc:
            LOG.warning("Provider %s indisponible: %s", name, type(exc).__name__)
    raise RuntimeError("Aucune source crypto valide; publication suspendue")


def selected_watch(rows):
    """Choisit la vraie monnaie au mieux classée pour chaque symbole."""
    found = {}
    for row in sorted(rows, key=lambda r: r["rank"] or 999999):
        if row["symbol"] in WATCH and row["symbol"] not in found and row["rank"] > 0:
            found[row["symbol"]] = row
    if len(found) != len(WATCH):
        raise RuntimeError("Il manque des cryptos suivies")
    return [found[sym] for sym in WATCH]


def usd(value):
    if value >= 1000:
        return f"${value:,.2f}".replace(",", " ")
    if value >= 1:
        return f"${value:.2f}"
    return f"${value:.6f}".rstrip("0").rstrip(".")


def pct(value):
    return f"{'+' if value > 0 else ''}{value:.2f} %"


def stamp(now):
    return now.strftime("%d/%m/%Y %H:%M UTC")


def format_prices(rows, source, now):
    lines = ["📊 ACTU CRYPTO | COURS DU MARCHÉ", "🕐 " + stamp(now), "",
             "Prix indicatifs en dollars américains (USD) :"]
    for r in selected_watch(rows):
        sign = "🟢" if r["change"] >= 0 else "🔴"
        lines.append(f"{sign} {r['symbol']} : {usd(r['price'])} | 24h : {pct(r['change'])}")
    return "\n".join(lines + ["", "ℹ️ Variation glissante sur 24 h, prix indicatifs.", "Source : " + source])


def movers(rows, direction):
    """Top parmi les 100 plus grandes capitalisations et volume >= 1 M USD."""
    filtered = [r for r in rows if 1 <= r["rank"] <= 100 and
                r["symbol"] not in STABLE and r["volume"] >= 1_000_000 and
                (r["change"] > 0 if direction == "up" else r["change"] < 0)]
    filtered.sort(key=lambda r: r["change"], reverse=(direction == "up"))
    unique = {}
    for row in filtered:
        unique.setdefault(row["symbol"], row)
    result = list(unique.values())[:5]
    if len(result) < 5:
        raise RuntimeError("Moins de 5 cryptos valides pour top " + direction)
    return result


def format_movers(rows, source, now, direction):
    rising = direction == "up"
    title = "🚀 TOP 5 DES HAUSSES" if rising else "📉 TOP 5 DES BAISSES"
    lines = [title, "🕐 " + stamp(now), "", "Variation sur les dernières 24 h :"]
    for i, r in enumerate(movers(rows, direction), 1):
        lines.append(f"{i}. {r['name']} ({r['symbol']}) : {pct(r['change'])} | {usd(r['price'])}")
    return "\n".join(lines + ["", "Univers : top 100 par capitalisation, volume ≥ 1 M$ sur 24 h.",
                                "Source : " + source, "⚠️ Les performances passées ne prédisent pas l'avenir."])


def fear_index():
    raw = request_json(FEAR, params={"limit": 1, "format": "json"})
    records = raw.get("data") or []
    if raw.get("metadata", {}).get("error") or not records:
        raise RuntimeError("Fear & Greed : réponse invalide")
    value = int(records[0]["value"])
    if not (0 <= value <= 100):
        raise RuntimeError("Fear & Greed : indice hors borne")
    # L'indice est publié quotidiennement : tolérance jusqu'à 48 h.
    ts = datetime.fromtimestamp(int(records[0]["timestamp"]), UTC)
    age = (datetime.now(UTC) - ts).total_seconds()
    if not (-300 <= age <= 48 * 3600):
        raise RuntimeError("Fear & Greed : indice périmé")
    return value, ts


def format_fear(value, observed_at, now):
    if value <= 24:
        mood = "Peur extrême 😱"
    elif value <= 44:
        mood = "Peur 😟"
    elif value <= 54:
        mood = "Neutre 😐"
    elif value <= 74:
        mood = "Avidité 🙂"
    else:
        mood = "Avidité extrême 🔥"
    return "\n".join(["🧠 SENTIMENT DU MARCHÉ CRYPTO", "🕐 " + stamp(now), "",
                      f"Fear & Greed : {value}/100 — {mood}", "",
                      "Cet indicateur mesure le sentiment du marché, pas sa direction future.",
                      "Date de la mesure : " + observed_at.strftime("%d/%m/%Y UTC"),
                      "Source : Alternative.me (Crypto Fear & Greed Index)",
                      "https://alternative.me/crypto/fear-and-greed-index/"])


def read_state():
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def send(text, dry_run):
    if dry_run:
        print("\n---- PREVISUALISATION ----\n" + text + "\n-------------------------")
        return True
    if not TOKEN or not CHAT:
        raise RuntimeError("Configurer TELEGRAM_ACTU_FOOT_BOT_TOKEN (ou TELEGRAM_BOT_TOKEN) et ACTU_CRYPTO_CHAT_ID")
    # POST ambigu : ne pas retenter sans certitude pour éviter les doublons.
    try:
        r = SESSION.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                         json={"chat_id": CHAT, "text": text,
                               "disable_web_page_preview": True}, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise RuntimeError("Telegram : réponse incertaine, pas de renvoi automatique") from exc
    if r.status_code != 200:
        raise RuntimeError(f"Telegram : HTTP {r.status_code} (vérifier bot, droits et canal)")
    try:
        if not r.json().get("ok"):
            raise RuntimeError("Telegram : réponse sans confirmation")
    except ValueError as exc:
        raise RuntimeError("Telegram : réponse JSON invalide") from exc
    LOG.info("Publication Telegram confirmée")


def send_photo(text, file_path, dry_run):
    """Publie image PNG + légende depuis le même bot Actu Foot."""
    if dry_run:
        print("APERÇU PNG:", file_path, "\\n", text)
        return
    if not TOKEN or not CHAT:
        raise RuntimeError("Bot/token ou ACTU_CRYPTO_CHAT_ID absent")
    from pathlib import Path
    with Path(file_path).open("rb") as f:
        try:
            response = SESSION.post(
                f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                data={"chat_id": CHAT, "caption": text[:1024]},
                files={"photo": (Path(file_path).name, f, "image/png")},
                timeout=(10, 90))
        except requests.RequestException as exc:
            raise RuntimeError("Réponse Telegram incertaine: ne pas retenter") from exc
    if response.status_code != 200:
        raise RuntimeError("Telegram sendPhoto HTTP " + str(response.status_code))
    if not response.json().get("ok"):
        raise RuntimeError("Telegram a refusé la photo")


def once(state, key, text, file_path, dry_run):
    if state.get("sent", {}).get(key):
        LOG.info("Déjà publié: %s", key)
        return False
    send_photo(text, file_path, dry_run)
    if not dry_run:
        state.setdefault("sent", {})[key] = datetime.now(UTC).isoformat()
    return True


def run_alerts(state, rows, source, now, dry_run):
    watch_state = state.setdefault("alerts", {})
    for row in selected_watch(rows):
        change = row["change"]
        symbol = row["symbol"]
        level = int(abs(change) // 5) * 5 if abs(change) >= 5 else 0
        direction = "+" if change > 0 else "-"
        prior = watch_state.get(symbol) or {}
        # Une nouvelle alerte est possible après un retour sous le seuil,
        # ou si un palier de 5 points supplémentaire est franchi.
        if level < 5:
            if not dry_run:
                watch_state[symbol] = {"direction": "", "level": 0}
            continue
        if prior.get("direction") == direction and int(prior.get("level") or 0) >= level:
            continue
        message = "\n".join([f"🚨 ALERTE {symbol} | VARIATION 24 H",
                              f"🕐 {stamp(now)}", "",
                              f"Prix : {usd(row['price'])}",
                              f"Variation sur 24 h : {pct(change)}",
                              f"Seuil franchi : {'+' if change > 0 else '-'}{level} %",
                              "", "ℹ️ Alerte sur variation 24 h, pas sur la dernière heure.",
                              "Source : " + source])
        image_path = render_alert_card(row, source, now, level, OUT_DIR / f"alert_{symbol.lower()}.png")
        send_photo(message, image_path, dry_run)
        if not dry_run:
            watch_state[symbol] = {"direction": direction, "level": level,
                                   "sent_at": now.isoformat()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("prices", "gainers", "losers", "movers", "alerts", "fear", "all"),
                        default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    if not args.dry_run and (not TOKEN or not CHAT):
        parser.error("Secrets Telegram manquants : bot de l'Actu Foot et ACTU_CRYPTO_CHAT_ID")
    now = datetime.now(UTC)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state = read_state()
    date = now.strftime("%Y-%m-%d")
    slot = now.strftime("%H")
    market_modes = {"prices", "gainers", "losers", "movers", "alerts", "all"}
    rows, source = market() if args.mode in market_modes else (None, None)
    try:
        if args.mode in ("prices", "all"):
            once(state, f"prices:{date}:{slot}", format_prices(rows, source, now), render_prices_card(selected_watch(rows), source, now, OUT_DIR / "prices.png"), args.dry_run)
        if args.mode in ("gainers", "movers", "all"):
            once(state, f"gainers:{date}:{slot}", format_movers(rows, source, now, "up"), render_movers_card(movers(rows,"up"), source, now, "up", OUT_DIR / "gainers.png"), args.dry_run)
        if args.mode in ("losers", "movers", "all"):
            once(state, f"losers:{date}:{slot}", format_movers(rows, source, now, "down"), render_movers_card(movers(rows,"down"), source, now, "down", OUT_DIR / "losers.png"), args.dry_run)
        if args.mode in ("fear", "all"):
            value, date_source = fear_index()
            once(state, f"fear:{date}", format_fear(value, date_source, now), render_fear_card(value, date_source, now, OUT_DIR / "fear.png"), args.dry_run)
        if args.mode in ("alerts", "all"):
            run_alerts(state, rows, source, now, args.dry_run)

    finally:
        if not args.dry_run:
            # Garder uniquement 14 jours de créneaux publiés.
            sent = state.setdefault("sent", {})
            if len(sent) > 280:
                state["sent"] = dict(sorted(sent.items(), key=lambda kv: kv[1], reverse=True)[:200])
            save_state(state)


if __name__ == "__main__":
    main()
