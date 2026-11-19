"""Ciné X: one private 'Secours' channel per owned public relay channel.

The account owner's existing Telethon session creates/recovers channels; bot posts
only link to invitations already verified and checkpointed in state.
No media is copied to the Secours channel (it is a fallback communication channel).
No Telegram side effects without --apply. Max one new channel per cycle.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import hashlib
import logging
import os
import re
from pathlib import Path
from urllib.parse import urlparse

LOG = logging.getLogger("cinex.rescue")
ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "state" / "rescue_channels.json"
INVITE_RE = re.compile(r"^https://t\.me/(?:\+[A-Za-z0-9_-]{12,}|joinchat/[A-Za-z0-9_-]{12,})/?$")
HANDLE_RE = re.compile(r"^@[A-Za-z][A-Za-z0-9_]{4,31}$")
BUTTON_TEXT = "🛟 Rejoindre le canal secours"
MAX_CREATED = 1
PAUSE_SECONDS = 60


def public_username(public) -> str | None:
    """Normalize resolved public channels or explicit @usernames; never guess IDs."""
    name = public if isinstance(public, str) else getattr(public, "username", None)
    if not name or not isinstance(name, str):
        return None
    name = name if name.startswith("@") else "@" + name
    if not HANDLE_RE.fullmatch(name):
        return None
    return name.lower()


def is_invite(url: str) -> bool:
    return isinstance(url, str) and bool(INVITE_RE.fullmatch(url.strip()))


def read_state(path: Path = STATE_PATH) -> dict:
    if not path.exists():
        return {"channels": {}}
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or not isinstance(state.get("channels"), dict):
        raise ValueError("État des canaux secours invalide")
    return state


def write_state(state: dict, path: Path = STATE_PATH) -> None:
    """Never commit any live Telegram invitation to the public repository."""
    safe = {"channels": {}}
    for username, original in state.get("channels", {}).items():
        row = dict(original)
        link = row.pop("invite_link", None)
        row.pop("invite", None)
        if is_invite(link):
            row["invite_sha256"] = hashlib.sha256(link.encode("utf-8")).hexdigest()
        safe["channels"][username] = row
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    temp.replace(path)


def rescue_link_for(public, *, path: Path = STATE_PATH) -> str | None:
    """The only source of buttons: verified, mapped private rescue invitations."""
    username = public_username(public)
    if not username:
        return None
    state = read_state(path)
    item = state["channels"].get(username)
    if not isinstance(item, dict):
        return None
    if public_username(item.get("public_username")) != username:
        raise ValueError("Rattachement de canal secours non conforme")
    if not str(item.get("rescue_channel_id", "")).startswith("-100"):
        return None
    runtime_path = os.getenv("CINEX_RESCUE_RUNTIME_FILE", "").strip()
    if not runtime_path:
        return None
    runtime = Path(runtime_path)
    if not runtime.is_file():
        return None
    receipt = json.loads(runtime.read_text(encoding="utf-8")).get("channels", {}).get(username)
    if not isinstance(receipt, dict):
        return None
    invite = receipt.get("url")
    if not is_invite(invite):
        return None
    if int(receipt.get("rescue_channel_id") or 0) != int(item["rescue_channel_id"]):
        return None
    expected = item.get("invite_sha256")
    if expected and hashlib.sha256(invite.encode("utf-8")).hexdigest() != expected:
        LOG.warning("Invitation Secours non conforme au canal %s", username)
        return None
    return invite.strip()


def add_rescue_tuple_row(rows, public, *, path: Path = STATE_PATH):
    """Append to tuple-based publication keyboard, preserving earlier buttons."""
    result = [list(row) for row in rows]
    link = rescue_link_for(public, path=path)
    if link and not any(any(url == link for _, url in row) for row in result):
        result.append([(BUTTON_TEXT, link)])
    return result


def add_rescue_button_row(rows, public, *, path: Path = STATE_PATH):
    """Append to BotHTTP / Telethon-style button keyboards."""
    from .bot_http import url_button
    result = [list(row) for row in rows]
    link = rescue_link_for(public, path=path)
    if link and not any(
        getattr(getattr(button, "button", button), "url", None) == link
        for row in result for button in row
    ):
        result.append([url_button(BUTTON_TEXT, link, style="primary")])
    return result


def targets_from_env(env: dict | None = None) -> list[str]:
    """Only owner-configured active channels and known official Ciné X channels.

    @seriesvf_cinex is provisioned separately even when a legacy series
    publisher still sends its posts to TG_PUBLIC_CHANNEL.
    """
    env = os.environ if env is None else env
    candidates = [
        (env.get("TG_PUBLIC_CHANNEL") if public_username(env.get("TG_PUBLIC_CHANNEL")) else "@CineXFilms_vf"),
        "@seriesvf_cinex",
        env.get("DESIR_PUBLIC_CHANNEL") or "@CineXDesirfr",
        env.get("COMEDIE_PUBLIC_CHANNEL") or "",
        env.get("ANIME_PUBLIC_CHANNEL") or "@CineXAnimeFR",
    ]
    if (str(env.get("CINEX_TORRENT9_PAUSED", "true")).lower() != "true"
            and str(env.get("CINEX_DEFER_MIRROR", "true")).lower() != "true"):
        candidates.append(env.get("TG_MIRROR_CHANNEL") or "@Torrent9SeriesFilms")
    targets = []
    seen = set()
    for item in candidates:
        name = public_username(item)
        if name is None:
            if item:
                raise ValueError("Identifiant public mal formé : " + repr(item))
            continue
        if name not in seen:
            seen.add(name)
            targets.append(name)
    return targets


def exact_private_candidates(dialogs: list, title: str):
    """Avoid hijacking an unrelated or public channel with the same title."""
    return [
        dialog.entity for dialog in dialogs
        if getattr(dialog.entity, "broadcast", False)
        and not getattr(dialog.entity, "username", None)
        and str(getattr(dialog.entity, "title", "")) == title
    ]


async def provision(*, apply: bool = False, max_created: int = MAX_CREATED):
    from telethon import TelegramClient, functions, utils
    from telethon.sessions import StringSession
    from telethon.errors import FloodWaitError, PeerFloodError

    state = read_state()
    targets = targets_from_env()
    report = {
        "mode": "apply" if apply else "simulation",
        "targets": len(targets), "existing": 0, "created": 0,
        "recovered": 0, "unavailable": 0, "errors": 0,
        "ready": 0,
    }
    credentials = (
        os.getenv("TG_API_ID", "").strip(),
        os.getenv("TG_API_HASH", "").strip(),
        (os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
         or os.getenv("TG_STREAM_SESSION") or "").strip()
    )
    if not all(credentials):
        raise RuntimeError("Session Telegram utilisateur absente")
    client = TelegramClient(
        StringSession(credentials[2]), int(credentials[0]), credentials[1],
        request_retries=1, connection_retries=2, flood_sleep_threshold=0,
    )
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session utilisateur expirée : aucun canal créé")
        me = await client.get_me()
        dialogs = [d async for d in client.iter_dialogs(limit=500)] if apply else []
        for username in targets:
            try:
                public = await client.get_entity(username)
                if not getattr(public, "broadcast", False):
                    raise ValueError("Destination non-broadcast")
                if public_username(public) != username:
                    raise ValueError("Identité publique Telegram différente")
                perm = await client.get_permissions(public, me)
                if not (getattr(perm, "is_creator", False) or (
                    getattr(perm, "is_admin", False)
                    and getattr(perm, "post_messages", False)
                    and getattr(perm, "edit_messages", False)
                )):
                    # Only channels with proven full publication/editing access.
                    raise ValueError("Le compte connecté n'a pas les droits administrateur de publication et modification")
                public_id = utils.get_peer_id(public)
                configured_films = str(os.getenv("TG_PUBLIC_CHANNEL", "")).strip()
                if username == "@cinexfilms_vf" and configured_films.startswith("-100"):
                    if int(configured_films) != public_id:
                        raise RuntimeError("Le canal Films ne correspond pas à son ID configuré")
                desired_title = str(getattr(public, "title", "") or "").strip() + " Secours"
                if not 8 <= len(desired_title) <= 128:
                    raise ValueError("Titre public Telegram invalide")
                entry = state["channels"].get(username)
                if entry and int(entry.get("public_id", 0)) != public_id:
                    raise RuntimeError("Canal public différent du checkpoint : refus de réaffectation")

                if not apply:
                    LOG.info("[SIMULATION] Canal de secours %s pour %s", desired_title, username)
                    if entry and entry.get("invite_sha256"):
                        report["ready"] += 1
                    continue

                candidates = exact_private_candidates(dialogs, desired_title)
                if len(candidates) > 1:
                    raise RuntimeError("Canaux secours homonymes : intervention manuelle requise")
                found = candidates[0] if candidates else None
                if entry and found is not None and utils.get_peer_id(found) != int(entry.get("rescue_channel_id", 0)):
                    raise RuntimeError("ID privé différent de la sauvegarde")
                if entry and found is None:
                    raise RuntimeError("Canal secours déjà enregistré mais absent de la session")
                if entry and found is not None and entry.get("invite_sha256"):
                    report["existing"] += 1
                    report["ready"] += 1
                    # Existing channels need ongoing profile synchronization too.
                    from .channel_profiles import sync_rescue_profile
                    await sync_rescue_profile(client, public, found, entry, pause=PAUSE_SECONDS)
                    write_state(state)
                    continue

                if found is None:
                    if report["created"] >= max_created:
                        LOG.info("Plafond de création atteint ; canal %s laissé pour plus tard", username)
                        continue
                    created = await client(functions.channels.CreateChannelRequest(
                        title=desired_title,
                        about="Canal privé de secours officiel du canal " + str(public.title),
                        broadcast=True, megagroup=False
                    ))
                    found = next(
                        (c for c in getattr(created, "chats", [])
                         if getattr(c, "broadcast", False) and str(c.title) == desired_title),
                        None
                    )
                    if found is None:
                        raise RuntimeError("Telegram n'a pas confirmé la création du canal")
                    report["created"] += 1
                    dialogs.append(type("RescueDialog", (), {"entity": found})())
                    await asyncio.sleep(PAUSE_SECONDS)
                else:
                    report["recovered"] += 1

                if getattr(found, "username", None):
                    raise RuntimeError("Canal secours doit rester privé")
                rescue_id = utils.get_peer_id(found)
                state["channels"][username] = {
                    "public_username": username, "public_id": public_id,
                    "public_title": str(public.title),
                    "rescue_title": desired_title, "rescue_channel_id": rescue_id,
                    "invite_sha256": (entry or {}).get("invite_sha256", ""),
                }
                # Save identity before getting the invite so interruptions don't
                # create duplicate channels on the next execution.
                write_state(state)
                from .rescue_links_runtime import get_existing_invite
                # Prefer existing owner-generated invitation; avoid replacing old public buttons.
                link = await get_existing_invite(
                    client, found, expected_sha=(entry or {}).get("invite_sha256"))
                if not link and not (entry or {}).get("invite_sha256"):
                    invite = await client(functions.messages.ExportChatInviteRequest(peer=found))
                    link = str(getattr(invite, "link", "") or "")
                if not is_invite(link):
                    raise RuntimeError("Lien Telegram d'invitation absent ; aucune nouvelle invitation publique créée")
                state["channels"][username]["invite_sha256"] = hashlib.sha256(
                    link.encode("utf-8")).hexdigest()
                write_state(state)
                from .channel_profiles import sync_rescue_profile
                await sync_rescue_profile(client, public, found, state["channels"][username],
                                          pause=PAUSE_SECONDS)
                write_state(state)
                report["ready"] += 1
                LOG.info("Secours enregistré : %s, ID=%s", desired_title, rescue_id)
                await asyncio.sleep(PAUSE_SECONDS)
            except (FloodWaitError, PeerFloodError):
                LOG.exception("Limitation Telegram : arrêt sans nouvelle tentative")
                raise
            except Exception as exc:
                report["errors"] += 1
                report["unavailable"] += 1
                LOG.warning("Secours %s ignoré : %s", username, exc)
        LOG.info("RÉSUMÉ CANAUX SECOURS %s", report)
        output = os.getenv("GITHUB_STEP_SUMMARY", "")
        if output:
            with open(output, "a", encoding="utf-8") as f:
                f.write("\n### Ciné X : canaux Secours\n" + "\n".join(
                    f"- {name}: {value}" for name, value in report.items()) + "\n")
        return report
    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Créer au maximum un canal secours")
    parser.add_argument("--max-created", type=int, default=MAX_CREATED)
    args = parser.parse_args()
    if args.max_created != 1:
        parser.error("1 canal nouveau maximum par exécution")
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(message)s")
    asyncio.run(provision(apply=args.apply, max_created=args.max_created))


if __name__ == "__main__":
    main()
