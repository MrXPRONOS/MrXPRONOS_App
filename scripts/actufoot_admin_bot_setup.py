#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Secure inventory / optional onboarding of Telegram bots in 'Actu Foot'.

The only eligible channels are those explicitly in the owner's named Telegram
folder. No bot token, private link, invitation, session or peer ID is logged
or saved to the repository. Never retry FloodWait/PeerFlood automatically.
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import io
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
from telethon import TelegramClient, errors, utils
from telethon.sessions import StringSession
from telethon.tl import functions, types

EXPECTED_HANDLES = frozenset(
    name.casefold() for name in (
        "FootFlashActuFR", "MercatoFootInfosFR", "LDCActuFootFR",
        "PremierLeagueActuFR", "LigaFootActuFR", "Ligue1FootActuFR",
        "FootAfriqueInfosFR", "SelectionsFootActu",
        "ScoresFootClassements", "DebriefFootAnalyses",
    )
)
EXISTING_HANDLE = "actufoot_mrxp"
FOLDER_NAME = "actufoot"
MAX_TARGET_CHANNELS = 10
MAX_CHANNEL_ADMINS = 50
MAX_API_BOTS = 125
ADMIN_FLAGS = (
    "change_info", "post_messages", "edit_messages", "delete_messages",
    "ban_users", "invite_users", "pin_messages", "manage_call", "other",
    "post_stories", "edit_stories", "delete_stories",
    "manage_direct_messages",
)
TOKEN_MATCH = re.compile(r"^[0-9]+:[A-Za-z0-9_-]{30,}$")


def fold(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "").casefold())
    return "".join(x for x in s if not unicodedata.combining(x))


def compact(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", fold(s))


def clean_secret_candidates(environment):
    """Read only the allowlisted Action bot secret names, plus the reaction JSON."""
    dedup = {}
    candidate_count = 0
    for name, value in environment.items():
        if not (name.endswith("_BOT_TOKEN") or re.fullmatch(r"TELEGRAM_REACTION_BOT_[0-9]{2}_TOKEN",name)):
            continue
        token = str(value or "").strip()
        if token:
            candidate_count += 1
            if TOKEN_MATCH.fullmatch(token):
                dedup.setdefault(token, name)
    bundle = str(environment.get("TELEGRAM_REACTION_BOTS_JSON") or "").strip()
    if bundle:
        try:
            parsed = json.loads(bundle)
            if not isinstance(parsed, dict):
                raise ValueError("invalid_bundle")
            for slot, token in parsed.items():
                if not str(slot).isdigit() or not isinstance(token, str):
                    continue
                token = token.strip()
                if TOKEN_MATCH.fullmatch(token):
                    candidate_count += 1
                    dedup.setdefault(token, "reaction_json")
        except (ValueError, TypeError):
            pass
    if len(dedup) > MAX_API_BOTS:
        raise ValueError("bot_count_over_safety_limit")
    return dedup, candidate_count


def verify_bot(entry):
    token, label = entry
    try:
        # Never log URLs or exceptions because the URL carries the token.
        response = requests.get(
            "https://api.telegram.org/bot" + token + "/getMe",
            timeout=12,
        )
        result = response.json()
        bot = result.get("result") or {}
        if (response.status_code != 200 or result.get("ok") is not True
            or bot.get("is_bot") is not True or type(bot.get("id")) is not int
            or not isinstance(bot.get("username"), str)):
            return None
        return {"id":bot["id"], "username":bot["username"],
                "label":label}
    except (ValueError, requests.RequestException):
        return None


def all_bots(environment):
    candidates, source_count = clean_secret_candidates(environment)
    bots, failed = {}, 0
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(verify_bot, item) for item in candidates.items()]
        for future in as_completed(futures):
            bot = future.result()
            if bot is None:
                failed += 1
                continue
            bots.setdefault(bot["id"], bot)
    # Prioritise publishing bots, then all other verified identities.
    ordered = sorted(bots.values(),key=lambda x: (
        "REACTION_BOT" in x["label"] or x["label"]=="reaction_json",
        x["label"], x["id"],
    ))
    return ordered, {"nonempty_secret_candidates":source_count,
                     "unique_tokens":len(candidates),
                     "verified_bot_identities":len(ordered),
                     "failed_getme":failed,
                     "deduplicated_identities":len(candidates)-failed-len(ordered)}


def folder_title(item):
    title = getattr(item,"title",None)
    return getattr(title,"text",title) or ""


def peer_channel_id(peer):
    return getattr(peer,"channel_id",None)


