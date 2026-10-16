"""Telegram relay orchestration. No redistribution unless rights are confirmed."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from .matching import document_key, is_poster, is_video, match_pairs
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


async def find_broadcast_by_exact_title(client, title: str):
    """Resolve a uniquely named channel already available to this Telegram account.

    Never joins channels and never guesses when titles are ambiguous.
    """
    wanted = " ".join(str(title).split()).casefold()
    matches = []
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        current = " ".join(str(getattr(entity, "title", "") or "").split()).casefold()
        if getattr(entity, "broadcast", False) and current == wanted:
            matches.append(entity)
            if len(matches) > 1:
                break
    return matches


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


async def load_archive_messages(client, entity, state: State, source_id: str, cfg: dict):
    """Read older pages independently of the latest-message cursor.

    A small overlap retains pairs split between two fetch windows. Never
    advance the archive cursor until all eligible posts in the page complete.
    """
    rescan = flag("FILM_RESCAN_HISTORY", False)
    if state.history_done(source_id) and not rescan:
        return [], None, True
    page_size = min(500, max(30, int(cfg.get("history_page_messages", 240))))
    overlap = min(30, max(3, int(cfg.get("history_overlap_messages", 12))))
    cursor = None if rescan else state.history_cursor(source_id)
    kwargs = {"limit": page_size}
    if cursor is not None:
        kwargs["max_id"] = cursor
    # Telegram yields newest first in this mode.
    page = [m async for m in client.iter_messages(entity, **kwargs)]
    if not page:
        return [], cursor, True
    page.sort(key=lambda m: m.id, reverse=True)
    done = len(page) < page_size
    next_cursor = None if done else int(page[-min(overlap, len(page))].id) + 1
    if not done and cursor is not None and next_cursor >= cursor:
        raise RuntimeError("Pagination historique immobile : éviter une boucle de lecture.")
    return sorted(page, key=lambda m: m.id), next_cursor, done


async def execute() -> int:
    from telethon import TelegramClient, utils
    from telethon.sessions import StringSession

    cfg = config_from(os.getenv("CHANNELS_CONFIG", "config/channels.json"))
    publish = flag("FILM_PUBLISH_ENABLED", False)
    credentials = (os.getenv("TG_API_ID"), os.getenv("TG_API_HASH"), (os.getenv("TG_SESSION_STRING") or os.getenv("TG_STRING_SESSION") or os.getenv("TG_STREAM_SESSION")))
    if not all(credentials):
        raise RuntimeError("Secrets requis : TG_API_ID, TG_API_HASH, TG_SESSION_STRING (ou TG_STRING_SESSION).")
    if publish and not any(x.get("redistribution_authorized") is True for x in cfg["sources"]):
        LOG.warning("Aucune source autorisée. Aucune publication ne sera envoyée.")
        return 0
    if publish and not flag("TG_RIGHTS_ATTESTED"):
        raise RuntimeError("Publication bloquée : TG_RIGHTS_ATTESTED doit être true.")

    state = State(os.getenv("STATE_PATH", "state/state.json"))
    seen_count = published_count = proposed_count = failed_count = 0
    max_posts = min(10, max(1, int(os.getenv("FILM_MAX_POSTS_PER_RUN", cfg.get("max_posts_per_run", 5)))))
    pause_seconds = max(3.0, float(cfg.get("publication_pause_seconds", 5)))
    client = TelegramClient(StringSession(credentials[2]), int(credentials[0]), credentials[1],
                            request_retries=1, connection_retries=2, flood_sleep_threshold=0)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram expirée ou révoquée. Régénérer TG_STRING_SESSION.")
        destination_private = await resolve_peer(client, cfg["private_channel"])
        destination_public = await resolve_peer(client, cfg["public_channel"])
        # Never silently send to an old channel when the intended destination changed.
        expected_title = (os.getenv("TG_EXPECTED_PUBLIC_TITLE") or
                          cfg.get("expected_public_title") or "").strip()
        actual_title = str(getattr(destination_public, "title", "") or "").strip()
        LOG.info("Destination publique résolue : %s", actual_title or "(sans titre)")
        if expected_title and expected_title.casefold() not in actual_title.casefold():
            matches = await find_broadcast_by_exact_title(client, expected_title)
            if len(matches) == 1:
                destination_public = matches[0]
                actual_title = str(getattr(destination_public, "title", ""))
                LOG.warning(
                    "Destination GitHub différente : utilisation du canal %s trouvé "
                    "dans les canaux de ce compte, sans rejoindre ni deviner un identifiant.",
                    actual_title
                )
            else:
                raise RuntimeError(
                    "Mauvaise destination : configurée='%s', attendue='%s'. "
                    "Canaux portant ce titre trouvés dans le compte : %d. "
                    "Renseigner TG_PUBLIC_CHANNEL avec le @username ou l'ID -100 "
                    "de Super Mario Film."
                    % (actual_title or "(inconnue)", expected_title, len(matches))
                )
        private_id = utils.get_peer_id(destination_private)
        if not str(private_id).startswith("-100"):
            raise ValueError("La destination privée doit être un canal (identifiant -100...).")
        invitation = (cfg.get("private_invite_link") or "").strip()
        if not invitation and publish:
            # A t.me/c/ link works only for private-channel members. Offer an
            # invitation to newcomers when the Telegram account is an admin.
            try:
                from telethon.tl.functions.messages import ExportChatInviteRequest
                exported = await client(ExportChatInviteRequest(peer=destination_private))
                invitation = str(getattr(exported, "link", "") or "")
                if invitation:
                    LOG.info("Lien d'accès privé obtenu automatiquement (valeur non journalisée).")
            except Exception as exc:
                LOG.warning("Invitation privée introuvable (%s) : renseigner TG_PRIVATE_INVITE_LINK.",
                            type(exc).__name__)

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
                fresh_messages = await load_messages(client, entity, old_seen, cfg)
                archive_messages, history_next, history_finished = await load_archive_messages(
                    client, entity, state, channel_key, cfg
                )
                if not fresh_messages and not archive_messages:
                    continue
                seen_count += len(fresh_messages) + len(archive_messages)
                # Pair *inside* each contiguous window; never pair unrelated
                # messages across two distant archive pages.
                fresh_pairs = screen_pairs(fresh_messages).pairs
                archive_pairs = screen_pairs(archive_messages).pairs
                seen_pair_ids = set()
                pairs = []
                for item in [*fresh_pairs, *archive_pairs]:
                    ident = (item.poster.id, item.movie.id)
                    if ident not in seen_pair_ids:
                        pairs.append(item)
                        seen_pair_ids.add(ident)
                LOG.info(
                    "Source %s : nouveaux=%s archive=%s paires=%s (cursor=%s, fin=%s)",
                    channel_name, len(fresh_messages), len(archive_messages),
                    len(pairs), state.history_cursor(channel_key), history_finished
                )
                for window_name, window in (("recent", fresh_messages), ("archives", archive_messages)):
                    if not window:
                        continue
                    screened = screen_pairs(window)
                    candid = match_pairs(window, max_gap=4, max_age_minutes=180)
                    photo_count = sum(bool(getattr(m, "photo", None)) for m in window)
                    video_count = sum(is_video(m) for m in window)
                    LOG.info(
                        "DIAGNOSTIC FORMAT %s/%s : messages=%d, photos=%d, videos=%d, "
                        "candidats_souples=%d, paires_strictes=%d, rejets=%s",
                        channel_name, window_name, len(window), photo_count,
                        video_count, len(candid), len(screened.pairs),
                        ",".join(screened.reasons[:15]) or "aucun"
                    )
                if not pairs:
                    LOG.warning(
                        "Aucune paire affiche/vidéo conforme dans les messages consultés "
                        "de %s. Pas de publication. Vérifier la structure du canal, "
                        "la durée (>40 min), la taille (>150 Mo), le délai et l'ordre.",
                        channel_name
                    )
                    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
                    if summary_file:
                        with open(summary_file, "a", encoding="utf-8") as summary:
                            summary.write(
                                "### Film Relay : aucune paire éligible dans " +
                                channel_name + "\\n"
                                "Le canal a été lu, mais aucun couple affiche/vidéo "
                                "ne respecte les filtres. Voir l'étape Run Telegram film relay.\\n"
                            )
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
                    if fresh_messages:
                        state.advance(channel_key, fresh_messages[-1].id)
                    state.advance_history(channel_key, history_next, history_finished)
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
