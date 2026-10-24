"""Séquence de partenariat CinéX : ouverture du canal, puis miroir ordonné."""
import argparse
import asyncio
import io
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from telethon import TelegramClient, utils
from film_relay.bot_http import url_button
from telethon.sessions import StringSession

from film_relay.bot_http import BotHTTPClient
from film_relay.runner import resolve_peer
from film_relay.recovery import existing_native_forwards

ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "assets/partenariat-canal-original.jpg"
CAPTION = (
    "🚀 FAITES GRANDIR VOTRE CANAL TELEGRAM SANS EFFORT !\n\n"
    "J'alimente votre canal avec du contenu adapté : films, animés, actus, etc.\n"
    "✅ Contenu régulier  ✅ Aucun effort  ✅ Vous gardez le contrôle\n\n"
    "🤝 En échange, je publie occasionnellement mes publicités selon notre accord.\n"
    "📩 @mr_xpronos — Réf. PARTENARIAT-CANAL"
)
MESSAGE = ("Bonjour 👋 Je suis intéressé par votre partenariat Telegram. "
           "Référence : PARTENARIAT-CANAL")
LINK = "https://t.me/mr_xpronos?text=" + quote(MESSAGE, safe="")
TARGETS = {
    "films": ("TG_PUBLIC_CHANNEL", "state/state.json"),
    "desir": ("DESIR_PUBLIC_CHANNEL", "state/desir_state.json"),
    "comedie": ("COMEDIE_PUBLIC_CHANNEL", "state/comedie_state.json"),
    "anime": ("ANIME_PUBLIC_CHANNEL", "state/anime_state.json"),
}

def settings(category):
    env, path = TARGETS[category]
    public = (os.getenv(env) or ("@CineXDesirfr" if category == "desir" else "")).strip()
    mirror = (os.getenv("TG_MIRROR_CHANNEL") or "@Torrent9SeriesFilms").strip()
    if mirror.lower() == "@torrent9seriesfilm":
        mirror = "@Torrent9SeriesFilms"  # ancienne variable GitHub corrigee
    if not public or mirror.lower() != "@torrent9seriesfilms" or public.lower() == mirror.lower():
        raise RuntimeError("Destinations CinéX invalides pour " + category)
    return public, mirror, ROOT / path, ROOT / (".partnership_" + category + ".json")

def load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)

def posts_after_intro(category, state, origin_key, anchor):
    result = [(anchor, "intro", "")]
    items = state.get("processed" if category == "films" else "completed", {})
    for key, item in items.items():
        pid = item.get("public_message_id" if category == "films" else "public_id")
        if pid and int(pid) > anchor:
            result.append((int(pid), "film", str(key)))
    if category == "films" and os.getenv("CINEX_SERIES_CATALOG_ENABLED") == "true":
        catalog = load(ROOT / "state" / "series_state.json")
        for key, item in catalog.get("completed", {}).items():
            pid = item.get("public_id")
            if str(key).startswith("tv-series:") and pid and int(pid) > anchor:
                result.append((int(pid), "series", str(key)))
    cursor = state.get("promotions", {}).get(origin_key, {})
    for rotation, pid in cursor.get("sent", {}).items():
        if int(pid) > anchor:
            result.append((int(pid), "promo", str(rotation)))
    result.sort()
    ids = [item[0] for item in result]
    if len(ids) != len(set(ids)) or sum(kind == "film" for _,kind,_ in result) > 2:
        raise RuntimeError("Messages de cycle incohérents : doublons ou plus de deux films.")
    return result