async def find_actufoot_targets(client):
    result = await client(functions.messages.GetDialogFiltersRequest())
    matches = [x for x in getattr(result,"filters",[])
               if compact(folder_title(x)) == FOLDER_NAME]
    if len(matches) != 1:
        raise ValueError("folder_not_found_or_ambiguous")
    folder = matches[0]
    peers = (*getattr(folder,"include_peers",[]),
             *getattr(folder,"pinned_peers",[]))
    listed_ids = {int(peer_channel_id(p)) for p in peers if peer_channel_id(p)}
    if not listed_ids:
        raise ValueError("folder_has_no_explicit_channels")
    owned = {}
    async for dialog in client.iter_dialogs(limit=500):
        item = dialog.entity
        if not isinstance(item,types.Channel) or not bool(getattr(item,"broadcast",False)):
            continue
        if int(item.id) in listed_ids:
            username=str(getattr(item,"username","") or "").casefold()
            if username == EXISTING_HANDLE:
                continue
            owned[item.id] = item
    if len(owned) != MAX_TARGET_CHANNELS:
        raise ValueError("folder_does_not_contain_exactly_ten_new_channels")
    # Only newly created football channels, not arbitrary channels in a folder.
    for item in owned.values():
        username=str(getattr(item,"username","") or "").casefold()
        title=compact(getattr(item,"title",""))
        identifiable=(
            username in EXPECTED_HANDLES
            or any(tag in title for tag in
                   ("foot","mercato","ligue","liga","league","selection",
                    "score","debrief","afrique","champion","national"))
        )
        if not identifiable:
            raise ValueError("unexpected_topic_channel_in_folder")
        # An administrator can promote bots only if their existing rights allow it.
        if not getattr(item,"creator",False):
            permission = getattr(item,"admin_rights",None)
            if not permission or not getattr(permission,"add_admins",False):
                raise ValueError("session_missing_promote_permission")
            missing = [flag for flag in ADMIN_FLAGS
                       if hasattr(permission,flag) and not getattr(permission,flag,False)]
            if missing:
                raise ValueError("session_cannot_grant_all_requested_rights")
    return list(sorted(owned.values(), key=lambda x:fold(x.title)))


async def channel_admins(client, channel):
    admins = await client.get_participants(
        channel, limit=MAX_CHANNEL_ADMINS+10,
        filter=types.ChannelParticipantsAdmins(),
    )
    return {int(x.id) for x in admins}


def full_rights():
    accepted=inspect.signature(types.ChatAdminRights).parameters
    flags={k:True for k in ADMIN_FLAGS if k in accepted}
    if "add_admins" not in accepted:
        raise RuntimeError("add_admins_permission_not_supported")
    flags["add_admins"]=False
    if "anonymous" in accepted:
        flags["anonymous"]=False
    if "manage_topics" in accepted:
        flags["manage_topics"]=False  # Only applicable to forum groups.
    if "manage_tags" in accepted:
        flags["manage_tags"]=False
    return types.ChatAdminRights(**flags),tuple(k for k in ADMIN_FLAGS if k in accepted)


def expected_rights(rights, keys):
    return bool(
        rights
        and getattr(rights,"add_admins",None) is False
        and all(getattr(rights,k,None) is True for k in keys)
    )


async def read_current_rights(client, channel, user):
    try:
        response=await client(functions.channels.GetParticipantRequest(channel=channel,participant=user))
        return getattr(response.participant,"admin_rights",None)
    except errors.UserNotParticipantError:
        return None


async def private_report(client, rows, summary, apply):
    day=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    header=[
        "AUDIT ACTU FOOT — BOTS ADMINISTRATEURS",
        "Mode : "+("AJOUT DEMANDÉ" if apply else "LECTURE SEULE"),
        "Dossier obligatoire : Actu Foot ; ciblage strict : 10 nouveaux canaux",
        "Règle : tous les droits de canal disponibles sauf ajout d'administrateurs.",
        "Limite Telegram : 50 administrateurs maximum, propriétaire inclus.",
        "Aucun token Telegram ne figure dans ce fichier.",
        "",
        "BILAN :", json.dumps(summary,ensure_ascii=False,indent=2),"",
    ]
    file=io.BytesIO(("\n".join(header)+
            "\n".join(rows)+"\n").encode("utf-8"))
    file.name="actu-foot-bots-admin-"+day+".txt"
    await client.send_file("me",file,force_document=True,caption=(
        "⚽ Actu Foot — audit bots administrateurs ("
        + ("ajout" if apply else "lecture seule") + ") "+day
    ))


