"""Telegram relay orchestration. No redistribution unless rights are confirmed."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from .matching import (document_key, filename_of, is_poster, is_video, match_pairs,
                       match_authorized_mkv_pairs, description_of, description_entities_of)
from .verification import screen_pairs
from .publication import (rich_caption, rich_video_title, film_folder_url,
                          send_public_poster_with_buttons)
from .state import State
from .recovery import (snapshot_telegram_posts, recover_from_snapshot,
                       existing_native_forwards)
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
    # Discovery sends suggestions to the account's Saved Messages only.
    # Source activation is exclusively a deliberate edit to channels.json;
    # never import historical auto_sources.json or TG_APPROVED_SOURCES_JSON.
    result["sources"] = sources
    if not all(x.get("channel") for x in sources):
        raise ValueError("Chaque source doit fournir un champ channel.")
    if result.get("private_layout", "poster_and_video") not in ("poster_and_video", "title_only"):
        raise ValueError("private_layout doit être poster_and_video ou title_only.")
    # Destination values can be set as GitHub Actions variables, without
    # committing channel identifiers into a public source repository.
    result["private_channel"] = os.getenv("TG_PRIVATE_CHANNEL") or result.get("private_channel")
    result["public_channel"] = os.getenv("TG_PUBLIC_CHANNEL") or result.get("public_channel")
    result["mirror_channel"] = os.getenv("TG_MIRROR_CHANNEL") or result.get("mirror_channel", "")
    if str(result["mirror_channel"]).strip().lower() == "@torrent9seriesfilm":
        LOG.warning("Ancien identifiant miroir corrigé automatiquement : @Torrent9SeriesFilms")
        result["mirror_channel"] = "@Torrent9SeriesFilms"
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
    if state.history_done(source_id) and not rescan and not cfg.get("archive_cycle", False):
        return [], None, True
    page_size = min(500, max(30, int(cfg.get("history_page_messages", 240))))
    overlap = min(30, max(3, int(cfg.get("history_overlap_messages", 12))))
    cursor = None if (rescan or (cfg.get("archive_cycle", False) and state.history_done(source_id))) else state.history_cursor(source_id)
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


async def forward_public_message(client, primary_public, mirror_channel, message_id: int) -> int:
    """Telegram native forward. Preserve 'Forwarded from <source channel>' header."""
    result = await client.forward_messages(
        mirror_channel, int(message_id), from_peer=primary_public
    )
    if isinstance(result, list):
        result = result[0] if result else None
    forward_id = getattr(result, "id", None)
    if forward_id is None:
        raise RuntimeError("Telegram n'a pas renvoyé de reçu pour le transfert du message.")
    return int(forward_id)


async def execute() -> int:
    from telethon import TelegramClient, utils
    from telethon.errors import FloodWaitError, PeerFloodError
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
    bot_token = os.getenv("CINEX_BOT_TOKEN", "").strip()
    if publish and not bot_token:
        raise RuntimeError(
            "Boutons Telegram obligatoires : ajouter le secret GitHub CINEX_BOT_TOKEN "
            "créé avec @BotFather et rendre ce bot administrateur du canal public. "
            "Aucun nouveau film n'a été envoyé."
        )

    state = State(os.getenv("STATE_PATH", "state/state.json"))
    recovery_cache = None
    seen_count = published_count = proposed_count = failed_count = 0
    # Hard safety cap: at most TWO completed films across all sources in one run.
    max_posts = min(2, max(1, int(os.getenv("FILM_MAX_POSTS_PER_RUN", cfg.get("max_posts_per_run", 2)))))
    pause_seconds = max(6.0, 2 * float(cfg.get("publication_pause_seconds", 5)))
    client = TelegramClient(StringSession(credentials[2]), int(credentials[0]), credentials[1],
                            request_retries=1, connection_retries=2, flood_sleep_threshold=0)
    bot_client = None
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
        if utils.get_peer_id(destination_public) == private_id:
            raise RuntimeError(
                "Le canal public et le canal privé correspondent au même canal. "
                "Renseigner deux destinations distinctes avant de publier."
            )
        if publish:
            # User session copies source media to private; bot sends public
            # poster + native URL buttons. Bot must be an admin of this channel.
            bot_client = TelegramClient(
                StringSession(), int(credentials[0]), credentials[1],
                request_retries=1, connection_retries=2, flood_sleep_threshold=0
            )
            await bot_client.start(bot_token=bot_token)
            identity = await bot_client.get_me()
            LOG.info(
                "Bot football sélectionné pour CinéX : @%s (ajouter comme administrateur du canal public).",
                getattr(identity, "username", None) or "(nom indisponible)"
            )
            bot_destination = await bot_client.get_entity(cfg["public_channel"])
            if utils.get_peer_id(bot_destination) != utils.get_peer_id(destination_public):
                raise RuntimeError(
                    "Le bot et le compte utilisateur ne résolvent pas le même canal public. "
                    "Vérifier TG_PUBLIC_CHANNEL et les droits admin du bot."
                )
            # Verify real Telegram posting permissions BEFORE copying any MKV
            # to private. Prevent orphaned private videos when a bot can read
            # a public channel but lacks the right to publish there.
            try:
                perms = (await bot_client.get_permissions(bot_destination, identity) if hasattr(bot_client, 'get_permissions') else None)
            except Exception as exc:
                raise RuntimeError(
                    "Impossible de contrôler les droits du bot @" +
                    str(getattr(identity, "username", "") or "inconnu") +
                    ". Ajouter le bot comme administrateur du canal public "
                    "avec l'autorisation Publier des messages."
                ) from exc
            can_publish = perms is None or bool(
                getattr(perms, "is_creator", False) or
                (getattr(perms, "is_admin", False) and
                 getattr(perms, "post_messages", False))
            )
            if not can_publish:
                raise RuntimeError(
                    "Bot @" + str(getattr(identity, "username", "") or "inconnu") +
                    " sans droit de publication dans le canal public. "
                    "Telegram > Canal public > Administrateurs > Ajouter ce bot, "
                    "activer Publier des messages. Aucun nouveau MKV n'a été envoyé."
                )
            LOG.info("Bot CinéX contrôlé : administrateur autorisé à publier dans le canal public.")
        mirror_destination = None
        mirror_key = ""
        if publish and cfg.get("mirror_channel"):
            try:
                proposed_mirror = await resolve_peer(client, cfg["mirror_channel"])
                proposed_key = str(utils.get_peer_id(proposed_mirror))
                if proposed_key in (str(private_id), str(utils.get_peer_id(destination_public))):
                    raise ValueError("Second canal identique au privé ou au premier canal public.")
                if not getattr(proposed_mirror, "broadcast", True):
                    raise ValueError("La destination secondaire doit être un canal.")
                if getattr(destination_public, "noforwards", False):
                    raise ValueError("Le premier canal public interdit les transferts natifs.")
                mirror_destination, mirror_key = proposed_mirror, proposed_key
                LOG.info("Transfert natif activé vers le second canal %s.",
                         getattr(mirror_destination, "username", "") or mirror_key)
            except Exception as exc:
                # The primary release remains available while an invalid or
                # inaccessible secondary username is being repaired.
                failed_count += 1
                LOG.error(
                    "SECOND CANAL INACCESSIBLE (%s) : %s. "
                    "Vérifier l'identifiant Telegram public exact ou utiliser l'ID -100 "
                    "via TG_MIRROR_CHANNEL. Aucun transfert secondaire ; "
                    "le privé et le canal public principal continuent.",
                    cfg["mirror_channel"], type(exc).__name__
                )
        if not getattr(destination_public, "username", None):
            raise RuntimeError(
                "Super Mario Film (destination publique) ne possède pas de @username public. "
                "Vérifier la confidentialité du canal ou corriger TG_PUBLIC_CHANNEL."
            )
        # Public posts now direct viewers to the shared films folder.
        # Stop exporting private invitation links on each two-hour run.
        invitation = film_folder_url()

        # Complete mirrored copies left pending after a previous partial run.
        # Do not re-upload a MKV or re-post the original public message.
        mirror_count = 0
        mirror_forwards = {}
        if publish and mirror_destination is not None:
            mirror_forwards = await existing_native_forwards(
                client, mirror_destination, utils.get_peer_id(destination_public)
            )
            for old_pair, old_public_id in state.pending_mirrors(mirror_key, limit=10):
                try:
                    already_forwarded = mirror_forwards.get(old_public_id)
                    if already_forwarded is not None:
                        state.mark_mirrored(old_pair, mirror_key, already_forwarded)
                        LOG.info("Transfert déjà présent, anti-doublon : public=%s -> miroir=%s",
                                 old_public_id, already_forwarded)
                        continue
                    copied_id = await forward_public_message(
                        client, destination_public, mirror_destination, old_public_id
                    )
                    state.mark_mirrored(old_pair, mirror_key, copied_id)
                    mirror_forwards[old_public_id] = copied_id
                    mirror_count += 1
                    LOG.info("Transfert repris : public=%s, miroir=%s",
                             old_public_id, copied_id)
                    await asyncio.sleep(2)
                except (FloodWaitError, PeerFloodError):
                    LOG.error("Restriction Telegram lors du transfert en attente : arrêt immédiat.")
                    raise
                except Exception as exc:
                    failed_count += 1
                    LOG.exception("Transfert en attente impossible pour %s : %s",
                                  old_pair, exc)
                    break

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
                archive_cfg = {**cfg, "archive_cycle": bool(src.get("archive_cycle", False))}
                archive_messages, history_next, history_finished = await load_archive_messages(
                    client, entity, state, channel_key, archive_cfg
                )
                if not fresh_messages and not archive_messages:
                    continue
                seen_count += len(fresh_messages) + len(archive_messages)
                # Pair *inside* each contiguous window; never pair unrelated
                # messages across two distant archive pages.
                # For an authorized source, use its own criteria: Telegram MKV
                # uploads often have no duration but do have a filename and size.
                pairing = {
                    "min_minutes": int(src.get("min_video_minutes", 40)),
                    "min_megabytes": int(src.get("min_video_megabytes", 150)),
                    "max_gap": int(src.get("max_pair_message_gap", 2)),
                    "max_age_minutes": int(src.get("max_pair_age_minutes", 60)),
                    "min_caption_chars": int(src.get("min_caption_chars", 25)),
                }
                mkv_mode = rights_ok and src.get("matching_mode") == "authorized_mkv"
                if mkv_mode:
                    fresh_pairs = match_authorized_mkv_pairs(fresh_messages)
                    archive_pairs = match_authorized_mkv_pairs(archive_messages)
                else:
                    fresh_pairs = screen_pairs(fresh_messages, **pairing).pairs
                    archive_pairs = screen_pairs(archive_messages, **pairing).pairs
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
                    screened = screen_pairs(window, **pairing)
                    candid = (match_authorized_mkv_pairs(window) if mkv_mode else
                              match_pairs(window, max_gap=pairing["max_gap"],
                                          max_age_minutes=pairing["max_age_minutes"]))
                    photo_count = sum(bool(getattr(m, "photo", None)) for m in window)
                    video_count = sum(is_video(m) for m in window)
                    mkv_count = sum(filename_of(m).endswith(".mkv") for m in window)
                    LOG.info(
                        "DIAGNOSTIC FORMAT %s/%s : messages=%d, photos=%d, videos=%d, "
                        "mkv=%d, candidats_format=%d, paires_strictes=%d, mode_mkv=%s, rejets=%s",
                        channel_name, window_name, len(window), photo_count,
                        video_count, mkv_count, len(candid), len(screened.pairs), mkv_mode,
                        ",".join(screened.reasons[:15]) or "aucun"
                    )
                if not pairs:
                    LOG.warning(
                        "Aucune paire affiche/vidéo conforme dans les messages consultés "
                        "de %s. Pas de publication. Vérifier la structure du canal, "
                        "les critères de taille, de délai, de description et l'ordre.",
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
                    if publish:
                        # GitHub push conflicts can lose checkpoint JSON even after
                        # Telegram accepted media. Reconcile from live Telegram
                        # before any new private or public send.
                        if recovery_cache is None:
                            recovery_cache = await snapshot_telegram_posts(
                                client, destination_private, destination_public, private_id
                            )
                            LOG.info(
                                "Anti-doublons Telegram : %s vidéos distinctes, %s publications publiques indexées",
                                len(recovery_cache.by_document),
                                len(recovery_cache.public_by_video),
                            )
                        recovered = recover_from_snapshot(
                            recovery_cache, state, pair_id, media_id, pair.movie, logger=LOG
                        )
                        if recovered == "complete":
                            continue
                    text = clean_caption(description_of(pair), description_entities_of(pair))
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
                                    caption=rich_caption(text, private=True), parse_mode="html"
                                )
                                state.stage_poster(pair_id, int(private_poster.id))
                                await asyncio.sleep(4)
                                stage = state.get_staged_posts(pair_id)
                                LOG.info("Affiche privée envoyée : message %s", private_poster.id)

                            private_post = await client.send_file(
                                destination_private, pair.movie.media,
                                caption=rich_video_title(text), parse_mode="html"
                            )
                            private_post_id = int(private_post.id)
                            state.stage(pair_id, private_post_id)
                            LOG.info("Vidéo privée envoyée : message %s", private_post_id)
                        url = private_message_link(private_id, private_post_id)
                        await asyncio.sleep(4)
                        public_post = await send_public_poster_with_buttons(
                            client, bot_client, bot_destination, pair.poster,
                            text, url, invitation
                        )
                        state.add(pair_id, media_id, private_post_id, int(public_post.id))
                        if mirror_destination is not None:
                            try:
                                copied_id = await forward_public_message(
                                    client, destination_public, mirror_destination,
                                    int(public_post.id)
                                )
                                state.mark_mirrored(pair_id, mirror_key, copied_id)
                                mirror_forwards[int(public_post.id)] = copied_id
                                mirror_count += 1
                                LOG.info("Public transféré avec attribution : %s -> %s",
                                         public_post.id, copied_id)
                            except (FloodWaitError, PeerFloodError):
                                LOG.error("Restriction Telegram lors du transfert miroir : arrêt immédiat.")
                                raise
                            except Exception as mirror_exc:
                                # Primary publication is already checkpointed.
                                # The next run retries this forward from processed state.
                                failed_count += 1
                                LOG.exception("Second canal en attente pour %s : %s",
                                              pair_id, mirror_exc)
                        # Checkpoint to the latest *completed* movie. If the run
                        # hits its posting cap, newer items remain available.
                        state.advance(channel_key, pair.movie.id)
                        published_count += 1
                        LOG.info("Publié : %s -> %s", pair_id, url)
                        await asyncio.sleep(pause_seconds)
                    except (FloodWaitError, PeerFloodError):
                        LOG.error("Restriction Telegram pendant publication : arrêt immédiat.")
                        raise
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
            except (FloodWaitError, PeerFloodError):
                LOG.error("Limitation Telegram : arrêt immédiat du passage ; ne pas insister.")
                raise
            except Exception as exc:
                failed_count += 1
                LOG.exception("Source inaccessible %s : %s", channel_name, exc)
        # Les promotions font partie du MÊME passage que les films.
        # Une seule rotation par destination et par exécution, même si le
        # dernier film avait été publié lors d'un passage précédent.
        promo_count = 0
        if publish and flag("CINEX_PROMOS_ENABLED", True):
            try:
                from .promotions import publish_promotions
                promo_report = await publish_promotions(
                    client, bot_client, destination_private,
                    destination_public, mirror_destination, state
                )
                promo_count = sum(promo_report[k] for k in ("private", "public", "mirror"))
                LOG.info(
                    "PUBS CINÉX dans le workflow films : privé=%s, public=%s, miroir=%s, ignorées=%s",
                    promo_report["private"], promo_report["public"],
                    promo_report["mirror"], promo_report["skipped"]
                )
            except (FloodWaitError, PeerFloodError):
                LOG.error("Restriction Telegram lors des publicités : arrêt immédiat.")
                raise
            except Exception as promo_exc:
                failed_count += 1
                LOG.exception("Échec des pubs intégrées au relais films : %s", promo_exc)

        LOG.info("Résumé : lus=%s, proposés=%s, publiés=%s, transferts=%s, erreurs=%s",
                 seen_count, proposed_count, published_count, mirror_count, failed_count)
        if publish and published_count == 0:
            LOG.warning(
                "FIN SANS PUBLICATION : aucun film n'a été envoyé. "
                "Voir les diagnostics de format, la destination et la présence "
                "de paires strictement validées dans les lignes précédentes."
            )
        summary_path = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as summary:
                summary.write(
                    "\\n### Film Relay — résultat\\n"
                    f"- Messages analysés : {seen_count}\\n"
                    f"- Films compatibles proposés : {proposed_count}\\n"
                    f"- Films réellement publiés : {published_count}\\n"
                    f"- Publications transférées vers le canal secondaire : {mirror_count}\\n"
                    f"- Erreurs : {failed_count}\\n"
                )
        if publish and published_count == 0 and mirror_count == 0 and promo_count == 0 and flag("FILM_REQUIRE_PUBLICATION"):
            LOG.error("TEST NON VALIDE : aucune publication réelle. Exécution marquée en échec.")
            return 2
        return 1 if failed_count else 0
    finally:
        if bot_client is not None:
            await bot_client.disconnect()
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
