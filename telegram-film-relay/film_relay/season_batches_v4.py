"""CinéX V4 Lot 3: season-sized, episode-aware, resumable Telegram batches.

Only verified, numbered source episodes are selected. Every new batch contains
one illustrated private cover followed by its videos, plus one public cover
followed by its videos. Existing receipts are never blindly reposted.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import re
from html import escape
from typing import Any

from .cinex_v4_policy import caption_with_automatic_ttl, is_main_relay
from .publication import (
    film_folder_url, make_button_keyboard, rich_caption, video_labels,
)
from .public_video_archive import is_video_message, video_document_id
from .radar_download_registry import is_bot_download_url
from .rescue_channels import public_username, rescue_link_for, is_invite
from .text import private_message_link

_EPISODE = re.compile(r"^S\d{2}E\d{2,3}$")
_INTERNAL = re.compile(r"^https://t\.me/c/\d{5,}/[1-9]\d*$")


def episode_code(row: dict) -> str:
    return f"S{int(row['season']):02d}E{int(row['episode']):02d}"


def batch_identifier(series_key: str, season: int, items: list) -> str:
    numbers = sorted({int(r["episode"]) for r in items})
    if not numbers or len(numbers) != len(items):
        raise ValueError("Lot saison : épisodes dupliqués ou absents")
    seed = f"{series_key}\0{int(season)}\0{','.join(map(str, numbers))}"
    return "CXBATCH_" + hashlib.sha256(seed.encode()).hexdigest()[:20]


def _existing_series(catalogue, key, title):
    from .short_series import normalized_key
    target = normalized_key(title or key)
    for old_key, entry in catalogue.get("series", {}).items():
        if (old_key == key or normalized_key(old_key) == normalized_key(key)
                or normalized_key(entry.get("title", "")) == target):
            return entry
    return {}


def select_season_batches(groups: dict, catalogue: dict, complete_candidates: list,
                          *, maximum: int = 25, limit: int = 2,
                          excluded: set | None = None) -> list:
    """One season per show and cycle. Complete seasons trump ongoing releases.

    Previously public episodes provide continuity. A missing episode stops
    progression; neither a filename guess nor a previous scan is sufficient.
    Oversized batches are held for review instead of being silently split.
    """
    if maximum < 1 or limit < 1:
        raise ValueError("Batch capacity must be positive")
    excluded = excluded or set()
    complete = {
        (key, int(rows[0]["season"])): rows for key, rows in complete_candidates
        if rows
    }
    chosen = []
    for key in sorted(groups):
        if key in excluded:
            continue
        rows = groups[key]
        if not rows:
            continue
        existing = _existing_series(catalogue, key, rows[0].get("title"))
        already_public = existing.get("public_episode_posts", {}) or {}
        seasons = sorted({int(r["season"]) for r in rows})
        for season in seasons:
            by_number = {}
            for row in sorted(rows, key=lambda r: r.get("timestamp", 0), reverse=True):
                if int(row["season"]) != season:
                    continue
                n = int(row["episode"])
                if not 1 <= n <= 999 or not row.get("video"):
                    continue
                by_number.setdefault(n, row)
            if not by_number:
                continue
            complete_rows = complete.get((key, season))
            is_complete = bool(complete_rows)
            # Existing published episodes are trusted only as prior receipts;
            # a public episode cannot be inferred solely from source metadata.
            published = {int(n) for n in by_number
                         if f"S{season:02d}E{n:02d}" in already_public}
            published |= {
                int(match.group(1))
                for name in already_public
                for match in [re.fullmatch(rf"S{season:02d}E(\d{{2,3}})", name)]
                if match
            }
            if is_complete:
                # The pre-existing conservative completion policy has checked
                # exact declared totals and artwork for this particular season.
                numbers = sorted({int(r["episode"]) for r in complete_rows})
                if numbers != list(range(1, max(numbers) + 1)):
                    continue
                pending = [by_number[n] for n in numbers
                           if n not in published and n in by_number]
                # No incomplete/oversized published season in a single tour.
                if len(pending) != len([n for n in numbers if n not in published]):
                    continue
            else:
                # Include contiguous *currently available* episodes from 1,
                # bridging previous public receipts but never missing numbers.
                pending = []
                for number in range(1, max(by_number) + 1):
                    if number in published:
                        continue
                    if number not in by_number:
                        break
                    # All lower episode numbers must already be public or be
                    # included in this same batch.
                    if any(x not in published and x not in
                           {int(r["episode"]) for r in pending}
                           for x in range(1, number)):
                        break
                    pending.append(by_number[number])
            if not pending:
                continue
            if len(pending) > maximum:
                continue  # no season splitting by arbitrary quota
            fallback = next((r["poster"] for r in rows
                             if r.get("poster") is not None
                             and getattr(r["poster"], "photo", None)), None)
            if fallback is None:
                continue
            for row in pending:
                if not row.get("poster"):
                    row["poster"] = fallback
            chosen.append((key, sorted(pending, key=lambda r: int(r["episode"])),
                           is_complete))
            break
        if len(chosen) >= limit:
            break
    return chosen


def batch_caption(title: str, items: list, *, complete: bool,
                  kind: str = "series") -> str:
    if not items:
        raise ValueError("Lot vide")
    season = int(items[0]["season"])
    if any(int(row["season"]) != season for row in items):
        raise ValueError("Mélange de saisons dans un même lot")
    numbers = sorted(int(row["episode"]) for row in items)
    nums = (f"Épisode {numbers[0]}" if len(numbers) == 1 else
            f"Épisodes {numbers[0]} à {numbers[-1]}"
            if numbers == list(range(numbers[0], numbers[-1] + 1)) else
            "Épisodes " + ", ".join(str(n) for n in numbers))
    prefix = "🌸" if kind == "anime" else "📺"
    suffix = ("Saison complète" if complete else
              "Saison en cours · nouveaux épisodes disponibles")
    cadence = {row.get("cadence_hint") for row in items}
    cadence_line = ("\n📅 Diffusion hebdomadaire annoncée"
                    if cadence == {"weekly"} else "")
    return (f"{prefix} {title} — Saison {season}\n"
            f"🎞️ {nums}\n{suffix}{cadence_line}")


def _buttons_as_pairs(message):
    result = []
    for row in (getattr(message, "buttons", None) or []):
        if len(row) != 1:
            return []
        btn = getattr(row[0], "button", row[0])
        result.append((str(getattr(btn, "text", "") or ""),
                       str(getattr(btn, "url", "") or "")))
    return result


def batch_private_rows(public_peer, download_index_url: str):
    handle = public_username(public_peer)
    if not is_main_relay(handle) or not _INTERNAL.fullmatch(download_index_url):
        raise RuntimeError("Fiche de lot privée : canal ou index non vérifié")
    return [
        [("📢 REJOINDRE LE CANAL", "https://t.me/" + handle.lstrip("@"))],
        [("📁 REJOINDRE LE DOSSIER", film_folder_url())],
        [("⬇️ TÉLÉCHARGER LES VIDÉOS", download_index_url)],
    ]


def batch_public_rows(public_peer, watch_url: str, download_index_url: str,
                      *, kind: str):
    if not (_INTERNAL.fullmatch(watch_url)
            and _INTERNAL.fullmatch(download_index_url)
            and watch_url != download_index_url):
        raise RuntimeError("Lot public : fiche ou index de téléchargement non vérifié")
    invitation = rescue_link_for(public_peer)
    if not is_invite(invitation):
        raise RuntimeError("Lot public : canal Secours non vérifié")
    watch_label, _ = video_labels(kind)
    return [
        [(watch_label, watch_url)],
        [("⬇️ TÉLÉCHARGER LES VIDÉOS", download_index_url)],
        [("🛟 REJOINDRE LE CANAL SECOURS", invitation)],
        [("📁 REJOINDRE LE DOSSIER", film_folder_url())],
    ]


async def _find_marked(client, peer, marker: str, limit=500):
    async for message in client.iter_messages(peer, limit=limit):
        if marker in str(getattr(message, "raw_text", "") or "").split():
            return message
    return None


def _save(series: dict, catalogue: dict, save_catalog) -> None:
    save_catalog(catalogue)


async def prepare_private_season_batch(
    user, bot, private, public, private_id: int,
    series_key: str, series: dict, items: list, catalogue: dict,
    save_catalog, unified, *, kind: str, complete: bool,
):
    """Store ALL video+poster pairs centrally, then send ONE private fiche.

    This fiche immediately precedes the newly copied PRIVATE videos. A private
    download index lists every episode's real CineRadar link, not one misleading
    single-file link for a whole season.
    """
    if not items or not all(int(x["season"]) == int(items[0]["season"]) for x in items):
        raise ValueError("Un lot doit contenir une seule saison")
    season = int(items[0]["season"])
    key = batch_identifier(series_key, season, items)
    marker = "#" + key
    batches = series.setdefault("season_batches", {})
    receipt = batches.setdefault(key, {
        "season": season,
        "episodes": [episode_code(r) for r in items],
        "complete": bool(complete),
        "downloads": {},
        "private_videos": {},
        "public_videos": {},
    })
    if receipt["episodes"] != [episode_code(r) for r in items]:
        raise RuntimeError("Reprise du lot : identité des épisodes incohérente")
    poster = next((r.get("poster") for r in items
                   if r.get("poster") is not None
                   and getattr(r["poster"], "photo", None)), None)
    if poster is None:
        raise RuntimeError("Lot sans affiche originale fiable")
    description = batch_caption(str(series.get("title") or items[0]["title"]),
                                items, complete=complete, kind=kind)
    for row in items:
        code = episode_code(row)
        if not is_bot_download_url(receipt["downloads"].get(code)):
            source_poster = row.get("poster") or poster
            download = await unified.store(
                row["video"], category=kind,
                title=f"{series.get('title') or row['title']} {code}",
                public=public, poster=source_poster,
                description=str(getattr(source_poster, "raw_text", "") or
                                description),
            )
            if not is_bot_download_url(download):
                raise RuntimeError(f"Stock central non vérifié pour {code}")
            receipt["downloads"][code] = download
            _save(series, catalogue, save_catalog)

    # Index must use real authenticated CineRadar tokens for EVERY episode.
    links = [f"{code} — {receipt['downloads'][code]}"
             for code in receipt["episodes"]]
    text = description + "\n\n📥 Télécharger les épisodes :\n" + "\n".join(links)
    if len(text.encode("utf-8")) >= 4000:
        raise RuntimeError("Index de téléchargement trop long")
    index_marker = marker + "_DOWNLOADS"
    if not receipt.get("download_index_id"):
        prior = await _find_marked(user, private, index_marker)
        if prior:
            receipt["download_index_id"] = int(prior.id)
            receipt.pop("index_uncertain", None)
            _save(series, catalogue, save_catalog)
        elif receipt.get("index_uncertain"):
            raise RuntimeError("Envoi de l'index incertain : vérification requise")
        else:
            receipt["index_uncertain"] = True
            _save(series, catalogue, save_catalog)
            sent = await user.send_message(
                private, text + "\n" + index_marker, link_preview=False)
            receipt["download_index_id"] = int(sent.id)
            receipt.pop("index_uncertain", None)
            _save(series, catalogue, save_catalog)
    verified = await user.get_messages(
        private, ids=int(receipt["download_index_id"]))
    raw = str(getattr(verified, "raw_text", "") or "")
    if (index_marker not in raw or
            any(url not in raw for url in receipt["downloads"].values())):
        raise RuntimeError("Index existant incohérent, aucun lien de lot publié")

    download_index_url = private_message_link(
        private_id, int(receipt["download_index_id"]))
    private_rows = batch_private_rows(public, download_index_url)
    cover_marker = marker + "_PRIVATE"
    if not receipt.get("private_cover_id"):
        prior = await _find_marked(user, private, cover_marker)
        if prior:
            receipt["private_cover_id"] = int(prior.id)
            receipt.pop("private_cover_uncertain", None)
            _save(series, catalogue, save_catalog)
        elif receipt.get("private_cover_uncertain"):
            raise RuntimeError("Envoi de l'affiche privée incertain")
        else:
            media = await user.download_media(poster.media, file=bytes)
            if not media:
                raise RuntimeError("Affiche source indisponible")
            stream = io.BytesIO(media)
            stream.name = "cinex_saison.jpg"
            receipt["private_cover_uncertain"] = True
            _save(series, catalogue, save_catalog)
            sent = await bot.send_file(
                private, stream, caption=rich_caption(description, private=True)
                + "\n" + cover_marker,
                buttons=make_button_keyboard(private_rows),
                parse_mode="html", force_document=False,
            )
            receipt["private_cover_id"] = int(sent.id)
            receipt.pop("private_cover_uncertain", None)
            _save(series, catalogue, save_catalog)
    cover = await user.get_messages(private, ids=int(receipt["private_cover_id"]))
    if (not getattr(cover, "photo", None)
            or cover_marker not in str(getattr(cover, "raw_text", "") or "")
            or _buttons_as_pairs(cover) != [row[0] for row in private_rows]):
        raise RuntimeError("Fiche privée de lot non conforme : trois boutons requis")
    return receipt


async def publish_public_season_batch(
    user, bot, public, private, private_id: int, series_key: str,
    series: dict, items: list, catalogue: dict, save_catalog, pause: float,
    *, kind: str, complete: bool,
):
    """One public poster, then each private-sourced video once, in episode order.

    A crash after a Telegram send is reconciled from the persisted receipt and
    real Telegram messages, never treated as proof that the post did not send.
    """
    from .publication import _recover_episode_public_video
    if not items:
        raise ValueError("Lot de publication vide")
    key = batch_identifier(series_key, int(items[0]["season"]), items)
    receipt = series.get("season_batches", {}).get(key)
    if not receipt or not receipt.get("private_cover_id") or not receipt.get("download_index_id"):
        raise RuntimeError("Lot privé non terminé : publication refusée")
    watch_url = private_message_link(private_id, int(receipt["private_cover_id"]))
    download_url = private_message_link(private_id, int(receipt["download_index_id"]))
    rows = batch_public_rows(public, watch_url, download_url, kind=kind)
    marker = "#" + key + "_PUBLIC"
    desc = batch_caption(str(series.get("title") or items[0]["title"]),
                         items, complete=complete, kind=kind)
    poster = next((r.get("poster") for r in items
                   if r.get("poster") is not None
                   and getattr(r["poster"], "photo", None)), None)
    if not poster:
        raise RuntimeError("Affiche authentique absente")
    if not receipt.get("public_cover_id"):
        prior = await _find_marked(user, public, marker, limit=350)
        if prior:
            receipt["public_cover_id"] = int(prior.id)
            receipt.pop("public_cover_uncertain", None)
            _save(series, catalogue, save_catalog)
        elif receipt.get("public_cover_uncertain"):
            raise RuntimeError("Publication affiche publique incertaine")
        else:
            photo = await user.download_media(poster.media, file=bytes)
            if not photo:
                raise RuntimeError("Affiche authentique non téléchargée")
            stream = io.BytesIO(photo)
            stream.name = "cinex_saison_public.jpg"
            receipt["public_cover_uncertain"] = True
            _save(series, catalogue, save_catalog)
            sent = await bot.send_file(
                public, stream,
                caption=rich_caption(desc) + "\n" + marker,
                parse_mode="html", buttons=make_button_keyboard(rows),
                force_document=False)
            receipt["public_cover_id"] = int(sent.id)
            receipt.pop("public_cover_uncertain", None)
            _save(series, catalogue, save_catalog)

    cover = await user.get_messages(public, ids=int(receipt["public_cover_id"]))
    if (not getattr(cover, "photo", None)
            or marker not in str(getattr(cover, "raw_text", "") or "")
            or _buttons_as_pairs(cover) != [r[0] for r in rows]):
        raise RuntimeError("Affiche publique non vérifiée : 4 boutons requis")

    for row in sorted(items, key=lambda r: int(r["episode"])):
        code = episode_code(row)
        saved = series.get("episodes", {}).get(str(row["season"]), {}).get(
            str(row["episode"]), {})
        private_mid = int(saved.get("message_id") or 0)
        if not private_mid:
            raise RuntimeError(f"Vidéo privée {code} absente avant publication")
        private_video = await user.get_messages(private, ids=private_mid)
        doc = video_document_id(private_video)
        if not is_video_message(private_video) or not doc:
            raise RuntimeError(f"Vidéo privée {code} invalide")
        existing = series.setdefault("public_episode_posts", {}).get(code)
        if existing:
            public_video = await user.get_messages(
                public, ids=int(existing.get("video") or 0))
            if (not is_video_message(public_video)
                    or video_document_id(public_video) != doc):
                raise RuntimeError(f"Reçu public {code} divergent")
            # Do not reshare historical episodes in a new incremental batch.
            receipt["public_videos"][code] = int(public_video.id)
            _save(series, catalogue, save_catalog)
            continue
        already = receipt["public_videos"].get(code)
        found = await user.get_messages(public, ids=int(already)) if already else None
        if not found:
            # After a timeout, recover only the matching document *following*
            # this exact batch cover. No guessing by title alone.
            found_id = await _recover_episode_public_video(
                user, public, int(receipt["public_cover_id"]), doc)
            if found_id:
                found = await user.get_messages(public, ids=int(found_id))
        if found and (not is_video_message(found)
                      or video_document_id(found) != doc
                      or _buttons_as_pairs(found) != [r[0] for r in rows]):
            raise RuntimeError(f"Reçu vidéo publique {code} non conforme")
        if not found:
            if receipt.setdefault("uncertain_videos", {}).get(code):
                raise RuntimeError(f"Vidéo publique {code} incertaine")
            receipt["uncertain_videos"][code] = True
            _save(series, catalogue, save_catalog)
            caption = caption_with_automatic_ttl(
                f"{'🌸' if kind == 'anime' else '📺'} "
                f"{str(series.get('title') or row['title'])} — {code}")
            result = await bot.copy_message(
                public, private, int(private_mid),
                caption=caption, parse_mode="html",
                buttons=make_button_keyboard(rows))
            mid = int(result.id)
            found = await user.get_messages(public, ids=mid)
            if (not is_video_message(found)
                    or video_document_id(found) != doc
                    or _buttons_as_pairs(found) != [r[0] for r in rows]):
                raise RuntimeError(f"Vidéo publique {code} envoyée non confirmée")
        receipt["public_videos"][code] = int(found.id)
        receipt.setdefault("uncertain_videos", {}).pop(code, None)
        series["public_episode_posts"][code] = {
            "poster": int(receipt["public_cover_id"]),
            "video": int(found.id), "private_video": private_mid,
            "batch": key,
        }
        _save(series, catalogue, save_catalog)
        if pause:
            await asyncio.sleep(pause)
    receipt["status"] = "complete"
    if not series.get("public_id"):
        series["public_id"] = int(receipt["public_cover_id"])
    season = str(items[0]["season"])
    series.setdefault("season_public_ids", {}).setdefault(
        season, int(receipt["public_cover_id"]))
    _save(series, catalogue, save_catalog)
    return receipt
