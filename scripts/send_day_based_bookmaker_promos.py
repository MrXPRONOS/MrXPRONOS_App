#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from telegram_promo_channels import promo_channels, deliver_to_both

BASE_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = BASE_DIR / "assets" / "images" / "daily-promos"
CONFIG_PATH = BASE_DIR / "config" / "partners.json"

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
SECONDARY_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_SECONDARY", "").strip()
FORCE_WEEKDAY = os.getenv("FORCE_WEEKDAY", "").strip()
SLEEP_SECONDS = int(os.getenv("TELEGRAM_SLEEP_BETWEEN_POSTS", "4"))
DRY_RUN = os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class Promo:
    weekday: int
    bookmaker: str
    title: str
    image: str
    offer: str
    intro: str


PROMOS = [
    Promo(0, "melbet", "👑 MELBET — ROYAL MONDAY", "melbet-royal-monday.jpg",
          "100% jusqu’à 100 USD",
          "Le lundi, profite de <b>Royal Monday</b> avec MelBet."),
    Promo(0, "linebet", "🍀 LINEBET — LUCKY MONDAY", "linebet-lucky-monday.jpg",
          "100% jusqu’à 100 €",
          "Le lundi, découvre <b>Lucky Monday</b> sur LineBet."),
    Promo(0, "betwinner", "💸 BETWINNER — BONUS RECHARGE LUNDI", "betwinner-recharge-monday.jpg",
          "50% jusqu’à 300 €",
          "Le lundi, BetWinner met en avant son bonus de recharge."),
    Promo(2, "1xbet", "⚡ 1XBET — X2 WEDNESDAY", "1xbet-x2-wednesday.jpg",
          "Jusqu’à 300 €",
          "Le mercredi, consulte l’offre <b>X2 Wednesday</b> de 1xBet."),
    Promo(2, "melbet", "🚀 MELBET — FAST GAMES DAY", "melbet-fast-games-wednesday.jpg",
          "100% jusqu’à 111 USD",
          "Le mercredi, MelBet met en avant <b>Fast Games Day</b>."),
    Promo(3, "betwinner", "🎁 BETWINNER — BONUS DU JEUDI", "betwinner-thursday-bonus.jpg",
          "100% du dépôt",
          "Le jeudi, profite de l’offre dédiée de BetWinner."),
    Promo(4, "1xbet", "🎉 1XBET — LUCKY FRIDAY", "1xbet-lucky-friday.jpg",
          "Jusqu’à 300 €",
          "Le vendredi, retrouve <b>Lucky Friday</b> sur 1xBet."),
]


def load_config():
    if not CONFIG_PATH.exists():
        raise SystemExit(f"Configuration absente: {CONFIG_PATH}")
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Configuration invalide: {exc}")
    promo_code = str(data.get("promo_code", "XPVIP")).strip() or "XPVIP"
    partners = data.get("partners", {})
    return promo_code, partners


PROMO_CODE, PARTNERS = load_config()


def partner(key: str):
    item = PARTNERS.get(key)
    if not item:
        raise SystemExit(f"Partenaire absent de config/partners.json: {key}")
    if not item.get("enabled", True):
        return None
    url = str(item.get("url", "")).strip()
    if not url:
        raise SystemExit(f"Lien partenaire vide pour {key}")
    return item


def caption_for(promo: Promo) -> str:
    return (
        f"<b>{promo.title}</b>\n\n"
        f"{promo.intro}\n\n"
        f"<blockquote>🎁 <b>OFFRE :</b> {promo.offer}\n"
        f"🎟 <b>CODE PROMO :</b> <code>{PROMO_CODE}</code></blockquote>\n\n"
        "<i>Crée un nouveau compte via le bouton ci-dessous, vérifie que le code promo "
        f"<b>{PROMO_CODE}</b> est bien renseigné lorsqu’un champ promo est proposé, "
        "puis consulte les conditions de l’offre avant ton dépôt.</i>\n\n"
        "👇 <b>Inscription :</b> utilise le bouton juste en dessous.\n\n"
        "⚠️ <b>18+</b> · <i>Offre soumise à conditions. Les montants et l’éligibilité "
        "peuvent varier selon le pays, la devise et le compte. Joue de façon responsable.</i>"
    )


def keyboard_for(promo: Promo):
    info = partner(promo.bookmaker)
    if not info:
        return None
    name = str(info.get("name") or promo.bookmaker)
    return {
        "inline_keyboard": [[
            {"text": f"🔥 S’inscrire sur {name}", "url": info["url"]}
        ]]
    }


def targets():
    items = [("primary", CHAT_ID)]
    if SECONDARY_CHAT_ID:
        items.append(("secondary", SECONDARY_CHAT_ID))
    seen = set()
    result = []
    for role, cid in items:
        cid = cid.strip()
        if cid and cid not in seen:
            seen.add(cid)
            result.append((role, cid))
    return result


def send_photo(promo: Promo):
    info = partner(promo.bookmaker)
    if not info:
        print(f"⏭️ {promo.bookmaker} désactivé dans config/partners.json")
        return

    image = ASSETS_DIR / promo.image
    if not image.exists():
        raise SystemExit(f"Affiche introuvable: {image}")

    caption = caption_for(promo)
    markup = keyboard_for(promo)

    if DRY_RUN:
        print(json.dumps({
            "promo": promo.title,
            "image": str(image),
            "caption": caption,
            "keyboard": markup,
        }, ensure_ascii=False, indent=2))
        return

    if not TOKEN or not CHAT_ID:
        raise SystemExit("Secrets manquants: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")

    api = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    def send_to(cid):
        data={
            "chat_id":cid,"caption":caption,"parse_mode":"HTML",
            "reply_markup":json.dumps(markup,ensure_ascii=False),
        }
        with image.open("rb") as fh:
            response=requests.post(
                api,data=data,files={"photo":(image.name,fh,"image/jpeg")},
                timeout=120)
        response.raise_for_status()
        if not response.json().get("ok",False):
            raise RuntimeError(f"Telegram rejected promo for {cid}")
    deliver_to_both(promo_channels(CHAT_ID,SECONDARY_CHAT_ID),
                    send_to,label=promo.title)


def weekday_today() -> int:
    if FORCE_WEEKDAY:
        day = int(FORCE_WEEKDAY)
        if not 0 <= day <= 6:
            raise SystemExit("FORCE_WEEKDAY doit être compris entre 0 et 6.")
        return day
    # Le Togo est en UTC toute l’année.
    return time.gmtime().tm_wday


def main():
    day = weekday_today()
    todays = [p for p in PROMOS if p.weekday == day]
    if not todays:
        print(f"ℹ️ Aucune promotion programmée aujourd’hui (weekday={day}).")
        return

    print(f"📅 weekday={day} | {len(todays)} promotion(s)")
    for index, promo in enumerate(todays, start=1):
        print(f"➡️ [{index}/{len(todays)}] {promo.title}")
        send_photo(promo)
        if index < len(todays):
            time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
