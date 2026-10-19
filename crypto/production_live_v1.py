"""Controlled recurring production of verified Actu Crypto posters.

Uses the same source validation and premium renderers as the tested one-time
history seeder. Only trusted real data, never DEMO. #10: review archive only.
The registry is tracked and committed by GitHub Actions with concurrency lock.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests

from crypto import production_seed_v1 as seed

UTC = timezone.utc
TODAY = datetime.now(UTC)
MODES = {
    "morning": (1, 5, 6),
    "midday": (2, 3),
    "evening": (1,),
    "alerts": (4,),
    "news": (8, 9),
    "weekly": (7,),
}
REG = Path("crypto/generated/test/regulation_v2_candidate.json")


def key_for(number: int, data: dict, mode: str) -> str:
    day = TODAY.strftime("%Y-%m-%d")
    if number in (8, 9):
        # Stable URL fingerprints prevent reposting the same published article.
        ids = data.get("fingerprints")
        if not isinstance(ids, list) or not ids:
            raise ValueError("News article fingerprints missing")
        joined = "|".join(sorted(set(ids)))
        return f"news:{number:02d}:" + hashlib.sha256(joined.encode()).hexdigest()[:24]
    if number == 7:
        iso = TODAY.isocalendar()
        return f"weekly:07:{iso.year}-W{iso.week:02d}"
    if number == 4:
        row = data.get("row") or {}
        symbol = row.get("symbol")
        variation = float(row["change"])
        direction = "up" if variation > 0 else "down"
        level = int(row["level"])
        return f"alert:04:{day}:{symbol}:{direction}:{level}"
    return f"daily:{number:02d}:{day}:{mode if number == 1 else 'default'}"


def blocked_by_initial_history(state: dict, number: int) -> bool:
    # Do not repeat initial-history posts as same-day daily messages.
    initial = state["sent"].get(f"initial_history_{number:02d}")
    if number in (4, 8, 9) or not isinstance(initial, dict):
        return False
    try:
        date = seed.datetime_from(initial["sent_at"]).date()
    except (KeyError, ValueError):
        raise RuntimeError("Invalid recorded initial-history timestamp") from None
    if number == 7:
        return date.isocalendar()[:2] == TODAY.date().isocalendar()[:2]
    return date == TODAY.date()


def record_send(chat: dict, caption: str, image: Path) -> int:
    seed.validate_image(image)
    with image.open("rb") as fp:
        try:
            resp = requests.post(
                "https://api.telegram.org/bot" + seed.TOKEN + "/sendPhoto",
                data={"chat_id": chat["id"], "caption": caption},
                files={"photo": (image.name, fp, "image/png")},
                timeout=(10, 90))
            resp.raise_for_status()
            result = resp.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError("Unknown Telegram send result — do not automatically retry") from None
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Telegram rejected photo")
    m = result.get("result")
    if (not isinstance(m, dict) or not isinstance(m.get("message_id"), int)
            or not isinstance(m.get("chat"), dict) or m["chat"].get("id") != chat["id"]
            or not isinstance(m.get("photo"), list) or not m["photo"]):
        raise RuntimeError("No confirmed production photo; manual audit required")
    return m["message_id"]


def alert_is_new(state: dict, data: dict) -> bool:
    """Do not repost a sustained 24h threshold, even on the next calendar day."""
    levels = state.setdefault("alert_levels", {})
    if not isinstance(levels, dict):
        raise ValueError("Corrupt alert monitor registry")
    rearmed = state.setdefault("alert_rearmed", {})
    published = state.setdefault("alert_last_published_signal", {})
    if not isinstance(rearmed, dict) or not isinstance(published, dict):
        raise ValueError("Corrupt alert delivery register")
    for sample in data.get("observations", []):
        symbol = sample["symbol"]
        change = float(sample["change"])
        level = int(sample["level"])
        last_observed = levels.get(symbol, {})
        direction = "up" if change >= 0 else "down"
        if level == 0 or (last_observed and last_observed.get("direction") != direction):
            rearmed[symbol] = True
        levels[symbol] = {"level": level, "direction": direction}
    seed.write_state(state)  # observations, not publication acknowledgements
    if data.get("status") == "no_alert":
        return False
    row = data["row"]
    symbol = row["symbol"]
    current_level = int(row["level"])
    current_dir = row["direction"]
    last_confirmed = published.get(symbol, {})
    if (last_confirmed.get("direction") == current_dir
            and int(last_confirmed.get("level", 0)) >= current_level
            and not rearmed.get(symbol, False)):
        print("CRYPTO_ALERT_ALREADY_CONFIRMED_SENT", symbol, current_level)
        return False
    last = state.get("alert_last_published", {}).get(symbol)
    if last:
        elapsed = (datetime.now(UTC) - seed.datetime_from(last)).total_seconds()
        if elapsed < 12 * 3600:
            print("CRYPTO_ALERT_COOLDOWN_12H", symbol)
            return False
    return True


def news_already_posted(state: dict, data: dict) -> bool:
    urls = state.setdefault("news_fingerprints", {})
    if not isinstance(urls, dict):
        raise ValueError("Corrupt news URL registry")
    ids = data.get("fingerprints", [])
    if not ids or not all(isinstance(i, str) for i in ids):
        raise ValueError("Missing article source identity")
    return any(x in urls for x in ids)


def publish_automatic_regulation():
    """No human sign-off: publish ONLY verifiable first-party regulator notices.

    These are *announcements* sourced to SEC/ESMA/European Commission.
    We make no claim about legal force, enforcement or effective dates.
    """
    from crypto import regulation_10_auto as official
    state = seed.read_state()
    path = seed.ROOT / "regulation_10_auto.json"
    path.unlink(missing_ok=True)
    candidate = official.collect(state)
    if candidate is None:
        print("CRYPTO_REG10_SKIP_NO_VERIFIABLE_OFFICIAL_NOTICE")
        return False
    official.validate_auto(candidate)
    fingerprint = candidate["fingerprint"]
    key = "reg10_official:" + fingerprint
    if key in state["sent"]:
        print("CRYPTO_REG10_SKIP_ALREADY_PUBLISHED", fingerprint)
        return False
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    seed.run("node","scripts/render_crypto_regulation_auto_v2.mjs")
    image = seed.ROOT / "regulation_10_auto.png"
    seed.validate_image(image)
    a = candidate["primary"]
    caption = (
        "⚖️ MR XPRONOS · VEILLE RÉGLEMENTAIRE #10\n\n"
        + "📌 " + a["source"] + " publie une annonce concernant les cryptoactifs.\n\n"
        + "Titre original : " + a["title"] + "\n\n"
        + "Source institutionnelle : " + candidate["official_verified_url"] + "\n"
        + "Publication indiquée par le flux : " + a["published_at"][:16] + " UTC\n"
        + "Zone de l'autorité : " + a["region"] + "\n\n"
        + "Source et titre de la page vérifiés automatiquement. "
        + "Le statut juridique, la date d'application et les effets de l'annonce "
        + "ne sont pas déterminés automatiquement. Consultez le texte officiel."
    )
    if len(caption) > 1024:
        raise ValueError("Official bulletin caption too long for Telegram")
    chat = seed.verify_production_route()
    message_id = record_send(chat,caption,image)
    state["sent"][key] = {
        "number":10,"message_id":message_id,
        "source":a["source"],"official_url":candidate["official_verified_url"],
        "sent_at":datetime.now(UTC).isoformat(),
        "classification":"institutional_announcement_not_legal_advice",
    }
    seed.write_state(state)
    print("CRYPTO_REG10_OFFICIAL_PUBLISHED","message_id="+str(message_id),
          "fingerprint="+fingerprint)
    return True


def publish_approved_regulation():
    """Only manual dispatch after an editor committed a checkable approval."""
    from crypto.regulation_10_approval import run as make_public
    seed.run("python", "-m", "crypto.export_regulation_v2")
    if not make_public():
        print("CRYPTO_REG10_NOT_PUBLISHED_NO_MATCHING_HUMAN_APPROVAL")
        return
    data = seed.read_json(seed.ROOT / "regulation_v2_approved.json")
    fp = data["fingerprint"]
    state = seed.read_state()
    key = "legal_approved_10:" + fp
    if key in state["sent"]:
        print("CRYPTO_REG10_ALREADY_PUBLISHED", fp)
        return
    chat = seed.verify_production_route()
    seed.run("node", "scripts/render_crypto_regulation_approved_v2.mjs")
    picture = seed.ROOT / "regulation_v2_approved.png"
    a = data["approval"]
    source = data["primary"]
    caption = ("⚖️ MR XPRONOS • RÉGLEMENTATION CRYPTO #10\n\n"
               + a["title_fr"] + "\n\n" + a["summary_fr"] + "\n\n"
               + "Juridiction : " + a["jurisdiction"] + "\n"
               + "Étape vérifiée : " + a["verified_stage"] + "\n"
               + "Effet : " + (a["effective_date"] if a["effective_date"] != "non_applicable" else "Non annoncé pour cette étape") + "\n"
               + "Texte officiel : " + a["official_url"] + "\n"
               + "Article d'origine : " + source["url"] + "\n\n"
               + "Analyse informative ; vérifiez la législation applicable.")
    if len(caption) > 1024:
        raise ValueError("Approved legal caption exceeds Telegram photo limit")
    message_id = record_send(chat, caption, picture)
    state["sent"][key] = {"number": 10, "message_id": message_id,
                            "source": a["official_source"],
                            "reviewed_by": a["approved_by"],
                            "sent_at": datetime.now(UTC).isoformat()}
    seed.write_state(state)
    print("CRYPTO_REG10_APPROVED_PUBLISHED", "message_id="+str(message_id))


def execute(mode: str):
    if mode == "legal":
        # Automated from official first-party publications, no human approval.
        # Source HTML/RSS disagreement means NO Telegram publication.
        publish_automatic_regulation()
        return

    chat = seed.verify_production_route()
    state = seed.read_state()
    failures = []
    for number in MODES[mode]:
        if blocked_by_initial_history(state, number):
            print("CRYPTO_LIVE_SKIP_INITIAL_ALREADY_POSTED", number)
            continue
        # Skip known timed posts before expensive API calls.
        if number not in (4, 8, 9):
            prekey = f"daily:{number:02d}:{TODAY:%Y-%m-%d}:{mode if number == 1 else 'default'}"
            if number == 7:
                iso = TODAY.isocalendar()
                prekey = f"weekly:07:{iso.year}-W{iso.week:02d}"
            if prekey in state["sent"]:
                print("CRYPTO_LIVE_SKIP_ALREADY_POSTED", number)
                continue
        try:
            if number == 4:
                seed.run("python", "-m", "crypto.export_alerts_v2")
                data = seed.read_json(seed.ROOT / "alerts_v2_data.json")
                if not alert_is_new(state, data):
                    print("CRYPTO_LIVE_SKIP_NO_NEW_ALERT", number)
                    continue
                seed.validated_real(4, data)
                seed.run("node", "scripts/render_crypto_alerts_v2.mjs")
                image = seed.ROOT / "alerts_v2.png"
                seed.validate_image(image)
            else:
                output = seed.prepared(number)
                if output is None:
                    print("CRYPTO_LIVE_SKIP_NO_REAL_EVENT", number)
                    continue
                data, image = output
            if number in (8, 9) and news_already_posted(state, data):
                print("CRYPTO_LIVE_SKIP_NEWS_ALREADY_SOURCED", number)
                continue
            key = key_for(number, data, mode)
            if key in state["sent"]:
                print("CRYPTO_LIVE_SKIP_DUPLICATE", number, key)
                continue
            caption = seed.caption_for(number, data)
            message_id = record_send(chat, caption, image)
            stamped = datetime.now(UTC).isoformat()
            state["sent"][key] = {
                "number": number, "message_id": message_id, "sent_at": stamped,
                "source": data.get("provider") or data.get("main", {}).get("source") or "Alternative.me",
            }
            if number == 4:
                symbol = data["row"]["symbol"]
                state.setdefault("alert_last_published", {})[symbol] = stamped
                state.setdefault("alert_last_published_signal", {})[symbol] = {
                    "level": int(data["row"]["level"]), "direction": data["row"]["direction"]}
                state.setdefault("alert_rearmed", {})[symbol] = False
            if number in (8, 9):
                for fp in data["fingerprints"]:
                    state["news_fingerprints"][fp] = {"number": number, "message_id": message_id}
            seed.write_state(state)
            print("CRYPTO_LIVE_PUBLISHED", "number="+str(number),
                  "message_id="+str(message_id), "photo_confirmed=1")
        except (OSError, ValueError, RuntimeError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
            # A one-off upstream source failure should not suppress unrelated news.
            # Do not auto-retry uncertain send calls on same iteration.
            print("CRYPTO_LIVE_FAILED", number, type(exc).__name__, str(exc)[:250])
            failures.append(number)
            continue
    if failures:
        raise RuntimeError("Production stage(s) failed: " + ",".join(map(str, failures)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=tuple(MODES) + ("legal",), required=True)
    args = parser.parse_args()
    execute(args.mode)


if __name__ == "__main__":
    main()
