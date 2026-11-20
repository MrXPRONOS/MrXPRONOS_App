"""Offline guard against accidental opening of personal Telegram sessions.

This test performs no Telegram API request, no logins and no side effects.
"""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PERSONAL_WORKFLOWS=(
 "cinex-phase1-health.yml",
 "cinex-rescue-channels.yml",
 "cinex-catalog-stage12.yml",
 "cinex-public-video-rotation.yml",
 "cinex-unified-preflight.yml",
 "cinex-trending-private.yml",
 "cinex-radar-library-access.yml",
 "cinex-provision-series-action-libraries.yml",
 "telegram-film-relay.yml",
 "telegram-discovery-daily.yml",
 "telegram-film-healthcheck.yml",
)

class PersonalCooldownWorkflowTests(unittest.TestCase):
 def test_all_known_personal_session_workflows_gate_login(self):
  for name in PERSONAL_WORKFLOWS:
   with self.subTest(workflow=name):
    content=(ROOT/".github"/"workflows"/name).read_text("utf-8")
    self.assertIn("check_personal_cooldown.py",content)
    self.assertIn("TG_PERSONAL_COOLDOWN_UNTIL_UTC",content)
    # The gate must appear after checkout but BEFORE the first session-backed
    # rescue_links_runtime invocation or film_relay command.
    gate=content.index("check_personal_cooldown.py")
    for marker in ("python -m film_relay.rescue_links_runtime",
                   "python -m film_relay.discovery",
                   "python -m film_relay.ten_video_rotation"):
     if marker in content:
      self.assertLess(gate,content.index(marker),name+" starts Telethon before the cooldown gate")

if __name__=="__main__":unittest.main()
