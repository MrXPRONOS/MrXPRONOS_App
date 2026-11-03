#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Relay the SAME production Shorts video with inline URL buttons to owned Telegram
public channels; forward the Coupons du jour original natively to Torrent9.

Never touches films/private libraries or the existing suspended film->Torrent9
mirrors. Uses an atomic per-chat Cloudflare D1 claim and does not retry an ambiguous
Telegram send to avoid duplicates.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from d1_publication_ledger import D1Ledger

CONFIG = Path("config/telegram_video_distribution.json")
RECEIPT = Path("telegram_out/production_short/telegram_primary_receipt.json")
REPORT = Path("telegram_out/production_short/telegram_distribution_report.json")
KIND = "shorts_video_channel_distribution"
FORWARD_KIND = "shorts_video_torrent9_forward"
PUBLIC_HANDLE = re.compile(r"^@[a-zA-Z0-9_]{5,32}$")


def headers(key: str) -> dict:
    return {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "Prefer": "return=representation,resolution=ignore-duplicates",
    }


def claim(session, url: str, key: str, kind: str, target: str, day: str) -> bool:
    response = session.post(
        url.rstrip("/") + "/rest/v1/telegram_sent",
        params={"on_conflict": "kind,ref_id,ref_date"},
        headers=headers(key),
        json={"kind": kind, "ref_id": target, "ref_date": day, "validation_sent": False},
        timeout=35,
    )
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, list):
        raise RuntimeError("Réponse du registre de diffusion inattendue")
    return len(result) > 0


def load() -> tuple[dict, dict]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    targets = config["destinations"]
    if not targets or not isinstance(targets, list):
        raise ValueError("Liste de canaux vide")
    primary = config["primary"]
    if primary.casefold() != "@mrxpronosfr" or receipt["primary_chat"].casefold() != primary.casefold():
        raise ValueError("La vidéo d'origine doit provenir de @mrxpronosfr")
    if config.get("torrent9_forward") != "@Torrent9SeriesFilms":
        raise ValueError("Destination Torrent9 non conforme")
    seen = set()
    for target in targets:
        name = target["chat"]
        if not PUBLIC_HANDLE.fullmatch(name):
            raise ValueError("Destination publique invalide: " + str(name))
        if name.casefold() in seen:
            raise ValueError("Canal en double dans la configuration")
        seen.add(name.casefold())
    if primary.casefold() not in seen:
        raise ValueError("Canal Coupons du jour absent des destinations")
    expected = config["buttons"]
    buttons = receipt["keyboard"]["inline_keyboard"]
    if len(buttons) != 3 or any(len(row) != 1 for row in buttons):
        raise ValueError("Trois boutons Telegram sont requis")
    if [row[0] for row in buttons] != expected:
        raise ValueError("Boutons de la vidéo différents de la configuration")
    if [b["url"] for b in expected] != [
        "https://t.me/mrxpronosfr",
        "https://t.me/actufoot_mrxp",
        "https://t.me/addlist/ZmW4vfwcrMAwNzJk",
    ]:
        raise ValueError("Liens des boutons non vérifiés")
    if not isinstance(receipt.get("primary_message_id"), int):
        raise ValueError("ID de la vidéo principale absent")
    datetime.strptime(receipt["published_day"], "%Y-%m-%d")
    return config, receipt


