"""Offline Lot 3 acceptance tests: whole seasons, weekly arrivals, strict links."""
from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from film_relay.season_batches_v4 import (
    select_season_batches, batch_caption, batch_identifier,
    active_descriptor, valid_source_batch,
    prepare_private_season_batch, publish_public_season_batch,
)
from film_relay.cinex_v4_policy import has_automatic_ttl

PUBLIC = -1006789012345
PRIVATE = -1001234567890
RESCUE = "https://t.me/+VerifiedAnimeRescue123"


def source_row(n, *, key="a", season=1, title="Série Exemple", poster=True):
    media = NS(id=1000 + n + season * 100, photo=object(), media="photo")
    media.raw_text = title + " — Saison " + str(season)
    media.noforwards = False
    video = NS(id=2000 + n + season * 100,
               document=NS(id=3000 + n + season * 100,
                           mime_type="video/mp4", attributes=[]),
               video=object(), media=f"vid-{season}-{n}", noforwards=False)
    return {
        "series": key, "title": title, "season": season, "episode": n,
        "source_key": f"-1009888888888:{video.id}",
        "poster": media if poster else None, "video": video,
        "timestamp": n,
    }


def as_catalogue(rows=None):
    return {"series": rows or {}}


class SeasonPlannerTests(unittest.TestCase):
    def test_complete_s01_one_cycle_s02_next_cycle(self):
        groups = {"s": [*[source_row(n, key="s") for n in range(1, 5)],
                        *[source_row(n, key="s", season=2) for n in range(1, 4)]]}
        full = [("s", groups["s"][:4]), ("s", groups["s"][4:])]
        selected = select_season_batches(groups, as_catalogue(), full)
        self.assertEqual(len(selected), 1)
        self.assertEqual([r["episode"] for r in selected[0][1]], [1, 2, 3, 4])
        self.assertTrue(selected[0][2])
        posted = {f"S01E{n:02d}": {"poster": 2, "video": n}
                  for n in range(1, 5)}
        later = as_catalogue({"s": {"title": "Série Exemple",
                                    "public_episode_posts": posted}})
        second = select_season_batches(groups, later, full)
        self.assertEqual(len(second), 1)
        self.assertEqual({r["season"] for r in second[0][1]}, {2})

    def test_initial_1_through_4_then_only_fifth(self):
        src = [source_row(n, key="show") for n in range(1, 5)]
        first = select_season_batches({"show": src}, as_catalogue(), [])
        self.assertEqual([r["episode"] for r in first[0][1]], [1, 2, 3, 4])
        self.assertFalse(first[0][2])
        posted = {f"S01E{n:02d}": {"video": n} for n in range(1, 5)}
        cat = as_catalogue({"show": {"title": "Série Exemple",
                                    "public_episode_posts": posted}})
        self.assertEqual(select_season_batches({"show": src}, cat, []), [])
        later = select_season_batches(
            {"show": src + [source_row(5, key="show")]}, cat, [])
        self.assertEqual([r["episode"] for r in later[0][1]], [5])
        self.assertIn("Épisode 5", batch_caption(
            "Série Exemple", later[0][1], complete=False))

    def test_missing_episode_prevents_sixth_until_fifth_is_available(self):
        cat = as_catalogue({"s": {
            "title": "Série Exemple",
            "public_episode_posts": {
                f"S01E{n:02d}": {"video": n} for n in range(1, 5)
            },
        }})
        self.assertEqual(select_season_batches(
            {"s": [source_row(6, key="s")]}, cat, []), [])
        self.assertEqual([r["episode"] for r in select_season_batches(
            {"s": [source_row(5, key="s"), source_row(6, key="s")]},
            cat, [])[0][1]], [5, 6])

    def test_no_unnumbered_guess_and_no_partial_complete_season(self):
        rows = [source_row(n) for n in range(1, 27)]
        self.assertEqual(select_season_batches(
            {"a": rows}, as_catalogue(), [("a", rows)],
            maximum=25), [])
        partial = [source_row(n) for n in (1, 2, 4)]
        pending = select_season_batches({"a": partial}, as_catalogue(), [])
        self.assertEqual([r["episode"] for r in pending[0][1]], [1, 2])

    def test_complete_thirty_episodes_never_truncated_to_twenty_five(self):
        rows = [source_row(n, key="longshow") for n in range(1, 31)]
        selected = select_season_batches(
            {"longshow": rows}, as_catalogue(),
            [("longshow", rows)], maximum=50)
        self.assertEqual(len(selected), 1)
        self.assertTrue(selected[0][2])
        self.assertEqual([int(r["episode"]) for r in selected[0][1]],
                         list(range(1, 31)))
        self.assertEqual(select_season_batches(
            {"longshow": rows}, as_catalogue(),
            [("longshow", rows)], maximum=25), [])

    def test_fifty_one_episode_complete_season_is_not_split(self):
        rows = [source_row(n, key="large") for n in range(1, 52)]
        self.assertEqual(select_season_batches(
            {"large": rows}, as_catalogue(),
            [("large", rows)], maximum=50), [])

    def test_cadence_only_when_source_explicit(self):
        rows = [source_row(1)]
        self.assertNotIn("hebdomadaire",
                         batch_caption("Titre", rows, complete=False))
        rows[0]["cadence_hint"] = "weekly"
        self.assertIn("hebdomadaire",
                      batch_caption("Titre", rows, complete=False))
        self.assertIn("Saison complète",
                      batch_caption("Titre", rows, complete=True))

    def test_batch_receipts_are_source_specific_and_one_season(self):
        rows = [source_row(1), source_row(2)]
        self.assertEqual(batch_identifier("a", 1, rows),
                         batch_identifier("a", 1, list(reversed(rows))))
        self.assertNotEqual(batch_identifier("a", 1, rows),
                            batch_identifier("a", 1, [source_row(3)]))
        active = active_descriptor("a", rows, complete=False)
        self.assertTrue(valid_source_batch(rows, active))
        self.assertFalse(valid_source_batch([rows[0]], active))
        self.assertFalse(valid_source_batch([
            rows[0], source_row(2, season=2)]))


