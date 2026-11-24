"""Safely reuse or create ONE owner-only manual Telegram source vault.

Dry-run is the default. Existing verified category libraries take precedence.
Never creates a channel when the personal session cannot be authenticated.
Never activates a source unless content rights and bot admin are verified.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import re
from dataclasses import dataclass

CHANNEL = re.compile(r"^-100[0-9]{6,}$")
CATS = (
    "films", "series", "animes", "comedie", "action", "desir",
    "formation_general", "formation_business", "formation_finance",
    "formation_digitale", "formation_mindset",
)
EXISTING_VARIABLES = {
    "films": "TG_PRIVATE_CHANNEL",
    "series": "SERIES_PRIVATE_CHANNEL",
    "animes": "ANIME_PRIVATE_CHANNEL",
    "comedie": "COMEDIE_PRIVATE_CHANNEL",
    "action": "ACTION_PRIVATE_CHANNEL",
    "desir": "DESIR_PRIVATE_CHANNEL",
    "formation_general": "FORMATION_STAGE_CHAT",
}
LABELS = {
    "films": "Films", "series": "Séries", "animes": "Animés",
    "comedie": "Comédie", "action": "Action", "desir": "Désir",
    "formation_general": "Formations générales",
    "formation_business": "Formations Business",
    "formation_finance": "Formations Finance",
    "formation_digitale": "Formations Digital",
    "formation_mindset": "Formations Mindset",
}
MARKER = "MRX_MANUAL_SOURCE_V1:"


def configured_chat(category: str, env=None):
    env = os.environ if env is None else env
    if category not in CATS:
        raise ValueError("Catégorie inconnue")
    custom = str(env.get("CINEX_MANUAL_" + category.upper() + "_CHAT") or "").strip()
    if custom:
        if not CHANNEL.fullmatch(custom):
            raise ValueError("ID du canal manuel personnalisé invalide")
        return custom
    existing = str(env.get(EXISTING_VARIABLES.get(category, ""), "") or "").strip()
    if category.startswith("formation_") and category != "formation_general":
        raw = str(env.get("FORMATION_DESTINATIONS_JSON") or "").strip()
        if raw:
            try:
                candidate = json.loads(raw).get(category.split("_", 1)[1])
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError("FORMATION_DESTINATIONS_JSON invalide") from exc
            existing = str(candidate or "").strip()
    if existing:
        if not CHANNEL.fullmatch(existing):
            # Some old public destination usernames are not suitable private vaults.
            raise ValueError("Canal privé configuré sans ID numérique -100")
        return existing
    return ""


def channel_title(category):
    return "MRX — Stock manuel " + LABELS[category]


@dataclass(frozen=True)
class Outcome:
    category: str
    mode: str
    exists: bool
    created: bool
    owner_verified: bool
    bot_verified: bool
    registered: bool


def verify_bot_token(token):
    import requests
    if not token or ":" not in token:
        return None
    try:
        response = requests.post(
            "https://api.telegram.org/bot" + token + "/getMe",
            timeout=10)
        data = response.json()
        info = data.get("result") if data.get("ok") else None
        if (isinstance(info, dict) and isinstance(info.get("username"), str)
                and isinstance(info.get("id"), int)):
            return info
    except (requests.RequestException, ValueError):
        return None
    return None


async def provision(category: str, *, apply=False, env=None):
    from telethon import TelegramClient, functions, utils
    from telethon.sessions import StringSession
    env = os.environ if env is None else env
    if category not in CATS:
        raise ValueError("Catégorie inconnue")
    session = str(env.get("TG_STRING_SESSION") or env.get("TG_SESSION_STRING") or "").strip()
    api_id = str(env.get("TG_API_ID") or "").strip()
    api_hash = str(env.get("TG_API_HASH") or "").strip()
    if not (session and api_id and api_hash):
        raise RuntimeError("Session personnelle absente : création impossible")
    owner = TelegramClient(StringSession(session), int(api_id), api_hash,
                           flood_sleep_threshold=0, request_retries=0)
    await owner.connect()
    try:
        if not await owner.is_user_authorized():
            raise RuntimeError("Session personnelle révoquée : création impossible")
        me = await owner.get_me()
        expected_title = channel_title(category)
        marker = MARKER + category
        configured = configured_chat(category, env)
        entity = await owner.get_entity(int(configured)) if configured else None
        if entity is None:
            matches = [
                d.entity async for d in owner.iter_dialogs(limit=500)
                if getattr(d.entity, "broadcast", False)
                and not getattr(d.entity, "username", None)
                and str(getattr(d.entity, "title", "")) == expected_title
            ]
            if len(matches) > 1:
                raise RuntimeError("Plusieurs canaux de même nom : revue requise")
            entity = matches[0] if matches else None
            if entity:
                full = await owner(functions.channels.GetFullChannelRequest(entity))
                if marker not in str(getattr(full.full_chat, "about", "") or ""):
                    raise RuntimeError("Nom existant sans marqueur propriétaire : revue requise")
        created = False
        if entity is None and apply:
            response = await owner(functions.channels.CreateChannelRequest(
                title=expected_title, about=marker,
                broadcast=True, megagroup=False))
            matches = [x for x in response.chats
                       if getattr(x, "broadcast", False)
                       and getattr(x, "title", "") == expected_title]
            if len(matches) != 1:
                raise RuntimeError("Telegram n'a pas confirmé la création")
            entity, created = matches[0], True
        if entity is None:
            return Outcome(category, "simulation", False, False, False, False, False)
        ident = str(utils.get_peer_id(entity))
        if not CHANNEL.fullmatch(ident):
            raise RuntimeError("Le canal sélectionné n'est pas un canal privé valide")
        if getattr(entity, "username", None) or not getattr(entity, "broadcast", False):
            raise RuntimeError("Refus : source publique ou groupe")
        perms = await owner.get_permissions(entity, me)
        if not getattr(perms, "is_creator", False):
            raise RuntimeError("Refus : le compte n'est pas propriétaire de ce canal")
        bot_token = str(env.get("CINEX_RADAR_BOT_TOKEN") or "").strip()
        bot = verify_bot_token(bot_token)
        bot_ready = False
        if bot:
            try:
                peer = await owner.get_entity("@" + bot["username"])
                access = await owner.get_permissions(entity, peer)
                bot_ready = bool(getattr(access, "is_creator", False) or
                                 (getattr(access, "is_admin", False) and
                                  getattr(access, "post_messages", False)))
            except Exception:
                bot_ready = False
        registered = False
        if (apply and bot_ready and
                str(env.get("CINEX_MANUAL_RIGHTS_ATTESTED", "")).lower() == "true" and
                str(env.get("CINEX_MANUAL_OWNER_APPROVED", "")).lower() == "true"):
            registered = register_d1(category, ident, env)
        # IDs are never printed or committed. A configured source can be reused
        # only when the owner and bot are verified on that actual Telegram peer.
        return Outcome(category, "apply" if apply else "simulation",
                       True, created, True, bot_ready, registered)
    finally:
        await owner.disconnect()


def register_d1(category, chat_id, env):
    import requests
    token = str(env.get("CLOUDFLARE_API_TOKEN") or env.get("CF_API_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("Jeton Cloudflare absent : activation refusée")
    account = str(env.get("CLOUDFLARE_ACCOUNT_ID") or
                  "9c86118191b804d91b5f5b2c89114999")
    db = str(env.get("CINERADAR_D1_DATABASE_ID") or
             "fa8b5009-bc1a-4a6e-b143-7a487c7297a5")
    endpoint = ("https://api.cloudflare.com/client/v4/accounts/" + account +
                "/d1/database/" + db + "/query")
    def query(sql, params=()):
        try:
            res = requests.post(endpoint,
                headers={"Authorization": "Bearer " + token},
                json={"sql": sql, "params": list(params)},timeout=15)
            data = res.json()
            if not res.ok or data.get("success") is not True or not data.get("result"):
                raise RuntimeError("D1 write refused")
            return data["result"][0].get("results") or []
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError("D1 unavailable") from exc
    previous = query(
        "SELECT category FROM cine_manual_fallback_sources WHERE chat_id=?",
        (chat_id,))
    if previous and (len(previous) != 1 or previous[0].get("category") != category):
        raise RuntimeError("Canal déjà attribué à une autre catégorie")
    query(
        "INSERT INTO cine_manual_fallback_sources "+
        "(chat_id,category,rights_attested,bot_access_verified,owner_approved,enabled,verified_at) "+
        "VALUES(?,?,1,1,1,1,CURRENT_TIMESTAMP) "+
        "ON CONFLICT(chat_id) DO UPDATE SET rights_attested=1,bot_access_verified=1,"+
        "owner_approved=1,enabled=1,verified_at=CURRENT_TIMESTAMP "+
        "WHERE cine_manual_fallback_sources.category=excluded.category",
        (chat_id,category))
    confirmation = query(
        "SELECT enabled FROM cine_manual_fallback_sources "+
        "WHERE chat_id=? AND category=?",(chat_id,category))
    if len(confirmation)!=1 or int(confirmation[0].get("enabled") or 0)!=1:
        raise RuntimeError("D1 n'a pas confirmé le canal de réserve")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category",choices=CATS,required=True)
    parser.add_argument("--apply",action="store_true")
    opts = parser.parse_args()
    try:
        result = asyncio.run(provision(opts.category,apply=opts.apply))
        # Safe summary: no Telegram IDs, user names, invite URLs or secrets.
        print(json.dumps(result.__dict__,sort_keys=True))
    except Exception as exc:
        # No exception body: Telegram API exceptions may contain private IDs.
        print(json.dumps({"category":opts.category,
                          "status":"blocked","error":type(exc).__name__}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
