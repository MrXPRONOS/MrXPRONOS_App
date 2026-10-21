"""CinéX cross-promotion: 3 Mr XPRONOS channel ads with native URL buttons.

Run after the movie relay, and independently for an initial one-shot rollout.
Never sends an advertisement without a real Telegram URL button.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import io
import hashlib
import logging
from pathlib import Path
import os

from PIL import Image

LOG = logging.getLogger("cinex_promotions")
PROMO_INTERVAL = 4

# Exact SHA-256 of the three user-approved original PNGs.
ORIGINAL_SHA256 = {
    "actu": "fb86f14886237b9c2bf5a57f5693c48cf535f30f401ef367ad7e95288b2424f7",
    "live": "8bf4f79049a7885161899953ae91651c1f13a2c84e73c726b5091c7fdb18b9b2",
    "jour": "3ad1309cefdfa267a38e85327bbbb632be03a724827c2c656c6a8396dfee7fe9",
}
CAMPAIGNS = (
    ("actu", "@actufoot_mrxp", "ACTU FOOT",
     "⚽ Ne rate plus l’actualité du football !\n📰 Mercato, résultats et infos.\n🔥 Le foot au quotidien.\n👇 Rejoins Actu Foot !",
     "📰 REJOINDRE ACTU FOOT", "INFOS • MERCATO • RÉSULTATS"),
    ("live", "@mr_xpronos_vip", "PRONOS LIVE VIP",
     "🔴 Le match est en cours ?\n⚽ Retrouve nos signaux et coupons live.\n📊 Des analyses pendant les rencontres.\n👇 Rejoins Pronos Live VIP !",
     "🔴 REJOINDRE PRONOS LIVE", "DIRECT • SIGNAUX • ALERTES"),
    ("jour", "@mrxpronosfr", "COUPONS DU JOUR",
     "⚽ Les matchs du jour t’attendent !\n🎯 Découvre nos sélections.\n📊 Pronostics et analyses football.\n👇 Rejoins le canal !",
     "🎯 REJOINDRE COUPONS DU JOUR", "MATCHS • SÉLECTIONS • ANALYSES"),
)

def promo_assets_dir() -> Path:
    """Directory containing the three unmodified, original PNG images."""
    override = (os.getenv("CINEX_PROMO_ASSETS_DIR") or "").strip()
    return (Path(override).expanduser() if override else
            Path(__file__).resolve().parents[1] / "assets" / "promotions")


def poster_path(index: int) -> Path:
    return promo_assets_dir() / f"mrx_{CAMPAIGNS[index][0]}.png"


def render_poster(index: int) -> io.BytesIO:
    """Read the original PNG bytes: no generated, repainted or converted artwork."""
    path = poster_path(index)
    if not path.is_file():
        raise FileNotFoundError(f"PNG original manquant : {path}")
    original = path.read_bytes()
    # The original artwork was uploaded to GitHub and normalized to PNG,
    # changing the legacy checksum. Require the actual PNG, never generate
    # replacement artwork or refuse a user-uploaded original for a stale hash.
    digest = hashlib.sha256(original).hexdigest()
    if digest != ORIGINAL_SHA256[CAMPAIGNS[index][0]]:
        LOG.info("PNG GitHub validé par structure/dimensions ; ancienne empreinte obsolète : %s", path.name)
    if not original.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"Affiche non PNG : {path}")
    with Image.open(io.BytesIO(original)) as picture:
        if picture.format != "PNG":
            raise ValueError(f"Affiche non PNG : {path}")
        if not os.getenv("CINEX_PROMO_ASSETS_DIR") and picture.size != (1229, 1536):
            raise ValueError(f"Affiche GitHub de dimensions inattendues : {path.name} / {picture.size}")
        picture.verify()
    result = io.BytesIO(original)
    result.name = path.name
    return result


def campaign_caption(index: int) -> str:
    return CAMPAIGNS[index][3]


def campaign_button(index: int):
    return CAMPAIGNS[index][4], "https://t.me/" + CAMPAIGNS[index][1].lstrip("@")


def _cursor(state, target: str):
    return state.data.setdefault("promotions", {}).setdefault(target,
            {"last_film_total": 0, "next_index": 0, "sent": {}})


def due(state, target: str, film_total: int, *, force=False):
    entry=_cursor(state,target)
    index=int(entry["next_index"]) % len(CAMPAIGNS)
    # Four completed contents between consecutive adverts in each channel.
    # The total is durable, so two contents in one run + two in the next
    # correctly trigger the advert after the fourth content.
    return index if (force or film_total-int(entry["last_film_total"]) >= PROMO_INTERVAL) else None


async def _recently_published(client, channel, caption, *, limit=80, exclude_ids=()):
    """Avoid repeating identical ad after a failed GitHub state commit."""
    now=datetime.now(timezone.utc)
    async for msg in client.iter_messages(channel, limit=limit):
        if (int(getattr(msg, "id", 0) or 0) in exclude_ids or
            str(getattr(msg,"raw_text","") or "").strip() != caption):
            continue
        dt=getattr(msg,"date",None)
        if dt and dt.tzinfo is None:
            dt=dt.replace(tzinfo=timezone.utc)
        if dt and now-dt <= timedelta(minutes=45):
            return int(msg.id)
    return None


async def _send_bot_poster(bot, channel, index: int):
    from .bot_http import url_button
    label,url=campaign_button(index)
    picture = render_poster(index)  # Original required; never publish a text-only replacement.
    return await bot.send_file(channel, picture, caption=campaign_caption(index),
                               buttons=[[url_button(label, url, style="primary")]], force_document=False)


async def _bot_can_post(bot, channel, identity):
    """No fallback to unbuttoned user messages in Telegram channels."""
    try:
        from telethon import utils
        # Private channel IDs are accessible after this bot joins; do not
        # reuse a user's session-specific access hash in a bot request.
        peer_id=utils.get_peer_id(channel)
        try:
            entity=await bot.get_entity(peer_id)
        except (ValueError, TypeError):
            entity=await bot.get_entity(channel)
        perm=await bot.get_permissions(entity, identity)
        allowed=bool(getattr(perm,"is_creator",False) or
                     (getattr(perm,"is_admin",False) and getattr(perm,"post_messages",False)))
        return entity if allowed else None
    except Exception as exc:
        LOG.warning("Bot non-administrateur pour %s : %s",channel,type(exc).__name__)
        return None


async def publish_promotions(user_client,bot,private,primary,mirror,state,
                             *,force=False, private_fallback=False,
                             current_run_films: int = 0) -> dict[str,int]:
    """One campaign per channel per run; primary forwarded intact to mirror.

    Normal rotation requires four completed contents since the previous advert.
    That quota is cumulative across runs. However, a run with zero new public
    content can never emit an advert merely because an old quota was pending.

    force=True intentionally bypasses this guard for an explicit one-shot
    rollout or maintenance command.
    """
    report={"private":0,"public":0,"mirror":0,"skipped":0}
    current_run_films = max(0, int(current_run_films or 0))
    if not force and current_run_films == 0:
        LOG.info("Publicités différées : aucun nouveau contenu dans ce passage.")
        return report

    from telethon import utils
    from .mirror_policy import torrent9_paused
    if torrent9_paused():
        mirror = None  # Publicités publiques et privées conservées ; aucun transfert.
    if bot is None:
        raise RuntimeError("Le bot est requis pour de vrais boutons Telegram")
    # The original PNG is mandatory. Fail closed instead of sending text-only ads.
    for poster_index in range(len(CAMPAIGNS)):
        render_poster(poster_index)
    identity=await bot.get_me()
    first_id=str(utils.get_peer_id(primary))
    private_id=str(utils.get_peer_id(private))
    mirror_id=str(utils.get_peer_id(mirror)) if mirror is not None else ""
    total=len(state.data.get("processed",{}))
    mirror_total=len(state.data.get("mirrors",{}).get(mirror_id,{})) if mirror else 0
    # Send *primary first* so mirror can keep Telegram's "Forwarded from..." origin.
    ready=await _bot_can_post(bot,primary,identity)
    idx=due(state,first_id,total,force=force)
    if idx is not None and ready is not None:
        entry=_cursor(state,first_id)
        caption=campaign_caption(idx)
        found=await _recently_published(
            user_client, primary, caption,
            exclude_ids={int(v) for v in entry["sent"].values()}
        )
        if found is not None:
            post_id=found
            LOG.info("Annonce déjà présente dans le public, envoi ignoré (%s)",post_id)
        else:
            post=await _send_bot_poster(bot,ready,idx)
            post_id=int(post.id);report["public"]+=1
        entry["sent"][str(entry["next_index"])]=post_id
        entry["last_film_total"]=total;entry["next_index"]=int(entry["next_index"])+1
        state.save()
    elif idx is not None:
        report["skipped"]+=1
        LOG.error("Public principal : le bot doit être administrateur.")
    # Mirror advertising follows the same four-content interval when enabled.
    if mirror is not None and due(state,mirror_id,mirror_total,force=force) is not None:
        e=_cursor(state,mirror_id)
        # The selected ad must exist in primary; don't make a detached poster.
        want=int(e["next_index"]) % len(CAMPAIGNS)
        if ready is not None:
            # Retrieve a photo matching the current campaign from primary.
            # Prefer the persisted primary receipt; it remains valid even hours
            # after the ad (the 45-minute duplicate scan is only for recovery).
            primary_cursor=state.data.get("promotions",{}).get(first_id,{})
            primary_post=primary_cursor.get("sent",{}).get(str(e["next_index"]))
            if primary_post is None:
                primary_post=await _recently_published(
                    user_client,primary,campaign_caption(want),limit=150
                )
            if primary_post is not None:
                primary_post=int(primary_post)
                from .recovery import existing_native_forwards
                found_map=await existing_native_forwards(user_client,mirror,utils.get_peer_id(primary))
                if primary_post in found_map:
                    forwarded_id=found_map[primary_post]
                else:
                    msg=await user_client.forward_messages(mirror,primary_post,from_peer=primary)
                    forwarded_id=int(msg[0].id if isinstance(msg,list) else msg.id)
                    report["mirror"]+=1
                e["sent"][str(e["next_index"])]=forwarded_id
                e["last_film_total"]=mirror_total
                e["next_index"]=int(e["next_index"])+1
                state.save()
            else:
                report["skipped"]+=1
                LOG.warning("Annonce miroir différée : afficher d'abord sa version publique.")
        else:
            report["skipped"]+=1
    if due(state,private_id,total,force=force) is not None:
        ready_private=await _bot_can_post(bot,private,identity)
        if ready_private is not None:
            e=_cursor(state,private_id);idx=int(e["next_index"])%len(CAMPAIGNS)
            exists=await _recently_published(
                user_client, private, campaign_caption(idx),
                exclude_ids={int(v) for v in e["sent"].values()}
            )
            if exists is not None:
                msg_id=exists
            else:
                post=await _send_bot_poster(bot,ready_private,idx)
                msg_id=int(post.id);report["private"]+=1
            e["sent"][str(e["next_index"])]=msg_id
            e["last_film_total"]=total;e["next_index"]=int(e["next_index"])+1
            state.save()
        elif private_fallback:
            # In the Desire-only flow, the personal session is already allowed
            # to publish in its own private library. It cannot create coloured
            # bot inline keyboards, so preserve a clickable text URL instead.
            e=_cursor(state,private_id)
            idx=int(e["next_index"])%len(CAMPAIGNS)
            caption=campaign_caption(idx)+"\n\n🔗 "+campaign_button(idx)[1]
            found=await _recently_published(
                user_client, private, caption,
                exclude_ids={int(v) for v in e["sent"].values()}
            )
            if found is not None:
                msg_id=found
            else:
                image=render_poster(idx)
                post=await user_client.send_file(
                    private, image, caption=caption, force_document=False
                )
                msg_id=int(post.id)
                report["private"]+=1
            e["sent"][str(e["next_index"])]=msg_id
            e["last_film_total"]=total
            e["next_index"]=int(e["next_index"])+1
            state.save()
            LOG.warning("Promo privée envoyée avec lien texte ; ajouter le bot au privé pour un bouton bleu.")
        else:
            report["skipped"]+=1
            LOG.error("Privé : bot non-administrateur. Ajouter le bot avec Publier messages.")
    return report
