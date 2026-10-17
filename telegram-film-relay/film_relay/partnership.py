"""Publication de l'offre partenariat AVANT chaque cycle CinéX.

Cinq canaux publics : CinéX classique, Désir, Comédie, Animés et Torrent.
Le miroir reçoit un transfert natif de la première affiche (un seul message).
Aucun message dans les bibliothèques privées. Jamais de visuel de substitution.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

LOG = logging.getLogger("cinex_partnership")
IMAGE_PATH = Path(__file__).resolve().parents[1] / "assets" / "promotions" / "partenariat-canal.png"
MARKER = "PARTENARIAT-CANAL"
DRAFT = (
    "Bonjour 👋 Je souhaite proposer mon canal Telegram pour votre partenariat. "
    "Voici le lien de mon canal :\n"
    "Référence : " + MARKER
)
BUTTON_URL = "https://t.me/mr_xpronos?text=" + quote(DRAFT, safe="")
CAPTION = (
    "🤝 PARTENARIAT TELEGRAM — " + MARKER + "\n\n"
    "Vous avez un canal de films, animés, comédies ou autres contenus ? "
    "Je vous propose de l'alimenter gratuitement avec des publications régulières, "
    "adaptées à votre thématique. Vous gardez le contrôle de votre canal.\n\n"
    "En échange, je pourrai publier occasionnellement mes propres publicités "
    "selon les conditions convenues ensemble.\n\n"
    "💬 Contact : @mr_xpronos\n"
    "👇 Cliquez ci-dessous pour proposer votre canal !"
)
RECENT_MINUTES = 30


def targets():
    """Les quatre catégories principales, puis le miroir, sans aucune bibliothèque privée."""
    return [
        ("classique", os.getenv("TG_PUBLIC_CHANNEL", "").strip(), "classic"),
        ("desir", os.getenv("DESIR_PUBLIC_CHANNEL", "@CineXDesirfr").strip(), "categories"),
        ("comedie", os.getenv("COMEDIE_PUBLIC_CHANNEL", "").strip(), "categories"),
        ("anime", os.getenv("ANIME_PUBLIC_CHANNEL", "").strip(), "categories"),
        ("torrent", os.getenv("TG_MIRROR_CHANNEL", "@Torrent9SeriesFilms").strip(), "mirror"),
    ]


def validate_artwork(path: Path = IMAGE_PATH):
    """Refuser toute autre affiche ou placeholder."""
    from PIL import Image
    if not path.is_file():
        raise FileNotFoundError(
            f"Affiche originale absente de GitHub : {path}. "
            "Ajouter l'image fournie par le propriétaire à ce chemin exact."
        )
    raw = path.read_bytes()
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Affiche partenariat invalide : un PNG original est requis.")
    with Image.open(io.BytesIO(raw)) as im:
        if im.size != (1536, 1536):
            raise ValueError("Image inattendue : l'original doit mesurer 1536 × 1536.")
        im.verify()
    return raw


async def recently_published(client, entity):
    now = datetime.now(timezone.utc)
    async for message in client.iter_messages(entity, limit=40):
        if MARKER not in (getattr(message, "raw_text", "") or ""):
            continue
        date = getattr(message, "date", None)
        if date is None:
            continue
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        if timedelta(0) <= now - date < timedelta(minutes=RECENT_MINUTES):
            return int(message.id)
    return None


async def _send_bot(bot, channel, artwork):
    from telethon import Button
    buf = io.BytesIO(artwork)
    buf.name = "partenariat-canal.png"
    return await bot.send_file(
        channel, buf, caption=CAPTION,
        buttons=[[Button.url("💬 PROPOSER MON CANAL", BUTTON_URL, style="primary")]],
        force_document=False,
    )


async def run():
    from telethon import TelegramClient, utils
    from telethon.sessions import StringSession

    pairs = targets()
    if any(not value for _, value, _ in pairs):
        raise RuntimeError(
            "Canaux publics manquants : vérifier TG_PUBLIC_CHANNEL, "
            "COMEDIE_PUBLIC_CHANNEL et ANIME_PUBLIC_CHANNEL. Aucun envoi."
        )
    if len({s.lower() for _, s, _ in pairs}) != len(pairs):
        raise RuntimeError("Deux destinations publiques portent le même identifiant. Aucun envoi.")
    artwork = validate_artwork()
    api_id = os.environ["TG_API_ID"]
    api_hash = os.environ["TG_API_HASH"]
    user_session = os.environ["TG_STRING_SESSION"]
    classic_token = os.getenv("CINEX_BOT_TOKEN", "").strip()
    category_token = os.getenv("CINEX_CATEGORY_BOT_TOKEN", "").strip()
    if not classic_token or not category_token:
        raise RuntimeError("Les deux jetons de bots CinéX sont requis, aucun envoi.")

    user = TelegramClient(StringSession(user_session), int(api_id), api_hash,
                          request_retries=1, connection_retries=2, flood_sleep_threshold=0)
    bots = {}
    await user.connect()
    try:
        if not await user.is_user_authorized():
            raise RuntimeError("Session utilisateur Telegram non autorisée.")
        for role, token in (("classic", classic_token), ("categories", category_token)):
            if role == "categories" and token == classic_token:
                bots[role] = bots["classic"]
                continue
            client = TelegramClient(StringSession(), int(api_id), api_hash,
                                    request_retries=1, connection_retries=2,
                                    flood_sleep_threshold=0)
            await client.start(bot_token=token)
            bots[role] = client

        # Pré-vérification : tous les canaux et droits du bot sont valides AVANT
        # le premier envoi. Miroir transféré via la session personnelle.
        resolved = {}
        for name, dest, role in pairs:
            entity = await user.get_entity(dest)
            if not getattr(entity, "broadcast", False):
                raise RuntimeError(f"{name} n'est pas un canal de diffusion.")
            resolved[name] = entity
            if role != "mirror":
                bot = bots[role]
                bot_entity = await bot.get_entity(dest)
                if utils.get_peer_id(bot_entity) != utils.get_peer_id(entity):
                    raise RuntimeError(f"Identifiant {name} différent entre bot et compte.")
                me = await bot.get_me()
                perm = await bot.get_permissions(bot_entity, me)
                if not (getattr(perm, "is_creator", False) or
                        (getattr(perm, "is_admin", False) and getattr(perm, "post_messages", False))):
                    raise RuntimeError(f"Bot sans droit de publication sur {name}.")
        receipts = {}
        for name, dest, role in pairs:
            previous = await recently_published(user, resolved[name])
            if previous:
                receipts[name] = previous
                LOG.info("Déjà publié récemment : %s/%s, anti-doublon.", name, previous)
                continue
            if role == "mirror":
                source = receipts.get("classique")
                if not source:
                    raise RuntimeError("Miroir impossible : affiche classique absente.")
                forwarded = await user.forward_messages(
                    resolved[name], source, from_peer=resolved["classique"]
                )
                msg = forwarded[0] if isinstance(forwarded, list) else forwarded
            else:
                msg = await _send_bot(bots[role], dest, artwork)
            if not msg or getattr(msg, "id", None) is None:
                raise RuntimeError(f"Telegram n'a pas confirmé la publication {name}.")
            receipts[name] = int(msg.id)
            LOG.info("Affiche avant contenus : %s id=%s", name, receipts[name])
            await asyncio.sleep(2)
        LOG.info("PARTNERSHIP_PUBLISHED %s", receipts)
        return receipts
    finally:
        seen = set()
        for bot in bots.values():
            if id(bot) in seen:
                continue
            seen.add(id(bot))
            await bot.disconnect()
        await user.disconnect()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.dry_run:
        print("Affiche:", IMAGE_PATH, "existante:", IMAGE_PATH.is_file())
        print("Destinations:", [(name, bool(value), role) for name,value,role in targets()])
        print("Légende:", CAPTION)
        print("Lien:", BUTTON_URL)
        return
    asyncio.run(run())


if __name__ == "__main__":
    main()
