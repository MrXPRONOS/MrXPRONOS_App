"""Publie l'affiche partenariat d'origine AVANT le cycle CinéX.

Photo GitHub obligatoire, aucun remplacement généré. Les refus Telegram sont
journalisés ; un échec ne bloque pas les films. Les doublons de relance courte
sont évités en inspectant les messages récents.
"""
import asyncio
import io
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from telethon import TelegramClient, Button, utils
from telethon.sessions import StringSession

ROOT=Path(__file__).resolve().parents[2]
IMAGE=ROOT/"telegram-film-relay"/"assets"/"partenariat-canal-original.png"
REF="PARTENARIAT-CANAL"
MSG="Bonjour 👋 Je suis intéressé par votre offre de partenariat pour les canaux Telegram. 🤝\nRéférence : "+REF
URL="https://t.me/mr_xpronos?text="+quote(MSG,safe="")
CAPTION=(
    "🚀 FAITES GRANDIR VOTRE CANAL TELEGRAM SANS EFFORT !\n\n"
    "Je m'occupe de publier régulièrement des contenus adaptés à votre canal : "
    "films, animés, sport et autres thématiques.\n"
    "✅ Canal actif — ✅ Aucun effort — ✅ Vous gardez le contrôle.\n\n"
    "🤝 En échange, je publie occasionnellement mes propres publicités, "
    "selon notre accord.\n\n"
    "📩 @mr_xpronos — Réf. PARTENARIAT-CANAL"
)

def destinations():
    """Canaux publics affichés dans le relais; pas les bibliothèques privées."""
    raw=[
       os.getenv("TG_PUBLIC_CHANNEL",""),
       os.getenv("DESIR_PUBLIC_CHANNEL","@CineXDesirfr"),
       os.getenv("COMEDIE_PUBLIC_CHANNEL",""),
       os.getenv("ANIME_PUBLIC_CHANNEL",""),
       os.getenv("TG_MIRROR_CHANNEL","@Torrent9SeriesFilms"),
    ]
    return list(dict.fromkeys(v.strip() for v in raw if v and v.strip()))

async def main():
    if not IMAGE.is_file():
        raise SystemExit("AFFICHE_ORIGINALE_ABSENTE : importer l'image fournie dans "+str(IMAGE))
    data=IMAGE.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SystemExit("L'affiche fournie doit être le PNG original.")
    creds=(os.getenv("TG_API_ID"),os.getenv("TG_API_HASH"),os.getenv("TG_STRING_SESSION"))
    if not all(creds):
        raise SystemExit("Session Telegram manquante.")
    tok=os.getenv("CINEX_BOT_TOKEN","").strip()
    if not tok:
        raise SystemExit("Bot Telegram manquant.")
    user=TelegramClient(StringSession(creds[2]),int(creds[0]),creds[1])
    bot=TelegramClient(StringSession(),int(creds[0]),creds[1])
    await user.connect()
    try:
        if not await user.is_user_authorized():
            raise SystemExit("Session Telegram expirée.")
        await bot.start(bot_token=tok)
        print("CANAUX_PREVUS",destinations())
        for dest in destinations():
            try:
                entity=await bot.get_entity(dest)
                if not getattr(entity,"broadcast",False):
                    print("PAS_UN_CANAL",dest);continue
                identity=await bot.get_me()
                perm=await bot.get_permissions(entity,identity)
                if not (getattr(perm,"is_creator",False) or (getattr(perm,"is_admin",False) and getattr(perm,"post_messages",False))):
                    print("BOT_SANS_PERMISSION",dest);continue
                cutoff=datetime.now(timezone.utc)-timedelta(minutes=40)
                found=False
                async for m in bot.iter_messages(entity,limit=30):
                    if m.date and m.date<cutoff:break
                    if REF in (m.raw_text or ""):
                        found=True;break
                if found:
                    print("DEJA_PUBLIE",dest);continue
                photo=io.BytesIO(data);photo.name="partenariat-canal.png"
                sent=await bot.send_file(entity,photo,caption=CAPTION,
                    buttons=[[Button.url("💬 Proposer un partenariat",URL,style="primary")]],
                    force_document=False)
                print("AFFICHE_ENVOYEE",dest,sent.id)
                await asyncio.sleep(2)
            except Exception as exc:
                print("ECHEC_CIBLE",dest,type(exc).__name__,str(exc)[:180])
    finally:
        await bot.disconnect()
        await user.disconnect()

if __name__=="__main__":
    asyncio.run(main())
