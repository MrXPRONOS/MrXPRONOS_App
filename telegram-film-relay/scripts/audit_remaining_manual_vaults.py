"""Read-only inventory of the nine remaining CinéX and Formation vaults.

Never creates channels, posts, joins, invites, grants rights or accesses files.
Output is a category-only summary with no private peer IDs, invites or tokens.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import Mapping

REMAINING = (
    "films", "animes", "comedie", "desir", "formation_general",
    "formation_business", "formation_finance", "formation_digitale",
    "formation_mindset",
)
CHANNEL_RE = re.compile(r"^-100[0-9]{6,}$")
CHANNEL_TITLE = {
    "films": "MRX — Stock manuel Films",
    "animes": "MRX — Stock manuel Animés",
    "comedie": "MRX — Stock manuel Comédie",
    "desir": "MRX — Stock manuel Désir",
    "formation_general": "MRX — Stock manuel Formations générales",
    "formation_business": "MRX — Stock manuel Formations Business",
    "formation_finance": "MRX — Stock manuel Formations Finance",
    "formation_digitale": "MRX — Stock manuel Formations Digital",
    "formation_mindset": "MRX — Stock manuel Formations Mindset",
}
PRIVATE_VARIABLE = {
    "films": "TG_PRIVATE_CHANNEL",
    "animes": "ANIME_PRIVATE_CHANNEL",
    "comedie": "COMEDIE_PRIVATE_CHANNEL",
    "desir": "DESIR_PRIVATE_CHANNEL",
    "formation_general": "FORMATION_STAGE_CHAT",
}
PUBLISHER_SECRET = {
    "films": "CINEX_BOT_TOKEN",
    "animes": "ANIME_BOT_TOKEN",
    "comedie": "COMEDIE_BOT_TOKEN",
    "desir": "DESIR_BOT_TOKEN",
    "formation_general": "FORMATION_BOT_TOKEN",
    "formation_business": "FORMATION_BOT_TOKEN",
    "formation_finance": "FORMATION_BOT_TOKEN",
    "formation_digitale": "FORMATION_BOT_TOKEN",
    "formation_mindset": "FORMATION_BOT_TOKEN",
}

@dataclass(frozen=True)
class AuditRow:
    category: str
    channel: str
    owner: str
    radar: str
    publisher: str
    ready: bool

def configured_id(category: str, env: Mapping[str, str]):
    if category not in REMAINING:
        raise ValueError("unknown_category")
    manual = str(env.get("CINEX_MANUAL_"+category.upper()+"_CHAT") or "").strip()
    fallback = str(env.get(PRIVATE_VARIABLE.get(category, ""), "") or "").strip()
    # Do NOT silently reuse a public Formation destination as an owner-only vault.
    candidate = manual or fallback
    if candidate and not CHANNEL_RE.fullmatch(candidate):
        raise ValueError("configured_private_id_invalid")
    return candidate

def find_private(dialogs, category, configured, peer_id):
    matches = []
    if configured:
        matches = [p for p in dialogs if str(peer_id(p)) == configured]
        if len(matches) != 1:
            return "configured_not_in_owner_dialogs", None
    else:
        matches = [p for p in dialogs
                   if getattr(p, "broadcast", False)
                   and not getattr(p, "username", None)
                   and str(getattr(p, "title", "")) == CHANNEL_TITLE[category]]
        if len(matches) > 1:
            return "ambiguous_duplicate_title", None
        if not matches:
            return "missing", None
    chosen = matches[0]
    if (not getattr(chosen, "broadcast", False)
            or getattr(chosen, "username", None)):
        return "not_private_broadcast", None
    return "found", chosen

async def audit():
    from telethon import TelegramClient, utils
    from telethon.sessions import StringSession

    env = os.environ
    session = str(env.get("TG_STRING_SESSION") or "").strip()
    api_id = str(env.get("TG_API_ID") or "").strip()
    api_hash = str(env.get("TG_API_HASH") or "").strip()
    if not session or not api_id.isdecimal() or not api_hash:
        raise RuntimeError("session_credentials_missing")
    client = TelegramClient(
        StringSession(session), int(api_id), api_hash,
        flood_sleep_threshold=0, request_retries=0, connection_retries=0
    )
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("session_not_authorized")
        owner = await client.get_me()
        if owner is None or owner.bot:
            raise RuntimeError("not_personal_owner")
        dialogs = [d.entity async for d in client.iter_dialogs(limit=500)]
        bot_entities = {}
        for label, token in (
            ("radar", str(env.get("CINE_RADAR_BOT_TOKEN") or "").strip()),
            *[(k, str(env.get(k) or "").strip())
              for k in sorted(set(PUBLISHER_SECRET.values()))],
        ):
            if not token:
                continue
            from urllib.parse import quote
            import requests
            try:
                reply = requests.post("https://api.telegram.org/bot" +
                                      quote(token, safe=":") + "/getMe", timeout=12)
                data = reply.json()
                user = data.get("result") if data.get("ok") else None
                if not isinstance(user, dict) or user.get("is_bot") is not True:
                    continue
                entity = await client.get_entity("@" + user["username"])
                if entity.id != user["id"] or not entity.bot:
                    continue
                if label == "radar" and user["username"].lower() != "cineradarfr_bot":
                    continue
                bot_entities[label] = entity
            except Exception:
                continue
        results = []
        for category in REMAINING:
            try:
                cfg = configured_id(category, env)
                code, peer = find_private(dialogs, category, cfg, utils.get_peer_id)
            except Exception:
                results.append(AuditRow(category, "configuration_invalid",
                                        "unknown","unknown","unknown",False))
                continue
            if peer is None:
                results.append(AuditRow(category, code, "unknown",
                                        "unknown", "unknown",False))
                continue
            try:
                perm = await client.get_permissions(peer, owner)
                owner_ok = getattr(perm, "is_creator", False) is True
            except Exception:
                owner_ok = False
            if not owner_ok:
                results.append(AuditRow(category, code, "not_creator",
                                        "unknown","unknown",False))
                continue
            flags = {}
            for label in ("radar", PUBLISHER_SECRET[category]):
                bot = bot_entities.get(label)
                if bot is None:
                    flags[label] = "bot_not_identified"
                    continue
                try:
                    p = await client.get_permissions(peer, bot)
                    flags[label] = (
                        "verified" if getattr(p,"is_creator",False) or (
                            getattr(p,"is_admin",False) and
                            getattr(p,"post_messages",False))
                        else "bot_missing_admin")
                except Exception:
                    flags[label] = "bot_missing_admin"
            results.append(AuditRow(
                category, "found", "creator_verified",
                flags.get("radar","bot_not_identified"),
                flags.get(PUBLISHER_SECRET[category],"bot_not_identified"),
                flags.get("radar")=="verified" and
                flags.get(PUBLISHER_SECRET[category])=="verified"
            ))
        return results
    finally:
        await client.disconnect()

def report(rows):
    if not rows:
        raise RuntimeError("no_categories_audited")
    summary={"total":len(rows),"ready":sum(r.ready for r in rows),
             "existing":sum(r.channel=="found" for r in rows),
             "missing":sum(r.channel=="missing" for r in rows),
             "needs_review":sum(not r.ready for r in rows),
             "categories":[r.__dict__ for r in rows]}
    return summary

def main():
    try:
        results=asyncio.run(audit())
        print("CINEX_MANUAL_NINE_INVENTORY "+json.dumps(
            report(results),ensure_ascii=False,sort_keys=True))
    except Exception as exc:
        print("CINEX_MANUAL_NINE_INVENTORY_BLOCKED "+type(exc).__name__)
        raise SystemExit(1)

if __name__=="__main__":
    main()
