"""Image originale puis films puis publicité : diffusion des 5 canaux publics CinéX."""
from __future__ import annotations
import asyncio
import io
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from telethon import Button, TelegramClient, utils
from telethon.sessions import StringSession

ROOT = Path(__file__).resolve().parents[2]
IMAGE = ROOT / "telegram-film-relay" / "assets" / "partenariat-canal-original.jpg"
REFERENCE = "PARTENARIAT-CANAL"
PREFILL = (
    "Bonjour 👋 Je suis intéressé par votre offre de partenariat "
    "pour les canaux Telegram. 🤝\nRéférence : " + REFERENCE
)
URL = "https://t.me/mr_xpronos?text=" + quote(PREFILL, safe="")
CAPTION = (
    "🚀 FAITES GRANDIR VOTRE CANAL TELEGRAM SANS EFFORT !\n\n"
    "Je m'occupe de publier régulièrement des contenus adaptés à votre canal : "
    "films, animés, sport et autres thématiques.\n"
    "✅ Canal actif — ✅ Aucun effort — ✅ Vous gardez le contrôle.\n\n"
    "🤝 En échange, je publie occasionnellement mes propres publicités, "
    "selon notre accord.\n\n"
    "📩 @mr_xpronos — Réf. PARTENARIAT-CANAL"
)


def targets():
    """Exclusivement les 5 canaux publics demandés, pas les bibliothèques privées."""
    names = [
        ("films", os.getenv("TG_PUBLIC_CHANNEL", "")),
        ("desir", os.getenv("DESIR_PUBLIC_CHANNEL", "@CineXDesirfr")),
        ("comedie", os.getenv("COMEDIE_PUBLIC_CHANNEL", "")),
        ("anime", os.getenv("ANIME_PUBLIC_CHANNEL", "")),
        ("torrent", os.getenv("TG_MIRROR_CHANNEL", "@Torrent9SeriesFilms")),
    ]
    return [(label, value.strip()) for label, value in names]


async def recent_post(user, channel):
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=90)
    async for item in user.iter_messages(channel, limit=50):
        if item.date and item.date < cutoff:
            break
        if REFERENCE in (item.raw_text or "") and item.photo:
            return item
    return None


async def bot_ready(bot, username):
    try:
        entity = await bot.get_entity(username)
        identity = await bot.get_me()
        permissions = await bot.get_permissions(entity, identity)
        if getattr(entity, "broadcast", False) and (
            getattr(permissions, "is_creator", False)
            or (getattr(permissions, "is_admin", False)
                and getattr(permissions, "post_messages", False))
        ):
            return entity
    except Exception as exc:
        print("BOT_NON_DISPONIBLE", username, type(exc).__name__)
    return None


async def main():
    if not IMAGE.is_file():
        raise SystemExit("AFFICHE_ORIGINALE_ABSENTE " + str(IMAGE))
    raw = IMAGE.read_bytes()
    if not raw.startswith(b"\xff\xd8\xff"):
        raise SystemExit("Affiche attendue : JPEG original, sans modification.")

    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")
    session = (os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
               or os.getenv("TG_STREAM_SESSION"))
    if not all((api_id, api_hash, session)):
        raise SystemExit("Secrets Telethon manquants.")
    tokens = []
    for t in (os.getenv("DESIR_BOT_TOKEN"), os.getenv("FOOTBALL_NEWS_BOT_TOKEN"),
              os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("CINEX_BOT_TOKEN")):
        if t and t not in tokens:
            tokens.append(t)
    if not tokens:
        raise SystemExit("Aucun bot de publication disponible.")

    user = TelegramClient(StringSession(session), int(api_id), api_hash)
    bots = []
    await user.connect()
    try:
        if not await user.is_user_authorized():
            raise SystemExit("Session Telethon expirée.")
        for token in tokens:
            bot = TelegramClient(StringSession(), int(api_id), api_hash)
            try:
                await bot.start(bot_token=token)
                bots.append(bot)
            except Exception as exc:
                print("BOT_CONNEXION_ECHEC", type(exc).__name__)
                await bot.disconnect()
        if not bots:
            raise SystemExit("Impossible de connecter les bots.")

        posted = {}
        failures = []
        seen_destinations = set()
        for label, dest in targets():
            if not dest:
                print("CANAL_NON_CONFIGURE", label)
                failures.append(label + ": non configuré")
                continue
            if dest.casefold() in seen_destinations:
                print("CANAL_DEJA_TRAITE", label, dest)
                continue
            seen_destinations.add(dest.casefold())
            try:
                channel = await user.get_entity(dest)
                if not getattr(channel, "broadcast", False):
                    raise ValueError("La destination n'est pas un canal de diffusion.")
                already = await recent_post(user, channel)
                if already:
                    posted[label] = (channel, already.id)
                    print("DEJA_PUBLIE", label, dest, already.id)
                    continue

                message = None
                for bot in bots:
                    peer = await bot_ready(bot, dest)
                    if peer is None:
                        continue
                    picture = io.BytesIO(raw)
                    picture.name = "partenariat-canal-original.jpg"
                    message = await bot.send_file(
                        peer, picture, caption=CAPTION,
                        buttons=[[Button.url("💬 Proposer un partenariat", URL,
                                             style="primary")]],
                        force_document=False
                    )
                    posted[label] = (channel, int(message.id))
                    print("AFFICHE_ENVOYEE", label, dest, message.id)
                    break

                # Le canal Torrent sert déjà de miroir : si aucun bot n'y est admin,
                # utiliser le transfert natif depuis le canal de films classiques.
                if message is None and label == "torrent" and "films" in posted:
                    source, source_id = posted["films"]
                    mirrored = await user.forward_messages(
                        channel, source_id, from_peer=source
                    )
                    message = mirrored[0] if isinstance(mirrored, list) else mirrored
                    if message:
                        posted[label] = (channel, int(message.id))
                        print("AFFICHE_TRANSFERREE", label, dest, message.id)

                if message is None:
                    failures.append(label + ": aucun bot autorisé")
                    print("ECHEC_CIBLE", label, dest, "aucun bot autorisé")
                else:
                    await asyncio.sleep(2)
            except Exception as exc:
                failures.append(label + ": " + type(exc).__name__)
                print("ECHEC_CIBLE", label, dest, type(exc).__name__, str(exc)[:200])

        print("BILAN_PARTENARIAT", len(posted), "/5 canaux",
              "ÉCHECS", "; ".join(failures) if failures else "aucun")
        if failures:
            raise SystemExit("DIFFUSION_PARTIELLE : " + "; ".join(failures))
    finally:
        for bot in bots:
            await bot.disconnect()
        await user.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
