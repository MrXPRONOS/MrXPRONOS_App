"""Read-only CineX channel and Telegram-number verification for GitHub Actions.

Reads Telegram metadata and permissions; NEVER publishes or forwards messages.
The JSON report deliberately excludes private IDs, secrets and invitation links.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

from film_relay.bot_http import BotHTTPClient
from film_relay.category_runner import category_config, preflight
from film_relay.runner import config_from
from film_relay.series_catalog import series_config
from film_relay.source_channels import source_list
from film_relay.media_guard import valid_photo_message
from film_relay.title_guard import title_assessment
from film_relay.desir_matching import pair_items, is_supported_video
from film_relay.matching import match_authorized_mkv_pairs, is_video, is_mkv_document
from film_relay.verification import screen_pairs
from telethon import errors

LOG = logging.getLogger("cinex_channel_audit")


def requested_channels():
    """Always return five categories; config errors stay local and anonymous."""
    entries = []
    def add(name, build):
        try:
            cfg, token = build()
            entries.append((name, cfg, token))
        except Exception:
            # Never include raw configuration values in the artifact.
            entries.append((name, None, ""))

    def films():
        classic = config_from(os.getenv("CHANNELS_CONFIG", "config/channels.json"))
        active = [row for row in classic["sources"]
                  if row.get("redistribution_authorized") is True]
        return ({
            "category": "films",
            "sources": [row["channel"] for row in active],
            "private": classic["private_channel"],
            "public": classic["public_channel"],
            "source_modes": [row.get("matching_mode", "standard") for row in active],
            "source_pairings": [
                {"min_minutes": int(row.get("min_video_minutes", 40)),
                 "min_megabytes": int(row.get("min_video_megabytes", 150)),
                 "max_gap": int(row.get("max_pair_message_gap", 2)),
                 "max_age_minutes": int(row.get("max_pair_age_minutes", 60)),
                 "min_caption_chars": int(row.get("min_caption_chars", 25))}
                for row in active],
        }, os.getenv("CINEX_FILM_BOT_TOKEN") or os.getenv("CINEX_BOT_TOKEN", ""))

    add("films", films)
    add("series", lambda: (
        series_config(),
        os.getenv("CINEX_SERIES_BOT_TOKEN") or os.getenv("CINEX_BOT_TOKEN", "")))
    add("desir", lambda: ({
        "category": "desir",
        "sources": source_list(os.getenv("DESIR_SOURCE_CHANNEL", "@Filmromatique"),
                               os.getenv("DESIR_EXTRA_SOURCE_CHANNEL", "@g_romanticfilm"),
                               os.getenv("DESIR_SOURCE_CHANNELS", "")),
        "private": os.getenv("DESIR_PRIVATE_CHANNEL", ""),
        "public": os.getenv("DESIR_PUBLIC_CHANNEL", "@CineXDesirfr"),
    }, os.getenv("DESIR_BOT_TOKEN") or os.getenv("CINEX_CATEGORY_BOT_TOKEN", "")))
    for name in ("comedie", "anime"):
        add(name, lambda name=name: (
            category_config(name),
            os.getenv("CINEX_CATEGORY_BOT_TOKEN", "")))
    return entries


def source_options(cfg, source, category):
    """Match policies by resolved source handle, not its filtered list index."""
    if category != "films":
        return "standard", None
    handle = str(getattr(source, "username", "") or "").casefold().lstrip("@")
    matches = [idx for idx, name in enumerate(cfg["sources"])
               if str(name).casefold().lstrip("@") == handle]
    if len(matches) != 1:
        raise ValueError("Cannot associate source with its configured matching policy")
    idx = matches[0]
    modes = cfg.get("source_modes", [])
    options = cfg.get("source_pairings", [])
    if idx >= len(modes) or idx >= len(options):
        raise ValueError("Matching rules missing for configured source")
    return modes[idx], options[idx]


def summarize_sample(messages, category, matching_mode="standard", pairing=None):
    """Anonymous read-only sample; not a complete publication history."""
    entries = list(messages)
    episodic = category in ("series", "anime")
    is_category = category in ("desir", "comedie")
    mkv = category == "films" and matching_mode == "authorized_mkv"
    video = is_supported_video if is_category else (is_mkv_document if mkv else is_video)
    # The classic film relay uses strict screen_pairs, not loose match_pairs.
    # Keep the offline audit aligned with production minimum file sizes,
    # durations, caption length, message-gap and time-window rules.
    screening = (screen_pairs(entries, **(pairing or {}))
                 if category == "films" and not mkv else None)
    paired = ([] if episodic else pair_items(entries) if is_category else
              match_authorized_mkv_pairs(entries) if mkv else screening.pairs)
    # The Désir/Comédie pairing routine also yields Item(None, video)
    # for orphan videos. Those must not count as valid poster/video pairs or
    # artificially inflate the quarantine denominator.
    with_posters = [item for item in paired if valid_photo_message(item.poster)]
    counts = {"sampled_messages": len(entries),
              "rejected_structural": screening.rejected if screening else 0,
              "pairing_evaluated": not episodic,
              "real_photos": sum(valid_photo_message(m) for m in entries),
              "web_previews": sum(
                  getattr(getattr(m, "media", None), "webpage", None) is not None
                  for m in entries),
              "protected_messages": sum(bool(getattr(m, "noforwards", False)) for m in entries),
              "video_files": sum(bool(video(m)) for m in entries),
              "pairs_found": len(with_posters),
              "pairs_verified": 0,
              "quarantined_uncertain": 0,
              "quarantined_mismatch": 0}
    for item in with_posters:
        poster = item.poster
        movie = item.video if is_category else item.movie
        result = (title_assessment(poster, movie) if valid_photo_message(poster)
                  and not getattr(movie, "noforwards", False) else "uncertain")
        key = ("pairs_verified" if result == "verified" else
               "quarantined_mismatch" if result == "mismatch" else
               "quarantined_uncertain")
        counts[key] += 1
    # Episodes use a separate catalog matcher. Do not treat them as
    # unmatched films or include them in the film-quarantine denominator.
    counts["unpaired_video_files"] = (None if episodic else max(
        0, counts["video_files"] - len(with_posters)))
    return counts


def aggregate_samples(samples):
    """Keep only totals: no source IDs, captions, file names or invite links."""
    if not samples:
        return {}
    keys = list(samples[0])
    totals = {}
    for key in keys:
        values = [sample[key] for sample in samples]
        if any(v is None for v in values):
            totals[key] = None
        elif all(isinstance(v, bool) for v in values):
            totals[key] = all(values)
        else:
            totals[key] = sum(int(v) for v in values)
    return totals


def audit_overall_status(channels):
    """Do not declare a green audit if a category is missing or partial."""
    required = {"films", "series", "desir", "comedie", "anime"}
    return ("ok" if set(channels) == required and
            all(item.get("status") == "ok" for item in channels.values())
            else "needs_attention")


def recent_public_summary(messages):
    """Recent destination metadata, without message texts or private IDs."""
    entries = [m for m in messages if getattr(m, "date", None) is not None
               and getattr(m, "action", None) is None]
    latest = max((m.date for m in entries), default=None)
    return {"sampled_posts": len(entries),
            "last_post_at": latest.isoformat() if latest else None,
            "recent_real_photos": sum(valid_photo_message(m) for m in entries),
            "recent_web_previews": sum(
                getattr(getattr(m, "media", None), "webpage", None) is not None
                for m in entries),
            "recent_protected": sum(bool(getattr(m, "noforwards", False))
                                    for m in entries)}


async def verify():
    session = (os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING") or
               os.getenv("TG_STREAM_SESSION") or "").strip()
    aid = os.getenv("TG_API_ID", "").strip()
    ahash = os.getenv("TG_API_HASH", "").strip()
    if not (aid.isdigit() and ahash and session):
        raise RuntimeError("Session ou identifiants d'API Telegram manquants.")
    client = TelegramClient(StringSession(session), int(aid), ahash,
                            request_retries=0, connection_retries=2,
                            flood_sleep_threshold=0, receive_updates=False)
    report = {"checked_at": datetime.now(timezone.utc).isoformat(),
              "scope": "technical_read_only",
              "redistribution_rights_verified": False,
              "publish_actions": 0, "channels": {}}
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("La session personnelle Telegram n'est plus autorisée.")
        for name, cfg, token in requested_channels():
            if cfg is None:
                report["channels"][name] = {"status": "error",
                                            "error_type": "ConfigurationError"}
                continue
            try:
                # Validates actual IDs, distinct destinations, real source handles.
                sources, private, public, _, _, _ = await preflight(client, None, cfg)
                unavailable_sources = max(0, len(cfg["sources"]) - len(sources))
                user = await client.get_me()
                user_permissions = await client.get_permissions(private, user)
                if not (getattr(user_permissions, "is_creator", False) or
                        (getattr(user_permissions, "is_admin", False) and
                         getattr(user_permissions, "post_messages", False))):
                    raise RuntimeError("Le compte utilisateur ne peut pas publier dans la bibliothèque privée.")
                if not token:
                    raise RuntimeError("Bot de publication absent de la configuration.")
                bot = BotHTTPClient(token, client)
                identity = await bot.get_me()
                perm = await bot.get_permissions(public, identity)
                if not (perm.is_creator or (perm.is_admin and perm.post_messages)):
                    raise RuntimeError("Le bot n'a pas le droit de publier dans la destination.")
                # Bounded sample of live Telegram metadata. No downloads,
                # sends, invitations or sensitive identifiers in the artifact.
                samples = []
                sample_errors = 0
                for source in sources:
                    if len(samples) >= 3:
                        break
                    try:
                        mode, pairing = source_options(cfg, source, name)
                        source_messages = await client.get_messages(source, limit=80)
                        samples.append(summarize_sample(source_messages, name, mode, pairing))
                    except errors.FloodWaitError:
                        raise
                    except Exception:
                        sample_errors += 1
                public_summary = None
                try:
                    public_messages = await client.get_messages(public, limit=20)
                    public_summary = recent_public_summary(public_messages)
                except errors.FloodWaitError:
                    raise
                except Exception:
                    sample_errors += 1
                sample_status = ("ok" if not sample_errors and not unavailable_sources
                                 and len(samples) == min(3, len(sources)) else "partial")
                # The actual numeric IDs have already been cross-checked in preflight.
                report["channels"][name] = {"status": "ok" if sample_status == "ok" else "needs_attention",
                                            "sources_validated": len(sources),
                                            "sources_unavailable": unavailable_sources,
                                            "sampling_limited": len(sources) > 3,
                                            "redistribution_rights_verified": False,
                                            "private_id_verified": True,
                                            "public_id_verified": True,
                                            "user_can_post_private": True,
                                            "bot_can_post": True,
                                            "source_sampled": len(samples),
                                            "source_sampling_limit": 3,
                                            "source_messages_per_source_limit": 80,
                                            "source_matching_sample": aggregate_samples(samples),
                                            "public_recent": public_summary,
                                            "sample_errors": sample_errors}
                LOG.info("Canaux %s : sources=%s, IDs cohérents, droits bot OK",
                         name, len(sources))
            except errors.FloodWaitError:
                # Respect Telegram limits; do not retry the other categories.
                raise
            except Exception as exc:
                # No private IDs or bot tokens in the report.
                report["channels"][name] = {"status": "error",
                                            "error_type": type(exc).__name__}
                LOG.error("Canaux %s : vérification refusée (%s)", name, type(exc).__name__)
    finally:
        await client.disconnect()
    report["status"] = audit_overall_status(report["channels"])
    return report


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        report = asyncio.run(verify())
    except Exception as exc:
        # Always leave a safe artifact explaining why live audit stopped;
        # never serialize exception text, sessions, tokens or channel IDs.
        report = {"status": "blocked", "error_type": type(exc).__name__,
                  "scope": "technical_read_only",
                  "redistribution_rights_verified": False,
                  "publish_actions": 0, "channels": {}}
        LOG.error("Audit interrompu : %s", type(exc).__name__)
    folder = Path("state")
    folder.mkdir(exist_ok=True)
    (folder / "channel_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("AUDIT_CANAL : " + json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
