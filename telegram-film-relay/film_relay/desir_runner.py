"""Independent CinéX Désir relay.

Licensed source media are republished without forward attribution to the own
private/public channels. Only the public poster/link is then forwarded natively
to the secondary channel, keeping Telegram's original-source attribution.
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
from .source_channels import source_list
from .publication import (rich_caption, rich_video_title, url_button_rows,
                          film_folder_url, send_public_poster_with_buttons)
from .recovery import snapshot_telegram_posts, existing_native_forwards

LOG = logging.getLogger("cinex_desir")
STATE_DEFAULT = "state/desir_state.json"

class ReceiptState:
    def __init__(self, path: str):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        self.data.setdefault("completed", {})
        self.data.setdefault("staged", {})
        self.data.setdefault("mirrors", {})
        self.data.setdefault("promotions", {})
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

    def mirror_done(self, target: str, public_message_id: int, forwarded_message_id: int):
        self.data["mirrors"].setdefault(target, {})[str(int(public_message_id))] = int(forwarded_message_id)
        self.save()
    def mirror_recorded(self, target: str, public_message_id: int) -> bool:
        return str(int(public_message_id)) in self.data["mirrors"].get(target, {})
    def mirror_pending(self, target: str) -> list[int]:
        entries = self.data["completed"].values()
        return sorted({int(entry["public_id"]) for entry in entries
                       if entry.get("public_id") and not self.mirror_recorded(target, entry["public_id"])})

class DesirPromotionsState:
    """Expose compatible receipt fields to the shared original-poster ad rotation."""
    def __init__(self, receipt_state: ReceiptState):
        self.receipt_state = receipt_state
        self.data = {
            # Two different source channels may contain the SAME Telegram
            # movie. Count each distinct public post once for advertising.
            "processed": {
                str(entry["public_id"]): entry
                for entry in receipt_state.data["completed"].values()
                if entry.get("public_id")
            },
            "mirrors": receipt_state.data["mirrors"],
            "promotions": receipt_state.data["promotions"],
        }
    def save(self):
        self.receipt_state.save()


async def publish_desir_promotions(user_client, bot, library, public, mirror,
                                   receipt_state: ReceiptState) -> dict:
    """One identical blue-button advert per destination after every two Desire films.

    The secondary channel receives an attributed native forward of the Desire
    public advertisement. Private sends require the bot's own posting rights.
    """
    from .promotions import publish_promotions
    bridge = DesirPromotionsState(receipt_state)
    result = await publish_promotions(user_client, bot, library, public, mirror, bridge,
                                      private_fallback=True)
    LOG.info("PUBS DÉSIR après deux films : privé=%s public=%s Torrent9=%s ignorées=%s",
             result["private"], result["public"], result["mirror"], result["skipped"])
    return result


def required(name: str, default: str = "") -> str:
    value = (os.getenv(name) or default).strip()
    if not value:
        raise RuntimeError(f"Configuration obligatoire manquante : {name}")
    return value

def verify_destination(source: str, public: str, private: str) -> None:
    if source.casefold() not in ("@filmromatique", "@g_romanticfilm"):
        raise RuntimeError("Source CinéX Désir non autorisée : @Filmromatique ou @g_romanticfilm.")
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
    if str(getattr(source_peer, "username", "") or "").casefold() != src.lstrip("@").casefold():
        raise RuntimeError("La source Telegram ne correspond pas à " + src)
    if getattr(public_peer, "username", "").lower() != "cinexdesirfr":
        raise RuntimeError("Le canal public Telegram ne correspond pas à @CineXDesirfr.")
    return source_peer, library_peer, public_peer

async def preflight_bot(bot, public, user_public):
    from telethon import utils
    peer = await bot.get_entity(public)
    if utils.get_peer_id(peer) != utils.get_peer_id(user_public):
        raise RuntimeError("Le bot et le compte personnel ne voient pas le même canal public.")
    who = await bot.get_me()
    try:
        permission = await bot.get_permissions(peer, who)
    except Exception as exc:
        from telethon.errors import UserNotParticipantError
        if isinstance(exc, UserNotParticipantError):
            raise RuntimeError(
                "Le bot @" + str(getattr(who, "username", "") or "inconnu") +
                " n'est pas membre de @CineXDesirfr. Ajoute ce bot comme "
                "administrateur avec le droit Publier des messages, puis relance le test."
            ) from exc
        raise
    allowed = bool(getattr(permission, "is_creator", False) or (
        getattr(permission, "is_admin", False) and getattr(permission, "post_messages", False)))
    if not allowed:
        raise RuntimeError("Ajouter le bot comme administrateur de @CineXDesirfr avec Publier.")
    return peer

async def preflight_mirror(client, public_peer, library_peer, source_peer, mirror_name):
    """Fail before uploading private media if the mirror cannot be published to."""
    from telethon import utils
    from telethon.errors import UserNotParticipantError
    mirror = await resolve_peer(client, mirror_name)
    username = str(getattr(mirror, "username", "") or "").lower()
    if username != "torrent9seriesfilms":
        raise RuntimeError("Le miroir doit être le canal @Torrent9SeriesFilms.")
    ids = [utils.get_peer_id(x) for x in (mirror, public_peer, library_peer, source_peer)]
    if len(set(ids)) != 4:
        raise RuntimeError("Les quatre canaux CinéX Désir doivent être distincts.")
    if getattr(public_peer, "noforwards", False):
        raise RuntimeError("Le canal @CineXDesirfr interdit le transfert natif. Désactiver la protection des contenus.")
    identity = await client.get_me()
    try:
        permission = await client.get_permissions(mirror, identity)
    except UserNotParticipantError as exc:
        raise RuntimeError("Le compte Telegram personnel ne fait pas partie des administrateurs de @Torrent9SeriesFilms.") from exc
    is_allowed = bool(getattr(permission, "is_creator", False) or
                      (getattr(permission, "is_admin", False) and getattr(permission, "post_messages", False)))
    if not is_allowed:
        raise RuntimeError("Le compte Telegram personnel doit pouvoir Publier dans @Torrent9SeriesFilms.")
    return mirror, str(utils.get_peer_id(mirror))


async def forward_public_poster(client, public_peer, mirror_peer, public_id: int) -> int:
    """Native Telegram forward retains 'Transféré de CinéX Désir', without video."""
    msg = await client.forward_messages(mirror_peer, int(public_id), from_peer=public_peer)
    if isinstance(msg, list):
        msg = msg[0] if msg else None
    if not getattr(msg, "id", None):
        raise RuntimeError("Le transfert Telegram n'a pas renvoyé d'identifiant.")
    return int(msg.id)


async def finish_mirrors(client, state: ReceiptState, mirror_peer, mirror_key: str,
                         public_peer, *, limit: int = 5) -> int:
    """Retry past public posts without reposting images, buttons, or private videos."""
    from telethon import utils
    recovered = await existing_native_forwards(
        client, mirror_peer, utils.get_peer_id(public_peer), limit=350
    )
    count = 0
    for public_id in state.mirror_pending(mirror_key)[:limit]:
        if public_id in recovered:
            state.mirror_done(mirror_key, public_id, recovered[public_id])
            LOG.info("CinéX Désir : transfert miroir déjà présent, public=%s", public_id)
            continue
        forwarded_id = await forward_public_poster(client, public_peer, mirror_peer, public_id)
        state.mirror_done(mirror_key, public_id, forwarded_id)
        count += 1
        LOG.info("CinéX Désir : affiche publique %s transférée vers Torrent9, id=%s",
                 public_id, forwarded_id)
        await asyncio.sleep(max(12.0, float(os.getenv('CINEX_PAUSE_SECONDS', '20'))))
    return count


def format_title(item):
    value = film_title(item).strip()
    return value if value else "Film CinéX Désir"

async def post_public(bot, user, public_peer, item, title, video_url: str,
                      invite_link: str):
    """Public post: photo, in-caption video link, and native green buttons.

    A visible URL inside the caption survives Telegram forwarding even on
    clients which do not preserve a bot's inline keyboard.
    """
    from .bot_http import url_button
    # Same two buttons as the classic relay. The former private-library
    # invitation is no longer shown in the public message.
    rows = [
        [url_button(label, url, style="success" if index == 0 else "danger")
         for label, url in row]
        for index, row in enumerate(url_button_rows(video_url))
    ]
    # The link in text must survive the subsequent native forward.
    caption = (f"<b>🎬 {escape(title[:560])}</b>\n\n"
               f"🔗 <a href=\"{escape(video_url, quote=True)}\">REGARDER LE FILM</a>"
               f"\n\n🎞️ <a href=\"{escape(film_folder_url(), quote=True)}\">"
               "PLUS DE FILMS ? REJOINS NOTRE TEAM !</a>")
    if item.poster is not None:
        import io
        contents = await user.download_media(item.poster.media, file=bytes)
        if not contents:
            raise RuntimeError("Affiche inaccessible, publication interrompue.")
        image = io.BytesIO(contents)
        image.name = "cinex_desir.jpg"
        return await bot.send_file(public_peer, image, caption=caption,
                                   parse_mode="html", buttons=rows, force_document=False)
    return await bot.send_message(public_peer, caption, parse_mode="html",
                                  buttons=rows, link_preview=False)


async def execute(*, publish: bool, limit: int, newest: bool, require_publication: bool = False) -> int:
    from telethon import TelegramClient, utils
    from telethon.sessions import StringSession
    from telethon.errors import FloodWaitError, PeerFloodError
    source = required("DESIR_SOURCE_CHANNEL", "@Filmromatique")
    extra_source = required("DESIR_EXTRA_SOURCE_CHANNEL", "@g_romanticfilm")
    public = required("DESIR_PUBLIC_CHANNEL", "@CineXDesirfr")
    private = required("DESIR_PRIVATE_CHANNEL")
    mirror_name = required("DESIR_MIRROR_CHANNEL", "@Torrent9SeriesFilms")
    verify_destination(source, public, private)
    verify_destination(extra_source, public, private)
    # Continue honoring the two historic variables, plus a single extensible
    # DESIR_SOURCE_CHANNELS list added later by the owner.
    sources = source_list(source, extra_source, os.getenv("DESIR_SOURCE_CHANNELS", ""))
    if any(name.casefold() == public.casefold() for name in sources):
        raise RuntimeError("Un canal source ne peut pas être le canal public Désir.")
    if mirror_name.casefold() != "@torrent9seriesfilms":
        raise RuntimeError("DESIR_MIRROR_CHANNEL doit être @Torrent9SeriesFilms.")
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
        source_peers = [src]
        for extra_name in sources[1:]:
            # User-added sources from the bulk variable must be public,
            # readable and unprotected; never join a channel automatically.
            try:
                second = await resolve_peer(client, extra_name)
                if (str(getattr(second, "username", "") or "").casefold()
                        != extra_name.lstrip("@").casefold()):
                    raise ValueError("Identifiant de la source complémentaire incohérent.")
                if getattr(second, "noforwards", False):
                    LOG.warning("Source %s protégée : ignorée.", extra_name)
                    continue
                if utils.get_peer_id(second) in {
                    utils.get_peer_id(src), utils.get_peer_id(library),
                    utils.get_peer_id(public_user),
                }:
                    raise RuntimeError("La source complémentaire ne doit pas être une destination.")
                source_peers.append(second)
                LOG.info("CinéX Désir : source complémentaire utilisable : %s", extra_name)
                await asyncio.sleep(max(12.0, float(os.getenv('CINEX_PAUSE_SECONDS', '20'))))
            except (FloodWaitError, PeerFloodError):
                raise
            except Exception as exc:
                LOG.warning("Source complémentaire %s indisponible : %s", extra_name, exc)
        mirror_peer, mirror_key = (None, "")
        bot_public = None
        if publish:
            token = required("DESIR_BOT_TOKEN")
            from .bot_http import BotHTTPClient
            bot = BotHTTPClient(token, client)
            bot_public = await preflight_bot(bot, public, public_user)
            # Validate destination and write rights before ANY private media upload.
            mirror_peer, mirror_key = await preflight_mirror(
                client, public_user, library, src, mirror_name
            )
            if state.mirror_pending(mirror_key) and not os.getenv('CINEX_DEFER_MIRROR'):
                await finish_mirrors(client, state, mirror_peer, mirror_key, public_user)
        # Cap is two films TOTAL across both sources, not two per channel.
        # Sort by real message timestamps instead of incomparable channel IDs.
        candidates = []
        messages_read = 0
        for source_peer in source_peers:
            try:
                messages = [m async for m in client.iter_messages(source_peer, limit=160)]
            except (FloodWaitError, PeerFloodError):
                raise
            except Exception as exc:
                LOG.warning("Lecture source %s impossible : %s",
                            getattr(source_peer, "username", "?"), exc)
                continue
            messages_read += len(messages)
            peer_id = utils.get_peer_id(source_peer)
            for item in pair_items(messages):
                candidates.append((source_peer, peer_id, item))
            await asyncio.sleep(max(12.0, float(os.getenv('CINEX_PAUSE_SECONDS', '20'))))
        if newest:
            from datetime import datetime, timezone
            def movie_time(record):
                date = getattr(record[2].video, "date", None)
                if date is None:
                    return 0.0
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                return date.timestamp()
            candidates.sort(key=movie_time, reverse=True)
        LOG.info("CinéX Désir : sources=%s, messages analysés=%s, vidéos candidates=%s, mode=%s",
                 len(source_peers), messages_read, len(candidates),
                 "PUBLICATION" if publish else "SIMULATION")
        private_id = utils.get_peer_id(library)
        for source_peer, peer_id, item in candidates:
            key = item_key(peer_id, item)
            if key in state.data["completed"]:
                continue
            title = format_title(item)
            LOG.info("Film candidat : canal=@%s source_message=%s affiche=%s type=%s",
                     getattr(source_peer, "username", "?"),
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
                    await asyncio.sleep(max(12.0, float(os.getenv('CINEX_PAUSE_SECONDS', '20'))))
                video = await client.send_file(
                    library, item.video.media,
                    caption=rich_video_title(title), parse_mode="html"
                )
                state.stage(key, "video", video.id)
            private_video_id = int(state.data["staged"][key]["video"])
            await asyncio.sleep(max(12.0, float(os.getenv('CINEX_PAUSE_SECONDS', '20'))))
            video_url = private_message_link(private_id, private_video_id)
            link = (os.getenv("DESIR_PRIVATE_INVITE_LINK") or "").strip()
            public_post = await post_public(bot, client, bot_public, item, title, video_url, link)
            state.complete(key, private_video_id, public_post.id)
            # Only forward the public bot-authored poster/link, NEVER the private video.
            await asyncio.sleep(max(12.0, float(os.getenv('CINEX_PAUSE_SECONDS', '20'))))
            forwarded_id = None
            if not os.getenv('CINEX_DEFER_MIRROR'):
                forwarded_id = await forward_public_poster(
                    client, public_user, mirror_peer, public_post.id
                )
                state.mirror_done(mirror_key, public_post.id, forwarded_id)
            completed += 1
            LOG.info("CinéX Désir : film privé=%s, affiche publique=%s, miroir=%s",
                     private_video_id, public_post.id, forwarded_id)
            await asyncio.sleep(max(20.0, float(os.getenv('CINEX_PAUSE_SECONDS', '20'))))
            if completed >= limit:
                break
        # Count films separately from CinéX classique. Publications are after
        # the second movie and always after its native Torrent9 mirror forward.
        if publish:
            await publish_desir_promotions(client, bot, library, public_user,
                                           None if os.getenv('CINEX_DEFER_MIRROR') else mirror_peer, state)
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
