"""Verify newly recorded CinéX publications against Telegram (read-only).

A pass means the referenced public Telegram message AND private video still
exist. It never sends messages, and no-new-posts is a neutral outcome.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {
    "films": ("state.json", "processed", "TG_PRIVATE_CHANNEL", "TG_PUBLIC_CHANNEL",
              "private_message_id", "public_message_id"),
    "series": ("series_state.json", "completed", "TG_PRIVATE_CHANNEL", "TG_PUBLIC_CHANNEL",
               "video_id", "public_id"),
    "desir": ("desir_state.json", "completed", "DESIR_PRIVATE_CHANNEL", "DESIR_PUBLIC_CHANNEL",
              "video_id", "public_id"),
    "comedie": ("comedie_state.json", "completed", "COMEDIE_PRIVATE_CHANNEL", "COMEDIE_PUBLIC_CHANNEL",
                "video_id", "public_id"),
    "anime": ("anime_state.json", "completed", "ANIME_PRIVATE_CHANNEL", "ANIME_PUBLIC_CHANNEL",
              "video_id", "public_id"),
}


def receipts():
    result = {}
    for category, (filename, key, *_) in CATEGORIES.items():
        path = ROOT / "state" / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        result[category] = data.get(key, {})
        if not isinstance(result[category], dict):
            raise ValueError(f"{category}: historique invalide")
    return result


async def check_new_posts(before):
    from film_relay.runner import resolve_peer
    now = receipts()
    new = {name: {key: value for key, value in rows.items()
                  if key not in before.get(name, {})}
           for name, rows in now.items()}
    checked = 0
    checked_anime_episodes = 0
    failed = []
    details = {}
    anime_catalog_path = ROOT / "state" / "anime_catalog.json"
    anime_catalog = (json.loads(anime_catalog_path.read_text(encoding="utf-8"))
                     if anime_catalog_path.exists() else {"series": {}})
    # A crashed Anime batch must not appear successful just because no new
    # public card was written: the next scheduled run has to resume it.
    if anime_catalog.get("active_batch"):
        failed.append("anime : série en cours non terminée ; reprise prioritaire requise.")
    creds = (os.getenv("TG_API_ID"), os.getenv("TG_API_HASH"),
             os.getenv("TG_SESSION_STRING") or os.getenv("TG_SESSION_STRING_FALLBACK"))
    if not all(creds):
        raise RuntimeError("Session Telegram requise pour vérifier les reçus")
    async with TelegramClient(StringSession(creds[2]), int(creds[0]), creds[1]) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram non autorisée")
        for name, rows in new.items():
            if not rows:
                details[name] = {"new": 0, "verified": 0}
                continue
            filename, key, private_env, public_env, private_field, public_field = CATEGORIES[name]
            private_name, public_name = os.getenv(private_env), os.getenv(public_env)
            if not private_name or not public_name:
                failed.append(f"{name}: destinations Telegram manquantes")
                continue
            try:
                private = await resolve_peer(client, private_name)
                public = await resolve_peer(client, public_name)
            except Exception as exc:
                failed.append(f"{name}: canal inaccessible ({type(exc).__name__})")
                continue
            verified = 0
            for record_key, record in rows.items():
                try:
                    private_id = int(record[private_field])
                    public_id = int(record[public_field])
                    if not private_id or not public_id:
                        raise ValueError("identifiant nul")
                    private_message, public_message = await asyncio.gather(
                        client.get_messages(private, ids=private_id),
                        client.get_messages(public, ids=public_id),
                    )
                    if not private_message or not getattr(private_message, "media", None):
                        raise ValueError("vidéo privée absente")
                    if not public_message or getattr(public_message, "action", None):
                        raise ValueError("publication publique absente")
                    if name == "anime" and record_key.startswith(
                            ("anime-series:", "anime-season:")):
                        if record_key.startswith("anime-season:"):
                            title_key, season_label = record_key[
                                len("anime-season:"):].rsplit(":S", 1)
                            season_map = anime_catalog.get("series", {}).get(
                                title_key, {}).get("episodes", {}).get(
                                    str(int(season_label)), {})
                            seasons = [season_map]
                        else:
                            title_key = record_key.split("anime-series:", 1)[1]
                            entry = anime_catalog.get("series", {}).get(title_key, {})
                            seasons = list(entry.get("episodes", {}).values())
                        ids = [int(video["message_id"])
                               for season in seasons for video in season.values()]
                        if not 1 <= len(ids) <= 25:
                            raise ValueError("saison anime incomplète ou supérieure à 25 épisodes")
                        messages = await client.get_messages(private, ids=ids)
                        if not isinstance(messages, (list, tuple)):
                            messages = [messages]
                        if len(messages) != len(ids) or any(
                            not message or not getattr(message, "media", None)
                            for message in messages
                        ):
                            raise ValueError("au moins un épisode privé manque dans Telegram")
                        checked_anime_episodes += len(ids)
                    verified += 1
                    checked += 1
                except Exception as exc:
                    failed.append(f"{name}: reçu {record_key} non confirmé ({type(exc).__name__}: {exc})")
            details[name] = {"new": len(rows), "verified": verified}
    return {"status": "failed" if failed else ("verified" if checked else "no_new_posts"),
            "verified_posts": checked, "verified_anime_episodes": checked_anime_episodes,
            "categories": details, "errors": failed,
            "proof": "Telegram get_messages public et privé, sans nouveau message envoyé"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if bool(args.snapshot) == bool(args.verify):
        parser.error("Choisir --snapshot ou --verify")
    if args.snapshot:
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot.write_text(json.dumps({k: list(v) for k, v in receipts().items()}) + "\n")
        print("Références de publication enregistrées avant le cycle.")
        return
    before = json.loads(args.verify.read_text(encoding="utf-8"))
    result = asyncio.run(check_new_posts(before))
    print("Vérification Telegram réelle : " + json.dumps(result, ensure_ascii=False))
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write("\n### CinéX : vérification réelle de Telegram\n")
            out.write(f"- Résultat : {result['status']}\n")
            out.write(f"- Publications nouvelles vérifiées : {result['verified_posts']}\n")
            out.write(f"- Épisodes Anime réellement retrouvés : {result['verified_anime_episodes']}\n")
            for name, row in result["categories"].items():
                out.write(f"- {name} : {row['verified']}/{row['new']} vérifiées\n")
            for error in result["errors"]:
                out.write(f"- ERREUR : {error}\n")
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
