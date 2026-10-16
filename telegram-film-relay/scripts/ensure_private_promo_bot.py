"""One-time minimal bot admin setup in the user's own private movie channel.

Only grants post_messages; no delete, edit, invite, promote or read-history
capabilities are requested beyond standard channel membership.
"""
from __future__ import annotations
import asyncio
import os

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import EditAdminRequest, GetParticipantRequest
from telethon.tl.types import ChatAdminRights, ChannelParticipantAdmin, ChannelParticipantCreator

from film_relay.runner import resolve_peer


async def execute():
    api_id=int(os.environ["TG_API_ID"])
    api_hash=os.environ["TG_API_HASH"]
    session=os.environ["TG_STRING_SESSION"]
    token=os.environ["CINEX_BOT_TOKEN"]
    user=TelegramClient(StringSession(session),api_id,api_hash)
    bot=TelegramClient(StringSession(),api_id,api_hash)
    await user.connect()
    try:
        if not await user.is_user_authorized():
            raise RuntimeError("Compte propriétaire Telegram non autorisé.")
        await bot.start(bot_token=token)
        me=await user.get_me()
        identity=await bot.get_me()
        handle=getattr(identity,"username",None)
        if not handle:
            raise RuntimeError("Le bot Telegram sélectionné n'a pas de @username.")
        private=await resolve_peer(user,os.environ["TG_PRIVATE_CHANNEL"])
        rights=await user.get_permissions(private,me)
        if not (getattr(rights,"is_creator",False) or
                (getattr(rights,"is_admin",False) and getattr(rights,"add_admins",False))):
            raise RuntimeError("Seul le créateur ou un administrateur autorisé peut ajouter le bot.")

        bot_entity=await user.get_entity("@"+handle)
        try:
            existing=await user(GetParticipantRequest(channel=private,participant=bot_entity))
            participant=existing.participant
            present_rights=getattr(participant,"admin_rights",None)
            if (isinstance(participant,ChannelParticipantCreator) or
                 bool(present_rights and getattr(present_rights,"post_messages",False))):
                print(f"PRIVÉ : @{handle} déjà autorisé à publier ; aucun changement.")
                return 0
        except Exception as exc:
            print("PRIVÉ : droits existants non confirmés ("+
                  type(exc).__name__+"), préparation d'une autorisation minimale.")

        minimal=ChatAdminRights(
            change_info=False,post_messages=True,edit_messages=False,
            delete_messages=False,ban_users=False,invite_users=False,
            pin_messages=False,add_admins=False,anonymous=False,
            manage_call=False,other=False,manage_topics=False,
            post_stories=False,edit_stories=False,delete_stories=False,
        )
        try:
            await user(EditAdminRequest(
                channel=private,user_id=bot_entity,
                admin_rights=minimal,rank="Annonces CinéX"
            ))
        except Exception as exc:
            print("L'ajout direct du bot a échoué : "+type(exc).__name__)
            print("Action Telegram : Canal privé → Administrateurs → Ajouter @"+
                  handle+" → activer Publier des messages.")
            return 2

        outcome=await user(GetParticipantRequest(channel=private,participant=bot_entity))
        checked=getattr(outcome.participant,"admin_rights",None)
        if not checked or not getattr(checked,"post_messages",False):
            raise RuntimeError("Droit Publier des messages non confirmé après la modification.")
        print("PRIVÉ : bot @"+handle+" autorisé à publier avec droits limités.")
        return 0
    finally:
        await bot.disconnect()
        await user.disconnect()


if __name__=="__main__":
    raise SystemExit(asyncio.run(execute()))
