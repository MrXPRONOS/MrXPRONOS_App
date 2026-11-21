import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts/diagnose_channel_reaction_targets.py"
spec = importlib.util.spec_from_file_location("reaction_forensics", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class DiagnosticTests(unittest.TestCase):
    def test_missing(self):
        self.assertEqual(mod.summarize_message(425, None),
                         {"id": 425, "status": "not_visible_or_deleted"})
        Empty = type("MessageEmpty", (), {})
        self.assertEqual(mod.summarize_message(426, Empty())["status"],
                         "not_visible_or_deleted")

    def test_service_action_is_reported_without_content(self):
        Pin = type("MessageActionPinMessage", (), {})
        Service = type("MessageService", (), {})
        msg = Service()
        msg.id = 427
        msg.action = Pin()
        msg.date = None
        result = mod.summarize_message(427, msg)
        self.assertEqual(result["status"], "service")
        self.assertEqual(result["service_action"], "MessageActionPinMessage")
        self.assertNotIn("text", result)

    def test_normal_photo_reports_only_metadata(self):
        Photo = type("MessageMediaPhoto", (), {})
        Content = type("Message", (), {})
        msg = Content()
        msg.id = 425
        msg.media = Photo()
        msg.message = "Private caption not for logs"
        msg.grouped_id = None
        msg.pinned = True
        msg.date = None
        result = mod.summarize_message(425, msg)
        self.assertEqual(result["status"], "content")
        self.assertEqual(result["media_type"], "MessageMediaPhoto")
        self.assertTrue(result["has_text"])
        self.assertNotIn("Private caption", str(result))


if __name__ == "__main__":
    unittest.main()
