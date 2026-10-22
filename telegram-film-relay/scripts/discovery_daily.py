"""Découverte quotidienne CinéX : 5 catégories, une session, un récapitulatif privé.

Lecture seule des canaux publics : aucun abonnement, média copié ou transfert.
Un message HTML par jour (même si aucun nouveau canal), avec un marqueur
idempotent aussi vérifié directement dans les Messages enregistrés Telegram.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import FloodWaitError, PeerFloodError
from telethon.sessions import StringSession

from film_relay.discovery import discover, load_config, normalize_username

LOG = logging.getLogger("cinex_discovery_daily")
ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/discovery_daily.json"
LEGACY_CONFIG = ROOT / "config/discovery.json"
STATE = ROOT / "state/discovery_daily_state.json"
LEGACY_REPORT = ROOT / "state/discovered_channels.json"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def categories() -> list[dict]:
    cfg = read_json(CONFIG)
    names = tuple(c["id"] for c in cfg.get("categories", []))
    if names != ("films", "desir", "comedie", "anime", "series"):
        raise ValueError("La recherche doit contenir les cinq catégories dans l'ordre.")
    if any(not c.get("queries") or len(c["queries"]) > 3 for c in cfg["categories"]):
        raise ValueError("Chaque catégorie doit contenir de 1 à 3 recherches.")
    return cfg["categories"]


def make_category_cfg(category: dict, settings: dict) -> dict:
    cfg = load_config(str(LEGACY_CONFIG))
    cfg["search_queries"] = list(category["queries"])
    cfg["seed_channels"] = []
    cfg["results_per_query"] = max(1, min(10, int(settings.get("results_per_query", 8))))
    cfg["max_channels_per_run"] = max(1, min(10, int(settings.get("max_channels_per_category", 6))))
    cfg["sample_messages"] = max(10, min(65, int(settings.get("sample_messages", 55))))
    cfg["request_pause_seconds"] = max(10.0, float(settings.get("pause_seconds", 12)))
    cfg["include_unverified"] = True  # Indiquer explicitement la vérification du format.
    if category["id"] == "anime":
        cfg["min_video_minutes"] = 10
        cfg["min_video_megabytes"] = 30
        cfg["min_caption_chars"] = 15
    if category["id"] == "series":
        cfg["min_video_minutes"] = 20
        cfg["min_video_megabytes"] = 70
        cfg["min_caption_chars"] = 15
    return cfg


def format_report(day: str, sections: list[dict], known: set[str]) -> str:
    lines = [
        "🔎 <b>CINÉX — DÉCOUVERTE QUOTIDIENNE</b>",
        "<i>Recherche de canaux publics, organisée par catégorie.</i>",
        f"<code>CINEX-DECOUVERTE-{day}</code>",
    ]
    total = 0
    fresh = 0
    for section in sections:
        entries = section["channels"]
        total += len(entries)
        lines.extend(("", f"<b>{escape(section['label'])} — {len(entries)} canal(aux)</b>"))
        if not entries:
            lines.append("<i>Aucun canal correspondant trouvé lors de ce passage.</i>")
            continue
        if len(entries) > 3:
            lines.append("<i>3 liens affichés ; autres candidats conservés dans l'historique.</i>")
        for entry in entries[:3]:
            name = normalize_username(entry.get("username", ""))
            if not name:
                continue
            key = name.casefold()
            new = key not in known
            fresh += int(new)
            status = "🆕" if new else "↩️"
            title = escape(str(entry.get("title") or name)[:52])
            verification = ("<i>Format affiche/vidéo repéré</i>" if entry.get("format_verified")
                            else "<i>Canal candidat : format non confirmé</i>")
            url = "https://t.me/" + name
            lines.extend((
                f"{status} <b>{title}</b>",
                f'🔗 <a href="{url}">{url}</a>',
                verification,
            ))
    lines.extend((
        "",
        f"📊 <b>Bilan : {total} canal(aux) examinés — {fresh} nouveau(x) dans cette sélection.</b>",
        "<i>Résultats à contrôler manuellement. Aucun canal rejoint ; droits de redistribution non vérifiés.</i>",
    ))
    report = "\n".join(lines)
    if len(report.encode("utf-8")) > 3900:
        raise ValueError("Récapitulatif trop long pour Telegram : réduire le quota de canaux.")
    return report


async def in_saved_messages(client, marker: str) -> bool:
    async for msg in client.iter_messages("me", limit=35):
        if marker in (getattr(msg, "raw_text", "") or ""):
            return True
    return False


async def run() -> int:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    marker = "CINEX-DECOUVERTE-" + day
    settings = read_json(CONFIG)
    groups = categories()
    state = read_json(STATE)
    if state.get("last_notification_day") == day:
        LOG.info("Déjà notifié le %s : aucun second envoi aujourd'hui.", day)
        return 0

    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")
    sid = (os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
           or os.getenv("TG_STREAM_SESSION"))
    if not (api_id and api_hash and sid):
        raise RuntimeError("Identifiants Telegram non configurés.")
    client = TelegramClient(StringSession(sid), int(api_id), api_hash,
                            request_retries=0, connection_retries=2,
                            flood_sleep_threshold=0, receive_updates=False)
    sections = []
    previous_known = set(state.get("known_usernames", []))
    if not previous_known:
        legacy = read_json(LEGACY_REPORT)
        previous_known.update(str(v.get("username", "")).lower()
                              for v in legacy.get("channels", []) if v.get("username"))
    offsets = state.get("offsets") or {}
    all_names = set()
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram expirée.")

        # Une relance après un envoi partiellement sauvegardé n'enverra jamais
        # un second digest. Lecture de quelques Messages enregistrés seulement.
        if await in_saved_messages(client, marker):
            state["last_notification_day"] = day
            save_json(STATE, state)
            LOG.info("Digest déjà visible dans Messages enregistrés, aucun doublon.")
            return 0

        for category in groups:
            ident = category["id"]
            cfg = make_category_cfg(category, settings)
            LOG.info("Recherche %s — %s expression(s)", ident, len(cfg["search_queries"]))
            entries, stats = await discover(client, cfg, start_offset=int(offsets.get(ident, 0)))
            if stats.get("rate_limited"):
                LOG.error("Limitation Telegram pendant %s : arrêt, aucune nouvelle requête.", ident)
                return 2
            offsets[ident] = int(stats.get("next_candidate_offset", 0))
            seen_in_category = set()
            valid = []
            for entry in entries:
                name = normalize_username(entry.get("username", ""))
                if name and name.lower() not in seen_in_category:
                    entry["category"] = ident
                    valid.append(entry)
                    all_names.add(name.lower())
                    seen_in_category.add(name.lower())
            sections.append({"id":ident, "label":category["label"],
                             "channels":valid,"statistics":stats})
            LOG.info("Catégorie %s : %s résultat(s), %s canaux lus",
                     ident, len(valid), stats.get("checked", 0))
            await asyncio.sleep(max(10.0, float(settings.get("pause_seconds", 12))))

        digest = format_report(day, sections, previous_known)
        await client.send_message("me", digest, parse_mode="html", link_preview=False)
        LOG.info("Récapitulatif privé envoyé pour les quatre catégories.")
        state["last_notification_day"] = day
        state["last_scan"] = datetime.now(timezone.utc).isoformat()
        state["offsets"] = offsets
        state["known_usernames"] = sorted(previous_known | all_names)
        state["categories"] = {
            sec["id"]: {"channels":sec["channels"],"statistics":sec["statistics"]}
            for sec in sections
        }
        save_json(STATE, state)
        return 0
    except (FloodWaitError, PeerFloodError) as exc:
        LOG.error("Telegram a limité le compte (%s) : aucun retry.", type(exc).__name__)
        return 2
    finally:
        await client.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level="INFO", format="%(asctime)s | %(levelname)s | %(message)s")
    raise SystemExit(asyncio.run(run()))
