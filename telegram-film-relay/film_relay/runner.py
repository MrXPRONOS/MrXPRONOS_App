"""Telegram relay orchestration. No redistribution unless rights are confirmed."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from .matching import document_key
from .verification import screen_pairs
from .state import State
from .text import (caption_with_link, clean_caption, first_title, private_message_link,
                   private_poster_caption, private_video_caption)

LOG = logging.getLogger("telegram_film_relay")


def flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("true", "yes", "1", "on")


def config_from(path: str) -> dict:
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    sources = result.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("sources doit être une liste.")
    # Auto-discovered sources are *registered* but never treated as authorized.
    # Dedupe by channel name and prefer explicitly configured source entries.
    source_path = Path(os.getenv("AUTO_SOURCES_PATH", "state/auto_sources.json"))
    approved_raw = os.getenv("TG_APPROVED_SOURCES_JSON", "").strip()
    approved = {}
    if approved_raw:
        approved_entries = json.loads(approved_raw)
        if not isinstance(approved_entries, list):
            raise ValueError("TG_APPROVED_SOURCES_JSON doit être un tableau JSON.")
        approved = {
            str(x.get("channel", "")).strip().lower(): str(x.get("rights_basis", "")).strip()
            for x in approved_entries if isinstance(x, dict) and x.get("rights_basis")
        }
    if source_path.exists():
        discovered = json.loads(source_path.read_text(encoding="utf-8")).get("sources", [])
        known = {str(s.get("channel", "")).lower() for s in sources}
        for candidate in discovered:
            name = str(candidate.get("channel", "")).lower()
            if name and name not in known:
                rights_basis = approved.get(name, "")
                sources.append({"channel": candidate["channel"],
                                "redistribution_authorized": bool(rights_basis),
                                "rights_basis": rights_basis,
                                "discovered_automatically": True})
                known.add(name)
    result["sources"] = sources
    if not all(x.get("channel") for x in sources):
        raise ValueError("Chaque source doit fournir un champ channel.")
    if result.get("private_layout", "poster_and_video") not in ("poster_and_video", "title_only"):
        raise ValueError("private_layout doit être poster_and_video ou title_only.")
    # Destination values can be set as GitHub Actions variables, without
    # committing channel identifiers into a public source repository.
    result["private_channel"] = os.getenv("TG_PRIVATE_CHANNEL") or result.get("private_channel")
    result["public_channel"] = os.getenv("TG_PUBLIC_CHANNEL") or result.get("public_channel")
    result["private_invite_link"] = os.getenv("TG_PRIVATE_INVITE_LINK") or result.get("private_invite_link", "")
    if result.get("private_channel") in (None, "", "-1001234567890"):
        raise ValueError("Renseigner private_channel dans config/channels.json.")
    if not result.get("public_channel") or result["public_channel"] == "@mon_canal_public":
        raise ValueError("Renseigner public_channel dans config/channels.json.")
    return result


async def resolve_peer(client, value: str):
    """Resolve channel @username or numeric -100 ID, including an uncached ID."""
    from telethon import utils

    if isinstance(value, int) or str(value).lstrip("-").isdigit():
        numeric_id = int(value)
        try:
            return await client.get_entity(numeric_id)
        except (ValueError, TypeError):
            async for dialog in client.iter_dialogs():
                if utils.get_peer_id(dialog.entity) == numeric_id:
                    return dialog.entity
            raise RuntimeError(f"Canal {numeric_id} introuvable pour ce compte (adhésion requise).")
    return await client.get_entity(value)


async def load_messages(client, entity, old_seen: int, cfg: dict):
    maximum = max(10, int(cfg.get("max_messages_per_run", 300)))
    if old_seen == 0:
        count = min(maximum, max(10, int(cfg.get("bootstrap_messages", 150))))
        msgs = [m async for m in client.iter_messages(entity, limit=count)]
    else:
        # Iterating in chronological order ensures backlogs can be drained.
        floor = max(0, old_seen - max(10, int(cfg.get("lookback_ids", 35))))
        msgs = [m async for m in client.iter_messages(entity, min_id=floor, limit=maximum, reverse=True)]
    return sorted(msgs, key=lambda m: m.id)


async def execute() -> int:
    from telethon import TelegramClient, utils
    from telethon.sessions import StringSession

    cfg = config_from(os.getenv("CHANNELS_CONFIG", "config/channels.json"))
    publish = flag("FILM_PUBLISH_ENABLED", False)
    credentials = (os.getenv("TG_API_ID"), os.getenv("TG_API_HASH"), os.getenv("TG_STRING_SESSION"))
    if not all(credentials):
        raise RuntimeError("Secrets requis : TG_API_ID, TG_API_HASH, TG_STRING_SESSION.")
    if publish and not any(x.get("redistribution_authorized") is True for x in cfg["sources"]):
        LOG.warning("Aucune source autorisée. Aucune publication ne sera envoyée.")
        return 0
    if publish and not flag("TG_RIGHTS_ATTESTED"):
        raise RuntimeError("Publication bloquée : TG_RIGHTS_ATTESTED doit être true.")

    state = State(os.getenv("STATE_PATH", "state/state.json"))
    seen_count = published_count = proposed_count = failed_count = 0
    max_posts = min(10, max(1, int(cfg.get("max_posts_per_run", 5))))
    pause_seconds = max(3.0, float(cfg.get("publication_pause_seconds", 5)))
    client = TelegramClient(StringSession(credentials[2]), int(credentials[0]), credentials[1],
                            request_retries=1, connection_retries=2, flood_sleep_threshold=0)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram expirée ou révoquée. Régénérer TG_STRING_SESSION.")
        destination_private = await resolve_peer(client, cfg["private_channel"])
        destination_public = await resolve_peer(client, cfg["public_channel"])
        private_id = utils.get_peer_id(destination_private)
        if not str(private_id).startswith("-100"):
            raise ValueError("La destination privée doit être un canal (identifiant -100...).")
        invitation = (cfg.get("private_invite_link") or "").strip()

        for src in cfg["sources"]:
            channel_name = str(src["channel"])
            # The example source is a placeholder, never a real input.
            if channel_name == "@source_authorisee":
                continue
            rights_ok = src.get("redistribution_authorized") is True
            if publish and not rights_ok:
                LOG.warning("Source %s ignorée pour publication : droits non confirmés", channel_name)
                continue
            if not publish and not rights_ok:
                LOG.info("[SIMULATION] Source %s : analyse de format uniquement (droits non confirmés).", channel_name)
            try:
                entity = await resolve_peer(client, channel_name)
                if getattr(entity, "broadcast", True) is False:
                    LOG.warning("Source %s ignorée : ce n'est pas un canal de diffusion", channel_name)
                    continue
                if getattr(entity, "noforwards", False):
                    LOG.warning("Source %s protégée contre les transferts : ignorée", channel_name)
                    continue
                channel_key = str(utils.get_peer_id(entity))
                old_seen = state.seen(channel_key)
                messages = await load_messages(client, entity, old_seen, cfg)
                if not messages:
                    continue
                seen_count += len(messages)
                pairs = screen_pairs(messages).pairs
                LOG.info("Source %s : %s messages, %s paires strictement validées", channel_name, len(messages), len(pairs))
                source_failed = False
                run_limit_reached = False
                for pair in pairs:
                    if publish and published_count >= max_posts:
                        run_limit_reached = True
                        LOG.info("Limite de publications de ce passage atteinte (%s).", max_posts)
                        break
                    if getattr(pair.poster, "noforwards", False) or getattr(pair.movie, "noforwards", False):
                        LOG.warning("Messages protégés : association %s/%s ignorée", pair.poster.id, pair.movie.id)
                        continue
                    pair_id = f"{channel_key}:{pair.poster.id}:{pair.movie.id}"
                    media_id = document_key(pair.movie)
                    if state.recorded(pair_id, media_id):
                        continue
                    text = clean_caption(pair.poster.raw_text or "", pair.poster.entities)
                    if len(text) < 12:
                        LOG.info("Affiche %s ignorée (description trop courte après nettoyage)", pair.poster.id)
                        continue
                    proposed_count += 1
                    if not publish:
                        LOG.info("[SIMULATION] %s : %s | vidéo=%s", channel_name, first_title(text), pair.movie.id)
                        continue
                    try:
                        # Keep partial private sends in state. GitHub saves this
                        # checkpoint at the end of a workflow run, including failures.
                        stage = state.get_staged_posts(pair_id)
                        if "video" in stage:
                            private_post_id = stage["video"]
                        else:
                            if cfg.get("private_layout", "poster_and_video") == "poster_and_video" and "poster" not in stage:
                                private_poster = await client.send_file(
                                    destination_private, pair.poster.media,
                                    caption=private_poster_caption(text), parse_mode=None
                                )
                                state.stage_poster(pair_id, int(private_poster.id))
                                await asyncio.sleep(2)
                                stage = state.get_staged_posts(pair_id)
                                LOG.info("Affiche privée envoyée : message %s", private_poster.id)

                            private_post = await client.send_file(
                                destination_private, pair.movie.media,
                                caption=private_video_caption(text), parse_mode=None
                            )
                            private_post_id = int(private_post.id)
                            state.stage(pair_id, private_post_id)
                            LOG.info("Vidéo privée envoyée : message %s", private_post_id)
                        url = private_message_link(private_id, private_post_id)
                        caption = caption_with_link(text, url, invitation)
                        await asyncio.sleep(2)
                        public_post = await client.send_file(
                            destination_public, pair.poster.media,
                            caption=caption, parse_mode=None
                        )
                        state.add(pair_id, media_id, private_post_id, int(public_post.id))
                        # Checkpoint to the latest *completed* movie. If the run
                        # hits its posting cap, newer items remain available.
                        state.advance(channel_key, pair.movie.id)
                        published_count += 1
                        LOG.info("Publié : %s -> %s", pair_id, url)
                        await asyncio.sleep(pause_seconds)
                    except Exception as exc:
                        source_failed = True
                        failed_count += 1
                        LOG.exception("Erreur de publication de %s : %s", pair_id, exc)
                        # Avoid advancing cursor when a pair was not published.
                        break
                if publish and not source_failed and not run_limit_reached:
                    state.advance(channel_key, messages[-1].id)
                if run_limit_reached:
                    break
            except Exception as exc:
                failed_count += 1
                LOG.exception("Source inaccessible %s : %s", channel_name, exc)
        LOG.info("Résumé : lus=%s, proposés=%s, publiés=%s, erreurs=%s",
                 seen_count, proposed_count, published_count, failed_count)
        return 1 if failed_count else 0
    finally:
        await client.disconnect()


def main():
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                        format="%(asctime)s | %(levelname)s | %(message)s")
    try:
        exit_code = asyncio.run(execute())
    except Exception:
        LOG.exception("Échec du programme")
        exit_code = 1
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
