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

import os
from datetime import datetime, timezone
import requests


def _ledger_config():
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        raise RuntimeError("Anti-doublon indisponible: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY manquant")
    return url + "/rest/v1/telegram_promo_deliveries", {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    }


def deliver_once_to_both(channels, send_one, *, campaign, label="Promotion"):
    """Idempotence atomique par date UTC et canal, même entre différents runs.

    L'insertion unique réserve la diffusion AVANT l'appel Telegram. Un échec
    incertain reste réservé: on privilégie l'absence de doublon plutôt qu'un
    renvoi potentiellement répété. Débloquer manuellement après vérification.
    """
    if not campaign or not isinstance(campaign, str):
        raise ValueError("Identifiant de campagne requis")
    endpoint, headers = _ledger_config()
    day = datetime.now(timezone.utc).date().isoformat()
    errors = []
    sent = 0
    for role, chat_id in channels:
        payload = {"campaign": campaign, "delivery_day": day, "chat_id": chat_id}
        reserve = requests.post(
            endpoint,
            params={"on_conflict": "campaign,delivery_day,chat_id"},
            headers={**headers, "Prefer": "resolution=ignore-duplicates,return=representation"},
            json=payload, timeout=25,
        )
        reserve.raise_for_status()
        rows = reserve.json()
        if not isinstance(rows, list):
            raise RuntimeError("Réponse Supabase inattendue lors de la réservation")
        if not rows:
            print(f"⏭️ Promotion déjà réservée/envoyée : {campaign} ({role})")
            continue
        try:
            send_one(chat_id)
            sent += 1
            finished = requests.patch(
                endpoint,
                params={
                    "campaign": "eq." + campaign,
                    "delivery_day": "eq." + day,
                    "chat_id": "eq." + chat_id,
                },
                headers=headers,
                json={"status": "sent", "sent_at": datetime.now(timezone.utc).isoformat()},
                timeout=25,
            )
            finished.raise_for_status()
            print(f"✅ {label} envoyé une fois ({role})")
        except Exception as exc:
            errors.append(f"{role}: {exc}")
            print(f"❌ Envoi incertain, réservation conservée ({role}): {exc}")
    if errors:
        raise RuntimeError("Une ou plusieurs livraisons sont incertaines : " + " | ".join(errors))
    return sent