async def run(apply=False):
    api_id=os.environ.get("TG_API_ID","").strip()
    api_hash=os.environ.get("TG_API_HASH","").strip()
    sess=(os.environ.get("TG_SESSION_STRING","") or
          os.environ.get("TG_STRING_SESSION","")).strip()
    if not api_id.isdigit() or not api_hash or not sess:
        print("ACTUFOOT_ADMIN_PREFLIGHT_MISSING_TELEGRAM_CONFIG")
        return 1
    bots, bot_stats=all_bots(os.environ)
    client=TelegramClient(StringSession(sess),int(api_id),api_hash,
        request_retries=0,connection_retries=1,receive_updates=False,
        flood_sleep_threshold=0)
    reports=[]
    summary={"bots":bot_stats,"mode":"apply" if apply else "audit",
             "expected_new_channels":10, "added":0,"already_correct":0,
             "failed":0,"blocked":False}
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("ACTUFOOT_ADMIN_SESSION_NOT_AUTHORIZED")
            return 1
        try:
            targets=await find_actufoot_targets(client)
        except ValueError as exc:
            summary["blocked"]=True
            summary["reason"]=str(exc)
            reports.append("Ciblage du dossier échoué : "+str(exc))
            await private_report(client,reports,summary,apply)
            print("ACTUFOOT_ADMIN_SUMMARY",json.dumps(summary,ensure_ascii=False))
            return 2
        summary["channels_verified"]=len(targets)
        admins={}
        for ch in targets:
            admins[ch.id]=await channel_admins(client,ch)
        # Telegram hard ceiling: never try to add bots which cannot fit
        # in each channel. Prevent partial 10-channel mutation.
        minimum_room=min(MAX_CHANNEL_ADMINS-len(v) for v in admins.values())
        summary["min_available_admin_slots"]=minimum_room
        summary["current_admin_counts"]={"min":min(map(len,admins.values())),
                                          "max":max(map(len,admins.values()))}
        if not bots:
            summary["blocked"]=True
            summary["reason"]="no_verified_bot_tokens"
        if any(len(set(x["id"] for x in bots)-admins[ch.id]) >
               MAX_CHANNEL_ADMINS-len(admins[ch.id]) for ch in targets):
            summary["blocked"]=True
            summary["reason"]="more_distinct_bots_than_telegram_admin_limit"
        rights, keys=full_rights()
        for ch in targets:
            present=admins[ch.id]
            reports.append(
                "\nCANAL : "+ch.title+" (@"+str(ch.username or "non_public")+")"
                +" | "+str(utils.get_peer_id(ch))
                +" | administrateurs actuels : "+str(len(present))
            )
            for bot in bots:
                status="existant" if bot["id"] in present else "à ajouter"
                reports.append("  @"+bot["username"]+" ["+bot["label"]+"] : "+status)
        if summary["blocked"]:
            reports.insert(0,"AUCUN BOT AJOUTÉ. Cause : "+summary["reason"])
        elif apply:
            for ch in targets:
                for bot in bots:
                    try:
                        user=await client.get_entity("@"+bot["username"])
                        if not getattr(user,"bot",False) or int(user.id)!=bot["id"]:
                            raise ValueError("identity_mismatch")
                        current=await read_current_rights(client,ch,user)
                        if expected_rights(current,keys):
                            summary["already_correct"]+=1
                            continue
                        await client(functions.channels.EditAdminRequest(
                            channel=ch,user_id=user,
                            admin_rights=rights,rank="Actu Foot",
                        ))
                        verified=await read_current_rights(client,ch,user)
                        if not expected_rights(verified,keys):
                            raise ValueError("admin_rights_not_verified")
                        summary["added"]+=1
                        await asyncio.sleep(3)
                    except (errors.FloodWaitError,errors.PeerFloodError):
                        raise
                    except Exception:
                        # Deliberately do not print Telegram exception values.
                        summary["failed"]+=1
                        reports.append("  ÉCHEC : @"+bot["username"]+" sur "+ch.title)
                        await asyncio.sleep(2)
        else:
            summary["ready_for_apply"]=not summary["blocked"]
        await private_report(client,reports,summary,apply)
        print("ACTUFOOT_ADMIN_SUMMARY",json.dumps(summary,ensure_ascii=False))
        return 0 if not summary["blocked"] and not summary["failed"] else 2
    except (errors.FloodWaitError,errors.PeerFloodError):
        print("ACTUFOOT_ADMIN_TELEGRAM_RATE_LIMIT_STOPPED_NO_RETRY")
        return 3
    finally:
        await client.disconnect()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    raise SystemExit(asyncio.run(run(apply=args.apply)))
