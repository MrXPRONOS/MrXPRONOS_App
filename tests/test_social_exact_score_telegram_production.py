"""No network: production teaser safety and routing."""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import social_exact_score_telegram_teaser as teaser
from telegram_production_guard import (
    validate_production_channel, ProductionChannelGuardError)


class ProductionTeaserTests(unittest.TestCase):
    def test_validate_production_channel_exact_username_admin(self):
        results = [
            {"ok": True, "result": {"id": -10017, "type": "channel",
                                    "username": "mrxpronosfr"}},
            {"ok": True, "result": {"id": 2411, "username": "productionbot"}},
            {"ok": True, "result": {"status": "administrator",
                                    "can_post_messages": True}},
        ]
        def get(url, **kwargs):
            value = Mock(status_code=200)
            value.json.return_value = results.pop(0)
            return value
        result = validate_production_channel("@mrxpronosfr", "dummy", request_get=get)
        self.assertEqual(result["username"], "mrxpronosfr")
        self.assertEqual(result["chat_id"], -10017)

    def test_reject_test_channel_even_if_admin(self):
        chat = Mock(status_code=200)
        chat.json.return_value = {"ok": True, "result": {
            "id": -10018, "type": "channel", "username": "predict_mrxp"}}
        with self.assertRaises(ProductionChannelGuardError):
            validate_production_channel("@predict_mrxp", "dummy",
                                        request_get=lambda *a, **k: chat)

    def test_reject_bot_without_post_permission(self):
        values = iter([
            {"ok": True, "result": {"id": -10017, "type": "channel",
                                    "username": "mrxpronosfr"}},
            {"ok": True, "result": {"id": 2411}},
            {"ok": True, "result": {"status": "member"}}
        ])
        def get(*args, **kwargs):
            response = Mock(status_code=200)
            response.json.return_value = next(values)
            return response
        with self.assertRaises(ProductionChannelGuardError):
            validate_production_channel("@mrxpronosfr", "dummy", request_get=get)

    def test_production_send_uses_main_guard(self):
        image = Path("fake.png")
        dest = {"chat_id": -10017, "username": "mrxpronosfr"}
        reply = Mock(status_code=200)
        reply.json.return_value = {"ok": True, "result": {
            "chat": {"id": -10017}, "message_id": 42}}
        with patch("telegram_production_guard.validate_production_channel",
                   return_value=dest) as guard, patch.object(
                   Path, "open") as open_file, patch.object(
                   teaser.requests, "post", return_value=reply) as poster:
            receipt = teaser.send_production(
                image, "<b>TOP 10</b>", {"youtube": "https://www.youtube.com/shorts/abc"},
                token="dummy", chat="@mrxpronosfr")
            self.assertEqual(receipt["url"], "https://t.me/mrxpronosfr/42")
            self.assertEqual(poster.call_args.kwargs["data"]["parse_mode"], "HTML")
            guard.assert_called_once_with("@mrxpronosfr", "dummy")

    def test_production_ref_constant_across_visual_updates(self):
        self.assertEqual(teaser.PRODUCTION_KIND, "dcscore_social_teaser_production")
        self.assertEqual(teaser.PRODUCTION_REF, "social-video-daily")
        self.assertEqual(teaser.PRODUCTION_CHANNEL, "@mrxpronosfr")


if __name__ == "__main__":
    unittest.main()
