import os
import asyncio
from unittest.mock import AsyncMock
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image

from film_relay.promotions import (
    CAMPAIGNS, PROMO_INTERVAL, render_poster, poster_path, campaign_caption,
    campaign_button, due, publish_promotions,
)
from film_relay.state import State


def make_png_fixtures(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    for index, key in enumerate(("actu", "live", "jour")):
        Image.new("RGB", (480, 600), (20 + index * 30, 40, 70)).save(
            path / f"mrx_{key}.png"
        )


class PromoTests(unittest.TestCase):
    def test_channels_and_four_line_captions(self):
        self.assertEqual([campaign[1] for campaign in CAMPAIGNS], [
            "@actufoot_mrxp", "@mr_xpronos_vip", "@mrxpronosfr",
        ])
        for index in range(3):
            lines = campaign_caption(index).splitlines()
            self.assertEqual(len(lines), 4)
            self.assertTrue(all(line.strip() for line in lines))
            self.assertEqual(
                campaign_button(index)[1],
                "https://t.me/" + CAMPAIGNS[index][1][1:],
            )

    def test_original_png_unchanged(self):
        with TemporaryDirectory() as folder:
            make_png_fixtures(folder)
            import hashlib
            hashes = {
                key: hashlib.sha256((Path(folder) / f"mrx_{key}.png").read_bytes()).hexdigest()
                for key in ("actu", "live", "jour")
            }
            with patch.dict(os.environ, {"CINEX_PROMO_ASSETS_DIR": folder}), \
                 patch("film_relay.promotions.ORIGINAL_SHA256", hashes):
                for index in range(3):
                    stream = render_poster(index)
                    path = poster_path(index)
                    self.assertEqual(stream.name, path.name)
                    self.assertEqual(stream.read(), path.read_bytes())
                    stream.seek(0)
                    poster = Image.open(stream)
                    self.assertEqual(poster.size, (480, 600))
                    self.assertEqual(poster.format, "PNG")

    def test_missing_original_does_not_generate_replacement(self):
        with TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"CINEX_PROMO_ASSETS_DIR": folder}):
                with self.assertRaises(FileNotFoundError):
                    render_poster(0)

    def test_missing_artwork_never_publishes_incorrect_poster(self):
        from types import SimpleNamespace
        from film_relay.promotions import _send_bot_poster
        bot = SimpleNamespace(send_message=AsyncMock(), send_file=AsyncMock())
        with TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"CINEX_PROMO_ASSETS_DIR": folder}):
                with self.assertRaises(FileNotFoundError):
                    asyncio.run(_send_bot_poster(bot, "test-channel", 2))
        bot.send_message.assert_not_awaited()
        bot.send_file.assert_not_awaited()

    def test_no_ad_on_run_without_new_content(self):
        """Even a pending historical quota cannot emit an advert on an empty run."""
        with TemporaryDirectory() as folder:
            state = State(str(Path(folder) / "state.json"))
            state.data["processed"] = {
                "old-1": {}, "old-2": {}, "old-3": {}, "old-4": {},
            }
            result = asyncio.run(publish_promotions(
                None, None, None, None, None, state,
                current_run_films=0,
            ))
            self.assertEqual(
                result,
                {"private": 0, "public": 0, "mirror": 0, "skipped": 0},
            )

    def test_four_content_cursor_consumes_backlog_in_one_promotion(self):
        """An old backlog must not generate many consecutive adverts."""
        from film_relay.promotions import _cursor
        with TemporaryDirectory() as folder:
            state = State(str(Path(folder) / "state.json"))
            entry = _cursor(state, "channel")
            entry["last_film_total"] = 9
            total = 14
            self.assertEqual(due(state, "channel", total), 0)
            entry["last_film_total"] = total
            entry["next_index"] += 1
            self.assertIsNone(due(state, "channel", total))
            self.assertIsNone(due(state, "channel", total + 3))
            self.assertEqual(due(state, "channel", total + 4), 1)

    def test_rotation_after_every_four_contents(self):
        with TemporaryDirectory() as folder:
            state = State(str(Path(folder) / "state.json"))
            self.assertEqual(PROMO_INTERVAL, 4)
            self.assertIsNone(due(state, "channel", 1))
            self.assertIsNone(due(state, "channel", 2))
            self.assertIsNone(due(state, "channel", 3))
            self.assertEqual(due(state, "channel", 4), 0)
            cursor = state.data["promotions"]["channel"]
            cursor["last_film_total"] = 4
            cursor["next_index"] = 1
            self.assertIsNone(due(state, "channel", 7))
            self.assertEqual(due(state, "channel", 8), 1)

    def test_two_plus_two_across_runs_reaches_four(self):
        with TemporaryDirectory() as folder:
            state = State(str(Path(folder) / "state.json"))
            self.assertIsNone(due(state, "channel", 2))
            # No advert was sent, so last_film_total remains zero.
            self.assertEqual(due(state, "channel", 4), 0)


if __name__ == "__main__":
    unittest.main()
