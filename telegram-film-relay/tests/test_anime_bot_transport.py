"""Bot-only transport contracts: fail closed on access and webhook conflicts."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock

from film_relay.anime_bot_transport import AnimeBotTransport


class BotTransportTests(unittest.TestCase):
    def _client(self, *, source_admin=True, post_messages=True, webhook=""):
        bot = AnimeBotTransport("123:placeholder")
        async def fake(method, data=None):
            if method == "getMe":
                return {"id": 123, "username": "cinex_anime_dedicated"}
            if method == "getChatMember":
                return {"status": "administrator" if source_admin else "member",
                        "can_post_messages": post_messages}
            if method == "getWebhookInfo":
                return {"url": webhook}
            if method == "copyMessage":
                return {"message_id": 77}
            if method == "getUpdates":
                return []
            if method == "sendMessage":
                return {"message_id": 55}
            raise AssertionError(method)
        bot.call = AsyncMock(side_effect=fake)
        return bot

    def test_explicit_admin_rights_and_destination_permissions(self):
        bot = self._client()
        who = asyncio.run(bot.assert_permissions(
            ["-1001234567890"], "-1002222222222", "-1003333333333"))
        self.assertEqual(who.id, 123)
        self.assertEqual(bot.call.await_count, 4)
        bot2 = self._client(source_admin=False)
        with self.assertRaisesRegex(RuntimeError, "administrator"):
            asyncio.run(bot2.assert_permissions(
                ["-1001234567890"], "-1002222222222", "-1003333333333"))
        bot3 = self._client(post_messages=False)
        with self.assertRaisesRegex(RuntimeError, "cannot post"):
            asyncio.run(bot3.assert_permissions(
                ["-1001234567890"], "-1002222222222", "-1003333333333"))

    def test_bot_never_consumes_another_webhook_poll_queue(self):
        bot = self._client(webhook="https://example.invalid/webhook")
        with self.assertRaisesRegex(RuntimeError, "active webhook"):
            asyncio.run(bot.assert_polling_available())

    def test_copy_server_side_requires_no_file_download(self):
        bot = self._client()
        result = asyncio.run(bot.copy_message(
            "-1003333333333", "-1001234567890", 99,
            caption="<b>Naruto</b>", reply_markup={
                "inline_keyboard": [[{"text": "Voir",
                                      "url": "https://t.me/c/1/2"}]]
            }))
        self.assertEqual(result, 77)
        data = bot.call.await_args.args[1]
        self.assertEqual(data["from_chat_id"], "-1001234567890")
        self.assertEqual(data["message_id"], "99")
        self.assertIn("inline_keyboard", data["reply_markup"])


if __name__ == "__main__":
    unittest.main()
