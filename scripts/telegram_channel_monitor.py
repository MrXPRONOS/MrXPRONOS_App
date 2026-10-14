#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rapport privé des canaux publics que le compte Telegram administre.

Lecture via le compte utilisateur Telethon (aucune adhésion / publication publique).
Historique privé Supabase, livraison dans les Messages enregistrés Telegram.
Les entrées / sorties exactes ne sont pas accessibles ici : seuls les écarts NETS
entre deux relevés sont connus.
"""
from __future__ import annotations

import asyncio
import html
import os
import statistics
from datetime import datetime, timezone
from typing import Any

import requests
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import Channel

UTC = timezone.utc
TABLE = "telegram_channel_metrics_daily"
DISPATCH_TABLE = "telegram_channel_report_dispatch"
MAX_POSTS = 50
SAMPLE = 10
MAX_MESSAGE = 3900


def required(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"Variable manquante : {name}")
    return value


def num(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class Storage:
    """Tables protégées par RLS : accès exclusivement avec la clé service role."""

    def __init__(self) -> None:
        self.base = required("SUPABASE_URL").rstrip("/") + "/rest/v1"
        key = required("SUPABASE_SERVICE_ROLE_KEY")
        self.http = requests.Session()
        self.http.headers.update({
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        })

    def select(self, table: str, params: dict[str, str]) -> list[dict]:
        response = self.http.get(
            f"{self.base}/{table}", params=params, timeout=25
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            raise RuntimeError(f"Réponse Supabase incorrecte pour {table}")
        return rows

    def insert(self, table: str, row: dict, ignore_duplicates: bool = False) -> None:
        prefer = "return=minimal"
        if ignore_duplicates:
            prefer = "resolution=ignore-duplicates,return=minimal"
        response = self.http.post(
            f"{self.base}/{table}",
            params={"on_conflict": "channel_id,observed_on"} if ignore_duplicates else None,
            headers={"Prefer": prefer},
            json=row,
            timeout=25,
        )
        response.raise_for_status()

    def was_sent(self, day: str) -> bool:
        return bool(self.select(DISPATCH_TABLE, {
            "select": "report_on", "report_on": f"eq.{day}", "limit": "1"
        }))

    def previous(self, channel_id: int, day: str) -> dict | None:
        rows = self.select(TABLE, {
            "select": "observed_on,subscriber_count",
            "channel_id": f"eq.{channel_id}",
            "observed_on": f"lt.{day}",
            "order": "observed_on.desc",
            "limit": "1",
        })
        return rows[0] if rows else None


def is_owned_or_admin(entity: Channel) -> bool:
    return bool(entity.creator or entity.admin_rights is not None)


def collect_views(messages: list) -> tuple[int | None, int | None, int | None, str | None, float | None, int]:
    """Évite de compter plusieurs fois les albums de photos."""
    seen = set()
    posts: list[dict] = []
    for message in messages:
        if getattr(message, "action", None) is not None:
            continue
        message_id = num(getattr(message, "id", None))
        if message_id is None:
            continue
        group = getattr(message, "grouped_id", None)
        key = ("album", group) if group is not None else ("post", message_id)
        view = num(getattr(message, "views", None))
        if key in seen:
            if posts and posts[-1]["key"] == key and view is not None:
                old = posts[-1]["views"]
                posts[-1]["views"] = max(view, old) if old is not None else view
            continue
        seen.add(key)
        date = getattr(message, "date", None)
        posts.append({
            "key": key,
            "id": message_id,
            "views": view,
            "date": date.isoformat() if date else None,
        })
        if len(posts) >= SAMPLE:
            break
    if not posts:
        return None, None, None, None, None, 0
    views = [p["views"] for p in posts if p["views"] is not None]
    average = round(statistics.mean(views), 2) if views else None
    latest = posts[0]
    return (latest["id"], latest["views"], len(views),
            latest["date"], average, len(posts))


async def inspect_channel(client: TelegramClient, channel: Channel, day: str, store: Storage) -> dict:
    subscribers = num(getattr(channel, "participants_count", None))
    try:
        full = await client(GetFullChannelRequest(channel))
        count = num(getattr(full.full_chat, "participants_count", None))
        if count is not None:
            subscribers = count
    except (errors.RPCError, ValueError) as exc:
        print(f"Statistiques abonnés indisponibles, canal {channel.id}: {type(exc).__name__}")

    messages = await client.get_messages(channel, limit=MAX_POSTS)
    last_id, last_views, view_samples, last_at, avg_views, sampled = collect_views(messages)
    previous = store.previous(channel.id, day)
    delta = (subscribers - int(previous["subscriber_count"])
             if previous and subscribers is not None and previous.get("subscriber_count") is not None
             else None)

    row = {
        "channel_id": channel.id,
        "observed_on": day,
        "title": channel.title or "(Sans titre)",
        "username": channel.username or "",
        "public_url": f"https://t.me/{channel.username}",
        "subscriber_count": subscribers,
        "last_post_id": last_id,
        "last_post_views": last_views,
        "last_post_at": last_at,
        "average_views_10": avg_views,
        "sampled_posts": sampled,
    }
    store.insert(TABLE, row, ignore_duplicates=True)
    return {**row, "delta": delta,
            "previous_on": previous.get("observed_on") if previous else None,
            "view_samples": view_samples}


def fmt(n: int | float | None) -> str:
    if n is None:
        return "indisponible"
    return f"{round(n):,}".replace(",", " ")


def block(row: dict, index: int) -> str:
    title = html.escape(row["title"])
    link = html.escape(row["public_url"], quote=True)
    delta = row["delta"]
    if delta is None:
        change = "🆕 Première mesure — référence initiale"
    elif delta > 0:
        change = f"🟢 Gain net : +{fmt(delta)}"
    elif delta < 0:
        change = f"🔴 Perte nette : −{fmt(abs(delta))}"
    else:
        change = "⚪ Variation nette : 0"

    views = fmt(row["last_post_views"])
    mean = fmt(row["average_views_10"])
    pct = (100 * float(row["average_views_10"]) / row["subscriber_count"]
           if row["average_views_10"] is not None and row["subscriber_count"] else None)
    reach = f"{pct:.1f} %" if pct is not None else "indisponible"
    return (
        f"<b>{index}. {title}</b>\n"
        f"🔗 <a href=\"{link}\">Ouvrir le canal</a>\n"
        f"👥 Abonnés : <b>{fmt(row['subscriber_count'])}</b>\n"
        f"{change}\n"
        f"👁 Dernière publication : <b>{views}</b> vues\n"
        f"📊 Vues moyennes : <b>{mean}</b> ({row['view_samples']} publications sur 10)\n"
        f"🎯 Vues / abonnés : <b>{reach}</b>\n"
    )


def report_parts(rows: list[dict], now: datetime) -> list[str]:
    day = now.strftime("%d/%m/%Y")
    header = (f"📊 <b>BILAN TELEGRAM — {day}</b>\n"
              f"⏰ Relevé quotidien à 06 h (heure du Togo)\n"
              f"📣 Canaux publics administrés : <b>{len(rows)}</b>\n")
    totals = [r["subscriber_count"] for r in rows if r["subscriber_count"] is not None]
    variations = [r["delta"] for r in rows if r["delta"] is not None]
    covered = sum(1 for r in rows if r["delta"] is not None)
    summary = (f"<b>📌 SYNTHÈSE</b>\n"
               f"👥 Total abonnés : <b>{fmt(sum(totals))}</b>\n"
               f"📈 Variation nette connue : <b>{'+' if sum(variations) > 0 else ''}{fmt(sum(variations))}</b>"
               f" ({covered}/{len(rows)} canaux comparables)\n"
               "ℹ️ Les gains/pertes indiqués sont les variations <b>nettes</b> "
               "du nombre d’abonnés depuis le relevé précédent, pas le détail "
               "exact des arrivées et départs.\n"
               "📊 Moyenne calculée sur les 10 dernières publications avec vues disponibles.")
    chunks = []
    current = header
    for i, row in enumerate(rows, start=1):
        item = "\n" + block(row, i)
        if len(current) + len(item) > MAX_MESSAGE and current != header:
            chunks.append(current)
            current = header + "\n(Suite)\n"
        current += item
    if len(current) + len("\n" + summary) > MAX_MESSAGE:
        chunks.append(current)
        current = header + "\n(Synthèse)\n"
    chunks.append(current + "\n" + summary)
    return chunks


async def main() -> None:
    api_id = required("TG_API_ID")
    if not api_id.isdecimal():
        raise RuntimeError("TG_API_ID doit être un nombre")
    api_hash = required("TG_API_HASH")
    session_string = required("TG_SESSION_STRING")
    now = datetime.now(UTC)
    day = now.date().isoformat()
    store = Storage()
    if store.was_sent(day):
        print(f"Rapport {day} déjà envoyé ; aucun doublon.")
        return

    client = TelegramClient(
        StringSession(session_string), int(api_id), api_hash,
        request_retries=0, connection_retries=2, flood_sleep_threshold=0,
        receive_updates=False,
    )
    rows = []
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram révoquée/non autorisée. Aucun code demandé en CI.")

        channels: dict[int, Channel] = {}
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            if (isinstance(entity, Channel) and entity.broadcast
                    and entity.username and is_owned_or_admin(entity)):
                channels[entity.id] = entity

        if not channels:
            raise RuntimeError("Aucun canal public administré trouvé dans les dialogues du compte.")
        print(f"Canaux publics administrés détectés : {len(channels)}")

        for channel in sorted(channels.values(), key=lambda c: (c.title or "").casefold()):
            try:
                rows.append(await inspect_channel(client, channel, day, store))
            except errors.FloodWaitError:
                raise
            except (errors.RPCError, ValueError) as exc:
                print(f"Canal {channel.id} non analysé : {type(exc).__name__}")
            await asyncio.sleep(1.5)

        if not rows:
            raise RuntimeError("Aucun canal analysé ; aucun rapport envoyé.")

        # Les messages partent uniquement vers l'espace privé du compte connecté.
        last_message = None
        for part in report_parts(rows, now):
            last_message = await client.send_message(
                "me", part, parse_mode="html", link_preview=False
            )
            await asyncio.sleep(0.5)

        store.insert(DISPATCH_TABLE, {
            "report_on": day, "channels_count": len(rows),
            "message_id": num(getattr(last_message, "id", None))
        })
        print(f"RAPPORT_TELEGRAM_ENVOYE date={day} canaux={len(rows)}")
    except errors.FloodWaitError as exc:
        raise RuntimeError(f"Telegram impose une pause de {exc.seconds} secondes ; aucun contournement.") from exc
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
