"""Test de livraison indépendant de la collecte RSS #08.

Un seul message de diagnostic (jamais une fausse actualité), vers @predict_mrxp
uniquement, après validation stricte du bot et de ses permissions.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import requests
from scripts.telegram_test_guard import validate_test_channel

TEST_CHANNEL = "@predict_mrxp"


def send_delivery_test(token: str, requester=requests.post) -> int:
    token = (token or "").strip()
    destination = validate_test_channel(TEST_CHANNEL, token)
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    message = (
        "🧪 TEST TECHNIQUE — MR XPRONOS ACTU CRYPTO #08\n\n"
        "✅ Vérification de la livraison des messages Telegram.\n"
        "Ce message est un TEST. Il ne contient AUCUNE actualité, "
        "aucun pronostic et aucun conseil financier.\n\n"
        f"📅 {now}\n"
        "📍 Canal de test : @predict_mrxp"
    )
    try:
        response = requester(
            "https://api.telegram.org/bot" + token + "/sendMessage",
            data={
                "chat_id": destination["chat_id"],
                "text": message,
                "disable_notification": True,
                "disable_web_page_preview": True,
            },
            timeout=(10, 45),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        # Ne jamais journaliser une URL contenant le token.
        raise RuntimeError(
            "Résultat d'envoi Telegram inconnu : ne pas relancer automatiquement"
        ) from None
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RuntimeError("Telegram a refusé le message de diagnostic")
    result = payload.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
        raise RuntimeError("Telegram a répondu sans identifiant de message fiable")
    received_chat = result.get("chat")
    if not isinstance(received_chat, dict) or received_chat.get("id") != destination["chat_id"]:
        raise RuntimeError("Telegram indique un destinataire inattendu")
    print(
        "BREAKING_08_DELIVERY_TEST_CONFIRMED",
        "chat=@" + destination["username"],
        "message_id=" + str(result["message_id"]),
        "bot=@" + destination["bot_username"],
    )
    return result["message_id"]


if __name__ == "__main__":
    send_delivery_test(os.environ.get("FOOTBALL_NEWS_BOT_TOKEN", ""))
