"""Contrôles hors réseau des publications bot HTTP."""
import asyncio
import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from film_relay.bot_http import BotHTTPClient, TelegramBotHTTPError
from telethon import Button
from telethon.tl.types import Channel


class DummyUser:
    async def get_entity(self, value):
        return Channel(id=123456789, title="CineX", photo=None, date=None)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.bot = BotHTTPClient("123456:fake-token", DummyUser())

    def test_blue_button(self):
        markup = self.bot._keyboard([[Button.url(
            "Proposer un partenariat", "https://t.me/mr_xpronos?text=PARTENARIAT-CANAL",
            style="primary"
        )]])
        self.assertEqual(markup["inline_keyboard"][0][0]["style"], "primary")

    def test_movie_button_color(self):
        markup = self.bot._keyboard([[Button.url("Regarder le film", "https://t.me/c/123/456", style="success")]])
        self.assertEqual(markup["inline_keyboard"][0][0]["style"], "success")

    def test_send_photo_has_no_bot_auth_request(self):
        sent = []
        async def fake_call(method, data=None, files=None):
            sent.append((method, data, files))
            return {"message_id": 312}
        self.bot._call = fake_call
        channel = Channel(id=123456789, title="CineX", photo=None, date=None)
        async def send():
            return await self.bot.send_file(
                channel, io.BytesIO(b"\\xff\\xd8\\xff"), caption="Test",
                buttons=[[Button.url("Contact", "https://t.me/mr_xpronos", style="primary")]]
            )
        obj = asyncio.run(send())
        self.assertEqual(obj.id, 312)
        self.assertEqual(sent[0][0], "sendPhoto")
        self.assertEqual(json.loads(sent[0][1]["reply_markup"])["inline_keyboard"][0][0]["style"], "primary")

    def test_429_never_retries(self):
        called = []
        class Response:
            status_code = 429
            def json(self):
                return {"ok":False, "parameters":{"retry_after":1319}, "description":"Too Many Requests"}
        def post(*args, **kwargs):
            called.append(True)
            return Response()
        with patch("film_relay.bot_http.requests.post", post):
            with self.assertRaisesRegex(TelegramBotHTTPError, "1319"):
                self.bot._call_sync("sendPhoto")
        self.assertEqual(len(called),1)


if __name__=="__main__":
    unittest.main()
