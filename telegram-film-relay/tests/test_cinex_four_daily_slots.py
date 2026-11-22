import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_cinex_four_daily_slots import inspect_messages, full_day_status, target_is_general

class TestAudit(unittest.TestCase):
    def test_four_slots(self):
        day="2026-11-21"
        messages=[SimpleNamespace(date=datetime(2026,11,21,h,12,tzinfo=timezone.utc),
                                  video=object(),media=None)
                  for h in (1,7,13,19)]
        v=inspect_messages(messages,day)
        self.assertEqual(v["video_slots"],[1,1,1,1])
        self.assertEqual(v["slots_with_video"],4)
        self.assertIn("4/4",full_day_status(v))
    def test_text_posts_not_media(self):
        day="2026-11-21"
        v=inspect_messages([SimpleNamespace(date=datetime(2026,11,21,2,tzinfo=timezone.utc),
                                             video=None,media=None)],day)
        self.assertEqual(v["videos"],0)
        self.assertIn("NON atteint",full_day_status(v))
    def test_dedicated_excluded(self):
        self.assertFalse(target_is_general({"title":"One Piece VF","categories":["animes"],"dedicated_title":"one piece"}))
        self.assertTrue(target_is_general({"title":"Films action CineX","categories":["films"],"dedicated_title":None}))
if __name__=="__main__":unittest.main()