class Bot:
    def __init__(self, token: str, name: str):
        self.token = token
        self.name = name
        self.session = requests.Session()
        self.bot_id = None
        self.source = None  # (chat_id, message_id) for this exact bot

    def call(self, method: str, data=None, files=None, timeout=60):
        # Do not expose the URL containing the bot token in an error message.
        try:
            response = self.session.post(
                "https://api.telegram.org/bot" + self.token + "/" + method,
                data=data, files=files, timeout=timeout,
            )
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError("Telegram " + method + ": " + type(exc).__name__) from None
        if response.status_code == 429:
            raise RuntimeError("Telegram rate limit; aucune répétition automatique")
        if not isinstance(body, dict) or not body.get("ok"):
            description = str(body.get("description", "réponse invalide"))[:180] if isinstance(body, dict) else ""
            raise RuntimeError("Telegram " + method + ": HTTP " + str(response.status_code) + " / " + description)
        return body["result"]

    def identify(self):
        self.bot_id = self.call("getMe")["id"]

    def chat(self, username: str):
        return self.call("getChat", {"chat_id": username})

    def can_post(self, username: str) -> bool:
        try:
            result = self.call("getChatMember", {"chat_id": username, "user_id": self.bot_id})
        except RuntimeError:
            return False
        status = result.get("status")
        return status == "creator" or (status == "administrator" and result.get("can_post_messages", False))

    def copy(self, dest: str, keyboard: dict, caption: str) -> int:
        src, msg = self.source
        result = self.call("copyMessage", {
            "chat_id": dest, "from_chat_id": src, "message_id": msg,
            "caption": caption[:1024],
            "reply_markup": json.dumps(keyboard, ensure_ascii=False),
        }, timeout=180)
        if not isinstance(result.get("message_id"), int):
            raise RuntimeError("Telegram copyMessage sans ID")
        return result["message_id"]

    def upload(self, dest: str, path: Path, keyboard: dict, caption: str) -> int:
        with path.open("rb") as f:
            result = self.call(
                "sendVideo", {
                    "chat_id": dest, "caption": caption[:1024],
                    "supports_streaming": "true",
                    "reply_markup": json.dumps(keyboard, ensure_ascii=False),
                }, {"video": (path.name, f, "video/mp4")}, timeout=600
            )
        if not isinstance(result.get("message_id"), int):
            raise RuntimeError("Telegram sendVideo sans ID")
        return result["message_id"]


async def user_forward(primary: str, original_id: int, torrent: str) -> int:
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    api_id = os.getenv("TG_API_ID", "").strip()
    api_hash = os.getenv("TG_API_HASH", "").strip()
    session = (os.getenv("TG_SESSION_STRING") or os.getenv("TG_STRING_SESSION") or "").strip()
    if not all((api_id, api_hash, session)):
        raise RuntimeError("Bot non autorisé sur Torrent9 et session personnelle Telegram non configurée")
    async with TelegramClient(StringSession(session), int(api_id), api_hash) as client:
        # No reupload: Telegram native forward, retaining Coupons du jour as origin.
        from_peer = await client.get_entity(primary)
        to_peer = await client.get_entity(torrent)
        if getattr(from_peer, "noforwards", False):
            raise RuntimeError("Le canal Coupons du jour protège les messages contre le transfert")
        me = await client.get_me()
        rights = await client.get_permissions(to_peer, me)
        can_post = bool(getattr(rights, "is_creator", False) or (
            getattr(rights, "is_admin", False) and getattr(rights, "post_messages", False)))
        if not can_post:
            raise RuntimeError("Le compte Telegram personnel ne peut pas publier dans Torrent9")
        sent = await client.forward_messages(to_peer, original_id, from_peer=from_peer)
        item = sent[0] if isinstance(sent, list) else sent
        if not item or not getattr(item, "id", None):
            raise RuntimeError("Transfert personnel Telegram sans ID")
        return int(item.id)


