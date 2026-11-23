"""Crash-safe, bot-only episode publishing to authorized CinéX destinations.

All send operations are journaled before contacting Telegram. The Bot API
cannot search channel history; uncertain sends require manual reconciliation,
never a blind automatic retry. This module never accesses user sessions.
"""
from __future__ import annotations

import asyncio
import os
from html import escape
from .cinex_v4_policy import caption_with_automatic_ttl
from .radar_download_registry import is_bot_download_url
from .rescue_channels import is_invite
from .publication import film_folder_url
from .cinex_v4_policy import canonical_public_handle, is_main_relay


def message_url(private_id: str, message_id: int) -> str:
    text = str(private_id)
    if not text.startswith("-100") or not text[1:].isdigit():
        raise ValueError("Expected Telegram private channel ID -100...")
    return f"https://t.me/c/{text[4:]}/{int(message_id)}"


def episode_key(row):
    return f"S{int(row['season']):02d}E{int(row['episode']):02d}"


class AnimeBotPublisher:
    def __init__(self, transport, store, state, *,
                 private_id: str, public_id: str, folder_url: str = "",
                 pause: float = 3.0, central_stock_id: str = "",
                 radar_registry=None, rescue_url: str = "",
                 public_handle: str = "@CineXAnimeFR"):
        self.transport = transport
        self.store = store
        self.state = state
        self.private_id = str(private_id)
        self.public_id = str(public_id)
        self.folder_url = folder_url
        self.pause = max(0.0, float(pause))
        if folder_url and not folder_url.startswith("https://t.me/addlist/"):
            raise ValueError("Unverified folder URL.")
        self.central_stock_id = str(central_stock_id or "")
        self.radar_registry = radar_registry
        self.rescue_url = str(rescue_url or "")
        self.public_handle = canonical_public_handle(public_handle)
        if not is_main_relay(self.public_handle):
            raise ValueError("Anime bot public destination is not an official relay")
        if self.central_stock_id and (
                not self.central_stock_id.startswith("-100") or
                not self.central_stock_id[1:].isdigit() or
                self.central_stock_id in (self.private_id, self.public_id)):
            raise ValueError("Invalid distinct central stock channel")

    async def _operation(self, key, action):
        journal = self.state.setdefault("operation_receipts", {})
        prior = journal.get(key)
        if prior:
            if prior.get("status") == "complete":
                return int(prior["message_id"])
            raise RuntimeError(
                f"Envoi Telegram {key} incertain : contrôle manuel obligatoire.")
        journal[key] = {"status": "inflight"}
        self.store.save(self.state)
        try:
            result = int(await action())
        except Exception:
            journal[key]["status"] = "uncertain"
            self.store.save(self.state)
            raise
        journal[key] = {"status": "complete", "message_id": result}
        self.store.save(self.state)
        if self.pause:
            await asyncio.sleep(self.pause)
        return result

    def _series(self, row):
        key = row["series"]
        entry = self.state.setdefault("series", {}).setdefault(
            key, {"title": row["title"], "episodes": {},
                  "public_episode_posts": {}, "season_index_ids": {},
                  "season_public_ids": {}, "index_pages": {}})
        if entry.get("title") != row["title"]:
            # Cosmetic title changes do not create a second series.
            pass
        return entry

    def _keyboard(self, watch_url: str, download_url: str):
        """Exactly the four approved public CineX anime buttons."""
        if (not is_bot_download_url(download_url)
                or not is_invite(self.rescue_url)
                or not self.folder_url.startswith("https://t.me/addlist/")):
            raise RuntimeError("Anime bot : links to stock, Secours or folder absent")
        if not watch_url.startswith("https://t.me/c/"):
            raise RuntimeError("Anime bot : verified private episode URL required")
        return {"inline_keyboard": [
            [{"text": "🌸 VOIR L'ANIMÉ", "url": watch_url}],
            [{"text": "⬇️ TÉLÉCHARGER LES VIDÉOS", "url": download_url}],
            [{"text": "🛟 REJOINDRE LE CANAL SECOURS", "url": self.rescue_url}],
            [{"text": "📁 REJOINDRE LE DOSSIER", "url": self.folder_url}],
        ]}

    def _library_keyboard(self, download_url: str):
        if not is_bot_download_url(download_url):
            raise RuntimeError("Anime bot : central download receipt missing")
        return {"inline_keyboard": [
            [{"text": "📢 REJOINDRE LE CANAL",
              "url": "https://t.me/" + self.public_handle.lstrip("@")}],
            [{"text": "📁 REJOINDRE LE DOSSIER", "url": self.folder_url}],
            [{"text": "⬇️ TÉLÉCHARGER", "url": download_url}],
        ]}

    async def _central_download(self, row, entry, poster, source):
        """Archive original poster then video in OWNER central stock before any
        public/private episode post. Each Telegram send has an uncertain-receipt
        lock: retries can never create blind duplicates.
        """
        if (not self.central_stock_id or self.radar_registry is None
                or not is_invite(self.rescue_url)
                or not self.folder_url.startswith("https://t.me/addlist/")):
            raise RuntimeError(
                "Anime Bot V2 requires central stock, CineRadar, verified Secours "
                "and shared folder before any new publication")
        marker = episode_key(row)
        stock = entry.setdefault("central_stock", {}).setdefault(marker, {})
        if not stock.get("cover"):
            stock["cover"] = await self._operation(
                f"stock:cover:{row['series']}:{marker}",
                lambda: self.transport.copy_message(
                    self.central_stock_id, poster["source_id"],
                    poster["message_id"],
                    caption=f"🌸 <b>{escape(entry['title'])}</b> — {marker}"))
            self.store.save(self.state)
        if not stock.get("video"):
            stock["video"] = await self._operation(
                f"stock:video:{row['series']}:{marker}",
                lambda: self.transport.copy_message(
                    self.central_stock_id, source["source_id"],
                    source["message_id"],
                    caption=f"🎞️ <b>{escape(entry['title'])}</b> — {marker}"))
            self.store.save(self.state)
        if not stock.get("download_url"):
            link = await asyncio.to_thread(
                self.radar_registry.register,
                private_channel=int(self.central_stock_id),
                message_id=int(stock["video"]),
                title=f"{entry['title']} {marker}",
                public_handle=self.public_handle,
            )
            if not is_bot_download_url(link):
                raise RuntimeError("Anime bot : CineRadar download not verified")
            stock["download_url"] = link
            self.store.save(self.state)
        if not is_bot_download_url(stock["download_url"]):
            raise RuntimeError("Anime bot : invalid existing download receipt")
        return stock["download_url"]

    def _poster(self, row):
        key = row.get("poster_source_key")
        source = self.state.get("messages", {}).get(key)
        if not source or source.get("kind") != "poster":
            raise RuntimeError("Original source poster missing: publishing denied.")
        if source["source_id"] != row["source_id"]:
            raise RuntimeError("Source poster and episode must share authorized chat.")
        return source

    async def _season_index(self, row, entry):
        season = str(row["season"])
        existing = entry.get("episodes", {}).get(season, {})
        sorted_nums = sorted(int(n) for n in existing)
        if not sorted_nums:
            return
        pages = entry.setdefault("index_pages", {}).setdefault(season, {})
        groups = [sorted_nums[i:i+25]
                  for i in range(0, len(sorted_nums), 25)]

        def contents(index, *, navigation):
            page_no = index + 1
            numbers = groups[index]
            lines = [
                f"📚 <b>{escape(entry['title'])} — Saison {int(season)}</b>",
                f"Page {page_no} / {len(groups)}", "",
            ]
            for n in numbers:
                record = existing[str(n)]
                lines.append(
                    f'🎞️ <a href="{message_url(self.private_id, record["message_id"])}">'
                    f'Épisode {n:02d}</a>')
            if navigation:
                lines.extend(["", "📖 Navigation :"])
                if page_no > 1:
                    previous = pages[str(page_no - 1)]
                    lines.append(
                        f'⬅️ <a href="{message_url(self.private_id, previous)}">'
                        f'Page {page_no-1}</a>')
                if page_no < len(groups):
                    following = pages[str(page_no + 1)]
                    lines.append(
                        f'➡️ <a href="{message_url(self.private_id, following)}">'
                        f'Page {page_no+1}</a>')
            text = "\n".join(lines)
            if len(text.encode("utf-8")) > 3900:
                raise RuntimeError("Episode index page too large.")
            return text

        # First allocate all pages to obtain their IDs without guessing any
        # Telegram URL. Each send is persisted before the next operation.
        for index in range(len(groups)):
            page_no = str(index + 1)
            if page_no not in pages:
                body = contents(index, navigation=False)
                page_id = await self._operation(
                    f"index:{row['series']}:{season}:{page_no}",
                    lambda text=body: self.transport.send_message(
                        self.private_id, text))
                pages[page_no] = int(page_id)
                self.store.save(self.state)

        # Second pass links all pages in both directions; the first private
        # season index always provides access to later pages and episodes.
        for index in range(len(groups)):
            page_id = int(pages[str(index + 1)])
            text = contents(index, navigation=True)
            try:
                await self.transport.edit_message(self.private_id, page_id, text)
            except Exception as exc:
                if "not modified" not in str(exc):
                    raise
        entry.setdefault("season_index_ids", {})[season] = int(pages["1"])
        self.store.save(self.state)

    async def _main_index(self, row, entry):
        seasons = entry.get("season_index_ids", {})
        if not seasons:
            return
        lines = [f"🌸 <b>{escape(entry['title'])}</b>",
                 "Saisons disponibles dans CinéX :", ""]
        for season, index_id in sorted(seasons.items(), key=lambda p: int(p[0])):
            lines.append(
                f'📚 <a href="{message_url(self.private_id, int(index_id))}">'
                f'Saison {int(season)}</a>')
        text = "\n".join(lines)
        if entry.get("main_index_id"):
            try:
                await self.transport.edit_message(
                    self.private_id, int(entry["main_index_id"]), text)
            except Exception as exc:
                if "not modified" not in str(exc):
                    raise
        else:
            idx = await self._operation(
                f"index:{row['series']}:main",
                lambda: self.transport.send_message(self.private_id, text))
            entry["main_index_id"] = idx
            self.store.save(self.state)

    async def _series_card(self, row, entry, poster):
        # One original public card for the entire series; future seasons
        # receive one season notice and never create a duplicate main card.
        key = row["series"]
        index_id = int(entry["main_index_id"])
        link = message_url(self.private_id, index_id)
        buttons = {"inline_keyboard": [
            [{"text": "📚 TOUTES LES SAISONS", "url": link}]]}
        caption = f"🌸 <b>{escape(entry['title'])}</b>\n📚 Saison(s) disponibles"
        if not entry.get("public_id"):
            entry["public_id"] = await self._operation(
                f"series-card:{key}", lambda: self.transport.copy_message(
                    self.public_id, poster["source_id"], poster["message_id"],
                    caption=caption, reply_markup=buttons))
            self.store.save(self.state)
        else:
            await self.transport.edit_buttons(
                self.public_id, int(entry["public_id"]), buttons)
        season = str(row["season"])
        announcements = entry.setdefault("season_public_ids", {})
        if season not in announcements:
            if len(announcements) == 0:
                announcements[season] = int(entry["public_id"])
            else:
                index_link = message_url(
                    self.private_id, entry["season_index_ids"][season])
                season_buttons = {"inline_keyboard": [[
                    {"text": "📺 SAISON " + season, "url": index_link}]]}
                announcements[season] = await self._operation(
                    f"season-card:{key}:{season}", lambda: self.transport.copy_message(
                        self.public_id, poster["source_id"], poster["message_id"],
                        caption=f"🌸 <b>{escape(entry['title'])}</b> — Saison {season}",
                        reply_markup=season_buttons))
            self.store.save(self.state)

    async def publish_episode(self, row):
        """One idempotent private + two public media posts and index updates."""
        key = row["series"]
        marker = episode_key(row)
        entry = self._series(row)
        # An imported public card may have been written by an unrelated bot.
        # Never modify or replace its buttons before bot ownership is checked.
        if entry.get("migrated_from_legacy") and entry.get("public_id"):
            if os.environ.get(
                    "CINEX_ANIME_LEGACY_PUBLIC_CARD_OWNERSHIP_VERIFIED") != "true":
                raise RuntimeError(
                    "Legacy public card author is unverified; bot publishing is blocked.")
        poster = self._poster(row)
        source = self.state.get("messages", {}).get(row["source_key"], {})
        if source.get("kind") != "video":
            raise RuntimeError("Original numbered video not available.")
        private_season = entry.setdefault("episodes", {}).setdefault(
            str(row["season"]), {})
        stored = private_season.get(str(row["episode"]))
        if stored:
            private_msg = int(stored["message_id"])
        else:
            private_msg = await self._operation(
                f"private:{key}:{marker}", lambda: self.transport.copy_message(
                    self.private_id, source["source_id"], source["message_id"],
                    caption=f"🌸 <b>{escape(entry['title'])}</b> — {marker}"))
            private_season[str(row["episode"])] = {
                "message_id": private_msg, "source_key": row["source_key"],
                "file_unique_id": source.get("file_unique_id") or ""}
            self.store.save(self.state)
        await self._season_index(row, entry)
        await self._main_index(row, entry)
        private_url = message_url(self.private_id, private_msg)
        posts = entry.setdefault("public_episode_posts", {})
        if marker not in posts:
            cover = await self._operation(
                f"cover:{key}:{marker}", lambda: self.transport.copy_message(
                    self.public_id, poster["source_id"], poster["message_id"],
                    caption=f"🌸 <b>{escape(entry['title'])}</b> — {marker}",
                    reply_markup=self._keyboard(private_url)))
            video = await self._operation(
                f"video:{key}:{marker}", lambda: self.transport.copy_message(
                    self.public_id, self.private_id, private_msg,
                    caption=caption_with_automatic_ttl(
                        f"🎞️ <b>{escape(entry['title'])}</b> — {marker}")))
            posts[marker] = {
                "poster": cover, "video": video, "private_video": private_msg}
            self.store.save(self.state)
        await self._series_card(row, entry, poster)
        # Optional: repost the authenticated source weekly GIF only once.
        # No fabricated GIF or automatic media upload. This switch stays off
        # until rights for the animation itself have been confirmed.
        gif_key = row.get("cadence_source_key")
        if (gif_key and os.environ.get(
                "CINEX_ANIME_GIF_REPOST_ENABLED", "").lower() == "true"
                and not entry.get("cadence_gif_public_id")):
            gif = self.state.get("messages", {}).get(gif_key)
            if (gif and gif.get("kind") == "animation"
                    and gif.get("source_id") == source.get("source_id")):
                entry["cadence_gif_public_id"] = await self._operation(
                    f"weekly-gif:{key}", lambda: self.transport.copy_message(
                        self.public_id, gif["source_id"], gif["message_id"],
                        caption=f"📅 <b>{escape(entry['title'])}</b> — Hebdomadaire"))
                self.store.save(self.state)
        source["status"] = "published"
        for other in row.get("alternate_source_keys", []):
            self.state.get("messages", {}).get(other, {})["status"] = "published"
        if row.get("cadence_hint") in ("weekly", "fortnightly"):
            entry["cadence_hint"] = row["cadence_hint"]
        entry.setdefault("last_episode_by_season", {})[
            str(row["season"])] = max(
                int(row["episode"]),
                int(entry.get("last_episode_by_season", {}).get(
                    str(row["season"]), 0)))
        entry["last_episode"] = int(row["episode"])
        entry["last_published_source_date"] = max(
            int(row.get("date") or 0),
            int(entry.get("last_published_source_date") or 0))
        self.store.save(self.state)
        return posts[marker]
