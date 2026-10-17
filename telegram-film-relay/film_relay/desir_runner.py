"""Independent CinéX Désir relay: no native forwarding attribution.

A deliberately bounded workflow: one source, one private library, one public
channel, one finished movie per first test; separate checkpoints from CinéX.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import logging
import os
from html import escape
from pathlib import Path

from .desir_matching import pair_items, film_title, item_key
from .matching import document_key
from .runner import resolve_peer
from .text import private_message_link
from .publication import rich_caption, rich_video_title, send_public_poster_with_buttons
from .recovery import snapshot_telegram_posts

LOG = logging.getLogger("cinex_desir")
STATE_DEFAULT = "state/desir_state.json"

class ReceiptState:
    def __init__(self, path: str):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        self.data.setdefault("completed", {})
        self.data.setdefault("staged", {})
    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True)+"\n",
                             encoding="utf-8")
        temporary.replace(self.path)
    def stage(self, key: str, field: str, value: int):
        self.data["staged"].setdefault(key, {})[field] = int(value)
        self.save()
    def complete(self, key: str, video_id: int, public_id: int):
        self.data["completed"][key] = {"video_id": int(video_id), "public_id": int(public_id)}
        self.data["staged"].pop(key, None)
        self.save()

def required(name: str, default: str = "") -> str:
    value = (os.getenv(name) or default).strip()
    if not value:
        raise RuntimeError(f"Configuration obligatoire manquante : {name}")
    return value

def verify_destination(source: str, public: str, private: str) -> None:
    if source.lower() != "@filmromatique":
        raise RuntimeError("Source refusée : DESIR_SOURCE_CHANNEL doit être @Filmromatique")
    if public.lower() != "@cinexdesirfr":
        raise RuntimeError("Destination refusée : DESIR_PUBLIC_CHANNEL doit être @CineXDesirfr")
    if not private.startswith("-100") or not private[1:].isdigit():
        raise RuntimeError("DESIR_PRIVATE_CHANNEL doit être l'identifiant numérique -100... du canal privé.")

async def preflight_user(client, src, private, public):
    from telethon import utils
    if not await client.is_user_authorized():
        raise RuntimeError("Session Telegram personnelle expirée.")
    source_peer = await resolve_peer(client, src)
    library_peer = await resolve_peer(client, private)
    public_peer = await resolve_peer(client, public)
    keys = {utils.get_peer_id(source_peer), utils.get_peer_id(library_peer), utils.get_peer_id(public_peer)}
    if len(keys) != 3:
        raise RuntimeError("La source, le public et le privé doivent être trois canaux distincts.")
    if getattr(source_peer, "noforwards", False):
        raise RuntimeError("Source protégée : aucune copie de média.")
    if getattr(source_peer, "username", "").lower() != "filmromatique":
        raise RuntimeError("La source Telegram ne correspond pas à @Filmromatique.")
    if getattr(public_peer, "username", "").lower() != "cinexdesirfr":
        raise RuntimeError("Le canal public Telegram ne correspond pas à @CineXDesirfr.")
    return source_peer, library_peer, public_peer

async def preflight_bot(bot, public, user_public):
    from telethon import utils
    peer = await bot.get_entity(public)
    if utils.get_peer_id(peer) != utils.get_peer_id(user_public):
        raise RuntimeError("Le bot et le compte personnel ne voient pas le même canal public.")
    who = await bot.get_me()
    permission = await bot.get_permissions(peer, who)
    allowed = bool(getattr(permission, "is_creator", False) or (
        getattr(permission, "is_admin", False) and getattr(permission, "post_messages", False)))
    if not allowed:
        raise RuntimeError("Ajouter le bot comme administrateur de @CineXDesirfr avec Publier.")
    return peer

def format_title(item):
    value = film_title(item).strip()
    return value if value else "Film CinéX Désir"

async def post_public(bot, user, public_peer, item, title, video_url: str,
                      invite_link: str):
    from telethon import Button
    if item.poster is not None:
        return await send_public_poster_with_buttons(
            user, bot, public_peer, item.poster, title, video_url, invite_link
        )
    buttons = [[Button.url("🎬 REGARDER LE FILM", video_url, style="success")]]
    if invite_link.startswith("https://t.me/"):
        buttons.append([Button.url("🔐 ACCÉDER À LA VIDÉOTHÈQUE", invite_link, style="success")])
    return await bot.send_message(
        public_peer,
        f"<b>🎬 {escape(title[:700])}</b>\n\n👇 Accède au film avec le bouton ci-dessous.",
        parse_mode="html", buttons=buttons, link_preview=False,
    )

async def execute(*, publish: bool, limit: int, newest: bool, require_publication: bool = False) -> int:
    from telethon import TelegramClient, utils
    from telethon.sessions import StringSession
    from telethon.errors import FloodWaitError, PeerFloodError
    source = required("DESIR_SOURCE_CHANNEL", "@Filmromatique")
    public = required("DESIR_PUBLIC_CHANNEL", "@CineXDesirfr")
    private = required("DESIR_PRIVATE_CHANNEL")
    verify_destination(source, public, private)
    credentials = (required("TG_API_ID"), required("TG_API_HASH"),
                   required("TG_STRING_SESSION", os.getenv("TG_SESSION_STRING", "")))
    state = ReceiptState(os.getenv("DESIR_STATE_PATH", STATE_DEFAULT))
    client = TelegramClient(StringSession(credentials[2]), int(credentials[0]), credentials[1],
                            request_retries=0, connection_retries=2,
                            flood_sleep_threshold=0, receive_updates=False)
    bot = None
    completed = 0
    try:
        await client.connect()
        src, library, public_user = await preflight_user(client, source, private, public)
        bot_public = None
        if publish:
            token = required("DESIR_BOT_TOKEN")
            bot = TelegramClient(StringSession(), int(credentials[0]), credentials[1],
                                 request_retries=0, connection_retries=2,
                                 flood_sleep_threshold=0, receive_updates=False)
            await bot.start(bot_token=token)
            bot_public = await preflight_bot(bot, public, public_user)
        # Small bounded window to minimize Telegram requests.
        messages = [m async for m in client.iter_messages(src, limit=160)]
        candidates = pair_items(messages)
        if newest:
            candidates.reverse()
        LOG.info("CinéX Désir : messages analysés=%s, vidéos candidates=%s, mode=%s",
                 len(messages), len(candidates), "PUBLICATION" if publish else "SIMULATION")
        peer_id = utils.get_peer_id(src)
        private_id = utils.get_peer_id(library)
        for item in candidates:
            key = item_key(peer_id, item)
            if key in state.data["completed"]:
                continue
            title = format_title(item)
            LOG.info("Film candidat : source_message=%s affiche=%s type=%s",
                     item.video.id, getattr(item.poster, "id", None),
                     (getattr(getattr(item.video, "file", None), "name", "") or "document"))
            if not publish:
                completed += 1
                if completed >= limit:
                    break
                continue
            if getattr(item.video, "noforwards", False) or (
                item.poster is not None and getattr(item.poster, "noforwards", False)
            ):
                LOG.warning("Média protégé : non publié.")
                continue
            staged = state.data["staged"].get(key, {})
            # Recover a completed private upload if the previous run crashed before commit.
            if "video" not in staged:
                # Bound the recovery search and do it only when needed.
                cache = await snapshot_telegram_posts(
                    client, library, public_user, private_id,
                    private_limit=110, public_limit=110
                )
                source_doc_id = getattr(getattr(item.video, "document", None), "id", None)
                recovered = cache.by_document.get(source_doc_id, []) if source_doc_id else []
                if recovered:
                    private_video_id = int(recovered[0])
                    existing_public_id = cache.public_by_video.get(private_video_id)
                    if existing_public_id:
                        state.complete(key, private_video_id, existing_public_id)
                        LOG.info("Publication existante reconnue ; doublon évité.")
                        continue
                    state.stage(key, "video", private_video_id)
                    staged = state.data["staged"][key]
            if "video" not in staged:
                if item.poster is not None and "poster" not in staged:
                    image = await client.send_file(
                        library, item.poster.media,
                        caption=rich_caption(title, private=True), parse_mode="html"
                    )
                    state.stage(key, "poster", image.id)
                    await asyncio.sleep(4)
                video = await client.send_file(
                    library, item.video.media,
                    caption=rich_video_title(title), parse_mode="html"
                )
                state.stage(key, "video", video.id)
            private_video_id = int(state.data["staged"][key]["video"])
            await asyncio.sleep(4)
            video_url = private_message_link(private_id, private_video_id)
            link = (os.getenv("DESIR_PRIVATE_INVITE_LINK") or "").strip()
            public_post = await post_public(bot, client, bot_public, item, title, video_url, link)
            state.complete(key, private_video_id, public_post.id)
            completed += 1
            LOG.info("CinéX Désir : un film publié, id privé=%s, id public=%s",
                     private_video_id, public_post.id)
            await asyncio.sleep(10)
            if completed >= limit:
                break
        LOG.info("Bilan CinéX Désir : %s publication(s) ou aperçu(s)", completed)
        if publish and require_publication and completed == 0:
            LOG.error("Premier test non validé : aucun nouveau film publié.")
            return 3
        return 0
    except (FloodWaitError, PeerFloodError) as exc:
        LOG.error("Restriction Telegram (%s) : arrêt immédiat, aucun retry.", type(exc).__name__)
        return 2
    finally:
        if bot is not None:
            await bot.disconnect()
        await client.disconnect()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--publish", action="store_true", help="Publier réellement au lieu de simuler")
    p.add_argument("--limit", type=int, default=1)
    p.add_argument("--newest", action="store_true")
    p.add_argument("--require-publication", action="store_true")
    args = p.parse_args()
    if args.limit < 1 or args.limit > 2:
        p.error("Limite autorisée : 1 ou 2 publications")
    logging.basicConfig(level="INFO", format="%(asctime)s | %(levelname)s | %(message)s")
    try:
        result = asyncio.run(execute(publish=args.publish, limit=args.limit,
                                     newest=args.newest, require_publication=args.require_publication))
    except Exception:
        LOG.exception("CinéX Désir : échec, voir message détaillé.")
        result = 1
    raise SystemExit(result)

if __name__ == "__main__":
    main()