async def session():
    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")
    sid = (os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
           or os.getenv("TG_STREAM_SESSION"))
    if not (api_id and api_hash and sid):
        raise RuntimeError("Secrets Telegram manquants")
    client = TelegramClient(StringSession(sid), int(api_id), api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError("Session personnelle non autorisée")
    return client, int(api_id), api_hash

async def before(category):
    public, mirror, _, marker = settings(category)
    data = IMAGE.read_bytes()
    if not data.startswith(bytes.fromhex("ffd8ff")):
        raise RuntimeError("Image originale JPG absente/invalide")
    client, api_id, api_hash = await session()
    bot = None
    try:
        public_peer = await resolve_peer(client, public)
        token = (os.getenv("CINEX_BOT_TOKEN") or "").strip()
        if not token:
            raise RuntimeError("Bot de publication requis")
        bot = BotHTTPClient(token, client)
        bot_peer = await bot.get_entity(public)
        if utils.get_peer_id(public_peer) != utils.get_peer_id(bot_peer):
            raise RuntimeError("Canal différent pour le bot et le compte")
        perm = await bot.get_permissions(bot_peer, await bot.get_me())
        if not (getattr(perm,"is_creator",False) or
                (getattr(perm,"is_admin",False) and getattr(perm,"post_messages",False))):
            raise RuntimeError("Bot sans droit de publication : " + public)
        existing = None
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=90)
        async for item in client.iter_messages(public_peer,limit=75):
            if item.date and item.date < cutoff:
                break
            if "PARTENARIAT-CANAL" in (item.raw_text or "") and item.photo:
                existing = int(item.id)
                break
        if existing:
            anchor = existing
            print("AFFICHE_DEJA_PUBLIEE", category, anchor)
        else:
            stream = io.BytesIO(data)
            stream.name = IMAGE.name
            sent = await bot.send_file(
                bot_peer, stream, caption=CAPTION,
                buttons=[[url_button("💬 Proposer un partenariat",LINK,style="primary")]],
                force_document=False)
            anchor = int(sent.id)
            print("AFFICHE_PUBLIEE", category, anchor)
        save(marker, {"category":category, "public":public,"mirror":mirror,"anchor":anchor})
    finally:
        if bot:
            await bot.disconnect()
        await client.disconnect()


def film_single_transfer_enabled():
    """Scoped owner authorization: other Torrent9 transfers remain paused."""
    from film_relay.mirror_policy import POLICY
    if os.getenv("CINEX_SINGLE_FILM_FORWARD_PAUSED", "").lower() in ("1", "yes", "true", "on"):
        return False
    try:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return policy.get("film_single_forward_enabled") is True


def pending_main_films(state, mirror_key):
    """Newest successfully published *film* poster first, excluding receipts."""
    processed = state.get("processed", {})
    transferred = state.get("mirrors", {}).get(mirror_key, {})
    candidates = []
    for item_key, receipt in processed.items():
        if item_key in transferred or not isinstance(receipt, dict):
            continue
        public_id = receipt.get("public_message_id")
        if public_id:
            candidates.append((str(item_key), int(public_id)))
    candidates.sort(key=lambda row: row[1], reverse=True)
    return candidates


async def forward_one_main_film():
    """At most ONE new native forward from primary CineX to Torrent9 per run.

    Does not depend on the disabled pre-content partnership announcement.
    Existing forwarded posts are reconciled before any new send, and a
    durable receipt is saved immediately after Telegram accepts a forward.
    """
    if not film_single_transfer_enabled():
        print("UN_SEUL_FILM_SUSPENDU : aucun transfert autorise.")
        return 0
    public_name, mirror_name, state_path, _ = settings("films")
    state = load(state_path)
    if not state.get("processed"):
        print("AUCUN_FILM_DISPONIBLE : rien a transferer.")
        return 0
    client, _, _ = await session()
    try:
        source = await resolve_peer(client, public_name)
        target = await resolve_peer(client, mirror_name)
        source_id = utils.get_peer_id(source)
        mirror_key = str(utils.get_peer_id(target))
        if source_id == utils.get_peer_id(target):
            raise RuntimeError("Le canal principal et le miroir sont identiques.")
        if getattr(source, "noforwards", False):
            raise RuntimeError("CineX principal interdit les transferts avec attribution.")
        if not getattr(target, "broadcast", False):
            raise RuntimeError("Le canal secondaire n'est pas un canal broadcast.")
        current = await client.get_me()
        permission = await client.get_permissions(target, current)
        if not (getattr(permission, "is_creator", False) or
                (getattr(permission, "is_admin", False) and
                 getattr(permission, "post_messages", False))):
            raise RuntimeError("Le compte Telegram ne peut pas publier dans Torrent9.")
        mirrored = state.setdefault("mirrors", {}).setdefault(mirror_key, {})
        prior = await existing_native_forwards(client, target, source_id, limit=900)
        transferred = 0
        for item_key, public_id in pending_main_films(state, mirror_key):
            if public_id in prior:
                mirrored[item_key] = int(prior[public_id])
                save(state_path, state)
                print("TRANSFERT_EXISTANT : public=", public_id,
                      "miroir=", prior[public_id])
                continue
            original = await client.get_messages(source, ids=public_id)
            if not original or getattr(original, "noforwards", False):
                print("FILM_INACCESSIBLE_OU_PROTEGE :", public_id)
                continue
            forwarded = await client.forward_messages(
                target, int(public_id), from_peer=source
            )
            if isinstance(forwarded, list):
                forwarded = forwarded[0] if forwarded else None
            if forwarded is None or not getattr(forwarded, "id", None):
                raise RuntimeError("Telegram n'a pas confirme le transfert du film.")
            mirrored[item_key] = int(forwarded.id)
            save(state_path, state)
            transferred = 1
            print("UN_FILM_TRANSFERE :", public_name, public_id,
                  "->", mirror_name, forwarded.id)
            break  # Hard limit, even when many earlier films are pending.
        if not transferred:
            print("AUCUN_NOUVEAU_TRANSFERT : aucun film eligible non duplique.")
        return transferred
    finally:
        await client.disconnect()


