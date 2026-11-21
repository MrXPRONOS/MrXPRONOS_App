"""Crash-safe, bot-only episode publishing to authorized CinéX destinations.

All send operations are journaled before contacting Telegram. The Bot API
cannot search channel history; uncertain sends require manual reconciliation,
never a blind automatic retry. This module never accesses user sessions.
"""
from __future__ import annotations

import asyncio
from html import escape


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
                 pause: float = 3.0):
        self.transport = transport
        self.store = store
        self.state = state
        self.private_id = str(private_id)
        self.public_id = str(public_id)
        self.folder_url = folder_url
        self.pause = max(0.0, float(pause))
        if folder_url and not folder_url.startswith("https://t.me/addlist/"):
            raise ValueError("Unverified folder URL.")

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

    def _keyboard(self, private_url):
        rows = [[{"text": "🎞️ VOIR L'ÉPISODE", "url": private_url}]]
        if self.folder_url:
            rows.append([{"text": "📁 Rejoindre CinéX",
                          "url": self.folder_url}])
        return {"inline_keyboard": rows}

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
        # Stable index pages of 25 episodes: edits never exceed 4096 characters.
        for start in range(0, len(sorted_nums), 25):
            nums = sorted_nums[start:start + 25]
            page_no = str(start // 25 + 1)
            title = escape(entry["title"])
            lines = [f"📚 <b>{title} — Saison {int(season)}</b>",
                     f"Page {page_no}", ""]
            for n in nums:
                item = existing[str(n)]
                lines.append(
                    f'🎞️ <a href="{message_url(self.private_id, item["message_id"])}">'
                    f'Épisode {n:02d}</a>')
            text = "\n".join(lines)
            if len(text.encode("utf-8")) > 3900:
                raise RuntimeError("Episode index page too large.")
            ref = pages.get(page_no)
            if ref:
                # editMessageText is idempotent; "message is not modified"
                # must be tolerated without reposting.
                try:
                    await self.transport.edit_message(self.private_id, ref, text)
                except Exception as exc:
                    if "not modified" not in str(exc):
                        raise
            else:
                ref = await self._operation(
                    f"index:{row['series']}:{season}:{page_no}",
                    lambda content=text: self.transport.send_message(
                        self.private_id, content))
                pages[page_no] = int(ref)
                self.store.save(self.state)

        # Each season keeps one stable visible index plus additional pages.
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
        if (entry.get("migrated_from_legacy")
                and entry.get("public_id")
                and __import__("os").environ.get(
                    "CINEX_ANIME_LEGACY_PUBLIC_CARD_OWNERSHIP_VERIFIED") != "true"):
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
                    caption=f"🎞️ <b>{escape(entry['title'])}</b> — {marker}"))
            posts[marker] = {
                "poster": cover, "video": video, "private_video": private_msg}
            self.store.save(self.state)
        await self._series_card(row, entry, poster)
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
