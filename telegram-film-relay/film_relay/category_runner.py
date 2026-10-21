"""Isolated CinéX Comedy / Anime relay, pre-integration manual testing only.

Each category has its own source, public channel, private library, state and
advert rotation. Public poster+link is forwarded natively to Torrent9, with
Telegram's originating-channel attribution. Never forwards private videos.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
from datetime import datetime, timezone

from .desir_matching import film_title, item_key, pair_items
from .desir_runner import (
    ReceiptState, DesirPromotionsState, finish_mirrors, forward_public_poster,
    post_public, preflight_mirror,
)
from .publication import rich_caption, rich_video_title
from .recovery import snapshot_telegram_posts
from .runner import resolve_peer
from .text import private_message_link
from .source_channels import source_list

LOG = logging.getLogger("cinex_categories")
CATEGORIES = {
    "comedie": {"prefix": "COMEDIE", "label": "CinéX Comédie", "fallback": "😂 Film comédie"},
    "anime": {"prefix": "ANIME", "label": "CinéX Anime", "fallback": "🌸 Film / épisode anime"},
}
_CHANNEL = re.compile(r"^@[a-zA-Z0-9_]{5,32}$")
_PRIVATE = re.compile(r"^-100\d{5,}$")


def category_config(category: str, env: dict | None = None) -> dict:
    """Validate ALL required ids before establishing any Telegram connection."""
    if category not in CATEGORIES:
        raise ValueError("Catégorie CinéX inconnue.")
    env = os.environ if env is None else env
    category_info = CATEGORIES[category]
    prefix = category_info["prefix"]
    default_sources = {
        "comedie": ("@comexflex",),
        "anime": ("@orak_dessinanime",),
    }
    # Backward compatible: existing singular variable + additional bulk list.
    # Explicitly user-authorized baseline sources are always available.
    sources = source_list(
        *(default_sources.get(category, ())),
        env.get(prefix + "_SOURCE_CHANNEL", ""),
        env.get(prefix + "_SOURCE_CHANNELS", ""),
        max_sources=12,
    )
    # These three channels have explicitly declared roles. A stale/incorrect
    # singular GitHub variable must never leak comedy movies into Anime or
    # episodes into Comedy, while other user-added sources remain permitted.
    cross_category = {
        "comedie": {"@orak_dessinanime", "@cineromances", "@filmsromantiques"},
        "anime": {"@comexflex", "@filmcomplets", "@cineromances", "@filmsromantiques"},
    }
    forbidden_sources = cross_category.get(category, set())
    for value in sources:
        if value.casefold() in forbidden_sources:
            LOG.warning(
                "%s : canal %s classé dans l'autre catégorie, ignoré. "
                "Corriger la variable GitHub %s_SOURCE_CHANNEL.",
                category_info["label"], value, prefix,
            )
    sources = [value for value in sources
               if value.casefold() not in forbidden_sources]
    # @filmcomplets feeds the classic film pipeline; keep it out of the
    # comedy pipeline to avoid duplicate films across categories.
    if category == "comedie":
        sources = [value for value in sources
                   if value.casefold() != "@filmcomplets"]
    source = sources[0] if sources else ""
    public = (env.get(prefix + "_PUBLIC_CHANNEL") or "").strip()
    private = (env.get(prefix + "_PRIVATE_CHANNEL") or "").strip()
    mirror = (env.get(prefix + "_MIRROR_CHANNEL") or "@Torrent9SeriesFilms").strip()
    for name, value in (("SOURCE", source), ("PUBLIC", public)):
        if not _CHANNEL.fullmatch(value):
            raise ValueError(f"{prefix}_{name}_CHANNEL : indiquer @identifiant (pas un nom inventé).")
    if not _PRIVATE.fullmatch(private):
        raise ValueError(f"{prefix}_PRIVATE_CHANNEL : identifiant Telegram -100... requis.")
    if mirror.casefold() != "@torrent9seriesfilms":
        raise ValueError("Le transfert natif doit viser @Torrent9SeriesFilms.")
    if any(item.casefold() == public.casefold() for item in sources):
        raise ValueError("Source et canal public doivent être distincts.")
    return {
        **category_info,
        "category": category,
        "source": source,
        "sources": sources,
        "public": public,
        "private": private,
        "mirror": mirror,
        "state_path": env.get(prefix + "_STATE_PATH") or f"state/{category}_state.json",
    }


def check_bot_permission(permission, category_name: str) -> None:
    if not (getattr(permission, "is_creator", False) or
            (getattr(permission, "is_admin", False) and
             getattr(permission, "post_messages", False))):
        raise RuntimeError(
            f"Ajouter le bot existant comme administrateur de {category_name} "
            "avec le droit Publier des messages."
        )


async def preflight(client, bot, cfg: dict):
    """Verify actual Telegram destinations and rights before uploading any file."""
    from telethon import utils
    if not await client.is_user_authorized():
        raise RuntimeError("Session personnelle Telegram expirée.")
    # Verify all declared sources without joining them. A source may be
    # temporarily inaccessible: other authorized sources should still work.
    from telethon.errors import FloodWaitError, PeerFloodError
    private = await resolve_peer(client, cfg["private"])
    public = await resolve_peer(client, cfg["public"])
    public_config = str(cfg["public"]).strip()
    if public_config.startswith("-100") and public_config[1:].isdigit():
        if utils.get_peer_id(public) != int(public_config):
            raise RuntimeError("Le numéro -100 du canal public résolu ne correspond pas à sa configuration.")
    elif (str(getattr(public, "username", "") or "").casefold()
          != public_config.lstrip("@").casefold()):
        raise RuntimeError("Le canal public résolu ne correspond pas à celui configuré.")
    private_id, public_id = utils.get_peer_id(private), utils.get_peer_id(public)
    if private_id != int(cfg["private"]):
        raise RuntimeError("Le numéro TG du canal privé résolu ne correspond pas au -100 configuré.")
    if private_id == public_id:
        raise RuntimeError("Les canaux privé et public ont le même identifiant Telegram.")
    if not getattr(private, "broadcast", False):
        raise RuntimeError("Le canal privé configuré n'est pas un canal de diffusion.")
    if not getattr(public, "broadcast", False):
        raise RuntimeError("Le canal public configuré n'est pas un canal de diffusion.")
    forbidden = {private_id, public_id}
    LOG.info("Audit canaux %s : destinations privées/publiques distinctes, numéros et types validés.",
             cfg.get("category", "series"))
    source_peers = []
    seen_ids = set()
    for name in cfg["sources"]:
        try:
            source = await resolve_peer(client, name)
            if (str(getattr(source, "username", "") or "").casefold()
                    != name.lstrip("@").casefold()):
                raise ValueError("La source résolue ne correspond pas à " + name)
            if not getattr(source, "broadcast", False):
                raise ValueError("La source doit être un canal de diffusion (pas un groupe).")
            if getattr(source, "noforwards", False):
                LOG.warning("Source %s protégée contre la copie : ignorée.", name)
                continue
            key = utils.get_peer_id(source)
            if key in forbidden:
                raise ValueError("Une source ne peut pas être une destination.")
            if key not in seen_ids:
                source_peers.append(source)
                seen_ids.add(key)
            await asyncio.sleep(max(12.0, float(os.getenv('CINEX_PAUSE_SECONDS', '20'))))
        except (FloodWaitError, PeerFloodError):
            raise
        except Exception as exc:
            LOG.warning("Source %s inaccessible : %s", name, exc)
    if not source_peers:
        raise RuntimeError("Aucun des canaux sources configurés n'est accessible et non protégé.")
    LOG.info("Audit sources : %s/%s canaux accessibles et distincts.",
             len(source_peers), len(cfg["sources"]))
    bot_public = None
    mirror = None
    mirror_key = ""
    if bot is not None:
        bot_public = await bot.get_entity(cfg["public"])
        if utils.get_peer_id(bot_public) != utils.get_peer_id(public):
            raise RuntimeError("Le bot et le compte utilisateur ne voient pas le même canal public.")
        bot_me = await bot.get_me()
        try:
            perms = await bot.get_permissions(bot_public, bot_me)
        except Exception as exc:
            from telethon.errors import UserNotParticipantError
            if isinstance(exc, UserNotParticipantError):
                raise RuntimeError(
                    f"Le bot @{getattr(bot_me, 'username', 'inconnu')} doit être "
                    f"administrateur de {cfg['public']} (Publier les messages)."
                ) from exc
            raise
        check_bot_permission(perms, cfg["public"])
        from .mirror_policy import torrent9_paused
        if not torrent9_paused():
            mirror, mirror_key = await preflight_mirror(
                client, public, private, source_peers[0], cfg["mirror"]
            )
    return source_peers, private, public, bot_public, mirror, mirror_key


async def run(*, category: str, publish: bool = False, limit: int = 1,
              require_publication: bool = False) -> int:
    from telethon import TelegramClient, utils
    from telethon.errors import FloodWaitError, PeerFloodError
    from telethon.sessions import StringSession
    if limit not in (1, 2):
        raise ValueError("La limite par lancement est de 1 ou 2 publications.")
    cfg = category_config(category)
    api_id = os.getenv("TG_API_ID", "").strip()
    api_hash = os.getenv("TG_API_HASH", "").strip()
    session = (os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING") or "").strip()
    if not (api_id and api_hash and session):
        raise RuntimeError("Secrets Telegram du compte personnel indisponibles.")
    state = ReceiptState(cfg["state_path"])
    client = TelegramClient(
        StringSession(session), int(api_id), api_hash,
        request_retries=0, connection_retries=2,
        flood_sleep_threshold=0, receive_updates=False,
    )
    bot = None
    completed = 0
    try:
        await client.connect()
        if publish:
            token = (os.getenv("CINEX_CATEGORY_BOT_TOKEN") or "").strip()
            if not token:
                raise RuntimeError("Configurer le bot existant dans CINEX_CATEGORY_BOT_TOKEN.")
            from .bot_http import BotHTTPClient
            bot = BotHTTPClient(token, client)
        source_peers, private, public, bot_public, mirror, mirror_key = await preflight(
            client, bot, cfg
        )
        if publish and mirror is not None and not os.getenv('CINEX_DEFER_MIRROR'):
            # Existing public posts missing from Torrent9 take priority; never
            # send a private video again merely because a forward failed.
            await finish_mirrors(client, state, mirror, mirror_key, public, limit=5)
        # Global cap of two across all sources, ordered by message timestamp.
        records = []
        messages_read = 0
        for peer in source_peers:
            try:
                messages = [m async for m in client.iter_messages(peer, limit=160)]
            except (FloodWaitError, PeerFloodError):
                raise
            except Exception as exc:
                LOG.warning("Lecture de la source @%s impossible : %s",
                            getattr(peer, "username", "?"), exc)
                continue
            messages_read += len(messages)
            peer_id = utils.get_peer_id(peer)
            records.extend((peer_id, item) for item in pair_items(messages))
            await asyncio.sleep(max(12.0, float(os.getenv('CINEX_PAUSE_SECONDS', '20'))))
        def order(record):
            ts = getattr(record[1].video, "date", None)
            if not isinstance(ts, datetime):
                return 0.0
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts.timestamp()
        records.sort(key=order, reverse=True)
        LOG.info("%s : %s sources, %s messages examinés, %s vidéos candidates, mode=%s",
                 cfg["label"], len(source_peers), messages_read, len(records),
                 "PUBLICATION" if publish else "SIMULATION")
        private_id = utils.get_peer_id(private)
        for source_id, item in records:
            key = item_key(source_id, item)
            if key in state.data["completed"]:
                continue
            if getattr(item.video, "noforwards", False) or (
                item.poster is not None and getattr(item.poster, "noforwards", False)
            ):
                continue
            title = film_title(item).strip() or cfg["fallback"]
            if not publish:
                LOG.info("[SIMULATION] %s : vidéo source=%s affiche=%s",
                         cfg["label"], item.video.id, getattr(item.poster, "id", None))
                completed += 1
                if completed >= limit:
                    break
                continue
            staged = state.data["staged"].get(key, {})
            if "video" not in staged:
                cache = await snapshot_telegram_posts(
                    client, private, public, private_id,
                    private_limit=110, public_limit=110,
                )
                doc_id = getattr(getattr(item.video, "document", None), "id", None)
                prior = cache.by_document.get(doc_id, []) if doc_id else []
                if prior:
                    saved_video = int(prior[0])
                    existing_public = cache.public_by_video.get(saved_video)
                    if existing_public:
                        state.complete(key, saved_video, int(existing_public))
                        LOG.info("Publication retrouvée : aucune copie en double.")
                        continue
                    state.stage(key, "video", saved_video)
                    staged = state.data["staged"][key]
            if "video" not in staged:
                if item.poster is not None and "poster" not in staged:
                    photo = await client.send_file(
                        private, item.poster.media,
                        caption=rich_caption(title, private=True), parse_mode="html",
                    )
                    state.stage(key, "poster", photo.id)
                    await asyncio.sleep(max(12.0, float(os.getenv('CINEX_PAUSE_SECONDS', '20'))))
                video = await client.send_file(
                    private, item.video.media, caption=rich_video_title(title),
                    parse_mode="html",
                )
                state.stage(key, "video", video.id)
            private_video_id = int(state.data["staged"][key]["video"])
            await asyncio.sleep(max(12.0, float(os.getenv('CINEX_PAUSE_SECONDS', '20'))))
            video_url = private_message_link(private_id, private_video_id)
            public_post = await post_public(
                bot, client, bot_public, item, title, video_url, ""
            )
            state.complete(key, private_video_id, public_post.id)
            await asyncio.sleep(max(12.0, float(os.getenv('CINEX_PAUSE_SECONDS', '20'))))
            mirrored_id = None
            if mirror is not None and not os.getenv('CINEX_DEFER_MIRROR'):
                mirrored_id = await forward_public_poster(
                    client, public, mirror, public_post.id
                )
                state.mirror_done(mirror_key, public_post.id, mirrored_id)
            LOG.info("%s : film publié privé=%s public=%s Torrent9=%s",
                     cfg["label"], private_video_id, public_post.id, mirrored_id)
            completed += 1
            await asyncio.sleep(max(20.0, float(os.getenv('CINEX_PAUSE_SECONDS', '20'))))
            if completed >= limit:
                break
        if publish:
            from .promotions import publish_promotions
            # Each category keeps its own two-film promotion counter,
            # and adverts are native-forwarded from its own public channel.
            report = await publish_promotions(
                client, bot, private, public,
                None if os.getenv('CINEX_DEFER_MIRROR') else mirror,
                DesirPromotionsState(state),
                private_fallback=True,
                current_run_films=completed,
            )
            LOG.info("%s : pub privé=%s public=%s Torrent9=%s",
                     cfg["label"], report["private"], report["public"], report["mirror"])
        if publish and require_publication and completed == 0:
            LOG.error("%s : aucun nouveau média envoyé au premier test.", cfg["label"])
            return 3
        LOG.info("%s : %s nouveau(x) média(s) validé(s).", cfg["label"], completed)
        return 0
    except (FloodWaitError, PeerFloodError) as exc:
        LOG.error("Telegram impose une limitation %s : arrêt immédiat.", type(exc).__name__)
        return 2
    finally:
        if bot is not None:
            await bot.disconnect()
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Test manuel des nouvelles catégories CinéX")
    parser.add_argument("--category", choices=tuple(CATEGORIES), required=True)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--limit", type=int, choices=(1, 2), default=1)
    parser.add_argument("--require-publication", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    try:
        code = asyncio.run(run(
            category=args.category, publish=args.publish, limit=args.limit,
            require_publication=args.require_publication,
        ))
    except Exception:
        LOG.exception("Échec %s : contrôle les variables, l'accès ou les permissions.", args.category)
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
