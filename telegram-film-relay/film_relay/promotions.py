"""CinéX cross-promotion: 3 Mr XPRONOS channel ads with native URL buttons.

Run after the movie relay, and independently for an initial one-shot rollout.
Never sends an advertisement without a real Telegram URL button.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import io
import logging
from pathlib import Path
import os

from PIL import Image

LOG = logging.getLogger("cinex_promotions")
CAMPAIGNS = (
    ("actu", "@actufoot_mrxp", "ACTU FOOT",
     "⚽ ACTU FOOT\n📰 Mercato, infos et résultats du football.\n📲 Rejoins le canal pour suivre l’actualité.",
     "📰 ACTU FOOT", "INFOS • MERCATO • RÉSULTATS"),
    ("live", "@mr_xpronos_vip", "PRONOS LIVE VIP",
     "⚡ PRONOS LIVE VIP\n🔴 Analyses et signaux pendant les matchs.\n📲 Suis les opportunités en direct.",
     "⚡ PRONOS LIVE", "DIRECT • SIGNAUX • ALERTES"),
    ("jour", "@mrxpronosfr", "COUPONS DU JOUR",
     "🎯 COUPONS DU JOUR\n⚽ Sélections et analyses des matchs du jour.\n📲 Découvre les nouveaux coupons.",
     "⚽ PRONOS DU JOUR", "MATCHS • SÉLECTIONS • ANALYSES"),
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
    if not original.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"Affiche non PNG : {path}")
    with Image.open(io.BytesIO(original)) as picture:
        if picture.format != "PNG":
            raise ValueError(f"Affiche non PNG : {path}")
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
    # Exactly two completed films between consecutive adverts in each channel.
    return index if (force or film_total-int(entry["last_film_total"]) >= 2) else None


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
    from telethon import Button
    label,url=campaign_button(index)
    try:
        picture = render_poster(index)
    except (FileNotFoundError, ValueError, OSError) as exc:
        # Keep approved text, original link button and campaign order.
        # Never invent another poster when the approved PNG is unavailable.
        LOG.warning("Affiche officielle absente/invalide (%s) : annonce texte", type(exc).__name__)
        return await bot.send_message(
            channel, campaign_caption(index), buttons=[[Button.url(label, url)]]
        )
    return await bot.send_file(channel, picture, caption=campaign_caption(index),
                               buttons=[[Button.url(label,url)]], force_document=False)


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
                             *,force=False) -> dict[str,int]:
    """One campaign per channel per run; primary forwarded intact to mirror.

    A campaign runs once after exactly 2 additional films on each channel. In the mirror,
    it forwards the actual branded/public post with the Telegram source header.
    """
    from telethon import utils
    if bot is None:
        raise RuntimeError("Le bot est requis pour de vrais boutons Telegram")
    # The PNG is optional for delivery, not for artwork: when missing,
    # the bot sends the original three-line caption with its URL button.
    identity=await bot.get_me()
    first_id=str(utils.get_peer_id(primary))
    private_id=str(utils.get_peer_id(private))
    mirror_id=str(utils.get_peer_id(mirror)) if mirror is not None else ""
    total=len(state.data.get("processed",{}))
    mirror_total=len(state.data.get("mirrors",{}).get(mirror_id,{})) if mirror else 0
    report={"private":0,"public":0,"mirror":0,"skipped":0}
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
        entry["last_film_total"]=(total if force else min(total, int(entry["last_film_total"])+2));entry["next_index"]=int(entry["next_index"])+1
        state.save()
    elif idx is not None:
        report["skipped"]+=1
        LOG.error("Public principal : le bot doit être administrateur.")
    # Ad forwarded in the mirror only after 2–3 forwarded films there.
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
                e["last_film_total"]=(mirror_total if force else min(mirror_total, int(e["last_film_total"])+2))
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
            e["last_film_total"]=(total if force else min(total, int(e["last_film_total"])+2));e["next_index"]=int(e["next_index"])+1
            state.save()
        else:
            report["skipped"]+=1
            LOG.error("Privé : bot non-administrateur. Ajouter le bot avec Publier messages.")
    return report