async def after(category):
    if category == "films":
        return await forward_one_main_film()
    from film_relay.mirror_policy import torrent9_paused
    if torrent9_paused():
        print('TORRENT9_SUSPENDU : aucun transfert, aucune reprise des messages en attente.')
        return
    public, mirror, state_path, marker = settings(category)
    receipt = load(marker)
    if (receipt.get("category"), receipt.get("public"), receipt.get("mirror")) != (category, public, mirror):
        raise RuntimeError("Affiche préalable de cette catégorie introuvable.")
    anchor = int(receipt["anchor"])
    state = load(state_path)
    client, _, _ = await session()
    try:
        source = await resolve_peer(client,public)
        target = await resolve_peer(client,mirror)
        if getattr(source,"noforwards",False):
            raise RuntimeError("Le canal source bloque les transferts.")
        source_key = str(utils.get_peer_id(source))
        mirror_key = str(utils.get_peer_id(target))
        sequence = posts_after_intro(category,state,source_key,anchor)
        prior = await existing_native_forwards(client,target,utils.get_peer_id(source),limit=450)
        forwarded = {}
        for origin_id, kind, key in sequence:
            if origin_id in prior:
                dest_id = int(prior[origin_id])
                print("MIROIR_EXISTANT",category,kind,origin_id,dest_id)
            else:
                message = await client.forward_messages(target,origin_id,from_peer=source)
                message = message[0] if isinstance(message,list) else message
                dest_id = int(message.id)
                print("TRANSFERT",category,kind,origin_id,dest_id)
                await asyncio.sleep(max(15.0, float(os.getenv('CINEX_FORWARD_PAUSE_SECONDS', '18'))))
            forwarded[origin_id] = dest_id
            if kind == "film":
                mirror_state = state.setdefault("mirrors",{}).setdefault(mirror_key,{})
                mirror_state[key if category=="films" else str(origin_id)] = dest_id
            if kind == "series":
                series_path = ROOT / "state" / "series_state.json"
                series_state = load(series_path)
                series_state.setdefault("mirrors",{}).setdefault(mirror_key,{})[str(origin_id)] = dest_id
                save(series_path, series_state)
            save(state_path,state)
        cursor = state.get("promotions",{}).get(source_key,{})
        if cursor:
            target_cursor = state.setdefault("promotions",{}).setdefault(
                mirror_key,{"sent":{},"next_index":0,"last_film_total":0})
            for origin_id,kind,rotation in sequence:
                if kind == "promo":
                    target_cursor.setdefault("sent",{})[rotation] = forwarded[origin_id]
            target_cursor["next_index"] = max(int(target_cursor.get("next_index",0)),
                                               int(cursor.get("next_index",0)))
            target_cursor["last_film_total"] = len(state.get("mirrors",{}).get(mirror_key,{}))
        save(state_path,state)
        print("CYCLE_OK",category,[(kind,origin_id) for origin_id,kind,_ in sequence])
    finally:
        await client.disconnect()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", choices=tuple(TARGETS), required=True)
    parser.add_argument("--phase", choices=("before","after"), required=True)
    args=parser.parse_args()
    asyncio.run(before(args.category) if args.phase=="before" else after(args.category))

if __name__=="__main__":
    main()