def distribute(config: dict, receipt: dict, path: Path, *, dry_run=False) -> dict:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    alternative = (os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or "").strip()
    desir_bot = (os.getenv("DESIR_BOT_TOKEN") or "").strip()
    if not token and not dry_run:
        raise RuntimeError("Jeton du bot Telegram manquant")
    primary = config["primary"]
    main_id = receipt["primary_message_id"]
    keyboard = receipt["keyboard"]
    caption = receipt["caption"]
    day = receipt["published_day"]
    report = {"primary": primary, "primary_message_id": main_id,
              "results": [], "torrent9": None, "errors": []}
    if dry_run:
        report["destinations"] = [d["chat"] for d in config["destinations"]]
        report["torrent9"] = config["torrent9_forward"]
        return report

    ledger = D1Ledger()
    bots = [Bot(token, "pronos")]
    for name, other in (("actu_cinex", alternative), ("desir", desir_bot)):
        if other and all(bot.token != other for bot in bots):
            bots.append(Bot(other, name))
    active = []
    for bot in bots:
        try:
            bot.identify()
            active.append(bot)
        except RuntimeError as exc:
            report["errors"].append({"bot": bot.name, "reason": str(exc)})
    main_bot = next((bot for bot in active if bot.token == token), None)
    if not main_bot:
        raise RuntimeError("Bot ayant publié la vidéo principale inaccessible")
    main_bot.source = (primary, main_id)

    used = set()
    main_chat_id = receipt.get("primary_chat_id")
    for item in config["destinations"]:
        name = item["chat"]
        # Resolve actual numeric destination to collapse @alias vs -100 duplicate.
        chat = None
        for bot in active:
            try:
                chat = bot.chat(name)
                break
            except RuntimeError:
                pass
        if chat is None:
            report["errors"].append({"channel": name, "reason": "Canal inaccessible aux bots"})
            continue
        resolved = str(chat.get("id"))
        if resolved in used:
            continue
        used.add(resolved)
        if name.lower() == primary.lower() or str(main_chat_id) == resolved:
            report["results"].append({"channel": name, "status": "origin", "id": main_id})
            continue
        selected = next((bot for bot in active if bot.can_post(name)), None)
        if selected is None:
            report["errors"].append({"channel": name, "reason": "Aucun bot administrateur avec Publier des messages"})
            continue
        if not ledger.claim(KIND, resolved, day):
            report["results"].append({"channel": name, "status": "already_claimed"})
            continue
        try:
            if selected.source:
                posted_id = selected.copy(name, keyboard, caption)
                method = "copyMessage"
            else:
                posted_id = selected.upload(name, path, keyboard, caption)
                method = "sendVideo"
                selected.source = (name, posted_id)
            ledger.mark(KIND, resolved, day, message_id=posted_id)
            report["results"].append({"channel": name, "status": "sent", "id": posted_id,
                                      "method": method, "bot": selected.name})
            print("SHORTS_TELEGRAM_CHANNEL_SENT", name, posted_id, method, selected.name)
        except Exception as exc:
            # Reservation retained for ambiguous response, avoids duplicate posts.
            report["errors"].append({"channel": name, "reason": str(exc)})

    torrent = config["torrent9_forward"]
    try:
        if ledger.claim(FORWARD_KIND, primary + ":" + torrent, day):
            forwarded_id = None
            used_method = None
            for bot in active:
                if bot.can_post(torrent):
                    # Copying vs forwarding: require native forwarding from Coupons du jour.
                    try:
                        message = bot.call("forwardMessage", {
                            "chat_id": torrent,
                            "from_chat_id": primary,
                            "message_id": main_id,
                        }, timeout=180)
                        forwarded_id = message.get("message_id")
                        used_method = "forwardMessage"
                        # Telegram may strip inline buttons from a native forward.
                        # Editing markup on a bot-created forward is a safe attempt,
                        # without generating any extra message.
                        try:
                            bot.call("editMessageReplyMarkup", {
                                "chat_id": torrent, "message_id": forwarded_id,
                                "reply_markup": json.dumps(keyboard, ensure_ascii=False),
                            })
                        except RuntimeError:
                            print("SHORTS_TORRENT9_BUTTONS_NOT_PRESERVED")
                        break
                    except RuntimeError as exc:
                        print("SHORTS_TORRENT9_BOT_FORWARD_FAILED", bot.name, str(exc))
            if forwarded_id is None:
                forwarded_id = asyncio.run(user_forward(primary, main_id, torrent))
                used_method = "native_forward_personal_account"
            ledger.mark(FORWARD_KIND, primary + ":" + torrent, day, message_id=int(forwarded_id))
            report["torrent9"] = {"status": "forwarded", "id": int(forwarded_id), "method": used_method}
            print("SHORTS_TORRENT9_FORWARDED", int(forwarded_id), used_method)
        else:
            report["torrent9"] = {"status": "already_claimed"}
    except Exception as exc:
        report["errors"].append({"channel": torrent, "reason": str(exc)})
        report["torrent9"] = {"status": "error"}

    return report