class FakeChannelTelegram:
    def __init__(self):
        self.messages = {}
        self.next_id = 75
        self.media_posts = []
        self.public_peer = NS(peer_id=PUBLIC, username="seriesvf_cinex")
        self.private_peer = NS(peer_id=PRIVATE)
        self.bot_copies = []

    def _key(self, peer):
        return int(getattr(peer, "peer_id", peer))

    def _new(self, peer, *, caption="", media=None, photo=None,
             video=None, document=None, buttons=None):
        self.next_id += 1
        msg = NS(
            id=self.next_id, raw_text=caption,
            media=media, photo=photo, video=video, document=document,
            buttons=buttons or [], channel=self._key(peer),
        )
        self.messages[(msg.channel, msg.id)] = msg
        self.media_posts.append(msg)
        return msg

    async def download_media(self, media, file=bytes):
        return b"image-authentique"

    async def send_message(self, peer, text, **kwargs):
        return self._new(peer, caption=text)

    async def send_file(self, peer, media, *, caption, **kwargs):
        if isinstance(media, str) and media.startswith("vid-"):
            s, n = map(int, media[4:].split("-"))
            doc = NS(id=3000 + n + s * 100, mime_type="video/mp4",
                     attributes=[])
            return self._new(peer, caption=caption, media=media,
                             video=object(), document=doc)
        return self._new(peer, caption=caption, media=media,
                         photo=object(), buttons=kwargs.get("buttons"))

    async def get_messages(self, peer, ids):
        return self.messages.get((self._key(peer), int(ids)))

    async def iter_messages(self, peer, limit):
        hits = [v for (cid, _), v in self.messages.items()
                if cid == self._key(peer)]
        for item in sorted(hits, key=lambda x: x.id, reverse=True)[:limit]:
            yield item

    async def copy_message(self, dest, source, mid, *, caption, buttons, **kwargs):
        m = await self.get_messages(source, ids=mid)
        self.bot_copies.append((self._key(dest), int(mid)))
        return self._new(dest, caption=caption, media=m.media, video=object(),
                         document=m.document, buttons=buttons)


class FakeDownloadRegistry:
    def __init__(self):
        self.calls = 0

    async def store(self, video, **kwargs):
        self.calls += 1
        return ("https://t.me/CineRadarFr_Bot?start=d_"
                + str(int(video.document.id)).zfill(24))


