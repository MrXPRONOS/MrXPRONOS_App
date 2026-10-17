import os
import asyncio
from unittest.mock import AsyncMock
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image

from film_relay.promotions import (
    CAMPAIGNS, render_poster, poster_path, campaign_caption, campaign_button, due,
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
    def test_channels_and_three_line_captions(self):
        self.assertEqual([campaign[1] for campaign in CAMPAIGNS], [
            "@actufoot_mrxp", "@mr_xpronos_vip", "@mrxpronosfr",
        ])
        for index in range(3):
            lines = campaign_caption(index).splitlines()
            self.assertEqual(len(lines), 3)
            self.assertTrue(all(line.strip() for line in lines))
            self.assertEqual(
                campaign_button(index)[1],
                "https://t.me/" + CAMPAIGNS[index][1][1:],
            )

    def test_original_png_unchanged(self):
        with TemporaryDirectory() as folder:
            make_png_fixtures(folder)
            with patch.dict(os.environ, {"CINEX_PROMO_ASSETS_DIR": folder}):
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

    def test_missing_artwork_sends_three_line_text_with_url_button(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from film_relay.promotions import _send_bot_poster
        from telethon import Button
        # Run without an actual Telegram connection.
        async def run():
            bot = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(id=42)))
            with TemporaryDirectory() as folder:
                with patch.dict(os.environ, {"CINEX_PROMO_ASSETS_DIR": folder}):
                    result = await _send_bot_poster(bot, "test-channel", 2)
            self.assertEqual(result.id, 42)
            self.assertEqual(bot.send_message.await_count, 1)
            args, kwargs = bot.send_message.await_args
            self.assertEqual(len(args[1].splitlines()), 3)
            self.assertTrue(kwargs["buttons"])
            self.assertEqual(kwargs["buttons"][0][0][2], "primary")
        # Patch the actual imported helper, regardless of whether Telethon is
        # present in the GitHub Actions test environment.
        with patch("telethon.Button.url",
                   side_effect=lambda label, url, **kw: (label, url, kw.get("style"))):
            asyncio.run(run())

    def test_two_movie_cursor_consumes_backlog_in_one_promotion(self):
        """An old backlog must not generate many consecutive adverts."""
        from film_relay.promotions import _cursor
        with TemporaryDirectory() as folder:
            state = State(str(Path(folder) / "state.json"))
            entry = _cursor(state, "channel")
            entry["last_film_total"] = 9
            total = 14
            self.assertEqual(due(state, "channel", total), 0)
            # Same operation performed after a successful Telegram send.
            entry["last_film_total"] = total
            entry["next_index"] += 1
            self.assertIsNone(due(state, "channel", total))
            self.assertEqual(due(state, "channel", total + 2), 1)

    def test_rotation_after_every_two_movies(self):
        with TemporaryDirectory() as folder:
            state = State(str(Path(folder) / "state.json"))
            self.assertIsNone(due(state, "channel", 1))
            self.assertEqual(due(state, "channel", 2), 0)
            cursor = state.data["promotions"]["channel"]
            cursor["last_film_total"] = 2
            cursor["next_index"] = 1
            self.assertIsNone(due(state, "channel", 3))
            self.assertEqual(due(state, "channel", 4), 1)
            cursor["last_film_total"] = 4
            cursor["next_index"] = 2
            self.assertIsNone(due(state, "channel", 5))
            self.assertEqual(due(state, "channel", 6), 2)


if __name__ == "__main__":
    unittest.main()
