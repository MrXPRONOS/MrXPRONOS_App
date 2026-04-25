import os
import glob
import json
import time
import requests
from datetime import datetime, timezone

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
OUT_DIR = os.environ.get("OUT_DIR", "telegram_out")

SITE_URL = os.environ.get("SITE_URL", "https://mrxpronos.github.io/MrXPRONOS_App/")
MORE_URL = os.environ.get("MORE_URL", SITE_URL + "pronos.html")

if not TOKEN or not CHAT_ID:
    raise SystemExit("Secrets manquants: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")

def send_photo(photo_path: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    keyboard = {
        "inline_keyboard": [
            [{"text": "Voir plus de coupons", "url": MORE_URL}],
            [{"text": "Ouvrir le site", "url": SITE_URL}],
        ]
    }

    with open(photo_path, "rb") as f:
        r = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "caption": caption,
                "reply_markup": json.dumps(keyboard),
            },
            files={"photo": f},
            timeout=120
        )
    r.raise_for_status()

def send_message(text: str):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=60)
    r.raise_for_status()

def main():
    files = sorted(glob.glob(os.path.join(OUT_DIR, "*.png")))
    if not files:
        send_message("Coupons SIMPLE du jour : aucun match trouvé.")
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    intro = f"Coupons SIMPLE du {today} (UTC)\nPlus de coupons fiables ici : {MORE_URL}"
    send_message(intro)

    # Envoi photo par photo (pour avoir des vrais boutons sous CHAQUE image)
    for idx, fpath in enumerate(files, 1):
        caption = ""  # laisse vide pour un rendu propre
        send_photo(fpath, caption=caption)
        time.sleep(0.7)  # anti rate-limit

    send_message(f"Fin des 5 coupons SIMPLE.\nVoir plus : {MORE_URL}")

    print(f"Envoyé sur Telegram: {len(files)} photos (avec boutons)")

if __name__ == "__main__":
    main()