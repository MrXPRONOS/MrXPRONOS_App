"""One-time, real-only, one-by-one crypto history seeding.

Production retry after verified channel administrator rights were added.
Second pass: sent IDs 2-6 recorded; only currently missing real posters may be posted.

Usage: python -m crypto.production_seed_v1 --number 1..10
Only sends supported validated REAL PNGs to ACTU_CRYPTO_CHAT_ID.
Never sends demos, never targets @predict_mrxp and never retries uncertain posts.
State kept in crypto/production_state.json and persisted by CI.

#10 is deliberately gated: no real legal statements before editorial approval.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

UTC = timezone.utc
ROOT = Path("crypto/generated/test")
STATE = Path("crypto/production_state.json")
WATCH = {"BTC", "ETH", "SOL", "BNB", "XRP"}
ALLOWED_PROVIDERS = {"CoinPaprika", "CoinLore", "CoinGecko"}
TOKEN_CANDIDATES = list(dict.fromkeys(
    token.strip() for token in (
        os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "",
        os.getenv("TELEGRAM_ACTU_FOOT_BOT_TOKEN") or "",
        os.getenv("ACTU_FOOT_BOT_TOKEN") or "",
        os.getenv("TELEGRAM_BOT_TOKEN") or "",
    ) if token and token.strip()
))
TOKEN = TOKEN_CANDIDATES[0] if TOKEN_CANDIDATES else ""
CHAT = (os.getenv("ACTU_CRYPTO_CHAT_ID") or "").strip()


def datetime_from(value: str):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timestamp without timezone")
    return dt.astimezone(UTC)


def recent(value: str, maximum_hours: float = 3):
    lag = (datetime.now(UTC) - datetime_from(value)).total_seconds()
    if not -300 <= lag <= 3600 * maximum_hours:
        raise ValueError("Real dataset timestamp outside live freshness window")


def read_json(path: Path) -> dict:
    if not path.is_file():
        raise ValueError("Real JSON unavailable: " + path.name)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Invalid JSON format")
    return data


def run(*args):
    # No shell; failures block send of this publication.
    subprocess.run(args, check=True)


def verify_production_route() -> dict:
    global TOKEN
    if not TOKEN_CANDIDATES or not CHAT:
        raise RuntimeError(
            "Missing production bot token or ACTU_CRYPTO_CHAT_ID "
            "(configure GitHub repository secret or variable)."
        )
    if CHAT.lower().lstrip("@") == "predict_mrxp":
        raise RuntimeError("The TEST channel is forbidden as production destination")

    def telegram_read(method, params):
        try:
            resp = requests.get(
                "https://api.telegram.org/bot" + TOKEN + "/" + method,
                params=params, timeout=(8, 20))
            resp.raise_for_status()
            payload = resp.json()
        except requests.HTTPError as exc:
            code = getattr(exc.response, "status_code", "unknown")
            raise RuntimeError(
                "Telegram preflight " + method + " HTTP " + str(code) +
                " (check bot token, channel membership, and bot permissions)"
            ) from None
        except requests.RequestException as exc:
            raise RuntimeError(
                "Telegram preflight " + method + " network failure: " +
                type(exc).__name__
            ) from None
        except ValueError:
            raise RuntimeError("Telegram preflight " + method + " invalid JSON") from None
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise RuntimeError("Telegram rejected route check " + method)
        result = payload.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("Telegram returned invalid " + method)
        return result

    attempts = []
    for index, candidate in enumerate(TOKEN_CANDIDATES, start=1):
        TOKEN = candidate
        try:
            me = telegram_read("getMe", {})
            chat = telegram_read("getChat", {"chat_id": CHAT})
            if chat.get("type") != "channel":
                raise RuntimeError("Destination is not a Telegram channel")
            if str(chat.get("username") or "").lower() == "predict_mrxp":
                raise RuntimeError("Cannot publish to test channel")
            bot_id = me.get("id")
            if not isinstance(bot_id, int):
                raise RuntimeError("Bot identity not returned")
            member = telegram_read(
                "getChatMember", {"chat_id": chat["id"], "user_id": bot_id})
            if not (member.get("status") == "creator" or
                    (member.get("status") == "administrator" and
                     member.get("can_post_messages") is True)):
                raise RuntimeError("Bot is not channel admin with post rights")
        except RuntimeError as exc:
            diagnostic = f"candidate={index} reason={str(exc)[:140]}"
            attempts.append(diagnostic)
            print("CRYPTO_PROD_ROUTE_CANDIDATE_REJECTED", diagnostic)
            continue
        print("CRYPTO_PROD_ROUTE_OK",
              "channel_verified=1", "bot_admin=1",
              "bot=@" + str(me.get("username") or "unknown"))
        return chat
    raise RuntimeError(
        "No configured Telegram bot is administrator with posting rights "
        "in ACTU_CRYPTO_CHAT_ID. " + "; ".join(attempts)
    )


def read_state() -> dict:
    if not STATE.exists():
        return {"sent": {}}
    state = read_json(STATE)
    if not isinstance(state.get("sent"), dict):
        raise ValueError("Broken production publication registry")
    return state


def write_state(state: dict):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_image(p: Path):
    if not p.is_file() or p.stat().st_size < 10000:
        raise ValueError("Real PNG missing or too small")
    with p.open("rb") as f:
        if f.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Image is not a PNG")


def validated_real(number: int, d: dict):
    if d.get("is_demo") is True or d.get("status") == "demo":
        raise ValueError("Demo source cannot enter production")
    if number == 1:
        recent(d["timestamp"])
        from crypto.financial_sanity import validate_global_usd
        validate_global_usd(d["rows"][0].get("market_cap_total"),
                            d["rows"][0].get("global_volume_24h"))
        if d["provider"] not in ALLOWED_PROVIDERS:
            raise ValueError("Unknown market data provider")
        rows = d["rows"]
        if len(rows) != 5 or set(r["symbol"] for r in rows) != WATCH:
            raise ValueError("Wrong major assets")
        if any(not isinstance(r.get("sparkline"), list) or len(r["sparkline"]) < 36 or r["price"] <= 0 for r in rows):
            raise ValueError("Invalid real 48h price charts")
    elif number in (2, 3):
        recent(d["timestamp"])
        if number == 3:
            from crypto.financial_sanity import validate_global_usd
            validate_global_usd(d["rows"][0].get("market_cap_total"),
                                d["rows"][0].get("global_volume_24h"))
        if d["provider"] not in ALLOWED_PROVIDERS or len(d["rows"]) != 5:
            raise ValueError("Top five data provider/count invalid")
        if any(int(r["rank"]) not in range(1, 101)
               or float(r["volume"]) < 1_000_000
               or float(r["price"]) <= 0
               or (float(r["change"]) <= 0 if number == 2 else float(r["change"]) >= 0)
               for r in d["rows"]):
            raise ValueError("Top five has invalid prices, ranks or variations")
    elif number == 4:
        if d.get("status") == "no_alert":
            return False
        if d.get("status") != "real_alert" or d.get("is_demo") is not False:
            raise ValueError("Refusing fictional alert")
        from crypto.export_alerts_v2 import threshold
        row = d["row"]
        if (row["symbol"] not in WATCH or
                threshold(float(row["change"])) != int(row["level"]) or
                int(row["level"]) < 5 or
                not isinstance(row.get("sparkline"), list) or
                len(row["sparkline"]) < 36):
            raise ValueError("Invalid real threshold alert")
        recent(d["collected_at"] if "collected_at" in d else d["timestamp"])
    elif number == 5:
        from crypto.send_crypto_fear_v2_test import validate_publication
        validate_publication(d)
    elif number == 6:
        from crypto.export_dominance_v2 import validate_real
        validate_real(d)
    elif number == 7:
        from crypto.export_weekly_v2 import validate_real
        validate_real(d)
    elif number == 8:
        from crypto.export_breaking_v2 import validate_real
        validate_real(d)
    elif number == 9:
        from crypto.export_exchanges_v2 import validate_real
        validate_real(d)
    else:
        raise RuntimeError("Regulatory #10 requires human legal review before real publication")
    return True


def prepared(number: int):
    if number == 10:
        raise RuntimeError("REG10_HOLD_FOR_HUMAN_REVIEW")
    tasks = {
        1: (("python", "-m", "crypto.test_channel_premium", "--export-design-json"),
            "scripts/render_crypto_market_v2.mjs", "market_design_data.json", "prices_v2.png"),
        2: (("python", "-m", "crypto.export_gainers_v2"),
            "scripts/render_crypto_gainers_v2.mjs", "gainers_v2_data.json", "gainers_v2.png"),
        3: (("python", "-m", "crypto.export_losers_v2"),
            "scripts/render_crypto_losers_v2.mjs", "losers_v2_data.json", "losers_v2.png"),
        4: (("python", "-m", "crypto.export_alerts_v2"),
            "scripts/render_crypto_alerts_v2.mjs", "alerts_v2_data.json", "alerts_v2.png"),
        5: (("python", "-m", "crypto.export_fear_v2"),
            "scripts/render_crypto_fear_v2.mjs", "fear_v2_data.json", "fear_v2.png"),
        6: (("python", "-m", "crypto.export_dominance_v2"),
            "scripts/render_crypto_dominance_v2.mjs", "dominance_v2_data.json", "dominance_v2.png"),
        7: (("python", "-m", "crypto.export_weekly_v2"),
            "scripts/render_crypto_weekly_v2.mjs", "weekly_v2_data.json", "weekly_v2.png"),
        8: (("python", "-m", "crypto.export_breaking_v2"),
            "scripts/render_crypto_breaking_v2.mjs", "breaking_v2_data.json", "breaking_v2.png"),
        9: (("python", "-m", "crypto.export_exchanges_v2"),
            "scripts/render_crypto_exchanges_v2.mjs", "exchanges_v2_data.json", "exchanges_v2.png"),
    }
    cmd, renderer, data_file, img_file = tasks[number]
    run(*cmd)
    data_path = ROOT / data_file
    # News collection may deliberately create no file.
    if number in (8, 9) and not data_path.is_file():
        print("CRYPTO_PROD_SKIP", number, "NO_QUALIFIED_RECENT_REAL_NEWS")
        return None
    d = read_json(data_path)
    if validated_real(number, d) is False:
        print("CRYPTO_PROD_SKIP", number, "NO_REAL_THRESHOLD")
        return None
    run("node", renderer)
    p = ROOT / img_file
    validate_image(p)
    return d, p


def price_caption(value: float) -> str:
    """Do not turn a real micro-cap token price into 0.00 USD in captions."""
    value = float(value)
    if value <= 0 or not __import__("math").isfinite(value):
        raise ValueError("Invalid asset price")
    if value >= 1:
        return f"{value:,.2f}"
    if value < 1e-10:
        return f"{value:.5g}"
    return f"{value:.12f}".rstrip("0").rstrip(".")


def caption_for(number: int, d: dict) -> str:
    if number == 1:
        rows = d["rows"]
        body = "\n".join(
            f"{r['symbol']}: {price_caption(r['price'])} USD | 24h {float(r['change']):+.2f}%"
            for r in rows)
        result = "📈 COURS DES CRYPTOS | #01\n\n" + body + "\n\nGraphiques 48h réels. Source : " + d["provider"]
    elif number in (2, 3):
        label = "HAUSSES" if number == 2 else "BAISSES"
        rows = d["rows"]
        body = "\n".join(
            f"{i}. {r['symbol']}: {float(r['change']):+.2f}% | {price_caption(r['price'])} USD"
            for i, r in enumerate(rows, 1))
        result = f"📊 TOP 5 {label} SUR 24H | #{number:02d}\n\n" + body + "\n\nTop 100, volume ≥1 M USD/j. Source : " + d["provider"]
    elif number == 4:
        r = d["row"]
        result = (
            "🚨 ALERTE MARCHÉ CRYPTO | #04\n\n"
            f"{r['symbol']} : {float(r['change']):+.2f}% sur 24 h\n"
            f"Palier observé : {int(r['level'])}%\n"
            f"Source : {d['provider']}\n\n"
            "Variation sur 24 h, pas un franchissement à cet instant."
        )
    elif number == 5:
        result = (
            "🧠 FEAR & GREED CRYPTO | #05\n\n"
            f"Indice : {d['score']}/100 • {d['classification']}\n"
            f"Depuis J-1 : {d['delta_1d']:+d} points.\n"
            "Historique journalier. Source : Alternative.me."
        )
    elif number == 6:
        result = (
            "₿ DOMINANCE BITCOIN | #06\n\n"
            f"BTC.D : {d['btc_dominance_pct']:.2f}%\n"
            f"Capitalisation globale : {d['market_cap_usd']/1e12:.3f} T USD\n"
            f"Variation 24h : {d['market_cap_change_24h_pct']:+.2f}%\n"
            f"Source : {d['provider']}."
        )
    elif number == 7:
        result = (
            "📆 BILAN HEBDOMADAIRE CRYPTO | #07\n\n"
            f"BTC : {d['btc']['change_7d']:+.2f}% sur 7 jours\n"
            f"ETH : {d['eth']['change_7d']:+.2f}% sur 7 jours\n"
            f"Dominance BTC : {d['btc_dominance_pct']:.2f}%\n"
            f"Fear & Greed : {d['fear']['score']}/100\n"
            f"Sources : {d['provider']} + Alternative.me."
        )
    elif number in (8, 9):
        primary = d["main"]
        other = d.get("confirmation")
        prefix = "🚨 BREAKING NEWS BTC/ETH | #08" if number == 8 else "🏦 ACTU DES PLATEFORMES | #09"
        result = (prefix + "\n\n" + d["headline_fr"] + "\n\n" +
                  "Titre original du média : " + primary["title"] + "\n\n")
        result += f"Source : {primary['source']}\n{primary['url']}\n"
        if other:
            result += f"Deuxième média : {other['source']}\n{other['url']}\n"
        elif number == 9:
            result += "Information attribuée à sa source, non recoupée.\n"
    else:
        raise ValueError("Only confirmed news in #1..#9 can be captioned")
    result += "\n\n📅 Relevé au " + datetime.now(UTC).strftime("%d/%m/%Y %H:%M UTC")
    result += "\nℹ️ Information et données indicatives, pas un conseil en investissement."
    if len(result) > 1024:
        raise ValueError("Caption too long: refuse truncating evidence links")
    return result


def send_one(number: int) -> bool:
    dest = verify_production_route()
    state = read_state()
    # Initial history is a one-time series per publication. Never republish
    # a number just because the automated workflow is retried.
    key = f"initial_history_{number:02d}"
    if key in state["sent"]:
        print("CRYPTO_PROD_ALREADY_SENT", number, state["sent"][key]["message_id"])
        return False
    if number == 10:
        print("CRYPTO_PROD_HOLD", number, "HUMAN_LEGAL_REVIEW_REQUIRED")
        return False
    result = prepared(number)
    if result is None:
        return False
    data, picture = result
    caption = caption_for(number, data)
    with picture.open("rb") as f:
        try:
            r = requests.post(
                "https://api.telegram.org/bot" + TOKEN + "/sendPhoto",
                data={"chat_id": dest["id"], "caption": caption},
                files={"photo": (picture.name, f, "image/png")},
                timeout=(10, 90))
            r.raise_for_status()
            payload = r.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError("Telegram result unknown — do not retry this number automatically") from None
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RuntimeError("Telegram rejected production PNG")
    posted = payload.get("result")
    if (not isinstance(posted, dict) or not isinstance(posted.get("message_id"), int)
            or not isinstance(posted.get("chat"), dict)
            or posted["chat"].get("id") != dest["id"]
            or not isinstance(posted.get("photo"), list) or not posted["photo"]):
        raise RuntimeError("Photo/destination not confirmed by Telegram; do not retry")
    state["sent"][key] = {
        "message_id": posted["message_id"],
        "sent_at": datetime.now(UTC).isoformat(),
        "number": number,
        "source": data.get("provider") or data.get("main", {}).get("source") or "Alternative.me",
    }
    write_state(state)
    print("CRYPTO_PROD_PUBLISHED",
          "number=" + str(number), "message_id=" + str(posted["message_id"]),
          "photo_confirmed=1", "recorded=1")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--number", type=int, choices=range(1, 11), required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        verify_production_route()
        print("CRYPTO_PROD_PREFLIGHT_OK")
    else:
        send_one(args.number)


if __name__ == "__main__":
    main()