class SeasonPublishingTests(unittest.TestCase):
    def test_private_single_cover_and_public_single_cover_plus_episodes(self):
        user = FakeChannelTelegram()
        stock = FakeDownloadRegistry()
        rows = [source_row(n, key="test") for n in range(1, 5)]
        cat = as_catalogue({"test": {"title": "Série Exemple",
                                     "episodes": {},
                                     "public_episode_posts": {}}})
        series = cat["series"]["test"]
        saved = []
        def write(data):
            saved.append(str(len(series.get("season_batches", {}))))

        async def publish():
            receipt = await prepare_private_season_batch(
                user, user, user.private_peer, user.public_peer, PRIVATE,
                "test", series, rows, cat, write, stock,
                kind="series", complete=False)
            self.assertEqual(stock.calls, 4)
            self.assertEqual(receipt["episodes"],
                             ["S01E01", "S01E02", "S01E03", "S01E04"])
            private_cover_id = receipt["private_cover_id"]
            for row in rows:
                video = await user.send_file(
                    user.private_peer, row["video"].media,
                    caption=f"{row['episode']}")
                series.setdefault("episodes", {}).setdefault("1", {})[
                    str(row["episode"])] = {"message_id": video.id}
            self.assertEqual(
                [m.id for m in user.media_posts if m.channel == PRIVATE
                 and m.photo and m.id >= private_cover_id],
                [private_cover_id])
            result = await publish_public_season_batch(
                user, user, user.public_peer, user.private_peer,
                PRIVATE, "test", series, rows, cat, write, 0,
                kind="series", complete=False)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(len(result["public_videos"]), 4)
            msgs = [m for m in user.media_posts if m.channel == PUBLIC]
            self.assertEqual(len(msgs), 5)
            self.assertTrue(msgs[0].photo)
            self.assertEqual([m.media for m in msgs[1:]],
                             [f"vid-1-{n}" for n in range(1, 5)])
            self.assertEqual([len(m.buttons) for m in msgs], [4]*5)
            self.assertTrue(all(has_automatic_ttl(m) for m in msgs[1:]))
            self.assertEqual(len(
                (await user.get_messages(user.private_peer, ids=private_cover_id)).buttons),
                3)
            self.assertEqual(len(user.bot_copies), 4)
            # Idempotent resume: no duplicate image or public episode.
            before = len(user.media_posts)
            await prepare_private_season_batch(
                user, user, user.private_peer, user.public_peer, PRIVATE,
                "test", series, rows, cat, write, stock,
                kind="series", complete=False)
            await publish_public_season_batch(
                user, user, user.public_peer, user.private_peer,
                PRIVATE, "test", series, rows, cat, write, 0,
                kind="series", complete=False)
            self.assertEqual(len(user.media_posts), before)

        with patch("film_relay.season_batches_v4.rescue_link_for",
                   return_value=RESCUE):
            asyncio.run(publish())
        self.assertTrue(saved)

    def test_missing_rescue_blocks_public_but_private_archives_persist(self):
        user = FakeChannelTelegram()
        rows = [source_row(1, key="test")]
        cat = as_catalogue({"test": {"title": "Série Exemple",
                                     "episodes": {"1": {"1": {"message_id": 78}}}}})
        series = cat["series"]["test"]

        async def exercise():
            rec = await prepare_private_season_batch(
                user, user, user.private_peer, user.public_peer, PRIVATE,
                "test", series, rows, cat, lambda _: None,
                FakeDownloadRegistry(), kind="series", complete=False)
            with self.assertRaisesRegex(RuntimeError, "Secours"):
                await publish_public_season_batch(
                    user, user, user.public_peer, user.private_peer,
                    PRIVATE, "test", series, rows, cat, lambda _: None, 0,
                    kind="series", complete=False)
            self.assertTrue(rec.get("private_cover_id"))

        with patch("film_relay.season_batches_v4.rescue_link_for",
                   return_value=None):
            asyncio.run(exercise())
        self.assertEqual([m for m in user.media_posts if m.channel == PUBLIC], [])


if __name__ == "__main__":
    unittest.main()
