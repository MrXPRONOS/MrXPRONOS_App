"""Audit and reconcile GitHub-configured bots on the seven CineX public + Secours pairs.

Only known, verified Telegram bots (Bot API getMe) and exact saved channel IDs.
No arbitrary GitHub secrets, no unrelated/source/stock channels, no media actions.
Private invites and secret token values are never logged. Dry-run is default.
On apply, new admins receive *post only* rights and existing admin powers are
not revoked. Any Telegram FloodWait stops the run without retry/circumvention.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from film_relay.cinex_v4_policy import MAIN_RELAY_HANDLES
from film_relay.rescue_channels import read_state, public_username
from film_relay.rescue_links_runtime import recover_checkpoint_peer
from scripts.add_private_stock_bots import BOT_SECRETS, discover_bot_candidates, USERNAME
from scripts.provision_private_stock import bot_identity

LOG = logging.getLogger("cinex.bot_admins")
EXTRA_BOT_SECRETS = (
    ("mrx_channel", "MRXPRONOS_CANAL_BOT_TOKEN"),
    ("editorial", "EDITORIAL_TELEGRAM_BOT_TOKEN"),
    ("partnership", "PARTNERSHIP_BOT_TOKEN"),
    ("anime_source", "CINEX_ANIME_SOURCE_BOT_TOKEN"),
    ("radar_alt", "CINE_RADAR_BOT_TOKEN"),
    ("canal", "CANAL_BOT_TOKEN"),
)
ALL_BOT_SECRETS = BOT_SECRETS + EXTRA_BOT_SECRETS
# The existing GitHub reaction workflow exposes slots 03..99 and an optional
# JSON bundle for further numbered bots. Only nonempty values are inspected.
REACTION_BOT_SECRETS = tuple(
    (f"reaction_{number:02d}", f"TELEGRAM_REACTION_BOT_{number:02d}_TOKEN")
    for number in range(3, 100)
)
REACTION_BUNDLE_KEY = "TELEGRAM_REACTION_BOTS_JSON"
# The new Fichiers Cloud Secours must be checked first, before existing Secours.
PRIORITY = ("@fichiers_cloud",)


def discover_network_bots(env=None, identify=None):
    env = os.environ if env is None else env
    identify = bot_identity if identify is None else identify
    base, missing, invalid = discover_bot_candidates(env, identify)
    seen = {int(bot["id"]) for bot in base}
    result = list(base)

    def add_verified(label, token):
        try:
            item = identify(token)
            uid = item.get("id")
            username = str(item.get("username") or "")
            if (item.get("is_bot") is not True or type(uid) is not int
                or uid <= 0 or not USERNAME.fullmatch(username)):
                raise ValueError("bot_identity_invalid")
            if uid not in seen:
                result.append({"id": uid, "username": username, "label": label})
                seen.add(uid)
        except Exception:
            invalid.append(label)

    for label, key in EXTRA_BOT_SECRETS:
        token = str(env.get(key) or "").strip()
        if not token:
            missing.append(label)
            continue
        add_verified(label, token)

    # Numbered reaction bots are GitHub secrets too. A previously unknown
    # reaction bot is not trusted by its slot name alone: Telegram getMe must
    # match a real bot account. Never print the token or its Bot API URL.
    reaction_tokens = {}
    for label, key in REACTION_BOT_SECRETS:
        token = str(env.get(key) or "").strip()
        if token:
            reaction_tokens[int(label.split("_")[1])] = (label, token)

    bundle = str(env.get(REACTION_BUNDLE_KEY) or "").strip()
    if bundle:
        try:
            parsed = json.loads(bundle)
            if not isinstance(parsed, dict):
                raise ValueError("reaction_bundle_not_a_mapping")
            for slot, token in parsed.items():
                if (not str(slot).isdecimal() or int(slot) < 3
                    or int(slot) > 9999 or not isinstance(token, str)):
                    raise ValueError("reaction_bundle_invalid_slot")
                token = token.strip()
                if token and int(slot) not in reaction_tokens:
                    reaction_tokens[int(slot)] = (f"reaction_{int(slot):02d}", token)
        except (ValueError, TypeError):
            raise RuntimeError("reaction_bot_secret_bundle_invalid") from None

    seen_tokens = set()
    for slot in sorted(reaction_tokens):
        label, token = reaction_tokens[slot]
        if token in seen_tokens:
            continue
        seen_tokens.add(token)
        add_verified(label, token)
    return result, missing, invalid

def validated_checkpoints():
    state = read_state()["channels"]
    if set(state) != MAIN_RELAY_HANDLES:
        raise RuntimeError("seven_official_checkpoints_required")
    for name, row in state.items():
        if (public_username(row.get("public_username")) != name
            or not str(row.get("public_id") or "").startswith("-100")
            or not str(row.get("rescue_channel_id") or "").startswith("-100")
            or not str(row.get("rescue_title") or "").endswith(" Secours")):
            raise RuntimeError("invalid_rescue_checkpoint")
    return state


def minimal_rights():
    from telethon.tl.types import ChatAdminRights
    return ChatAdminRights(
        change_info=False, post_messages=True, edit_messages=False,
        delete_messages=False, ban_users=False, invite_users=False,
        pin_messages=False, add_admins=False, anonymous=False,
        manage_call=False, other=False, manage_topics=False,
        post_stories=False, edit_stories=False, delete_stories=False,
    )


def admin_with_post_rights(current):
    """Keep existing admin permissions and add post_messages, never downgrade."""
    from telethon.tl.types import ChatAdminRights
    keys = (
        "change_info", "edit_messages", "delete_messages", "ban_users",
        "invite_users", "pin_messages", "add_admins", "anonymous",
        "manage_call", "other", "manage_topics", "post_stories",
        "edit_stories", "delete_stories",
    )
    return ChatAdminRights(post_messages=True, **{
        name: bool(getattr(current, name, False)) for name in keys
    })


async def participant_rights(client, channel, bot):
    from telethon.tl.functions.channels import GetParticipantRequest
    from telethon.errors import UserNotParticipantError
    try:
        member = await client(GetParticipantRequest(channel=channel, participant=bot))
        p = member.participant
        return p, getattr(p, "admin_rights", None)
    except UserNotParticipantError:
        return None, None


async def identify_targets(client, checkpoint, owner):
    from telethon import utils
    dialogs = [d async for d in client.iter_dialogs(limit=500)]
    by_id = {utils.get_peer_id(d.entity): d.entity for d in dialogs}
    targets = []
    handles = PRIORITY + tuple(sorted(MAIN_RELAY_HANDLES - set(PRIORITY)))
    for name in handles:
        row = checkpoint[name]
        public = await client.get_entity(name)
        if (not getattr(public, "broadcast", False)
            or public_username(public) != name
            or utils.get_peer_id(public) != int(row["public_id"])):
            raise RuntimeError("public_channel_identity_mismatch")
        rescue = await recover_checkpoint_peer(client, by_id, row)
        if rescue is None:
            raise RuntimeError("rescue_channel_identity_unavailable")
        for kind, channel in (("rescue", rescue), ("main", public)):
            permissions = await client.get_permissions(channel, owner)
            if not (getattr(permissions, "is_creator", False) or (
                getattr(permissions, "is_admin", False)
                and getattr(permissions, "add_admins", False)
            )):
                raise RuntimeError("owner_cannot_add_admins")
            targets.append((name, kind, channel))
    return targets


async def run(*, apply=False, pause=12, max_changes=220):
    from telethon import TelegramClient, functions
    from telethon.sessions import StringSession
    from telethon.errors import FloodWaitError, PeerFloodError, UserNotParticipantError

    candidates, missing, invalid = discover_network_bots()
    if not candidates:
        raise RuntimeError("no_verified_configured_bots")
    if invalid:
        raise RuntimeError("invalid_bot_tokens_or_identity")
    if len(candidates) > 30:
        raise RuntimeError("unexpected_bot_inventory_growth")
    if not 5 <= pause <= 120 or not 1 <= max_changes <= 220:
        raise ValueError("invalid_rate_limits")
    checkpoint = validated_checkpoints()
    api_id = os.getenv("TG_API_ID", "").strip()
    api_hash = os.getenv("TG_API_HASH", "").strip()
    session = (os.getenv("TG_STRING_SESSION") or
               os.getenv("TG_SESSION_STRING") or
               os.getenv("TG_STREAM_SESSION") or "").strip()
    if not api_id.isdecimal() or not api_hash or not session:
        raise RuntimeError("owner_personal_session_not_configured")
    print("CINEX_BOT_INVENTORY", "known_standard_secret_names", len(ALL_BOT_SECRETS),
          "reaction_slot_names", len(REACTION_BOT_SECRETS),
          "configured_reaction_slots", sum(bool(os.getenv(k)) for _, k in REACTION_BOT_SECRETS),
          "reaction_bundle_present", bool(os.getenv(REACTION_BUNDLE_KEY)),
          "distinct_verified_bots", len(candidates),
          "secret_slots_absent", len(missing),
          "standard_secrets_present", len(ALL_BOT_SECRETS) - len(missing))
    client = TelegramClient(StringSession(session), int(api_id), api_hash,
                            flood_sleep_threshold=0, request_retries=1,
                            connection_retries=2)
    await client.connect()
    total_verified = total_updated = total_missing = total_failed = 0
    rows = []
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("owner_personal_session_not_authorized")
        owner = await client.get_me()
        if owner is None or getattr(owner, "bot", False):
            raise RuntimeError("expected_personal_user_session")
        targets = await identify_targets(client, checkpoint, owner)
        for name, kind, channel in targets:
            counters = {"already_admin": 0, "promoted": 0,
                        "missing_admin": 0, "errors": 0}
            for entry in candidates:
                try:
                    bot = await client.get_entity("@" + entry["username"])
                    if not getattr(bot, "bot", False) or int(bot.id) != entry["id"]:
                        raise RuntimeError("bot_identity_changed")
                    member, rights = await participant_rights(client, channel, bot)
                    is_admin = rights is not None or type(member).__name__ == "ChannelParticipantCreator"
                    can_post = is_admin and bool(getattr(rights, "post_messages", True))
                    if is_admin and can_post:
                        counters["already_admin"] += 1
                        total_verified += 1
                        continue
                    counters["missing_admin"] += 1
                    total_missing += 1
                    if not apply:
                        continue
                    if total_updated >= max_changes:
                        raise RuntimeError("maximum_administrator_changes_reached")
                    desired = admin_with_post_rights(rights) if is_admin else minimal_rights()
                    # Telegram channel creator can grant post-only rights.
                    try:
                        await client(functions.channels.EditAdminRequest(
                            channel=channel, user_id=bot, admin_rights=desired,
                            rank="CinéX"))
                    except UserNotParticipantError:
                        # Some Telegram versions require membership first.
                        await client(functions.channels.InviteToChannelRequest(
                            channel=channel, users=[bot]))
                        await asyncio.sleep(pause)
                        await client(functions.channels.EditAdminRequest(
                            channel=channel, user_id=bot, admin_rights=desired,
                            rank="CinéX"))
                    await asyncio.sleep(pause)
                    confirmed, verified_rights = await participant_rights(client, channel, bot)
                    if not verified_rights or not verified_rights.post_messages:
                        raise RuntimeError("post_only_admin_not_confirmed")
                    counters["promoted"] += 1
                    total_updated += 1
                    total_verified += 1
                except (FloodWaitError, PeerFloodError):
                    raise
                except Exception as exc:
                    counters["errors"] += 1
                    total_failed += 1
                    # Nothing sensitive from Telegram exceptions enters logs.
                    LOG.error("BOT_ADMIN_FAILURE kind=%s bot=%s error=%s",
                              kind, entry["label"], type(exc).__name__)
            rows.append({"target": kind + ":" + name,
                         **counters})
            LOG.info("BOT_ADMIN_CHANNEL %s %s already=%s promoted=%s remaining=%s errors=%s",
                     kind, name, counters["already_admin"], counters["promoted"],
                     counters["missing_admin"] - counters["promoted"], counters["errors"])
    finally:
        await client.disconnect()
    report = {"mode": "apply" if apply else "audit", "bots": len(candidates),
              "targets_verified": len(rows), "required_targets": 14,
              "already_or_new_admins": total_verified, "promoted": total_updated,
              "missing_before": total_missing, "errors": total_failed,
              "missing_secret_slots": len(missing), "targets": rows}
    output = os.getenv("GITHUB_STEP_SUMMARY", "").strip()
    if output:
        with Path(output).open("a", encoding="utf-8") as f:
            f.write("\n### CinéX : administrateurs des 7 canaux Secours et 7 canaux principaux\n")
            f.write(f"- Bots uniques vérifiés : {len(candidates)}\n")
            f.write(f"- Canaux examinés : {len(rows)}/14\n")
            f.write(f"- Administrations ajoutées : {total_updated}\n")
            f.write(f"- Erreurs de contrôle : {total_failed}\n")
            f.write(f"- Variables de bot absentes : {len(missing)}\n")
            for row in rows:
                f.write(f"- {row['target']} : déjà admin={row['already_admin']}, "
                        f"ajoutés={row['promoted']}, non corrigés="
                        f"{row['missing_admin']-row['promoted']}, erreurs={row['errors']}\n")
    print("CINEX_BOT_ADMIN_SUMMARY", json.dumps({
        k: v for k, v in report.items() if k != "targets"
    }, sort_keys=True))
    if total_failed or len(rows) != 14 or (apply and total_missing != total_updated):
        raise RuntimeError("admin_network_partially_complete")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--pause", type=int, default=12)
    parser.add_argument("--max-changes", type=int, default=220)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from scripts.check_personal_cooldown import seconds_remaining
    if seconds_remaining():
        raise RuntimeError("personal_telegram_session_in_cooldown")
    asyncio.run(run(apply=args.apply, pause=args.pause, max_changes=args.max_changes))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Exception type only; API URLs may contain a secret in their text.
        print("CINEX_BOT_ADMIN_STOP", type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)
