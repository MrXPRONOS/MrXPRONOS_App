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
from film_relay.bot_http import url_button
from telethon.tl.types import Channel


class DummyUser:
    async def get_entity(self, value):
        return Channel(id=123456789, title="CineX", photo=None, date=None)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.bot = BotHTTPClient("123456:fake-token", DummyUser())

    def test_blue_button(self):
        markup = self.bot._keyboard([[url_button(
            "Proposer un partenariat", "https://t.me/mr_xpronos?text=PARTENARIAT-CANAL",
            style="primary"
        )]])
        self.assertEqual(markup["inline_keyboard"][0][0]["style"], "primary")

    def test_movie_button_color(self):
        markup = self.bot._keyboard([[url_button("Regarder le film", "https://t.me/c/123/456", style="success")]])
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
                buttons=[[url_button("Contact", "https://t.me/mr_xpronos", style="primary")]]
            )
        obj = asyncio.run(send())
        self.assertEqual(obj.id, 312)
        self.assertEqual(sent[0][0], "sendPhoto")
        self.assertEqual(json.loads(sent[0][1]["reply_markup"])["inline_keyboard"][0][0]["style"], "primary")

    def test_unchanged_public_buttons_are_idempotent(self):
        async def unchanged(method, data=None, files=None):
            raise TelegramBotHTTPError("Bad Request: message is not modified")
        self.bot._call = unchanged
        channel = Channel(id=123456789, title="CineX", photo=None, date=None)
        rows = [[url_button("Saison 1", "https://t.me/c/123/1")]]
        result = asyncio.run(self.bot.edit_reply_markup(channel, 4, buttons=rows))
        self.assertFalse(result)

    def test_copy_video_includes_four_inline_buttons(self):
        calls = []
        async def fake_call(method, data=None, files=None):
            calls.append((method, data))
            return {"message_id": 900}
        self.bot._call = fake_call
        public = Channel(id=234567890, title="Public", photo=None, date=None)
        private = Channel(id=345678901, title="Private", photo=None, date=None)
        rows = [[url_button(name, url, style="primary")] for name, url in (
            ("Voir", "https://t.me/c/1234/20"),
            ("Télécharger", "https://t.me/CineRadarFr_Bot?start=d_123456789012345678901234"),
            ("Secours", "https://t.me/+VerifiedRescueExample"),
            ("Dossier", "https://t.me/addlist/Example"),
        )]
        result = asyncio.run(self.bot.copy_message(
            public, private, 88, caption="Test vidéo", parse_mode="html",
            buttons=rows))
        self.assertEqual(result.id, 900)
        self.assertEqual(calls[0][0], "copyMessage")
        self.assertEqual(calls[0][1]["parse_mode"], "HTML")
        markup = json.loads(calls[0][1]["reply_markup"])
        self.assertEqual(len(markup["inline_keyboard"]), 4)
        self.assertEqual(markup["inline_keyboard"][0][0]["text"], "Voir")

    def test_bot_identity_read_retries_one_transient_timeout(self):
        from requests.exceptions import Timeout
        calls = []
        class Response:
            status_code = 200
            def json(self):
                return {"ok": True, "result": {"id": 15, "username": "main_bot"}}
        def request(*args, **kwargs):
            calls.append(args[0])
            if len(calls) == 1:
                raise Timeout("temporary read failure")
            return Response()
        with patch("film_relay.bot_http.requests.post", side_effect=request), \
             patch("film_relay.bot_http.time.sleep", return_value=None):
            self.assertEqual(self.bot._call_sync("getMe")["id"], 15)
        self.assertEqual(len(calls), 2)

    def test_bot_read_retry_is_bounded_and_429_is_not_retried(self):
        from requests.exceptions import Timeout
        class Response:
            status_code = 429
            def json(self):
                return {"ok": False, "parameters": {"retry_after": 40}}
        with patch("film_relay.bot_http.requests.post",
                   side_effect=Timeout("offline")) as post, \
             patch("film_relay.bot_http.time.sleep", return_value=None):
            with self.assertRaisesRegex(TelegramBotHTTPError, "lecture en échec"):
                self.bot._call_sync("getChatMember")
            self.assertEqual(post.call_count, 2)
        with patch("film_relay.bot_http.requests.post",
                   return_value=Response()) as post:
            with self.assertRaisesRegex(TelegramBotHTTPError, "40"):
                self.bot._call_sync("getChatMember")
            self.assertEqual(post.call_count, 1)

    def test_uncertain_send_photo_is_never_retried(self):
        from requests.exceptions import Timeout
        with patch("film_relay.bot_http.requests.post",
                   side_effect=Timeout("post accepted, reply missing")) as post:
            with self.assertRaisesRegex(TelegramBotHTTPError, "envoi incertain"):
                self.bot._call_sync("sendPhoto")
            self.assertEqual(post.call_count, 1)

    def test_bot_read_retries_one_gateway_error_only(self):
        class Response:
            def __init__(self, status):
                self.status_code = status
            def json(self):
                if self.status_code == 503:
                    return {"ok": False, "description": "temporarily down"}
                return {"ok": True, "result": {"id": 9}}
        with patch("film_relay.bot_http.requests.post",
                   side_effect=[Response(503), Response(200)]) as post, \
             patch("film_relay.bot_http.time.sleep", return_value=None):
            self.assertEqual(self.bot._call_sync("getMe")["id"], 9)
            self.assertEqual(post.call_count, 2)

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
