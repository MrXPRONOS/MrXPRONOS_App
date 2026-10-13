#!/usr/bin/env python3
"""Prospection prudente de canaux publics Telegram (football Afrique francophone).
Lecture uniquement. Aucune adhésion, aucun message, aucun accès aux membres.
Lancement manuel; session utilisateur dans les secrets d'environnement.
"""
import argparse
import asyncio
import csv
import json
import os
import re
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import Channel

UTC = timezone.utc
SEARCH_TERMS = (
    "foot togo", "foot burkina", "foot benin",
    "foot afrique", "pronostic foot", "prono afrique",
)
SEED_USERNAMES = (
    "FootAfrica", "Benfootrobot", "remapronostics0",
    "caf_pronos", "louise_prono", "CanalPlusSportInfos",
)
COUNTRIES = {
    "Togo": ("togo", "togolais", "lomé", "lome", "+228", "🇹🇬"),
    "Burkina Faso": ("burkina", "ouaga", "ouagadougou", "burkinab", "+226", "🇧🇫"),
    "Bénin": ("bénin", "benin", "béninois", "beninois", "cotonou", "+229", "🇧🇯"),
    "Côte d'Ivoire": ("ivoire", "ivoirien", "abidjan", "+225", "🇨🇮"),
    "Sénégal": ("sénégal", "senegal", "dakar", "+221", "🇸🇳"),
    "Mali": ("mali", "bamako", "+223", "🇲🇱"),
    "Cameroun": ("cameroun", "douala", "yaoundé", "yaounde", "+237", "🇨🇲"),
}
NEWS = ("actualit", "mercato", "foot", "football", "ligue", "champion", "match", "score", "transfert")
BET = ("pronostic", "prono", "pari", "cote", "combiné", "combine", "coupon", "bookmaker", "1xbet", "melbet")
SALE_PATTERNS = (
    r"(?i)\b(?:je vends|nous vendons|mis(?:e)? en vente)\b.{0,50}\b(?:canal|chaine|chaîne)\b",
    r"(?i)\b(?:canal|chaine|chaîne)\b.{0,35}\b(?:à vendre|a vendre|en vente)\b",
)


def normalize_username(text):
    text = re.sub(r"^https?://(?:www\.)?t\.me/(?:s/)?", "", (text or "").strip(), flags=re.I)
    text = text.lstrip("@").split("/")[0].split("?")[0]
    if not re.fullmatch(r"[a-zA-Z0-9_]{5,32}", text):
        raise ValueError("Nom de canal invalide")
    return text


def classify(text):
    lowered = text.lower()
    news = sum(lowered.count(word) for word in NEWS)
    bet = sum(lowered.count(word) for word in BET)
    if bet > news and bet >= 2:
        return "pronostics"
    if news >= bet and news >= 2:
        return "actualités football"
    return "mixte ou à vérifier"


def evaluate(entity, messages, now):
    title = getattr(entity, "title", "") or ""
    username = getattr(entity, "username", "") or ""
    subscriber_count = getattr(entity, "participants_count", None)
    sample = " ".join(((m.raw_text or "")[:350]) for m in messages)
    combined = title + " " + sample
    regions = [country for country, terms in COUNTRIES.items()
               if any(term in combined.lower() for term in terms)]
    age_limit = now - timedelta(days=14)
    mature = [m for m in messages if m.date and age_limit <= m.date.astimezone(UTC)
              <= now - timedelta(hours=24) and isinstance(m.views, int)]
    reach = int(statistics.median([m.views for m in mature])) if mature else None
    views_ratio = (round(100 * reach / subscriber_count, 2)
                   if reach is not None and isinstance(subscriber_count, int) and subscriber_count else None)
    last_post = max((m.date.astimezone(UTC) for m in messages if m.date), default=None)
    sale_hits = []
    for m in messages:
        text = (m.raw_text or "").replace("\n", " ")
        if any(re.search(pattern, text) for pattern in SALE_PATTERNS):
            sale_hits.append({
                "lien": f"https://t.me/{username}/{m.id}",
                "extrait": text[:180],
            })
    return {
        "canal": title, "username": username, "lien": f"https://t.me/{username}",
        "categorie": classify(combined), "abonnés": subscriber_count,
        "vues_medianes_posts_1_14j": reach, "ratio_vues_pct": views_ratio,
        "publications_lues": len(messages),
        "derniere_publication_utc": last_post.isoformat() if last_post else None,
        "pays_evoques_dans_contenu": regions,
        "pays_reels_des_abonnes_verifies": False,
        "indices_annonce_vente": sale_hits[:2],
        "vente_confirmee": False,
    }


