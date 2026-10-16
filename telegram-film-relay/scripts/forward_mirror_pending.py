"""One-time safe bootstrap: forward only existing primary public posts to mirror.

No MKV upload, no public poster creation. Deduplicate by Telegram's native
forward origin headers, even if GitHub's mirror checkpoint is stale.
"""
from __future__ import annotations
import asyncio
import os
from telethon import TelegramClient, utils
from telethon.sessions import StringSession
from film_relay.runner import forward_public_message
from film_relay.recovery import existing_native_forwards
from film_relay.state import State


async def run() -> int:
    session = os.environ["TG_STRING_SESSION"]
    source = os.environ["TG_PUBLIC_CHANNEL"]
    destination = os.getenv("TG_MIRROR_CHANNEL", "@Torrent9SeriesFilms")
    if destination.casefold() == "@torrent9seriesfilm":
        destination = "@Torrent9SeriesFilms"
    client = TelegramClient(StringSession(session), int(os.environ["TG_API_ID"]),
                            os.environ["TG_API_HASH"], connection_retries=1,
                            request_retries=1, flood_sleep_threshold=0)
    state = State(os.environ.get("STATE_PATH", "state/state.json"))
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram user session is not authorized")
        origin = await client.get_entity(source)
        mirror = await client.get_entity(destination)
        if utils.get_peer_id(origin) == utils.get_peer_id(mirror):
            raise RuntimeError("Primary and secondary channels must be different")
        if getattr(origin, "noforwards", False):
            raise RuntimeError("Public origin disallows native forwarding")
        own = await client.get_me()
        perms = await client.get_permissions(mirror, own)
        if not (getattr(perms, "is_creator", False) or
                (getattr(perms, "is_admin", False) and
                 getattr(perms, "post_messages", False))):
            raise RuntimeError("Telegram account lacks rights to post in mirror")
        target_id = str(utils.get_peer_id(mirror))
        present = await existing_native_forwards(
            client, mirror, utils.get_peer_id(origin)
        )
        attempted = forwarded = skipped = 0
        for pair_id, public_id in state.pending_mirrors(target_id, limit=10):
            attempted += 1
            existing_id = present.get(public_id)
            if existing_id:
                state.mark_mirrored(pair_id, target_id, existing_id)
                skipped += 1
                print(f"Déjà transféré : public={public_id} ; reçu réparé.")
                continue
            copied_id = await forward_public_message(client, origin, mirror, public_id)
            state.mark_mirrored(pair_id, target_id, copied_id)
            present[public_id] = copied_id
            forwarded += 1
            print(f"Transfert attribué : public={public_id} → secondaire={copied_id}")
            await asyncio.sleep(1)
        print(f"RÉSULTAT MIROIR : à examiner={attempted}, transférés={forwarded}, "
              f"doublons empêchés={skipped}. Aucun nouveau MKV ni poster original envoyé.")
        return 0
    finally:
        await client.disconnect()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
