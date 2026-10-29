"""CinéX Anime : une saison complète (1-25 épisodes) + un film, ou deux films.

La seule variable de sources est ANIME_SOURCE_CHANNEL. Tous les épisodes
numérotés sont validés ensemble; un lot interrompu reste prioritaire et
bloque les autres titres. Aucune fiche publique avant la fin du transfert.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import logging
import os
import re
import unicodedata
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from telethon import TelegramClient, utils
from telethon.errors import FloodWaitError, PeerFloodError
from telethon.sessions import StringSession

from .bot_http import BotHTTPClient, url_button
from .editing import edit_message_if_changed
from .catalog_scan import read_source_window, source_window_ids, finalize_scan, episode_audit
from .anime_policy import complete_anime_seasons, select_anime_season, anime_movie_slots
from .category_runner import category_config, preflight
from .desir_matching import is_supported_video
from .desir_runner import ReceiptState, DesirPromotionsState
from .matching import filename_of
from .promotions import publish_promotions
from .text import first_title, private_message_link

LOG = logging.getLogger("cinex_anime_catalog")
ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "state/anime_catalog.json"
SEASON_EP = re.compile(
    r"(?i)\b(?:s(?:aison|eason)?\s*0*(\d{1,2})\s*[-._ ]*"
    r"(?:[eé](?:pisode|p)?[\s._-]*0*(\d{1,3}))|"
    r"(\d{1,2})\s*[xX]\s*0*(\d{1,3})|"
    r"(?:[eé](?:pisode|p)?[\s._-]*0*(\d{1,3})))\b"
)
CLEAN_CODES = re.compile(r"(?i)\b(?:saison|season|episode|épisode|ep)[\s._-]*\d+\b|"
                         r"\bS\d{1,2}[\s._-]*E\d{1,3}\b|\b\d{1,2}x\d{1,3}\b|\bE\d{1,3}\b")
GENERIC = {"anime", "animé", "saison", "épisode", "episode", "vf", "vostfr",
           "film", "dessin anime", "serie", "série"}

# Une source peut annoncer « No Longer Rangers S02 » dans l'affiche,
# puis publier séparément « Episode_01.mkv », « Episode_02.mkv », etc.
# L'ancienne expression ne comprenait pas le token S02 isolé.
SEASON_HEADER = re.compile(
    r"(?i)(?<![A-Za-z0-9])s(?:aison|eason)?[\s._-]*0*(\d{1,2})(?!\d)"
)
EXPLICIT_EP_SEASON = re.compile(
    r"(?i)\b(?:s\d{1,2}\s*[-._ ]*e\d+|saison[\s._-]*\d+[\s._-]*[eé](?:pisode|p)?[\s._-]*\d+|"
    r"season[\s._-]*\d+[\s._-]*e\d+|\d+x\d+)\b"
)



def episode_numbers(text: str):
    match = SEASON_EP.search(text or "")
    if not match:
        # Episode is often labeled E01, without explicit season: default S01,
        # but NEVER infer the episode number.
        return None
    season = int(match.group(1) or match.group(3) or 1)
    episode = int(match.group(2) or match.group(4) or match.group(5))
    if not (1 <= season <= 50 and 1 <= episode <= 999):
        return None
    return season, episode


def series_title(text: str) -> str:
    value = first_title(text or "").strip()
    value = re.sub(r"(?i)^@[A-Za-z0-9_]{5,32}\s+(?:vf|fv)?\s*", "", value)
    # Strip the complete-season label BEFORE removing the season number.
    # Otherwise "Mushishi Saison 2 complète" becomes "Mushishi complète",
    # while "Mushishi S02E03" becomes "Mushishi": two false series.
    value = re.sub(
        r"(?i)\bs(?:aison|eason)?[\s._-]*0*\d{1,2}[\s:._-]+compl[eè]te\b",
        " ", value)
    value = CLEAN_CODES.sub(" ", value)
    # Completeness labels belong to eligibility evidence, not to the anime
    # identity: "Mushishi - 25 épisodes" and "Mushishi E03" are one title.
    value = re.sub(r"(?i)\b(?:s[eé]rie|saison)\s+compl[eè]te\b", " ", value)
    value = re.sub(r"(?i)\b\d{1,3}\s*(?:[eé]pisodes?|eps)\b", " ", value)
    value = re.sub(r"(?i)\b(?:int[eé]grale|fin de (?:la )?s[eé]rie)\b", " ", value)
    value = SEASON_HEADER.sub(" ", value)
    value = re.sub(r"(?i)(?:\b(?:mp4|mkv)\b|^@[^\s]+\s+(?:vf|fv)\b)", " ", value)
    value = re.sub(r"(?i)\b(?:vf|vostfr|1080p|720p|dub|hd|complet)\b", " ", value)
    value = re.sub(r"[|_\[\](){},:.]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" -.#!")
    if not value or value.casefold() in GENERIC or len(value) < 3:
        return ""
    return value[:90]


def slug(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title.lower())
    ascii_title = normalized.encode("ascii", "ignore").decode()
    name = re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-")[:55]
    if not name:
        raise ValueError("Titre animé non exploitable.")
    return name


def classify(messages, source_id: int):
    """Une affiche de série peut précéder des dizaines d'épisodes.

    Aucun rattachement par proximité entre séries différentes ; les épisodes
    doivent porter un numéro explicite.
    """
    latest_poster = None
    current_season = 1
    candidates = []
    season_header = SEASON_HEADER
    for msg in sorted(messages, key=lambda x: int(x.id)):
        if getattr(msg, "noforwards", False):
            continue
        caption = str(getattr(msg, "raw_text", "") or "")
        if getattr(msg, "photo", None):
            latest_poster = msg
            current_season = 1
            found = season_header.search(caption)
            if found:
                current_season = int(found.group(1))
            continue
        if not is_supported_video(msg):
            # Text-only season banners are not new series or videos.
            found = season_header.search(caption)
            if found and 1 <= int(found.group(1)) <= 50:
                current_season = int(found.group(1))
            continue
        raw = str(getattr(msg, "raw_text", "") or "")
        filename = filename_of(msg)
        numbers = episode_numbers(raw) or episode_numbers(filename)
        if numbers:
            # Priorité : saison explicite dans la vidéo, puis en-tête S02/
            # Saison 2 de la source. Ne JAMAIS supposer S1 si S02 est annoncé.
            explicit = SEASON_HEADER.search(raw) or SEASON_HEADER.search(filename)
            x_format = re.search(r"(?i)\b\d{1,2}\s*[xX]\s*\d{1,3}\b",
                                 raw + " " + filename)
            season = int(explicit.group(1)) if explicit else (
                numbers[0] if x_format else current_season
            )
            numbers = (season, numbers[1])
        if not numbers:
            continue
        context = str(getattr(latest_poster, "raw_text", "") or "")
        video_title = series_title(raw) or series_title(Path(filename).stem)
        poster_title = series_title(context)
        # Drop source-channel signatures and do not mistake an episode-only
        # filename for the anime title.
        episode_only = re.fullmatch(
            r"(?i)(?:s\d{1,2}\s*[-._ ]*e\d{1,3}|"
            r"(?:episode|épisode|ep|e)\s*[-._ ]*\d{1,3}|"
            r"\d{1,2}x\d{1,3})"
            r"(?:\s*\.(?:mkv|mp4))?", (raw or filename).strip()
        ) is not None
        title = (poster_title or video_title) if episode_only else (video_title or poster_title)
        if not title:
            continue
        series_key = slug(title)
        season, episode = numbers
        candidates.append({
            "source_key": f"{source_id}:{int(msg.id)}",
            "series": series_key, "title": title,
            "season": season, "episode": episode,
            "video": msg, "poster": latest_poster,
            "timestamp": (getattr(msg, "date", None).timestamp()
                          if isinstance(getattr(msg, "date", None), datetime) else 0),
        })
    return candidates


MOVIE_LABEL = re.compile(r"(?i)\b(?:film|movie|long[ -]?m[eé]trage)\b")
SERIES_LABEL = re.compile(r"(?i)\b(?:s[eé]rie|saison|season|[eé]pisodes?|\bep[ ._-]*\d{1,3})\b")


def is_anime_movie(item) -> bool:
    """Only standalone anime features, never a numbered series episode."""
    video = item.video
    filename = filename_of(video)
    caption = str(getattr(video, "raw_text", "") or "")
    poster_text = str(getattr(item.poster, "raw_text", "") or "")
    details = " ".join((caption, filename, poster_text))
    if episode_numbers(caption) or episode_numbers(filename):
        return False
    if SERIES_LABEL.search(details) or SEASON_HEADER.search(details):
        return False
    duration = getattr(getattr(video, "file", None), "duration", None)
    try:
        feature_length = float(duration or 0) >= 50 * 60
    except (TypeError, ValueError):
        feature_length = False
    # An explicit film label also supports MKV files without duration metadata.
    return bool(MOVIE_LABEL.search(details) or feature_length)


def pending_anime_series(eligible, catalogue):
    """Compatibility selector: only an entire matching active batch may resume."""
    active = catalogue.get("active_batch")
    if active:
        planned = {entry["source_key"] for entry in active.get("episodes", [])}
        for key, rows in eligible:
            if (key == active.get("key") and planned
                    and {row["source_key"] for row in rows} == planned):
                return (key, rows)
        return None
    return select_anime_season(eligible, catalogue)



def season_text(title: str, season: int, episodes: dict) -> str:
    rows = [f"📚 <b>{escape(title)} — Saison {season}</b>", "",
            "<i>Choisis un épisode ci-dessous.</i>", ""]
    for no, entry in sorted(episodes.items(), key=lambda x: int(x[0])):
        url = str(entry["url"])
        rows.append(f'🎞️ <a href="{escape(url, quote=True)}">Épisode {int(no):02d}</a>')
    result = "\n".join(rows)
    if len(result.encode("utf-8")) > 3950:
        raise ValueError("Index saison trop long : pagination nécessaire.")
    return result


def main_index_text(title: str, private_id: int, season_indices: dict) -> str:
    lines = [f"🌸 <b>{escape(title)}</b>",
             "<i>Toutes les saisons disponibles dans la bibliothèque CinéX.</i>", ""]
    for s, index_id in sorted(season_indices.items(), key=lambda x: int(x[0])):
        url = private_message_link(private_id, index_id)
        lines.append(f'📺 <a href="{url}">Saison {int(s)}</a>')
    return "\n".join(lines)


def public_buttons(private_id: int, series_entry: dict):
    seasons = series_entry.get("season_indices", {})
    rows = []
    for season, index_id in sorted(seasons.items(), key=lambda x: int(x[0])):
        rows.append([url_button("📺 Saison " + str(int(season)),
                                private_message_link(private_id, index_id),
                                style="primary")])
    rows.append([url_button("📚 Tous les épisodes",
                            private_message_link(private_id, series_entry["main_index_id"]),
                            style="success")])
    # The existing shared folder is the official way to join the private library.
    from .publication import film_folder_url
    rows.append([url_button("➕ Rejoindre CinéX", film_folder_url(), style="danger")])
    return rows


def read_catalog():
    if not CATALOG.exists():
        return {"series": {}}
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def save_catalog(data: dict):
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    temp = CATALOG.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")
    temp.replace(CATALOG)


def episode_marker(key: str) -> str:
    return "#CXEP_" + hashlib.sha256(key.encode()).hexdigest()[:18]


async def find_marked(client, peer, marker: str, limit=160):
    async for msg in client.iter_messages(peer, limit=limit):
        if re.search(re.escape(marker) + r"(?!_[A-Za-z0-9])",
                     getattr(msg, "raw_text", "") or ""):
            return int(msg.id)
    return None


async def backfill_private_covers(client, private, catalogue, groups, pause):
    """Repair earlier short series that had episodes but no private cover image."""
    from .short_series import normalized_key
    for key, items in groups.items():
        entry = catalogue.get("series", {}).get(key)
        if not entry or entry.get("private_poster_id") or not entry.get("episodes"):
            continue
        title = normalized_key(key)
        known = set()
        for candidate, seasons in catalogue.get("source_observed", {}).items():
            if normalized_key(candidate) != title:
                continue
            for season, eps in seasons.items():
                known.update((int(season), int(ep)) for ep in eps)
        for season, eps in entry.get("episodes", {}).items():
            known.update((int(season), int(ep)) for ep in eps)
        if len(known) > 12 or any(ep > 12 for _, ep in known):
            continue
        poster = next((r["poster"] for r in items if r.get("poster") is not None), None)
        if poster is None:
            continue
        cover_marker = "#CXANIME_" + hashlib.sha256(key.encode()).hexdigest()[:15] + "_POSTER"
        recovered = await find_marked(client, private, cover_marker, limit=700)
        if not recovered:
            media = await client.download_media(poster.media, file=bytes)
            if not media:
                continue
            stream = io.BytesIO(media)
            stream.name = "cinex_private_series.jpg"
            caption = f"📺 <b>{escape(str(entry.get('title') or key))}</b>\n" + cover_marker
            photo = await client.send_file(
                private, stream, caption=caption, parse_mode="html", force_document=False
            )
            recovered = int(photo.id)
            await asyncio.sleep(pause)
        entry["private_poster_id"] = int(recovered)
        save_catalog(catalogue)
        LOG.info("Fiche privée historique réparée pour %s : %s", key, recovered)


def batch_descriptor(key, items):
    """Persist just Telegram IDs, never source videos, for crash recovery."""
    return {
        "key": key,
        "season": (int(items[0]["season"]) if len({int(row["season"]) for row in items}) == 1
                   else None),
        "count": len(items),
        "episodes": [
            {"source_key": row["source_key"],
             "season": int(row["season"]), "episode": int(row["episode"]),
             "title": row["title"],
             "poster_id": int(row["poster"].id) if row.get("poster") else None}
            for row in items
        ],
    }


async def recover_active_rows(client, sources, all_candidates, active):
    """Retrieve a previously started batch by exact IDs if it left the scan window."""
    if not active:
        return all_candidates
    peers = {str(utils.get_peer_id(peer)): peer for peer in sources}
    planned = {row["source_key"]: row for row in active.get("episodes", [])}
    # Historical poster and episode captions can have different title forms.
    # A resumed transfer must retain its original series grouping.
    for row in all_candidates:
        if row["source_key"] in planned:
            row["series"] = active["key"]
            row["title"] = planned[row["source_key"]]["title"]
    seen = {row["source_key"] for row in all_candidates}
    for expected in active.get("episodes", []):
        source_key = str(expected.get("source_key", ""))
        if source_key in seen or ":" not in source_key:
            continue
        source_id, message_id = source_key.rsplit(":", 1)
        peer = peers.get(source_id)
        if peer is None:
            continue
        message = await client.get_messages(peer, ids=int(message_id))
        if message is None or not is_supported_video(message):
            continue
        poster = None
        if expected.get("poster_id"):
            poster = await client.get_messages(peer, ids=int(expected["poster_id"]))
            if poster is not None and (not getattr(poster, "photo", None)
                                       or getattr(poster, "noforwards", False)):
                poster = None
        all_candidates.append({
            "source_key": source_key,
            "series": active["key"],
            "title": expected["title"],
            "season": int(expected["season"]),
            "episode": int(expected["episode"]),
            "video": message, "poster": poster,
            "timestamp": (message.date.timestamp()
                          if isinstance(getattr(message, "date", None), datetime) else 0),
        })
        seen.add(source_key)
        LOG.info("Reprise Anime : épisode %s retrouvé par son ID Telegram", source_key)
    return all_candidates


def ready_full_batch(items, expected=None):
    """Validate all episode media before writing even the first private post."""
    if not (1 <= len(items) <= 25):
        return False
    positions = {(int(row["season"]), int(row["episode"])) for row in items}
    if len(positions) != len(items):
        return False
    if expected is not None:
        planned = {(int(row["season"]), int(row["episode"]))
                   for row in expected.get("episodes", [])}
        if positions != planned:
            return False
    return (any(row.get("poster") is not None and
                getattr(row["poster"], "photo", None) and
                not getattr(row["poster"], "noforwards", False)
                for row in items)
            and all(is_supported_video(row["video"]) and
                    getattr(row["video"], "media", None) is not None and
                    getattr(row["video"], "document", None) is not None
                    for row in items))


def all_episodes_uploaded(series, items):
    return all(
        str(row["episode"]) in series.get("episodes", {}).get(str(row["season"]), {})
        for row in items
    )


async def publish_catalog(*, publish: bool, limit: int, episode_cap: int) -> int:
    if not 1 <= episode_cap <= 25:
        raise ValueError("Anime : entre 1 et 25 épisodes par série, jamais 26 ou plus.")
    cfg = category_config("anime")
    session = (os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING") or
               os.getenv("TG_STREAM_SESSION") or "").strip()
    api_id = os.getenv("TG_API_ID", "").strip()
    api_hash = os.getenv("TG_API_HASH", "").strip()
    if not (api_id and api_hash and session):
        raise RuntimeError("Session Telegram manquante.")

    state = ReceiptState(cfg["state_path"])
    catalogue = read_catalog()
    catalogue.setdefault("series", {})
    client = TelegramClient(StringSession(session), int(api_id), api_hash,
                            request_retries=0, connection_retries=2,
                            flood_sleep_threshold=0, receive_updates=False)
    bot = None
    pause = max(12.0, float(os.getenv("CINEX_PAUSE_SECONDS", "20")))
    completed_series = set()
    posted_cards = 0
    copied_episodes = 0
    try:
        await client.connect()
        if publish:
            token = (os.getenv("CINEX_CATEGORY_BOT_TOKEN") or "").strip()
            if not token:
                raise RuntimeError("Bot CinéX Anime manquant.")
            bot = BotHTTPClient(token, client)
        sources, private, public, bot_public, mirror, mirror_key = await preflight(client, bot, cfg)
        private_id = utils.get_peer_id(private)
        all_candidates = []
        scan_plans = []
        unnumbered_skipped = 0
        for source in sources:
            source_id = utils.get_peer_id(source)
            messages, plan = await read_source_window(
                client, source, catalogue, source_id, archive_pages=4)
            allowed = source_window_ids(messages, plan)
            candidates = [row for row in classify(messages, source_id)
                          if int(row["video"].id) in allowed]
            all_candidates.extend(candidates)
            if plan is not None:
                scan_plans.append(plan)
            # Unnumbered uploads are reported, never assigned a guessed number.
            numbered_ids = {int(row["video"].id) for row in candidates}
            unnumbered_skipped += sum(
                1 for msg in messages
                if int(msg.id) in allowed and is_supported_video(msg)
                and int(msg.id) not in numbered_ids
            )
            LOG.info("Canal source validé : catégorie=%s, épisodes identifiés=%s, vidéos sans index=%s",
                     "anime_catalog", len(candidates), unnumbered_skipped)
            await asyncio.sleep(pause)
        all_candidates = await recover_active_rows(
            client, sources, all_candidates, catalogue.get("active_batch"))
        all_candidates.sort(key=lambda x: x["timestamp"], reverse=True)
        groups = {}
        for row in all_candidates:
            groups.setdefault(row["series"], []).append(row)
        LOG.info("CinéX Anime : %s séries, %s épisodes identifiables, sources=%s",
                 len(groups), len(all_candidates), cfg["sources"])
        # No unrelated historical cover repairs during a locked series batch.
        # A full 1-25 episode run is validated before any new upload.
        eligibility_reasons = {}
        eligible = complete_anime_seasons(
            groups, catalogue, maximum=episode_cap,
            diagnostics=eligibility_reasons)
        excluded_totals = {}
        for reason in eligibility_reasons.values():
            excluded_totals[reason] = excluded_totals.get(reason, 0) + 1
        LOG.info("Éligibilité anime : groupes=%s, retenus=%s, exclus=%s",
                 len(groups), len(eligible), excluded_totals)
        LOG.info("%s : %s séries complètes (1 à %s épisodes) admissibles",
                 "anime_catalog", len(eligible), episode_cap)
        active = catalogue.get("active_batch")
        if active:
            # Resume exactly the batch pinned before a crash, even if the
            # source window has moved or the old batch had multiple seasons.
            expected = {str(row["source_key"]) for row in active.get("episodes", [])}
            recovered = [row for row in all_candidates
                         if row["source_key"] in expected]
            selected = ((str(active["key"]), sorted(
                recovered, key=lambda row: (row["season"], row["episode"])))
                        if (len(expected) == len(recovered)
                            and ready_full_batch(recovered, active)) else None)
        else:
            selected = pending_anime_series(eligible, catalogue)
        if active and selected is None:
            LOG.warning("Anime : série %s interrompue, épisodes introuvables ou "
                        "incomplets ; AUCUNE autre série ou film ne sera envoyé.",
                        active.get("key"))
        series_attempted = False
        for key, items in ([selected] if selected else []):
            # Compatibilité avec les catalogues créés avant la correction S02.
            # Ne pas créer une deuxième fiche ni recharger les épisodes déjà copiés.
            if key not in catalogue["series"]:
                previous = next((
                    older_key for older_key, older in catalogue["series"].items()
                    if slug(series_title(str(older.get("title", "")))) == key
                ), None)
                if previous:
                    key = previous
            existing = catalogue["series"].get(key, {})
            known_keys = set(existing.get("source_items", {}))
            pending = [x for x in sorted(items, key=lambda x: (x["season"], x["episode"]))
                       if x["source_key"] not in known_keys]
            # A locked batch might already have all private episodes but still
            # need its public season announcement after a crash.
            if (not active and not pending and existing.get("public_id")
                    and all_episodes_uploaded(existing, items)):
                continue
            title = str(existing.get("title") or items[0]["title"])
            series_attempted = True
            if not ready_full_batch(items, active):
                LOG.warning("Anime %s : liste complète des épisodes indisponible ; "
                            "aucune publication, même en mode film, pour ce cycle.", title)
                break
            LOG.info("Anime : saison EXCLUSIVE %s, %s épisodes prévalidés, %s à transférer",
                     title, len(items), len(pending))
            if not publish:
                completed_series.add(key)
                break
            if not active:
                catalogue["active_batch"] = batch_descriptor(key, items)
                save_catalog(catalogue)
                active = catalogue["active_batch"]

            series = catalogue["series"].setdefault(
                key, {"title": title, "public_id": None, "main_index_id": None,
                      "season_indices": {}, "episodes": {}, "source_items": {}})
            marker = "#CXANIME_" + hashlib.sha256(key.encode()).hexdigest()[:15]
            # Save the original series illustration in the PRIVATE channel too.
            # Its deterministic caption marker prevents duplicate posters after a crash.
            if not series.get("private_poster_id"):
                poster_marker = marker + "_POSTER"
                private_poster = await find_marked(client, private, poster_marker, limit=700)
                if not private_poster:
                    original_poster = next(
                        (row["poster"] for row in items if row.get("poster") is not None), None
                    )
                    if original_poster is None:
                        LOG.warning("Affiche absente pour %s : aucun épisode envoyé.", title)
                        continue
                    raw_poster = await client.download_media(original_poster.media, file=bytes)
                    if not raw_poster:
                        LOG.warning("Affiche introuvable pour %s : aucun épisode envoyé.", title)
                        continue
                    photo_stream = io.BytesIO(raw_poster)
                    photo_stream.name = "cinex_private_series.jpg"
                    sent_poster = await client.send_file(
                        private, photo_stream,
                        caption=f"🌸 <b>{escape(title)}</b>\n"
                                f"<i>Fiche de la série et épisodes ci-dessous.</i>\n{poster_marker}",
                        parse_mode="html", force_document=False,
                    )
                    private_poster = int(sent_poster.id)
                    await asyncio.sleep(pause)
                series["private_poster_id"] = int(private_poster)
                save_catalog(catalogue)
            if not series.get("main_index_id"):
                recovered = await find_marked(client, private, marker)
                if recovered:
                    series["main_index_id"] = recovered
                else:
                    new = await client.send_message(
                        private, f"🌸 <b>{escape(title)}</b>\n"
                                 "<i>Index des saisons en préparation.</i>\n" + marker,
                        parse_mode="html", link_preview=False)
                    series["main_index_id"] = int(new.id)
                    await asyncio.sleep(pause)
                save_catalog(catalogue)
            for row in pending:
                season_key = str(row["season"])
                number_key = str(row["episode"])
                if season_key not in series["season_indices"]:
                    season_marker = marker + "_S" + season_key
                    prior = await find_marked(client, private, season_marker)
                    if prior:
                        series["season_indices"][season_key] = prior
                    else:
                        new = await client.send_message(
                            private, f"📚 <b>{escape(title)} — Saison {row['season']}</b>"
                                     "\n<i>Index des épisodes en préparation.</i>\n" + season_marker,
                            parse_mode="html", link_preview=False)
                        series["season_indices"][season_key] = int(new.id)
                        await asyncio.sleep(pause)
                    save_catalog(catalogue)
                ep = series["episodes"].setdefault(season_key, {})
                if number_key in ep:
                    # Even when another source has the same episode, do not re-upload.
                    series["source_items"][row["source_key"]] = ep[number_key]["message_id"]
                    save_catalog(catalogue)
                    continue
                legacy = state.data["completed"].get(row["source_key"], {})
                prior_id = legacy.get("video_id")
                if not prior_id:
                    prior_id = await find_marked(client, private, episode_marker(row["source_key"]))
                if prior_id:
                    private_msg_id = int(prior_id)
                else:
                    caption = (f"🌸 <b>{escape(title)}</b> — "
                               f"S{row['season']:02d}E{row['episode']:02d}\n"
                               f"{episode_marker(row['source_key'])}")
                    new = await client.send_file(private, row["video"].media,
                                                 caption=caption, parse_mode="html")
                    private_msg_id = int(new.id)
                    await asyncio.sleep(pause)
                ep[number_key] = {"message_id": private_msg_id,
                                  "url": private_message_link(private_id, private_msg_id)}
                series["source_items"][row["source_key"]] = private_msg_id
                copied_episodes += 1
                save_catalog(catalogue)
                season_msg_id = int(series["season_indices"][season_key])
                body = season_text(title, row["season"], ep)
                # Keep marker for interrupted-run recovery of the season index.
                await edit_message_if_changed(client, private, season_msg_id,
                                          body + "\n" + marker + "_S" + season_key,
                                          parse_mode="html", link_preview=False)
                await asyncio.sleep(pause)

            # A public series card is strictly forbidden until every episode
            # of the prevalidated full batch has its private message receipt.
            if not all_episodes_uploaded(series, items):
                raise RuntimeError("Anime : série incomplète ; fiche publique non créée.")
            index_id = int(series["main_index_id"])
            index_text = main_index_text(title, private_id, series["season_indices"])
            await edit_message_if_changed(client, private, index_id,
                                      index_text + "\n" + marker,
                                      parse_mode="html", link_preview=False)
            await asyncio.sleep(pause)

            season_numbers = {int(row["season"]) for row in items}
            # Legacy batches could include two seasons; keep their original
            # single card instead of inventing a duplicate during recovery.
            season_no = str(next(iter(season_numbers))) if len(season_numbers) == 1 else None
            season_posts = series.setdefault("season_public_ids", {})
            had_public_card = bool(series.get("public_id"))
            if had_public_card:
                # Map the original series card to its historical first season.
                # Do not republish the old season merely because this mapping
                # did not exist in a pre-update catalogue.
                if not season_posts:
                    earlier = [str(s) for s in series.get("episodes", {})
                               if str(s) != season_no]
                    first_season = min(earlier, key=int) if earlier else season_no
                    if first_season:
                        season_posts[first_season] = int(series["public_id"])
                await bot.edit_reply_markup(bot_public, series["public_id"],
                                            buttons=public_buttons(private_id, series))
                LOG.info("Boutons de saisons mis à jour : %s", title)
            else:
                # Recover the original series card after a partial state failure.
                old_public = await find_marked(client, public, marker, limit=140)
                if old_public:
                    public_id = int(old_public)
                else:
                    original_poster = next((x["poster"] for x in items if x["poster"] is not None), None)
                    if original_poster is None:
                        LOG.warning("Aucune affiche authentique pour %s ; fiche publique différée.", title)
                        continue
                    raw = await client.download_media(original_poster.media, file=bytes)
                    if not raw:
                        LOG.warning("Affiche introuvable pour %s ; publication différée.", title)
                        continue
                    picture = io.BytesIO(raw)
                    picture.name = "cinex_anime.jpg"
                    index_link = private_message_link(private_id, index_id)
                    cap = (f"🌸 <b>{escape(title)}</b>\n\n"
                           "<i>Saisons et épisodes disponibles dans la bibliothèque CinéX.</i>\n"
                           f'📚 <a href="{index_link}">VOIR TOUTES LES SAISONS</a>\n'
                           f"{marker}")
                    post = await bot.send_file(
                        bot_public, picture, caption=cap, parse_mode="html",
                        buttons=public_buttons(private_id, series), force_document=False)
                    public_id = int(post.id)
                    posted_cards += 1
                series["public_id"] = public_id
                if season_no:
                    season_posts[season_no] = public_id
                first_ep = next(iter(series["source_items"].values()), index_id)
                state.complete("anime-series:" + key, int(first_ep), int(public_id))
                save_catalog(catalogue)
                LOG.info("Fiche publique CinéX Anime : %s -> %s", title, public_id)
            # Each later season gets a distinct public announcement, not only
            # an invisible button edit on the older season's original card.
            if season_no and season_no not in season_posts:
                season_marker = marker + "_S" + season_no
                public_season_id = await find_marked(
                    client, public, season_marker, limit=200)
                if not public_season_id:
                    original_poster = next(
                        (row["poster"] for row in items if row.get("poster") is not None),
                        None)
                    if original_poster is None:
                        raise RuntimeError("Affiche absente pour la nouvelle saison.")
                    raw = await client.download_media(original_poster.media, file=bytes)
                    if not raw:
                        raise RuntimeError("Affiche introuvable pour la nouvelle saison.")
                    picture = io.BytesIO(raw)
                    picture.name = "cinex_anime_season.jpg"
                    season_link = private_message_link(
                        private_id, int(series["season_indices"][season_no]))
                    caption = (f"🌸 <b>{escape(title)} — Saison {int(season_no)}</b>\n\n"
                               "<i>Nouvelle saison complète disponible.</i>\n"
                               f'📺 <a href="{season_link}">VOIR LES ÉPISODES</a>\n'
                               f"{season_marker}")
                    public_post = await bot.send_file(
                        bot_public, picture, caption=caption, parse_mode="html",
                        buttons=public_buttons(private_id, series), force_document=False)
                    public_season_id = int(public_post.id)
                    posted_cards += 1
                season_posts[season_no] = int(public_season_id)
                save_catalog(catalogue)
            if season_no and season_no in season_posts and had_public_card:
                first_ep = int(series["episodes"][season_no][
                    str(min(row["episode"] for row in items))]["message_id"])
                state.complete(f"anime-season:{key}:S{season_no}",
                               first_ep, int(season_posts[season_no]))
                save_catalog(catalogue)
            completed_series.add(key)
            catalogue["active_batch"] = None
            save_catalog(catalogue)
            LOG.info("Anime : lot %s terminé et verrou libéré (%s épisodes)", title, len(items))
            await asyncio.sleep(pause)
            break  # Never start a second anime series in this cycle.

        if publish:
            scan_progress = finalize_scan(catalogue, scan_plans, all_candidates)
            audit = episode_audit(catalogue, all_candidates, category="anime_catalog",
                                  ignored_unnumbered=unnumbered_skipped)
            save_catalog(catalogue)
            LOG.info("Historique %s : %s ; audit : %s épisodes en attente, %s saisons avec trous",
                     "anime_catalog", scan_progress, audit["not_yet_indexed_total"],
                     audit["numbering_gap_seasons"])
            if completed_series:
                report = await publish_promotions(
                    client, bot, private, public,
                    None if os.getenv("CINEX_DEFER_MIRROR") else mirror,
                    DesirPromotionsState(state),
                    private_fallback=True,
                    current_run_films=posted_cards,
                )
                LOG.info("Publicités Anime : %s", report)
        LOG.info("FIN : %s séries mises à jour, %s fiches nouvelles, %s épisodes privés",
                 len(completed_series), posted_cards, copied_episodes)
        film_slots = anime_movie_slots(
            limit, finished_series=bool(completed_series),
            active_batch=bool(catalogue.get("active_batch")))
        if publish and film_slots and (not series_attempted or completed_series):
            LOG.info("Anime : %s saison terminée ; %s film(s) prévu(s).",
                     int(bool(completed_series)), film_slots)
            # Fully close the catalogue's Telegram connection before opening
            # the movie relay; it shares the same user session and state.
            if bot is not None:
                await bot.disconnect()
                bot = None
            await client.disconnect()
            from .category_runner import run as publish_anime_movies
            return await publish_anime_movies(category="anime", publish=True,
                                             limit=film_slots)
        return 0
    except (FloodWaitError, PeerFloodError):
        LOG.error("Limitation Telegram : arrêt, aucune nouvelle tentative.")
        return 2
    finally:
        if bot is not None:
            await bot.disconnect()
        await client.disconnect()


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--publish", action="store_true")
    arg.add_argument("--limit", type=int, choices=(1, 2), default=2)
    arg.add_argument("--episode-cap", type=int, choices=range(1, 26), default=25)
    args = arg.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(message)s")
    try:
        code = asyncio.run(publish_catalog(publish=args.publish,
                                           limit=args.limit,
                                           episode_cap=args.episode_cap))
    except Exception:
        LOG.exception("Échec du catalogue Animés")
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