def safe_cell(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def save_report(out_dir, rows, meta):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rapport.json").write_text(
        json.dumps({"meta": meta, "canaux": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    fields = ("canal", "username", "lien", "categorie", "abonnés",
              "vues_medianes_posts_1_14j", "ratio_vues_pct",
              "publications_lues", "derniere_publication_utc",
              "pays_evoques_dans_contenu", "pays_reels_des_abonnes_verifies",
              "vente_confirmee", "indices_annonce_vente")
    with (out / "rapport.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: safe_cell(row.get(key)) for key in fields})


async def scan(max_searches, max_channels, max_posts, pause, out):
    api_id = os.getenv("TG_API_ID", "").strip()
    api_hash = os.getenv("TG_API_HASH", "").strip()
    session_string = os.getenv("TG_SESSION_STRING", "").strip()
    if not (api_id.isdecimal() and api_hash and session_string):
        raise RuntimeError("Secrets GitHub requis: TG_API_ID, TG_API_HASH, TG_SESSION_STRING")
    started = datetime.now(UTC)
    meta = {"debut_utc": started.isoformat(), "mode": "lecture_publique_seulement",
            "recherches_max": max_searches, "canaux_max": max_channels,
            "posts_par_canal_max": max_posts, "erreurs": [], "flood_wait": None}
    rows, candidates = [], {}
    client = TelegramClient(
        StringSession(session_string), int(api_id), api_hash,
        request_retries=0, connection_retries=2, flood_sleep_threshold=0,
        receive_updates=False,
    )
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram révoquée/non autorisée. Aucune reconnexion automatique.")
        for handle in SEED_USERNAMES[:min(len(SEED_USERNAMES), max_channels)]:
            try:
                entity = await client.get_entity(normalize_username(handle))
                if isinstance(entity, Channel) and entity.broadcast and entity.username:
                    candidates[entity.username.lower()] = entity
            except errors.FloodWaitError:
                raise
            except (errors.RPCError, ValueError) as exc:
                meta["erreurs"].append(f"seed @{handle}: {type(exc).__name__}")
            await asyncio.sleep(pause)
        for term in SEARCH_TERMS[:max_searches]:
            if len(candidates) >= max_channels:
                break
            result = await client(SearchRequest(q=term, limit=8))
            for channel in result.chats:
                if (isinstance(channel, Channel) and channel.broadcast and
                        channel.username and channel.username.lower() not in candidates):
                    candidates[channel.username.lower()] = channel
                    if len(candidates) >= max_channels:
                        break
            await asyncio.sleep(pause)
        for entity in list(candidates.values())[:max_channels]:
            try:
                messages = await client.get_messages(entity, limit=max_posts)
                rows.append(evaluate(entity, messages, datetime.now(UTC)))
            except errors.FloodWaitError:
                raise
            except (errors.RPCError, ValueError) as exc:
                meta["erreurs"].append(f"analyse @{entity.username}: {type(exc).__name__}")
            await asyncio.sleep(pause)
    except errors.FloodWaitError as exc:
        meta["flood_wait"] = exc.seconds
        meta["erreurs"].append("Limitation Telegram: arrêt immédiat, aucun nouvel appel.")
    except errors.PeerFloodError:
        meta["erreurs"].append("Restriction compte Telegram: arrêt immédiat.")
    finally:
        await client.disconnect()
        rows.sort(key=lambda item: (
            not bool(item["pays_evoques_dans_contenu"]),
            -(item["ratio_vues_pct"] if item["ratio_vues_pct"] is not None else -1),
            -(item["vues_medianes_posts_1_14j"] or 0)
        ))
        meta["fin_utc"] = datetime.now(UTC).isoformat()
        meta["canaux_analyses"] = len(rows)
        save_report(out, rows, meta)
    print(f"TELEGRAM_DISCOVERY canaux={len(rows)} recherches_max={max_searches} "
          f"flood_wait={meta['flood_wait']} rapport={out}/rapport.json")


def main():
    parser = argparse.ArgumentParser(description="Découverte prudente de canaux publics")
    parser.add_argument("--max-searches", type=int, default=6, choices=range(1, 7))
    parser.add_argument("--max-channels", type=int, default=12, choices=range(1, 13))
    parser.add_argument("--max-posts", type=int, default=20, choices=range(5, 26))
    parser.add_argument("--pause", type=float, default=5.0)
    parser.add_argument("--out", default="telegram_research_out")
    args = parser.parse_args()
    if args.pause < 5.0 or args.pause > 30.0:
        parser.error("Pause obligatoire de 5 à 30 secondes entre appels")
    asyncio.run(scan(args.max_searches, args.max_channels, args.max_posts, args.pause, args.out))


if __name__ == "__main__":
    main()
