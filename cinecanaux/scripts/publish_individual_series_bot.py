#!/usr/bin/env python3
"""CinéX Séries : catalogue et publication de fiches uniquement par bots.

Ne fait jamais appel à TG_SESSION_STRING, Telethon ou à un compte personnel.
Un message épinglé récent est accessible avec getChat; tous les anciens
épinglages ne le sont PAS. Le webhook Radar peut capter les prochains pins.
Aucun envoi avant l'activation explicite du drapeau GitHub et le contrôle D1.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import quote

import requests

from audit_series_bots import BotAPI, is_admin, parse_channel_ids

CHAT = re.compile(r"^-100\d{6,}$")
INVITE = re.compile(r"^https://t\.me/(?:\+[A-Za-z0-9_-]{12,}|joinchat/[A-Za-z0-9_-]{12,})/?$")
FOLDER = re.compile(r"^https://t\.me/addlist/[A-Za-z0-9_-]{8,}$")
TOKEN = re.compile(r"^[a-zA-Z0-9_-]{24}$")
HANDLE = "seriesvf_cinex"
PUBLIC = "-1004406527554"
RESCUE = "-1003822435811"
ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "telegram-film-relay/state/rescue_channels.json"


def parse_season(s: str) -> int | None:
    match = re.search(r"(?:^|[\s#|[(])(?:saison|season|s)[\s.:-]*0?([1-9][0-9]?)(?=$|[\s#|)\]:._-])",
                      (s or "")[:2500], flags=re.I)
    season = int(match.group(1)) if match else 0
    return season if 1 <= season <= 50 else None


def parse_expected(s: str) -> int | None:
    s = (s or "")[:2500]
    m = re.search(r"(?:^|[^\d])([1-9][0-9]?)\s*(?:épisodes?|episodes?|eps\b)", s, re.I)
    if not m:
        m = re.search(r"(?:nombre\s+d['’]\s*épisodes?|épisodes?\s*(?:au\s*total)?)[\s:=-]*([1-9][0-9]?)",s,re.I)
    return int(m.group(1)) if m else None


def parse_season_counts(value: str) -> dict[str,int]:
    mapping = {}
    for term in re.split(r"[\s,;]+", str(value or "").strip()):
        if not term:
            continue
        match = re.fullmatch(r"(-100[0-9]{6,}):([1-9][0-9]?)", term)
        if not match or not 1 <= int(match.group(2)) <= 50:
            raise ValueError("CINEX_SERIES_SEASON_COUNTS : format ID:NB_SAISONS invalide")
        mapping[match.group(1)] = int(match.group(2))
    return mapping


def d1(sql: str, params: list | None = None) -> list[dict]:
    token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    db = os.getenv("CINERADAR_D1_DATABASE_ID", "").strip()
    if not token or not account or not db:
        raise RuntimeError("D1 non configurée : aucune publication")
    response = requests.post(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{db}/query",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        json={"sql": sql, "params": params or []}, timeout=(8, 25))
    try:
        data = response.json()
    except ValueError as error:
        raise RuntimeError("D1 réponse invalide") from error
    if response.status_code != 200 or not data.get("success") or not data.get("result") or not data["result"][0].get("success"):
        raise RuntimeError("D1 requête non confirmée (HTTP %s)" % response.status_code)
    return data["result"][0].get("results") or []


def request_bot(bot: str, method: str, values: dict):
    response = requests.post("https://api.telegram.org/bot" + bot + "/" + method,
                             json=values, timeout=(8, 25))
    try:
        data = response.json()
    except ValueError as error:
        raise RuntimeError("Réponse Telegram indéterminée (vérification manuelle requise)") from error
    if not response.ok or data.get("ok") is not True:
        desc = str(data.get("description") or "").lower()
        if method == "editMessageReplyMarkup" and "message is not modified" in desc:
            return True
        raise RuntimeError("Bot API %s code %s" % (method, data.get("error_code", response.status_code)))
    return data["result"]


def check_publisher(bot: BotAPI, chat_id: str, me_id: int):
    channel = bot.call("getChat", {"chat_id": chat_id})
    if str(channel.get("id")) != chat_id or channel.get("type") != "channel":
        raise RuntimeError("ID de canal incohérent")
    role = bot.call("getChatMember", {"chat_id": chat_id, "user_id": me_id})
    if not is_admin(role) or (role.get("status") == "administrator" and not role.get("can_post_messages", False)):
        raise RuntimeError("Le bot éditeur n'a pas le droit de publier dans " + chat_id)
    return channel


def rescue_link(publisher: BotAPI, me_id: int) -> str:
    ref = json.loads(STATE.read_text(encoding="utf-8"))["channels"]["@seriesvf_cinex"]
    if str(ref["rescue_channel_id"]) != RESCUE or str(ref["public_id"]) != PUBLIC:
        raise RuntimeError("Le canal de secours ne correspond pas au registre")
    chat = check_publisher(publisher, RESCUE, me_id)
    live = str(chat.get("invite_link") or "").strip()
    supplied = os.getenv("CINEX_SERIES_RESCUE_INVITE_URL", "").strip()
    if INVITE.fullmatch(live):
        return live
    if INVITE.fullmatch(supplied) and hashlib.sha256(supplied.encode()).hexdigest() == ref["invite_sha256"]:
        return supplied
    raise RuntimeError("Lien d'invitation du secours Séries introuvable ou non vérifié")


def catalogue_complete(chat_id: str) -> dict:
    source = d1("SELECT expected_seasons FROM cine_series_channels WHERE chat_id=?", [chat_id])
    declared = int(source[0].get("expected_seasons") or 0) if source else 0
    seasons = d1("SELECT season,expected_episodes FROM cine_series_seasons WHERE chat_id=? ORDER BY season", [chat_id])
    posters = d1("SELECT season,source_message_id,caption FROM cine_series_posters WHERE chat_id=? ORDER BY season", [chat_id])
    media = d1("SELECT season,episode,source_message_id FROM cine_series_episodes WHERE chat_id=? ORDER BY season,episode", [chat_id])
    if not declared or not seasons or len(seasons) != declared or len(posters) != declared or len(seasons) > 50 or len(media) > 300:
        return {"ready": False, "reason": "saisons, affiches ou épisodes manquants"}
    total = 0
    for n, season in enumerate(seasons, 1):
        if int(season["season"]) != n or int(posters[n - 1]["season"]) != n:
            return {"ready": False, "reason": "ordre des saisons incomplet"}
        expected = int(season.get("expected_episodes") or 0)
        episodes = [x for x in media if int(x["season"]) == n]
        if not 1 <= expected <= 100 or len(episodes) != expected:
            return {"ready": False, "reason": "nombre d'épisodes non vérifié pour S%d" % n}
        if any(int(x["episode"]) != i or int(x["source_message_id"]) <= 0
               for i, x in enumerate(episodes, 1)):
            return {"ready": False, "reason": "épisodes non contigus pour S%d" % n}
        total += expected
    if total != len(media) or not total:
        return {"ready": False, "reason": "catalogue incomplet"}
    return {"ready": True, "count": total, "seasons": len(seasons), "main_poster": int(posters[0]["source_message_id"])}


def keyboard(token, rescue, folder):
    if not TOKEN.fullmatch(token) or not INVITE.fullmatch(rescue) or not FOLDER.fullmatch(folder):
        raise RuntimeError("Paramètres des boutons invalides")
    return {"inline_keyboard": [
        [{"text": "📥 Télécharger toutes les saisons", "url": "https://t.me/CineRadarFr_Bot?start=sr_" + token, "style": "success"}],
        [{"text": "🛟 Rejoindre le canal de secours", "url": rescue, "style": "danger"}],
        [{"text": "📂 Rejoindre le dossier", "url": folder, "style": "primary"}],
    ]}


def sync_channel(publisher: BotAPI, publisher_id: int, radar_id: int, chat_id: str, rights: bool, expected_seasons: int | None = None):
    chat = publisher.call("getChat", {"chat_id": chat_id})
    if str(chat.get("id")) != chat_id or chat.get("type") != "channel":
        raise RuntimeError("Canal privé inaccessible ou différent du registre")
    role = publisher.call("getChatMember", {"chat_id": chat_id, "user_id": publisher_id})
    radar = publisher.call("getChatMember", {"chat_id": chat_id, "user_id": radar_id})
    publisher_ok = is_admin(role)
    radar_ok = is_admin(radar)
    title = str(chat.get("title") or "").strip()[:150]
    d1("INSERT INTO cine_series_channels(chat_id,title,publisher_access,radar_access,rights_attested,expected_seasons,verified_at) VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP) "
       "ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title,publisher_access=excluded.publisher_access,"
       "radar_access=excluded.radar_access,rights_attested=excluded.rights_attested,"
       "expected_seasons=COALESCE(excluded.expected_seasons,cine_series_channels.expected_seasons),verified_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP",
       [chat_id, title, "verified" if publisher_ok else "not_admin", "verified" if radar_ok else "not_admin", 1 if rights else 0,expected_seasons])

    pin = chat.get("pinned_message") or {}
    caption = str(pin.get("caption") or pin.get("text") or "").strip()
    season = parse_season(caption)
    got_pin = bool(pin.get("photo"))
    if got_pin and season and int(pin.get("message_id") or 0) > 0:
        d1("INSERT INTO cine_series_posters(chat_id,season,source_message_id,caption) VALUES(?,?,?,?) "
           "ON CONFLICT(chat_id,season) DO UPDATE SET source_message_id=excluded.source_message_id,"
           "caption=excluded.caption,observed_at=CURRENT_TIMESTAMP",
           [chat_id,season,int(pin["message_id"]),caption[:1800]])
        expected = parse_expected(caption)
        if expected:
            d1("INSERT INTO cine_series_seasons(chat_id,season,expected_episodes) VALUES(?,?,?) "
               "ON CONFLICT(chat_id,season) DO UPDATE SET expected_episodes=excluded.expected_episodes,observed_at=CURRENT_TIMESTAMP",
               [chat_id,season,expected])
    return {
        "chat_id": chat_id, "title": title, "publisher_admin": publisher_ok, "radar_admin": radar_ok,
        "latest_pin": (int(pin["message_id"]) if pin.get("message_id") else None),
        "latest_pin_season": season, "latest_pin_is_photo": got_pin,
    }


def publish_one(bot: str, bot_api: BotAPI, publisher_id: int, chat_id: str, rescue: str, folder: str):
    source = d1("SELECT title,rights_attested,radar_access,publisher_access FROM cine_series_channels WHERE chat_id=? AND enabled=1", [chat_id])
    if not source or source[0]["rights_attested"] != 1 or source[0]["radar_access"] != "verified" or source[0]["publisher_access"] != "verified":
        return {"chat_id": chat_id, "status": "BLOCKED_RIGHTS_OR_BOT_ACCESS"}
    complete = catalogue_complete(chat_id)
    if not complete["ready"]:
        return {"chat_id": chat_id, "status": "NOT_READY", "reason": complete["reason"]}
    existing = d1("SELECT token,public_post_id,rescue_post_id,state FROM cine_series_publications WHERE chat_id=?", [chat_id])
    if existing:
        record = existing[0]
        if record["state"] == "published":
            markup = keyboard(record["token"], rescue, folder)
            for cid, mid in [(PUBLIC,record["public_post_id"]),(RESCUE,record["rescue_post_id"])]:
                if not mid:
                    raise RuntimeError("Publication D1 incohérente, ne pas renvoyer")
                request_bot(bot, "editMessageReplyMarkup", {"chat_id": cid, "message_id": int(mid), "reply_markup": markup})
            return {"chat_id": chat_id, "status": "UPDATED_IN_PLACE"}
        return {"chat_id": chat_id, "status": "PENDING_MANUAL_REVIEW"}
    token = secrets.token_urlsafe(18)
    if not TOKEN.fullmatch(token):
        raise RuntimeError("Token d'accès de série invalide")
    markup = keyboard(token, rescue, folder)
    check_publisher(bot_api, chat_id, publisher_id)
    # Transaction before the first API call: a timeout must NOT duplicate posts.
    d1("INSERT INTO cine_series_publications(token,chat_id,state) VALUES(?,?,'pending')", [token,chat_id])
    poster_id = complete["main_poster"]
    public_post = request_bot(bot,"copyMessage",{
        "chat_id": PUBLIC, "from_chat_id": chat_id, "message_id": poster_id,
        "reply_markup": markup, "disable_notification": True})
    public_id = int(public_post["message_id"])
    d1("UPDATE cine_series_publications SET public_post_id=?,updated_at=CURRENT_TIMESTAMP WHERE token=? AND state='pending'",
       [public_id,token])
    rescue_post = request_bot(bot,"copyMessage",{
        "chat_id": RESCUE, "from_chat_id": chat_id, "message_id": poster_id,
        "reply_markup": markup, "disable_notification": True})
    rescue_id = int(rescue_post["message_id"])
    d1("UPDATE cine_series_publications SET rescue_post_id=?,state='published',updated_at=CURRENT_TIMESTAMP WHERE token=? AND state='pending'",
       [rescue_id,token])
    return {"chat_id": chat_id, "status": "PUBLISHED", "public_message_id": public_id,
            "rescue_message_id": rescue_id, "seasons": complete["seasons"], "episodes": complete["count"]}


def main():
    ids = parse_channel_ids(os.getenv("CINEX_SERIES_CHANNEL_IDS", ""))
    if not ids:
        print("CINEX_SERIES_CHANNEL_IDS est vide — rien à modifier")
        return 0
    bot_token = os.getenv("CINEX_PUBLISH_BOT_TOKEN", "").strip()
    radar_token = os.getenv("CINEX_RADAR_BOT_TOKEN", "").strip()
    if not bot_token or not radar_token:
        raise RuntimeError("Les jetons des deux bots sont requis")
    bot = BotAPI(bot_token)
    radar = BotAPI(radar_token)
    me = bot.call("getMe", {})
    radar_me = radar.call("getMe", {})
    if str(radar_me.get("username","")).lower() != "cineradarfr_bot":
        raise RuntimeError("Le jeton Ciné Radar ne correspond pas au bot officiel")
    rights = os.getenv("CINEX_SERIES_RIGHTS_ATTESTED","").lower() == "true"
    declared_counts = parse_season_counts(os.getenv("CINEX_SERIES_SEASON_COUNTS",""))
    publish = os.getenv("CINEX_SERIES_PUBLISH_ENABLED","").lower() == "true"
    results = []
    for cid in ids:
        try:
            result = sync_channel(bot,int(me["id"]),int(radar_me["id"]),cid,rights,declared_counts.get(cid))
        except Exception as error:
            results.append({"chat_id": cid, "status": "SOURCE_ERROR", "error": str(error)[:150]})
            continue
        results.append({**result, "status": "INDEXED"})
    # Validate full public/rescue prerequisites BEFORE the first publication.
    if publish:
        if not rights:raise RuntimeError("CINEX_SERIES_RIGHTS_ATTESTED doit valoir true")
        gate = d1("SELECT value FROM bot_settings WHERE setting_key='cine_delivery_enabled'")
        if not gate or gate[0].get("value") != "1":
            raise RuntimeError("CINEX_DOWNLOADS_ENABLED n'est pas activé dans D1")
        public_chat = check_publisher(bot,PUBLIC,int(me["id"]))
        if str(public_chat.get("username","")).lower() != HANDLE:
            raise RuntimeError("Canal public Séries inattendu")
        rescue = rescue_link(bot,int(me["id"]))
        folder = os.getenv("CINEX_SERIES_FOLDER_URL","").strip()
        if not FOLDER.fullmatch(folder):
            raise RuntimeError("CINEX_SERIES_FOLDER_URL manquante (lien https://t.me/addlist/...)")
        for entry in results:
            if entry["status"] != "INDEXED":
                continue
            try:
                published = publish_one(bot_token,bot,int(me["id"]),entry["chat_id"],rescue,folder)
                entry.update(published)
            except Exception as error:
                entry.update({"status":"PUBLICATION_REQUIRES_REVIEW","error":str(error)[:150]})
    Path("cinex-series-sync-report.json").write_text(json.dumps({
        "mode":"bot_only", "publish_enabled":publish,"rights_attested":rights,
        "count":len(ids),"channels":results},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for item in results:
        print("SERIE_SYNC",item["chat_id"],item["status"],item.get("latest_pin_season",""))
    return 1 if any(x["status"] in ("SOURCE_ERROR","PUBLICATION_REQUIRES_REVIEW") for x in results) else 0


if __name__=="__main__":
    try:sys.exit(main())
    except Exception as error:
        print("CINEX_SERIES_BLOCKED",str(error),file=sys.stderr)
        sys.exit(1)
