"""Offline checks of one-message Telegram Saved Messages discovery summaries."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from film_relay.discovery import (notification_summary, notification_text,
                                  notify_saved_messages, normalize_username)
from film_relay.desir_runner import verify_destination


def found(name, title, count):
    return {"username": name, "title": title, "matching_pairs": count}


class DigestTests(unittest.TestCase):
    def test_only_one_telegram_message_for_multiple_channels(self):
        first = found("film_romance_20", "Cinéma & Films", 3)
        second = found("g_romanticfilm", "Films <romantiques>", 12)
        bot = SimpleNamespace(send_message=AsyncMock())
        sent = set()
        result = asyncio.run(notify_saved_messages(
            bot, [first, second, first], sent
        ))
        self.assertEqual(result, (["film_romance_20", "g_romanticfilm"], 0))
        bot.send_message.assert_awaited_once()
        args, kwargs = bot.send_message.await_args
        self.assertEqual(args[0], "me")
        self.assertEqual(kwargs["parse_mode"], "html")
        self.assertFalse(kwargs["link_preview"])
        html = args[1]
        self.assertEqual(html.count("https://t.me/film_romance_20"), 2)
        self.assertEqual(html.count("https://t.me/g_romanticfilm"), 2)
        self.assertIn("<b>1. Cinéma &amp; Films</b>", html)
        self.assertIn("<b>2. Films &lt;romantiques&gt;</b>", html)
        self.assertIn("<a href=", html)
        self.assertIn(chr(10) + chr(10), html)
        self.assertNotIn(chr(92) + "n", html)  # no visible backslash-n sequences
        self.assertIn("Droits de redistribution", html)

    def test_no_repeat_in_same_session_and_no_empty_messages(self):
        first = found("film_romance_20", "Film", 3)
        second = found("g_romanticfilm", "Films", 4)
        client = SimpleNamespace(send_message=AsyncMock())
        sent = {"film_romance_20"}
        result = asyncio.run(notify_saved_messages(client, [first, second], sent))
        self.assertEqual(result, (["g_romanticfilm"], 0))
        self.assertEqual(client.send_message.await_count, 1)
        result = asyncio.run(notify_saved_messages(client, [first, second], sent))
        self.assertEqual(result, ([], 0))
        self.assertEqual(client.send_message.await_count, 1)

    def test_failed_digest_marks_nobody_as_notified(self):
        client = SimpleNamespace(send_message=AsyncMock(side_effect=ValueError("No send")))
        sent = set()
        got = asyncio.run(notify_saved_messages(
            client, [found("g_romanticfilm", "Films", 2)], sent
        ))
        self.assertEqual(got, ([], 1))
        self.assertEqual(sent, set())

    def test_second_desir_source_is_explicitly_allowed(self):
        verify_destination("@Filmromatique", "@CineXDesirfr", "-100123456789")
        verify_destination("@g_romanticfilm", "@CineXDesirfr", "-100123456789")
        with self.assertRaises(RuntimeError):
            verify_destination("@unknownsource", "@CineXDesirfr", "-100123456789")

    def test_link_is_standalone_and_clickable(self):
        part = notification_text(found("g_romanticfilm", "Films", 7))
        lines = part.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], "<b>1. Films</b>")
        self.assertEqual(lines[1],
                         '🔗 <a href="https://t.me/g_romanticfilm">https://t.me/g_romanticfilm</a>')
        self.assertIn("7 paires", lines[2])

    def test_one_digest_fits_telegram_limit(self):
        sample = [found("romantic_film_test_%02d" % n, "Titre " + "X" * 160, 11)
                  for n in range(16)]
        self.assertLess(len(notification_summary(sample)), 4000)


if __name__ == "__main__":
    unittest.main()
