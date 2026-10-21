import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE_FILE = Path(__file__).with_name("distribute_short_telegram.py")
spec = importlib.util.spec_from_file_location("telegram_video_distribution", MODULE_FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TelegramVideoDistributionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cfg = json.loads(Path("config/telegram_video_distribution.json").read_text(encoding="utf-8"))
        self.config = cfg
        self.receipt = {
            "primary_chat": "@mrxpronosfr",
            "primary_message_id": 12345,
            "primary_chat_id": -1001234567,
            "keyboard": {"inline_keyboard": [[button] for button in cfg["buttons"]]},
            "caption": "Vidéo réelle • 18+",
            "published_day": "2026-10-21",
            "target": "2026-10-21",
        }
        self.config_file = Path(self.tmp.name) / "channels.json"
        self.receipt_file = Path(self.tmp.name) / "receipt.json"
        self.config_file.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        self.receipt_file.write_text(json.dumps(self.receipt, ensure_ascii=False), encoding="utf-8")
        self.patch_cfg = mock.patch.object(module, "CONFIG", self.config_file)
        self.patch_receipt = mock.patch.object(module, "RECEIPT", self.receipt_file)
        self.patch_cfg.start()
        self.patch_receipt.start()
        self.addCleanup(self.patch_cfg.stop)
        self.addCleanup(self.patch_receipt.stop)

    def test_exact_3_buttons_and_7_channels(self):
        config, receipt = module.load()
        self.assertEqual(len(receipt["keyboard"]["inline_keyboard"]), 3)
        self.assertEqual(len(config["destinations"]), 7)
        self.assertEqual(config["torrent9_forward"], "@Torrent9SeriesFilms")

    def test_dry_run_never_calls_telegram_or_supabase(self):
        config, receipt = module.load()
        with mock.patch.object(module.requests, "Session", side_effect=AssertionError("network call")):
            result = module.distribute(config, receipt, Path("missing.mp4"), dry_run=True)
        self.assertEqual(len(result["destinations"]), 7)
        self.assertEqual(result["torrent9"], "@Torrent9SeriesFilms")

    def test_reject_modified_folder_url(self):
        self.receipt["keyboard"]["inline_keyboard"][2][0]["url"] = "https://invalid.test/list"
        self.receipt_file.write_text(json.dumps(self.receipt, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(ValueError):
            module.load()

    def test_reject_duplicate_destinations(self):
        config = dict(self.config)
        config["destinations"] = self.config["destinations"] + [{"chat":"@CineXAnimeFR","label":"duplicate"}]
        self.config_file.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(ValueError):
            module.load()

    def test_seven_destinations_share_original_media_and_forward_to_torrent9(self):
        config, receipt = module.load()
        forwarded = []
        class FakeBot:
            def __init__(self, token, name):
                self.token, self.name, self.source, self.bot_id = token, name, None, 42
            def identify(self):
                pass
            def chat(self, username):
                targets = [d["chat"] for d in config["destinations"]]
                return {"id": 1000 + targets.index(username)}
            def can_post(self, username):
                return username != "@Torrent9SeriesFilms"
            def copy(self, target, keyboard, caption):
                self_case.assertEqual(len(keyboard["inline_keyboard"]), 3)
                self_case.assertEqual(self.source, ("@mrxpronosfr", 12345))
                forwarded.append(target)
                return 100 + len(forwarded)
            def upload(self, *args):
                raise AssertionError("main bot must copy; no second MP4 upload")
        self_case = self
        with mock.patch.dict(module.os.environ, {
            "TELEGRAM_BOT_TOKEN": "mock", "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "mock_key", "FOOTBALL_NEWS_BOT_TOKEN": "",
            "DESIR_BOT_TOKEN": "",
        }):
            with mock.patch.object(module, "Bot", FakeBot), \
                 mock.patch.object(module, "claim", return_value=True), \
                 mock.patch.object(module.asyncio, "run", return_value=777), \
                 mock.patch.object(module.requests, "Session"):
                result = module.distribute(config, receipt, Path("unused.mp4"))
        self.assertEqual(len(forwarded), 6)
        self.assertEqual(len(result["results"]), 7)
        self.assertEqual(result["torrent9"]["id"], 777)
        self.assertFalse(result["errors"])

    def test_claim_has_atomic_uniqueness_key(self):
        fake_session = mock.Mock()
        fake_response = mock.Mock()
        fake_response.json.return_value = [{"kind":"shorts_video_channel_distribution"}]
        fake_session.post.return_value = fake_response
        self.assertTrue(module.claim(fake_session, "https://example.supabase.co", "key",
                                     "shorts_video_channel_distribution", "-1001234", "2026-10-21"))
        kwargs = fake_session.post.call_args.kwargs
        self.assertEqual(kwargs["params"]["on_conflict"], "kind,ref_id,ref_date")

if __name__ == "__main__":
    unittest.main()
