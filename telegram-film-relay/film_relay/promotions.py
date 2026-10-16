"""CinéX cross-promotion: 3 Mr XPRONOS channel ads with native URL buttons.

Run after the movie relay, and independently for an initial one-shot rollout.
Never sends an advertisement without a real Telegram URL button.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
import io
import logging
import math
from pathlib import Path
import os

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

LOG = logging.getLogger("cinex_promotions")
CAMPAIGNS = (
    ("actu", "@actufoot_mrxp", "ACTU FOOT",
     "⚽ Infos, mercato, résultats : reste au cœur du foot !", "📰 ACTU FOOT",
     "INFOS • MERCATO • RÉSULTATS"),
    ("live", "@mr_xpronos_vip", "PRONOS LIVE VIP",
     "🔴 Matchs en direct, signaux et coupons live !", "⚡ PRONOS LIVE",
     "DIRECT • SIGNAUX • ALERTES"),
    ("jour", "@mrxpronosfr", "COUPONS DU JOUR",
     "🎯 Sélections et analyses des matchs du jour !", "⚽ PRONOS DU JOUR",
     "MATCHS • SÉLECTIONS • ANALYSES"),
)


def _font(size, bold=True):
    folder = Path("/usr/share/fonts/truetype/dejavu")
    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    locations = (
        folder / filename,
        Path("/usr/share/fonts/truetype/liberation2") /
        ("LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf"),
    )
    for path in locations:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _center(draw, y, text, font, color, width=1080, stroke_width=0, stroke_fill=None):
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    x = (width - (bbox[2]-bbox[0])) // 2
    draw.text((x, y), text, font=font, fill=color,
              stroke_width=stroke_width, stroke_fill=stroke_fill)


def render_poster(index: int) -> io.BytesIO:
    """Render a native 1080x1350 premium navy/gold photo at runtime.

    No external hosting, file upload, image token or unstable URL is needed.
    """
    key, handle, headline, caption, button, descriptor = CAMPAIGNS[index]
    w, h = 1080, 1350
    im = Image.new("RGB", (w, h), "#07111F")
    # Reuse the Mr XPRONOS repository football artwork when available.
    art = Path(__file__).resolve().parents[2] / "assets/images/blog-hero-ball.webp"
    if art.is_file():
        bg = Image.open(art).convert("RGB")
        scale = max(w / bg.width, h / bg.height)
        bg = bg.resize((math.ceil(bg.width * scale), math.ceil(bg.height * scale)),
                       Image.Resampling.LANCZOS)
        bg = bg.crop(((bg.width-w)//2, (bg.height-h)//2,
                      (bg.width+w)//2, (bg.height+h)//2))
        bg = ImageEnhance.Brightness(bg).enhance(0.31)
        im.paste(bg)
    overlay = Image.new("RGBA", (w,h), (0,0,0,0))
    od = ImageDraw.Draw(overlay)
    for y in range(h):
        opacity = 105 + int(125 * abs((y-h/2)/(h/2)))
        od.line([(0,y),(w,y)],fill=(2, 9, 23,min(250,opacity)),width=1)
    im = Image.alpha_composite(im.convert("RGBA"), overlay)
    d=ImageDraw.Draw(im)
    gold="#E7BE65"; soft="#FFEDBD"; white="#F6F8FF"
    # restrained premium light strips + stadium arcs
    d.rounded_rectangle([65,68,1015,1280],radius=40,
                        outline=(220,171,71,185),width=4)
    d.arc([75, 340, 1005, 940],185,355,fill=(210,161,65,105),width=8)
    d.arc([165,420,915,850],184,356,fill=(196,146,53,70),width=5)
    for x in range(90,1000,85):
        d.ellipse((x,180,(x+4),184),fill=(254,220,142,110))
    # brand and hierarchy
    _center(d,115,"♛",_font(95), gold)
    _center(d,235,"MR X PRONOS",_font(53),soft)
    d.line((328,325,752,325),fill=gold,width=3)
    _center(d,385,"LE FOOTBALL AUTREMENT",_font(25,False),white)
    lines = {"actu":["ACTU","FOOT"],"live":["PRONOS","LIVE VIP"],
             "jour":["COUPONS","DU JOUR"]}[key]
    for off,line in enumerate(lines):
        fs=129 if len(line)<8 else 113 if len(line)<10 else 93
        _center(d,545+off*162,line,_font(fs),gold if off==0 else white,
                stroke_width=2,stroke_fill="#332A17")
    d.rounded_rectangle((135,920,945,1012),radius=42,
                        fill=(8,15,31,232),outline=(231,190,97,255),width=3)
    _center(d,946,descriptor,_font(28),white)
    d.rounded_rectangle((125,1060,955,1180),radius=33,fill=(220,171,70,242))
    _center(d,1083,handle,_font(53), "#091326")
    _center(d,1220,"REJOINS NOTRE CANAL TELEGRAM",_font(27),soft)
    out=io.BytesIO()
    im.convert("RGB").save(out,format="JPEG",quality=89,optimize=True,progressive=True)
    out.seek(0)
    out.name=f"mrx_{key}.jpg"
    return out


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
    # Alternating two and three complete films between ads.
    threshold=2 if index % 2 == 0 else 3
    return index if (force or film_total-int(entry["last_film_total"]) >= threshold) else None


async def _recently_published(client, channel, caption, *, limit=60):
    """Avoid repeating identical ad after a failed GitHub state commit."""
    now=datetime.now(timezone.utc)
    async for msg in client.iter_messages(channel, limit=limit):
        if str(getattr(msg,"raw_text","") or "").strip() != caption:
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
    picture=render_poster(index)
    return await bot.send_file(channel, picture,caption=campaign_caption(index),
                               buttons=[[Button.url(label,url)]], force_document=False)


async def _bot_can_post(bot, channel, identity):
    """No fallback to unbuttoned user messages in Telegram channels."""
    try:
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

    A campaign runs once after 2–3 more films on each channel. In the mirror,
    it forwards the actual branded/public post with the Telegram source header.
    """
    from telethon import utils
    if bot is None:
        raise RuntimeError("Le bot est requis pour de vrais boutons Telegram")
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
        found=await _recently_published(user_client,primary,caption)
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
    # Ad forwarded in the mirror only after 2–3 forwarded films there.
    if mirror is not None and due(state,mirror_id,mirror_total,force=force) is not None:
        e=_cursor(state,mirror_id)
        # The selected ad must exist in primary; don't make a detached poster.
        want=int(e["next_index"]) % len(CAMPAIGNS)
        if ready is not None:
            # Retrieve a photo matching the current campaign from primary.
            primary_post=await _recently_published(user_client,primary,campaign_caption(want),limit=150)
            if primary_post is not None:
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
            exists=await _recently_published(user_client,private,campaign_caption(idx))
            if exists is not None:
                msg_id=exists
            else:
                post=await _send_bot_poster(bot,ready_private,idx)
                msg_id=int(post.id);report["private"]+=1
            e["sent"][str(e["next_index"])]=msg_id
            e["last_film_total"]=total;e["next_index"]=int(e["next_index"])+1
            state.save()
        else:
            report["skipped"]+=1
            LOG.error("Privé : bot non-administrateur. Ajouter le bot avec Publier messages.")
    return report
