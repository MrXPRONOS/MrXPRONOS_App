"""CinéX Anime : une fiche par série, épisodes privés, index par saison.

Sources inchangées : category_config("anime") utilise ANIME_SOURCE_CHANNEL(S)
et sa source historique. Aucun épisode sans numéro explicite n'est deviné.
Le canal public ne reçoit qu'une nouvelle fiche par anime ; les reprises
actualisent les index privés et les boutons, sans republier d'affiche.
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
    value = re.sub(r"^@[A-Za-z0-9_]{5,32}\s+", "", value)
    value = CLEAN_CODES.sub(" ", value)
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


async def publish_catalog(*, publish: bool, limit: int, episode_cap: int) -> int:
    cfg = category_config("anime")  # sources historiques + variables inchangées
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
        for source in sources:
            messages = [m async for m in client.iter_messages(source, limit=160)]
            all_candidates.extend(classify(messages, utils.get_peer_id(source)))
            await asyncio.sleep(pause)
        all_candidates.sort(key=lambda x: x["timestamp"], reverse=True)
        groups = {}
        for row in all_candidates:
            groups.setdefault(row["series"], []).append(row)
        LOG.info("CinéX Anime : %s séries, %s épisodes identifiables, sources=%s",
                 len(groups), len(all_candidates), cfg["sources"])
        # Do not publish public cards based on uncertain inferred episode numbers.
        for key, items in groups.items():
            if len(completed_series) >= limit or copied_episodes >= episode_cap:
                break
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
            if not pending:
                continue
            pending = pending[:episode_cap - copied_episodes]
            title = str(existing.get("title") or items[0]["title"])
            LOG.info("Animé %s : %s épisodes nouveaux (lot borné)", title, len(pending))
            if not publish:
                completed_series.add(key)
                continue

            series = catalogue["series"].setdefault(
                key, {"title": title, "public_id": None, "main_index_id": None,
                      "season_indices": {}, "episodes": {}, "source_items": {}})
            marker = "#CXANIME_" + hashlib.sha256(key.encode()).hexdigest()[:15]
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

            index_id = int(series["main_index_id"])
            index_text = main_index_text(title, private_id, series["season_indices"])
            await edit_message_if_changed(client, private, index_id,
                                      index_text + "\n" + marker,
                                      parse_mode="html", link_preview=False)
            await asyncio.sleep(pause)

            if series.get("public_id"):
                await bot.edit_reply_markup(bot_public, series["public_id"],
                                            buttons=public_buttons(private_id, series))
                LOG.info("Boutons de saisons mis à jour : %s", title)
            else:
                # Recover an existing card after partial GitHub state failure.
                old_public = await find_marked(client, public, marker, limit=140)
                if old_public:
                    public_id = old_public
                else:
                    original_poster = next((x["poster"] for x in items if x["poster"] is not None), None)
                    if original_poster is None:
                        LOG.warning("Aucune affiche authentique pour %s ; fiche publique différée.", title)
                        completed_series.add(key)
                        continue
                    raw = await client.download_media(original_poster.media, file=bytes)
                    if not raw:
                        LOG.warning("Affiche introuvable pour %s ; publication différée.", title)
                        completed_series.add(key)
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
                first_ep = next(iter(series["source_items"].values()), index_id)
                state.complete("anime-series:" + key, int(first_ep), int(public_id))
                save_catalog(catalogue)
                LOG.info("Fiche publique CinéX Anime : %s -> %s", title, public_id)
            completed_series.add(key)
            await asyncio.sleep(pause)

        if publish:
            report = await publish_promotions(
                client, bot, private, public,
                None if os.getenv("CINEX_DEFER_MIRROR") else mirror,
                DesirPromotionsState(state), private_fallback=True)
            LOG.info("Publicités Anime : %s", report)
        LOG.info("FIN : %s séries mises à jour, %s fiches nouvelles, %s épisodes privés",
                 len(completed_series), posted_cards, copied_episodes)
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
    arg.add_argument("--episode-cap", type=int, choices=range(1, 13), default=6)
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
