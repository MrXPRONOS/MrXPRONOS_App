#!/usr/bin/env python3
"""Optional CineX public-channel membership; existing Mr XPRONOS bot/webhook.

Run --check-only before activation. No channel is joined, no film is copied.
For Telegram Ads, use the PUBLIC URL, never the join-request URL.
"""
from __future__ import annotations
import argparse
import json
import os
from telegram_membership_setup import (
    Channel, Telegram, bot_token, clean, create_request_link,
    public_channel_url, setup_webhook, validate_admin,
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    chat_id = clean(os.getenv("CINEX_MEMBERSHIP_CHANNEL")) or clean(os.getenv("TG_PUBLIC_CHANNEL"))
    if not chat_id:
        raise SystemExit("Renseigner CINEX_MEMBERSHIP_CHANNEL (ou TG_PUBLIC_CHANNEL).")

    token = bot_token()
    tg = Telegram(token)
    me = tg.call("getMe")
    channel = Channel("CINEX", "CinéX Films", chat_id, "films, séries et nouveautés")
    chat = validate_admin(tg, int(me["id"]), channel)
    if chat.get("type") != "channel" or not chat.get("username"):
        raise SystemExit("Le canal CinéX doit être un canal public avec @username.")

    public_url = public_channel_url(chat)
    info = tg.call("getWebhookInfo") or {}
    expected = clean(os.getenv("TELEGRAM_MEMBERSHIP_WEBHOOK_URL")) or (
        "https://nhwafcpndlufzzxexikh.supabase.co/functions/v1/telegram-membership"
    )
    current = clean(info.get("url"))
    if current and current != expected:
        raise SystemExit(
            "Le webhook existant appartient à un autre service : aucun remplacement automatique."
        )

    print("CANAL_PUBLIC_CINEX", public_url)
    print("WEBHOOK_CURRENT_OK", current == expected)
    if args.check_only:
        print("CHECK_ONLY_OK: Aucun message, lien ou webhook créé.")
        return

    # Preserve the same Telegram webhook for the original three channels.
    setup_webhook(tg, token, replace=False)
    invite = create_request_link(tg, channel, chat["id"])
    msg = tg.call("sendMessage", json_body={
        "chat_id": chat["id"],
        "parse_mode": "HTML",
        "disable_notification": True,
        "text": (
            "🎬 <b>BIENVENUE CHEZ CINÉX</b> 🍿\n\n"
            "Découvre les affiches, bandes-annonces et publications disponibles "
            "directement dans ce canal public.\n\n"
            "💡 <b>L'abonnement est facultatif.</b> Tu peux consulter le contenu "
            "public sans t'abonner.\n\n"
            "🔔 Pour retrouver facilement les nouveautés et être averti des nouvelles "
            "publications, rejoins le canal et active les notifications.\n\n"
            "<i>Les vidéos accessibles via un autre canal peuvent nécessiter "
            "une étape supplémentaire.</i>"
        ),
        "reply_markup": {"inline_keyboard": [[{
            "text": "🔔 S'ABONNER (FACULTATIF)",
            "url": invite,
        }]]},
    })
    try:
        tg.call("pinChatMessage", json_body={
            "chat_id": chat["id"],
            "message_id": msg["message_id"],
            "disable_notification": True,
        })
        pinned = True
    except RuntimeError as exc:
        print("PIN_WARNING", str(exc))
        pinned = False
    print("ACTIVATED", json.dumps({
        "public_ad_url": public_url,
        "optional_join_url": invite,
        "pinned": pinned,
        "message_id": msg["message_id"],
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
