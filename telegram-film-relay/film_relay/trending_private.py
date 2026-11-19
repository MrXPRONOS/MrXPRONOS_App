"""CinéX tendance -> canaux privés dédiés et publications épinglées.

La découverte des tendances vient directement de Ciné Radar (TMDB/AniList/Simkl).
La diffusion ne se fait que pour un titre explicitement autorisé dans Radar,
avec un média déjà disponible dans les vidéothèques administrées.
Exécution en simulation par défaut. Une création de canal max par cycle.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import unicodedata
from pathlib import Path

import requests

from .bot_http import BotHTTPClient, TelegramBotHTTPError, url_button
from .publication import film_folder_url
from .public_video_archive import is_video_message, video_document_id

LOG = logging.getLogger("cinex.trending_private")
ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state/trending_private.json"
RADAR_URL = "https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/api/radar/trends?limit=12"
KINDS = {"films", "series", "animes"}
PUBLIC = {
    "films": "@CineXFilms_vf",
    "series": "@seriesvf_cinex",
    "animes": "@CineXAnimeFR",
}
CATALOGUES = {
    "series": ROOT / "state/series_catalog.json",
    "animes": ROOT / "state/anime_catalog.json",
}
MIN_PAUSE = 30
MAX_NEW_CHANNELS = 1
MAX_EPISODES_PER_RUN = 12


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    value = re.sub(r"(?i)\b(?:vf|vostfr|hd|1080p|720p|complet|serie|series|anime|film)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def canonical_key(item: dict) -> str:
    """Common title key across provider IDs: do not create 2 channels per title."""
    name = normalize(item.get("title_original") or item.get("original") or item.get("title"))
    year = item.get("year") or ""
    return f"{item.get('kind')}:{name}:{year}"


def safe_trends(items: list[dict], *, max_per_kind: int = 8) -> list[dict]:
    """Reject stale/unapproved and duplicate titles; no search based on guesses."""
    output = []
    per_kind = {kind: 0 for kind in KINDS}
    seen = set()
    for item in sorted(items, key=lambda x: (int(x.get("rank") or 999), str(x.get("source")))):
        kind = item.get("kind")
        rank = item.get("rank")
        if kind not in KINDS or item.get("authorized") is not True:
            continue
        if item.get("source") not in ("tmdb", "anilist", "simkl"):
            continue
        if not isinstance(rank, int) or rank < 1 or rank > 25:
            continue
        if len(normalize(item.get("title", ""))) < 5 or per_kind[kind] >= max_per_kind:
            continue
        identity = canonical_key(item)
        if identity in seen:
            continue
        seen.add(identity)
        per_kind[kind] += 1
        output.append(item)
    return output


def read_state() -> dict:
    if not STATE.exists():
        return {"channels": {}}
    data = json.loads(STATE.read_text(encoding="utf-8"))
    if not isinstance(data.get("channels"), dict):
        raise ValueError("État CinéX corrompu ; aucune action Telegram")
    return data


def save_state(state: dict):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    temporary.replace(STATE)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def match_catalog_series(item: dict, catalog: dict) -> dict | None:
    """Use the exact available and indexed series, never a guessed title."""
    options = [normalize(item.get(x)) for x in ("title", "original")]
    options += [normalize(x) for x in str(item.get("aliases") or "").split("|")]
    options = {x for x in options if len(x) >= 5}
    matches = []
    for data in (catalog.get("series") or {}).values():
        title = normalize(data.get("title", ""))
        if not title or title not in options:
            continue
        if not data.get("public_id") or not data.get("private_poster_id"):
            continue
        if not data.get("episodes"):
            continue
        matches.append(data)
    return matches[0] if len(matches) == 1 else None


def episode_plan(entry: dict):
    result = []
    for season, episodes in sorted(entry.get("episodes", {}).items(), key=lambda pair: int(pair[0])):
        numbers = sorted(int(k) for k in episodes if str(k).isdigit())
        if not numbers or numbers != list(range(1, numbers[-1] + 1)):
            # Never imply a complete season when an episode is missing.
            LOG.warning("Saison %s incomplète, aucune diffusion de cette saison", season)
            continue
        for number in numbers:
            record = episodes.get(str(number))
            if not record or not record.get("message_id"):
                return []
            result.append((int(season), number, int(record["message_id"])))
    return result


def film_from_public(item: dict, posters: list, state: dict) -> dict | None:
    names = {normalize(item.get("title")), normalize(item.get("original"))}
    names.update(normalize(a) for a in str(item.get("aliases") or "").split("|"))
    names = {n for n in names if len(n) >= 5}
    candidates = []
    processed = state.get("processed", {})
    for post in posters:
        if not getattr(post, "photo", None):
            continue
        first = str(getattr(post, "raw_text", "") or "").splitlines()[0]
        if normalize(first) not in names:
            continue
        matches = [x for x in processed.values()
                   if isinstance(x, dict) and int(x.get("public_message_id") or 0) == int(post.id)]
        if len(matches) == 1 and matches[0].get("private_message_id"):
            candidates.append({"public_id": post.id, "poster_id": post.id,
                               "private_id": int(matches[0]["private_message_id"])})
    return candidates[0] if len(candidates) == 1 else None


def channel_title(item: dict) -> str:
    identity = canonical_key(item)
    suffix = hashlib.sha256(identity.encode()).hexdigest()[:8]
    category = {"films": "Film", "series": "Série", "animes": "Animé"}[item["kind"]]
    return f"Ciné X {category} • {str(item['title'])[:55]} [{suffix}]"


def buttons(invite: str):
    if not re.match(r"^https://t\.me/(?:\+|joinchat/)[a-zA-Z0-9_-]{12,}$", invite):
        raise ValueError("Lien d'invitation privé Telegram non validé")
    return [
        [url_button("🎬 VOIR LE CONTENU / LES SAISONS", invite, style="success")],
        [url_button("👥 REJOINDRE LA TEAM", film_folder_url(), style="danger")],
    ]


def get_trends() -> list[dict]:
    response = requests.get(RADAR_URL, timeout=(8, 18), headers={"accept": "application/json"})
    response.raise_for_status()
    content = response.json()
    if not isinstance(content, dict) or not isinstance(content.get("items"), list):
        raise ValueError("Flux Ciné Radar incompatible")
    return safe_trends(content["items"])


async def locate_existing_channel(client, title: str):
    """Recover a creation after an interrupted checkpoint, by unique exact name."""
    matches = []
    async for dialog in client.iter_dialogs(limit=300):
        entity = dialog.entity
        if getattr(entity, "broadcast", False) and str(getattr(entity, "title", "")) == title:
            matches.append(entity)
    if len(matches) > 1:
        raise RuntimeError("Plusieurs canaux privés portent le même titre ; arrêt")
    return matches[0] if matches else None


async def ensure_channel(client, item: dict, record: dict):
    from telethon import functions, utils
    if record.get("channel_id"):
        channel = await client.get_entity(int(record["channel_id"]))
        if utils.get_peer_id(channel) != int(record["channel_id"]):
            raise RuntimeError("Identifiant de vidéothèque différent de l'état")
        return channel, False
    title = channel_title(item)
    channel = await locate_existing_channel(client, title)
    created = False
    if channel is None:
        result = await client(functions.channels.CreateChannelRequest(
            title=title,
            about="Vidéothèque Ciné X privée. Contenus publiés avec autorisation ; classement par saisons.",
            broadcast=True,
            megagroup=False,
        ))
        channel = next((c for c in getattr(result, "chats", ()) if getattr(c, "broadcast", False)), None)
        if channel is None:
            raise RuntimeError("Telegram n'a pas retourné le canal créé")
        created = True
    record["channel_id"] = utils.get_peer_id(channel)
    record["channel_title"] = title
    return channel, created


async def private_invitation(client, channel, record: dict) -> str:
    from telethon import functions
    if record.get("invite"):
        return str(record["invite"])
    invitation = await client(functions.messages.ExportChatInviteRequest(peer=channel))
    invite = str(getattr(invitation, "link", "") or "")
    buttons(invite)
    record["invite"] = invite
    return invite


async def copy_verified(client, source, destination, msg_id: int, record: dict, key: str):
    """Forward from *owned* existing library; mark only after Telegram confirms."""
    if record["copied"].get(key):
        verified = await client.get_messages(destination, ids=int(record["copied"][key]))
        if verified:
            return int(verified.id)
        record["copied"].pop(key, None)
    original = await client.get_messages(source, ids=msg_id)
    if not original or not getattr(original, "media", None):
        raise RuntimeError("Média original introuvable : " + str(msg_id))
    if getattr(original, "noforwards", False):
        raise RuntimeError("Média protégé : transfert non autorisé")
    # Reconcile a Telegram-accepted copy after a lost GitHub checkpoint.
    # A dedicated channel only contains this title's own media.
    source_document = video_document_id(original)
    source_photo = getattr(getattr(original, "photo", None), "id", None)
    async for prior in client.iter_messages(destination, limit=400):
        if source_document and video_document_id(prior) == source_document:
            record["copied"][key] = int(prior.id)
            return int(prior.id)
        if source_photo and getattr(getattr(prior, "photo", None), "id", None) == source_photo:
            record["copied"][key] = int(prior.id)
            return int(prior.id)
    copied = await client.forward_messages(destination, msg_id, from_peer=source)
    if isinstance(copied, list):
        copied = copied[0] if len(copied) == 1 else None
    if not copied or not getattr(copied, "media", None):
        raise RuntimeError("Copie non confirmée par Telegram")
    if video_document_id(original) and video_document_id(copied) != video_document_id(original):
        raise RuntimeError("Document transféré différent du document original")
    record["copied"][key] = int(copied.id)
    return int(copied.id)


async def prepare_entry(client, kind: str, item: dict, primary, library, catalogue, film_state):
    from telethon import utils
    if kind in ("series", "animes"):
        entry = match_catalog_series(item, catalogue)
        if not entry:
            return None
        plan = episode_plan(entry)
        if not plan:
            return None
        post_id = int(entry["public_id"])
        post = await client.get_messages(primary, ids=post_id)
        if not post or not getattr(post, "photo", None):
            return None
        cover = await client.get_messages(library, ids=int(entry["private_poster_id"]))
        if not cover or not getattr(cover, "photo", None):
            return None
        # Validate season records before channel creation.
        for _, _, episode_id in plan:
            msg = await client.get_messages(library, ids=episode_id)
            if not is_video_message(msg):
                LOG.warning("Épisode absent : %s", episode_id)
                return None
        return {"public_id": post_id, "cover_id": int(entry["private_poster_id"]),
                "episodes": plan, "kind": kind, "title": entry["title"]}
    public_photos = [p async for p in client.iter_messages(primary, limit=1500)
                     if getattr(p, "photo", None)]
    entry = film_from_public(item, public_photos, film_state)
    if not entry:
        return None
    video = await client.get_messages(library, ids=entry["private_id"])
    if not is_video_message(video):
        return None
    public_cover = await client.get_messages(primary, ids=entry["public_id"])
    if not public_cover or not getattr(public_cover, "photo", None):
        return None
    return {"public_id": entry["public_id"], "cover_id": int(entry["public_id"]),
            "video_id": entry["private_id"], "kind": kind,
            "episodes": [], "title": str(item["title"])}


async def work_item(client, bot, item, state, library, public, candidate,
                    *, max_copies: int = MAX_EPISODES_PER_RUN):
    from telethon.errors import FloodWaitError, PeerFloodError
    identity = canonical_key(item)
    record = state["channels"].setdefault(identity, {
        "title": item["title"], "kind": item["kind"],
        "copied": {}, "announced": False, "pinned": False,
    })
    record.setdefault("copied", {})
    channel, created = await ensure_channel(client, item, record)
    save_state(state)
    if created:
        LOG.info("Nouveau canal privé : %s", record["channel_title"])
        await asyncio.sleep(60)
    invite = await private_invitation(client, channel, record)
    save_state(state)
    copies = 0
    if candidate["kind"] == "films":
        if not record["copied"].get("cover"):
            # Existing public poster belongs to an administrator of the same ecosystem.
            await copy_verified(client, public, channel, candidate["cover_id"], record, "cover")
            save_state(state)
            await asyncio.sleep(MIN_PAUSE)
        if not record["copied"].get("movie"):
            await copy_verified(client, library, channel, candidate["video_id"], record, "movie")
            save_state(state)
            await asyncio.sleep(MIN_PAUSE)
        all_done = bool(record["copied"].get("cover") and record["copied"].get("movie"))
    else:
        if not record["copied"].get("cover"):
            await copy_verified(client, library, channel, candidate["cover_id"], record, "cover")
            save_state(state)
            await asyncio.sleep(MIN_PAUSE)
        completed_seasons = set()
        for season, ep, msg_id in candidate["episodes"]:
            if copies >= max_copies:
                break
            season_key = "season:" + str(season)
            if season not in completed_seasons and not record["copied"].get(season_key):
                label = f"📺 {candidate['title']} — Saison {season}"
                recovered = None
                async for prior in client.iter_messages(channel, limit=400):
                    if not prior.media and str(prior.raw_text or "") == label:
                        recovered = prior
                        break
                message = recovered or await client.send_message(channel, label, link_preview=False)
                if not message:
                    raise RuntimeError("Bannière de saison non confirmée")
                record["copied"][season_key] = int(message.id)
                save_state(state)
                await asyncio.sleep(MIN_PAUSE)
            completed_seasons.add(season)
            key = f"episode:{season}:{ep}"
            if key in record["copied"]:
                continue
            await copy_verified(client, library, channel, msg_id, record, key)
            copies += 1
            save_state(state)
            await asyncio.sleep(MIN_PAUSE)
        all_done = all(f"episode:{season}:{ep}" in record["copied"]
                       for season, ep, _ in candidate["episodes"])
    if not all_done:
        LOG.info("Canal %s partiellement rempli ; reprise au prochain cycle", identity)
        return False, created
    if not record.get("announced"):
        await bot.edit_reply_markup(public, candidate["public_id"], buttons=buttons(invite))
        post = await client.get_messages(public, ids=candidate["public_id"])
        if not post or not any(
            getattr(button, "url", None) == invite
            for row in (getattr(post, "buttons", None) or ())
            for button in row
        ):
            raise RuntimeError("Bouton du canal tendance non vérifié")
        record["announced"] = True
        save_state(state)
        await asyncio.sleep(MIN_PAUSE)
    if not record.get("pinned"):
        try:
            await bot.pin_message(public, candidate["public_id"])
        except TelegramBotHTTPError as exc:
            reason = str(exc).lower()
            if not any(part in reason for part in ("not enough rights", "not enough permission", "forbidden")):
                raise
            await asyncio.sleep(MIN_PAUSE)
            await client.pin_message(public, candidate["public_id"], notify=False)
        record["pinned"] = True
        save_state(state)
    return True, created


async def execute(*, apply=False):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import FloodWaitError, PeerFloodError

    trends = get_trends()
    state = read_state()
    report = {"trends": len(trends), "matched": 0,
              "channels_created": 0, "finished": 0, "skipped": 0, "errors": 0,
              "mode": "apply" if apply else "dry-run"}
    if not trends:
        LOG.info("Aucune tendance propriétaire autorisée : aucune action")
        return report
    credentials = (os.getenv("TG_API_ID"), os.getenv("TG_API_HASH"),
                   os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
                   or os.getenv("TG_STREAM_SESSION"))
    if not all(credentials):
        raise RuntimeError("Session personnelle Telegram absente")
    if apply and os.getenv("CINEX_TRENDS_ENABLED", "").lower() != "true":
        raise RuntimeError("CINEX_TRENDS_ENABLED=true requis pour créer des canaux")
    token = os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    if apply and not token:
        raise RuntimeError("Jeton du bot CinéX absent")
    client = TelegramClient(StringSession(credentials[2]), int(credentials[0]), credentials[1],
                            request_retries=1, flood_sleep_threshold=0)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram propriétaire expirée")
        bot = BotHTTPClient(token, client) if apply else None
        film_state = load_json(ROOT / "state/state.json")
        catalogues = {k: load_json(v) for k, v in CATALOGUES.items()}
        created = 0
        for item in trends:
            kind = item["kind"]
            identity = canonical_key(item)
            # No speculative matching with unrelated channel posts.
            pub = await client.get_entity(PUBLIC[kind])
            library_value = (os.getenv("ANIME_PRIVATE_CHANNEL") if kind == "animes" else
                             os.getenv("TG_PRIVATE_CHANNEL"))
            if not library_value or not library_value.startswith("-100"):
                LOG.warning("Canal privé non déclaré pour %s", kind)
                report["skipped"] += 1
                continue
            library = await client.get_entity(int(library_value))
            candidate = await prepare_entry(
                client, kind, item, pub, library, catalogues.get(kind, {}), film_state)
            if not candidate:
                report["skipped"] += 1
                continue
            report["matched"] += 1
            LOG.info("TENDANCE CORRESPONDANTE %s %s (#%s) : %s",
                     kind, item["title"], candidate["public_id"], "apply" if apply else "simulation")
            if not apply:
                continue
            if identity not in state["channels"] and created >= MAX_NEW_CHANNELS:
                report["skipped"] += 1
                continue
            try:
                done, newly_created = await work_item(
                    client, bot, item, state, library, pub, candidate)
                if newly_created:
                    created += 1
                    report["channels_created"] += 1
                if done:
                    report["finished"] += 1
            except (FloodWaitError, PeerFloodError):
                raise
            except Exception as exc:
                report["errors"] += 1
                LOG.exception("Tendance %s conservée pour une reprise sûre : %s", identity, exc)
            await asyncio.sleep(MIN_PAUSE)
        LOG.info("BILAN %s", report)
        if os.getenv("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as output:
                output.write("\n### Ciné Radar : vidéothèques tendance\n" +
                             "\n".join(f"- {k} : {v}" for k, v in report.items()) + "\n")
        return report
    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Autoriser création et épingles")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = asyncio.run(execute(apply=args.apply))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
