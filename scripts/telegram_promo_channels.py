"""Destination validation and delivery reporting for scheduled bookmaker promotions.

This module is deliberately restricted to *promotional* Telegram campaigns.
It does not modify the channels used by prediction or result notifications.
"""
from __future__ import annotations


def promo_channels(primary: str | None, secondary: str | None):
    """Return two distinct configured Telegram channels, or fail explicitly."""
    first = (primary or "").strip()
    second = (secondary or "").strip()
    if not first:
        raise ValueError("TELEGRAM_CHAT_ID (canal principal) n'est pas configuré")
    if not second:
        raise ValueError(
            "TELEGRAM_CHAT_ID_SECONDARY est absent. "
            "Ajoute le deuxième canal aux GitHub Actions Secrets."
        )
    if first == second:
        raise ValueError(
            "TELEGRAM_CHAT_ID et TELEGRAM_CHAT_ID_SECONDARY "
            "désignent le même canal"
        )
    return (("primary", first), ("secondary", second))


def deliver_to_both(channels, send_one, *, label="Promotion"):
    """Attempt BOTH deliveries independently and surface any failures.

    send_one(chat_id) is responsible for opening/rewinding the upload and
    checking the Telegram HTTP/API result. A failure on one channel must
    never prevent attempting the other.
    """
    errors = []
    for role, chat_id in channels:
        try:
            send_one(chat_id)
            print(f"✅ {label} envoyé vers {chat_id} ({role})")
        except Exception as exc:
            errors.append(f"{role} ({chat_id}): {exc}")
            print(f"❌ Envoi promotion échoué : {role} ({chat_id}): {exc}")
    if errors:
        raise RuntimeError("Échec Telegram sur un ou plusieurs canaux : " + " | ".join(errors))
    return 2
