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
    {"text": "📲 REJOINDRE LE CANAL GRATUIT", "url": JOIN_URL, "style": "primary"}
]]}

MESSAGES = (
    ("01-long", """🚨 <b>ARRÊTE D’ACHETER DES COUPONS QUI TE FONT PERDRE !</b>

💸 Tu paies pour recevoir un pronostic, puis tu risques encore ta mise ? <i>Ton argent mérite mieux que des promesses « 100 % sûres ».</i>

<blockquote><b><i>Un bon pronostic n’a pas besoin d’une étiquette VIP pour convaincre.</i></b></blockquote>

⚽ Chez <b>Mr XPRONOS</b>, les coupons et analyses sont <b>GRATUITS</b>.

📸 Ce ticket gagnant est un résultat passé, jamais une garantie.

📲 <b>REJOINS NOTRE CANAL TELEGRAM GRATUIT</b> 👇

🔞 <i>18+ • Les paris comportent un risque de perte.</i>"""),
    ("02-direct", """💰 <b>ON TE VEND DES COUPONS « SÛRS » ?</b>

<blockquote><b><i>Payant ne veut pas dire gagnant.</i></b></blockquote>

✋ Arrête de payer l’accès à des pronostics.
✅ Nos coupons et analyses sont <b>GRATUITS</b>.

📲 <b>REJOINS MR XPRONOS SUR TELEGRAM</b> 👇

🔞 <i>18+ • Aucun pari garanti.</i>"""),
    ("03-court", """⚽ <b>UN COUPON PEUT PERDRE. POURQUOI LE PAYER EN PLUS ?</b>

<blockquote><b><i>Moins de promesses, plus de transparence.</i></b></blockquote>

✅ <b>Nos pronostics sont GRATUITS.</b>
📲 <b>REJOINS LE CANAL TELEGRAM</b> 👇

🔞 <i>18+ • Risque de perte.</i>"""),
    ("04-humour", """😂 <b>TON PORTEFEUILLE EN A MARRE DES « COUPONS SÛRS ».</b>

Tu paies le ticket, il perd… et le vendeur revient : <i>« Frère, le prochain est cadeau… à moitié prix. »</i> 💸

<blockquote><b><i>La seule chose certaine, c’est que tu as payé le coupon.</i></b></blockquote>

⚽ Ici, <b>nos coupons sont GRATUITS</b>.

📲 <b>REJOINS MR XPRONOS SUR TELEGRAM</b> 👇

🔞 <i>18+ • Aucun gain garanti.</i>"""),
    ("05-humour-court", """💀 <b>COUPON PAYANT, RÉSULTAT PERDANT : TON PORTEFEUILLE A DÉMISSIONNÉ.</b> 😂

<blockquote><b><i>Un pronostic payant peut aussi perdre !</i></b></blockquote>

✅ <b>Les nôtres sont GRATUITS.</b>
📲 <b>REJOINS LE CANAL TELEGRAM</b> 👇

🔞 <i>18+ • Risque de perte.</i>"""),
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
        if BUTTONS["inline_keyboard"][0][0].get("style") != "primary":
            raise ValueError("Bouton bleu requis")
        if "<blockquote>" not in caption or "<i>" not in caption:
            raise ValueError("Citation et italique requis")
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
