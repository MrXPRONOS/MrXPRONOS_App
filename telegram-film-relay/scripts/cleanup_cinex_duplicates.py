"""Carefully remove *confirmed* duplicate CinéX posts from own destinations.

Safety:
- needs an exact processed source pair and its exact Telegram document ID;
- keeps checkpoint's canonical private video and canonical public message;
- verifies that the canonical public post links to the canonical private video;
- only deletes old private documents with the SAME document ID;
- removes the matching public references BEFORE old private copies;
- never deletes source channel posts or other movies;
- defaults to read-only; --apply must be explicit.
"""
from __future__ import annotations
import argparse
import asyncio
import os
from collections import defaultdict
from dataclasses import dataclass

from telethon import TelegramClient, utils
from telethon.sessions import StringSession

from film_relay.recovery import movie_document_id, referenced_private_messages
from film_relay.state import State


@dataclass(frozen=True)
class CleanupPlan:
    doc_id: int
    pair_id: str
    canonical_private: int
    canonical_public: int
    old_private_videos: tuple[int, ...]
    old_private_photos: tuple[int, ...]
    old_public_posts: tuple[int, ...]


def photo_matches(first, second) -> bool:
    if not (getattr(first, "photo", None) and getattr(second, "photo", None)):
        return False
    first_id = getattr(first.photo, "id", None)
    second_id = getattr(second.photo, "id", None)
    if first_id is not None and first_id == second_id:
        return True
    caption1 = " ".join(str(getattr(first, "raw_text", "") or "").split()).casefold()
    caption2 = " ".join(str(getattr(second, "raw_text", "") or "").split()).casefold()
    return bool(caption1 and len(caption1) >= 15 and caption1 == caption2)


def choose_plan(state, private_messages, public_messages, private_id):
    """Return at most one conservative cleanup plan (no Telegram mutations)."""
    private_by_id = {int(msg.id): msg for msg in private_messages}
    public_by_id = {int(msg.id): msg for msg in public_messages}
    candidates = []
    for media_key, pair_id in state.data.get("videos", {}).items():
        if not media_key.startswith("doc:"):
            continue
        entry = state.data.get("processed", {}).get(pair_id)
        if not entry:
            continue
        doc_id = int(media_key[4:])
        all_videos = sorted(
            int(msg.id) for msg in private_messages if movie_document_id(msg) == doc_id
        )
        if len(all_videos) <= 1:
            continue
        keep_video = int(entry["private_message_id"])
        keep_public = int(entry["public_message_id"])
        if keep_video not in all_videos or keep_public not in public_by_id:
            raise RuntimeError("Publication canonique absente : nettoyage annulé.")
        if keep_video not in referenced_private_messages(public_by_id[keep_public], private_id):
            raise RuntimeError("Lien de la publication conservée non vérifiable : nettoyage annulé.")
        old_videos = tuple(vid for vid in all_videos if vid != keep_video)
        old_photos = []
        canonical_photo = private_by_id.get(keep_video - 1)
        for video_id in old_videos:
            maybe_photo = private_by_id.get(video_id - 1)
            if photo_matches(maybe_photo, canonical_photo):
                old_photos.append(video_id - 1)
        # Only public posts which link to this very same document/video group.
        link_targets = set(all_videos)
        old_public = []
        for post in public_messages:
            msg_id = int(post.id)
            if msg_id == keep_public:
                continue
            if referenced_private_messages(post, private_id) & link_targets:
                old_public.append(msg_id)
        candidates.append(CleanupPlan(doc_id, pair_id, keep_video, keep_public,
                                      old_videos, tuple(sorted(set(old_photos))),
                                      tuple(sorted(set(old_public)))))
    if len(candidates) > 1:
        raise RuntimeError("Plusieurs groupes dupliqués : nettoyage automatique annulé.")
    return candidates[0] if candidates else None


async def execute(*, apply: bool) -> int:
    api_id = int(os.environ["TG_API_ID"])
    api_hash = os.environ["TG_API_HASH"]
    session = os.environ["TG_STRING_SESSION"]
    state = State(os.environ.get("STATE_PATH", "state/state.json"))
    client = TelegramClient(StringSession(session), api_id, api_hash,
                            request_retries=1, connection_retries=1,
                            flood_sleep_threshold=0)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram non autorisée.")
        private = await client.get_entity(int(os.environ["TG_PRIVATE_CHANNEL"]))
        public = await client.get_entity(os.environ["TG_PUBLIC_CHANNEL"])
        private_id = utils.get_peer_id(private)
        private_messages = [m async for m in client.iter_messages(private, limit=250)]
        public_messages = [m async for m in client.iter_messages(public, limit=250)]
        plan = choose_plan(state, private_messages, public_messages, private_id)
        if not plan:
            print("AUDIT : aucun groupe de copies identiques correspondant au suivi ; aucun changement.")
            return 0
        print(
            f"Nettoyage ciblé de la paire {plan.pair_id} : "
            f"conserver vidéo privée {plan.canonical_private}, "
            f"post public {plan.canonical_public}; "
            f"supprimer {len(plan.old_private_videos)} vidéos anciennes, "
            f"{len(plan.old_private_photos)} affiches associées vérifiées, "
            f"{len(plan.old_public_posts)} publications publiques obsolètes."
        )
        if not apply:
            print("APERÇU UNIQUEMENT — AUCUNE SUPPRESSION. "
                  "La suppression doit être expressément activée dans le workflow.")
            return 0
        if plan.old_public_posts:
            await client.delete_messages(public, list(plan.old_public_posts))
        private_remove = [*plan.old_private_videos, *plan.old_private_photos]
        if private_remove:
            await client.delete_messages(private, sorted(set(private_remove)))
        print(
            "NETTOYAGE TERMINÉ : anciennes copies identiques retirées ; "
            "publication canonique et source d'origine conservées."
        )
        return 0
    finally:
        await client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(execute(apply=args.apply)))
