"""Transient Telegram invite lookup: never persist invite URLs in public Git.

All invitation URLs remain in runner-local memory / an untracked 0600 file.
The tracked ledger stores *only* SHA-256 fingerprints for identity checks.
A missing/revoked invite fails closed; never silently generates replacements.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import stat
from pathlib import Path

LOG = logging.getLogger("cinex.private_links")


def fingerprint(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def is_valid_invitation(url: str) -> bool:
    from .rescue_channels import is_invite
    return is_invite(url)


async def get_existing_invite(client, channel, *, expected_sha: str | None = None) -> str | None:
    """Read an existing owner-admin invitation; never rotate a live link."""
    from telethon import functions, types
    choices = []
    full = await client(functions.channels.GetFullChannelRequest(channel=channel))
    primary = getattr(getattr(full, "full_chat", None), "exported_invite", None)
    if is_valid_invitation(getattr(primary, "link", "")) and not getattr(primary, "revoked", False):
        choices.append(str(primary.link))
    if expected_sha and any(fingerprint(link) == expected_sha for link in choices):
        return next(link for link in choices if fingerprint(link) == expected_sha)
    try:
        response = await client(functions.messages.GetExportedChatInvitesRequest(
            peer=channel, admin_id=types.InputUserSelf(), limit=100, revoked=False
        ))
    except Exception:
        LOG.warning("Liste d'invitations inaccessible ; utilisation éventuelle de l'invitation primaire vérifiée")
        response = None
    for row in getattr(response, "invites", []):
        link = str(getattr(row, "link", "") or "")
        if is_valid_invitation(link) and not getattr(row, "revoked", False) and not getattr(row, "expire_date", None):
            choices.append(link)
    choices = list(dict.fromkeys(choices))
    if expected_sha:
        exact = [link for link in choices if fingerprint(link) == expected_sha]
        if len(exact) != 1:
            LOG.warning("Invitation existante absente ou révoquée ; aucune nouvelle invitation générée")
            return None
        return exact[0]
    # For unrecorded private channels, use the primary link when unambiguous.
    return choices[0] if len(choices) == 1 else None


def write_runtime(path: Path, data: dict):
    """Runner temporary storage with 0600 permission, never in git."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(data, output, ensure_ascii=False, sort_keys=True)
    except Exception:
        path.unlink(missing_ok=True)
        raise


async def hydrate(path: Path) -> dict:
    from telethon import TelegramClient, utils
    from telethon.sessions import StringSession
    from .rescue_channels import STATE_PATH, read_state

    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")
    session = os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING") or os.getenv("TG_STREAM_SESSION")
    if not api_id or not api_hash or not session:
        raise RuntimeError("Identifiants Telegram requis pour récupérer les liens Secours")
    data = read_state(STATE_PATH)["channels"]
    if not data:
        write_runtime(path, {"channels": {}})
        return {"ready": 0, "missing": 0}
    client = TelegramClient(StringSession(session), int(api_id), api_hash,
                            flood_sleep_threshold=0)
    links = {}
    missing = 0
    async with client:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram personnelle non autorisée")
        dialogs = [d async for d in client.iter_dialogs(limit=500)]
        by_id = {utils.get_peer_id(d.entity): d.entity for d in dialogs}
        for username, row in data.items():
            channel_id = int(row.get("rescue_channel_id") or 0)
            if channel_id not in by_id:
                missing += 1
                LOG.warning("Canal secours introuvable pour %s", username)
                continue
            channel = by_id[channel_id]
            if getattr(channel, "username", None) or not getattr(channel, "broadcast", False):
                missing += 1
                continue
            link = await get_existing_invite(client, channel,
                                             expected_sha=row.get("invite_sha256"))
            if not link:
                missing += 1
                continue
            links[username] = {
                "url": link, "invite_sha256": fingerprint(link),
                "rescue_channel_id": channel_id,
            }
    write_runtime(path, {"channels": links})
    LOG.info("Liens Secours récupérés en mémoire: %d ; indisponibles: %d", len(links), missing)
    return {"ready": len(links), "missing": missing}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    report = asyncio.run(hydrate(Path(args.output)))
    if report["missing"]:
        raise SystemExit("Certaines invitations sont indisponibles ; publications sans bouton Secours")


if __name__ == "__main__":
    main()