async def audit_personal_forward(primary: str, torrent: str) -> dict:
    """Verify real personal-account forwarding rights without publishing."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    api_id=os.getenv("TG_API_ID","").strip()
    api_hash=os.getenv("TG_API_HASH","").strip()
    session=(os.getenv("TG_SESSION_STRING") or os.getenv("TG_STRING_SESSION") or "").strip()
    if not all((api_id,api_hash,session)):
        return {"ready":False,"reason":"session personnelle non configurée"}
    async with TelegramClient(StringSession(session),int(api_id),api_hash) as client:
        source=await client.get_entity(primary)
        target=await client.get_entity(torrent)
        me=await client.get_me()
        rights=await client.get_permissions(target,me)
        can_post=bool(getattr(rights,"is_creator",False) or (
            getattr(rights,"is_admin",False) and getattr(rights,"post_messages",False)))
        return {
            "ready":True,
            "source_forward_allowed": not bool(getattr(source,"noforwards",False)),
            "can_post_in_torrent9":can_post,
        }


def audit_permissions() -> int:
    """Read-only Telegram Bot API check. Never sends or forwards any media."""
    cfg=json.loads(CONFIG.read_text(encoding="utf-8"))
    raw=[
        ("pronos",os.getenv("TELEGRAM_BOT_TOKEN","")),
        ("actu_cinex",os.getenv("FOOTBALL_NEWS_BOT_TOKEN","")),
        ("desir",os.getenv("DESIR_BOT_TOKEN",""))
    ]
    bots=[]
    for name,token in raw:
        if token and not any(b.token==token for b in bots):
            b=Bot(token,name)
            try:
                b.identify()
                bots.append(b)
            except RuntimeError as exc:
                print("TELEGRAM_VIDEO_PERMISSION_BOT_ERROR",name,str(exc))
    targets=[d["chat"] for d in cfg["destinations"]]+[cfg["torrent9_forward"]]
    rights={}
    for target in targets:
        rights[target]={bot.name:bot.can_post(target) for bot in bots}
        print("TELEGRAM_VIDEO_PERMISSION",target,json.dumps(rights[target],ensure_ascii=False))
    missing=[target for target in targets if not any(rights[target].values())]
    origin=cfg["primary"]
    main_ok=bool(bots and any(b.name=="pronos" and b.can_post(origin) for b in bots))
    mirror_bot=any(
        b.can_post(cfg["torrent9_forward"]) and
        (b.name=="pronos" or b.can_post(origin))
        for b in bots
    )
    session_ready=all((os.getenv("TG_API_ID"),os.getenv("TG_API_HASH"),
                       os.getenv("TG_SESSION_STRING") or os.getenv("TG_STRING_SESSION")))
    try:
        personal_rights=asyncio.run(audit_personal_forward(origin,cfg["torrent9_forward"]))
    except Exception as exc:
        personal_rights={"ready":False,"error_type":type(exc).__name__}
    print("TELEGRAM_VIDEO_PERSONAL_FORWARD_AUDIT",json.dumps(personal_rights,ensure_ascii=False))
    print("TELEGRAM_VIDEO_PERMISSION_REPORT",json.dumps({
        "main_bot_can_publish_coupon":main_ok,
        "missing_bot_admin_channels":missing,
        "torrent9_bot_forward_possible":mirror_bot,
        "torrent9_personal_forward_secrets_present":bool(session_ready),
        "torrent9_personal_forward":personal_rights,
    },ensure_ascii=False))
    return 0 if main_ok else 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video", type=Path)
    p.add_argument("--audit-permissions", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if args.audit_permissions:
        return audit_permissions()
    if args.video is None:
        p.error("--video est requis hors audit permissions")
    config, receipt = load()
    if not args.dry_run and (not args.video.is_file() or args.video.stat().st_size < 1000):
        raise RuntimeError("Le MP4 de production manque")
    report = distribute(config, receipt, args.video, dry_run=args.dry_run)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SHORTS_TELEGRAM_DISTRIBUTION", json.dumps({
        "success": len([r for r in report["results"] if r["status"] in ("sent", "origin")]),
        "skipped": len([r for r in report["results"] if r["status"] == "already_claimed"]),
        "torrent9": report["torrent9"],
        "errors": report["errors"],
    }, ensure_ascii=False))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
