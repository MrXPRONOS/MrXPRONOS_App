#!/usr/bin/env python3
"""5 variantes avec la même photo et un bouton vers @mrxpronosfr, test seulement."""
import argparse
import json
import os
import re
import sys
import time
from html import unescape
from pathlib import Path

import requests
from telegram_test_guard import validate_test_channel, TestChannelGuardError

ROOT = Path(__file__).resolve().parents[1]
PHOTO = ROOT / "assets/telegram/promo_coupon_2026-10-25.jpg"
TEST_CHAT = "predict_mrxp"
JOIN_URL = "https://t.me/mrxpronosfr"
JOIN = '<a href="' + JOIN_URL + '">Rejoins notre canal Telegram</a>'
BUTTONS = {"inline_keyboard": [[
    {"text": "📲 REJOINDRE LE CANAL GRATUIT", "url": JOIN_URL}
]]}

MESSAGES = (
    ("01-long", """🚨 <b>ARRÊTEZ D'ACHETER DES COUPONS QUI PERDENT !</b>

💸 Pourquoi continuer à payer pour des pronostics qui vous font perdre de l'argent ?

🎯 Un bon pronostiqueur n'a pas besoin de vendre ses coupons pour montrer son travail.

✅ Ce ticket du 25 octobre montre un pari gagnant à la cote 4,18. Un résultat passé ne garantit pas les suivants.

⚽ Tu veux découvrir des coupons et des analyses <b>GRATUITEMENT</b> ?

📲 """ + JOIN + """ et clique sur le bouton ci-dessous 👇

🔞 18+ • Jouez responsablement."""),
    ("02-direct", """💰 <b>POURQUOI PAYER DES COUPONS ?</b>

Ce ticket gagnant affiche une cote de 4,18. ⚽
Chez Mr XPRONOS, on partage des coupons gratuits.

📲 <b>REJOINS NOTRE CANAL TELEGRAM</b> pour les découvrir !
👉 """ + JOIN + """ 👇

🔞 18+ • Aucun gain garanti."""),
    ("03-court", """⚽ <b>UN TICKET GAGNANT. COTE 4,18.</b>

🎯 Tu veux découvrir nos coupons gratuits ?
📲 """ + JOIN + """ maintenant 👇

🔞 18+ • Risque de perte."""),
    ("04-humour", """😂 <b>TON PORTEFEUILLE MÉRITE DES VACANCES !</b>

Tu achètes des coupons, ils perdent… et ton argent prend un aller simple. ✈️💸

Ici, on partage des analyses et des coupons <b>GRATUITEMENT</b>.
Le ticket sur l'image est gagnant, mais personne ne gagne à tous les coups !

📲 """ + JOIN + """ 👇

🔞 18+ • Jouez responsablement."""),
    ("05-humour-court", """💀 Acheter un coupon pour perdre ? <b>Ton portefeuille demande le divorce.</b> 😂

⚽ Nos coupons gratuits t'attendent.
📲 """ + JOIN + """ 👇

🔞 18+ • Aucun gain garanti."""),
)


def check():
    if not PHOTO.is_file() or PHOTO.stat().st_size < 1000:
        raise ValueError("Image du coupon absente ou vide")
    with PHOTO.open("rb") as f:
        sig = f.read(4)
    if sig[:3] != b"\xff\xd8\xff":
        raise ValueError("La photo doit être au format JPEG pour sendPhoto")
    assert len(MESSAGES) == 5
    for name, caption in MESSAGES:
        visible = unescape(re.sub(r"<[^>]+>", "", caption))
        if not 1 <= len(visible) <= 1024:
            raise ValueError(name + ": légende trop longue pour sendPhoto")
        if JOIN_URL not in caption or "18+" not in caption:
            raise ValueError(name + ": lien ou avertissement absent")
        if caption.count("<b>") != caption.count("</b>"):
            raise ValueError(name + ": balises HTML incorrectes")
        print("VARIANT_OK", name, len(visible))
    print("IMAGE_OK", PHOTO.stat().st_size, "bytes ; BUTTON_OK", JOIN_URL)


def send(selected):
    token = (os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_TEST_CHAT_ID") or "@predict_mrxp").strip()
    if not token:
        print("::error::FOOTBALL_NEWS_BOT_TOKEN manquant")
        return 1
    try:
        verified = validate_test_channel(chat_id, token)
        if verified.get("username") != TEST_CHAT or not verified.get("can_post"):
            raise TestChannelGuardError("Canal de test incorrect")
    except TestChannelGuardError as exc:
        print("::error::Refus vérification canal test:", str(exc))
        return 1

    chosen = [(i, name, caption) for i, (name, caption) in enumerate(MESSAGES, 1)
              if selected == "all" or selected == str(i)]
    links = []
    for idx, name, caption in chosen:
        with PHOTO.open("rb") as photo:
            try:
                response = requests.post(
                    "https://api.telegram.org/bot" + token + "/sendPhoto",
                    data={
                        "chat_id": verified["chat_id"],
                        "caption": caption,
                        "parse_mode": "HTML",
                        "reply_markup": json.dumps(BUTTONS, ensure_ascii=False),
                        "protect_content": "false",
                    },
                    files={"photo": (PHOTO.name, photo, "image/jpeg")},
                    timeout=(10, 45),
                )
                payload = response.json()
            except (requests.RequestException, ValueError):
                # Ne jamais afficher une URL d'exception : elle contient le token du bot.
                print("::error::Echec réseau/API Telegram pour", name)
                return 1
        result = payload.get("result") if isinstance(payload, dict) else None
        mid = result.get("message_id") if isinstance(result, dict) else None
        if response.status_code != 200 or payload.get("ok") is not True or not isinstance(mid, int):
            print("::error::Echec publication", name, "HTTP", response.status_code)
            return 1
        url = "https://t.me/" + TEST_CHAT + "/" + str(mid)
        print("COUPON_VARIANT_SENT", name, url)
        links.append((name, url))
        if (idx, name, caption) != chosen[-1]:
            time.sleep(1)

    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as f:
            f.write("### Photos + légendes + boutons publiés dans le canal de test\n\n")
            for name, url in links:
                f.write("- [" + name + "](" + url + ")\n")
            f.write("\nCanal de test : @predict_mrxp. Bouton : @mrxpronosfr.\n")
    return 0


def main():
    p = argparse.ArgumentParser()
    actions = p.add_mutually_exclusive_group(required=True)
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--send", action="store_true")
    p.add_argument("--variant", choices=["all", "1", "2", "3", "4", "5"], default="all")
    args = p.parse_args()
    try:
        check()
    except (ValueError, AssertionError) as exc:
        print("::error::Validation échouée:", str(exc))
        return 1
    return send(args.variant) if args.send else 0


if __name__ == "__main__":
    sys.exit(main())
