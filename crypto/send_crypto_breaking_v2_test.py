"""#08 : publication MANUELLE uniquement vers le canal Telegram de test.

Le registre crypto/breaking_08_state.json empêche de renvoyer les mêmes liens
lors des exécutions suivantes (le workflow commite le registre après succès).
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from crypto.export_breaking_v2 import validate_real, load_state, already_published
from scripts.telegram_test_guard import validate_test_channel

ROOT = Path("crypto/generated/test")
DATA = ROOT / "breaking_v2_data.json"
IMAGE = ROOT / "breaking_v2.png"
STATE = Path("crypto/breaking_08_state.json")


def main() -> None:
    if not DATA.is_file() or not IMAGE.is_file() or IMAGE.stat().st_size < 10_000:
        raise RuntimeError("Contenu réel ou image absents : envoi refusé")
    d = json.loads(DATA.read_text(encoding="utf-8"))
    validate_real(d)
    state = load_state(STATE)
    if already_published([d["main"], d["confirmation"]], state):
        print("BREAKING_08_DUPLICATE — aucun nouvel envoi")
        return

    token = (os.environ.get("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    # Protection supplémentaire: vérifie nom, type et droits du canal.
    dest = validate_test_channel("@predict_mrxp", token)
    main, confirm = d["main"], d["confirmation"]
    posted = datetime.fromisoformat(d["collected_at"]).astimezone(timezone.utc)
    title = main["title"]
    # Les titres originaux sont conservés pour éviter une traduction automatique infidèle.
    caption = (
        "🚨 ACTU CRYPTO #08 — BREAKING NEWS\n"
        f"{'₿ BITCOIN' if d['topic']=='bitcoin' else 'Ξ ETHEREUM'}\n\n"
        f"📰 {title}\n\n"
        f"✅ Deux médias indépendants confirment cette actualité.\n"
        f"• {main['source']} : {main['url']}\n"
        f"• {confirm['source']} : {confirm['url']}\n\n"
        f"📆 Collecte : {posted:%d/%m/%Y %H:%M} UTC\n"
        "ℹ️ Titre original en anglais. Information, pas conseil financier."
    )
    if len(caption) > 1024:
        raise RuntimeError("Légende trop longue, envoi refusé")

    with IMAGE.open("rb") as f:
        try:
            resp = requests.post(
                "https://api.telegram.org/bot" + token + "/sendPhoto",
                data={"chat_id": dest["chat_id"], "caption": caption},
                files={"photo": (IMAGE.name, f, "image/png")},
                timeout=(10, 90))
            resp.raise_for_status()
        except requests.RequestException:
            # Un timeout peut survenir après une publication réussie.
            raise RuntimeError("Résultat Telegram incertain : ne pas relancer automatiquement") from None
    try:
        outcome = resp.json()
    except ValueError:
        raise RuntimeError("Réponse Telegram illisible : ne pas relancer automatiquement") from None
    if outcome.get("ok") is not True:
        raise RuntimeError("Telegram a refusé cette publication")
    state["sent_urls"] = list(dict.fromkeys(
        list(state.get("sent_urls", [])) + d["fingerprints"]))[-600:]
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("BREAKING_08_TELEGRAM_TEST_SENT", outcome.get("result", {}).get("message_id"), dest["username"])


if __name__ == "__main__":
    main()
