"""Offline guard against accidental opening of personal Telegram sessions.

This test performs no Telegram API request, no logins and no side effects.
"""
import unittest
import re
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
 "formation-telegram.yml",
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

 def test_every_shared_personal_session_lock_uses_non_replacing_queue(self):
  """Inspect every workflow, including future non-CineX consumers."""
  checked=0
  for path in sorted((ROOT/".github"/"workflows").glob("*.y*ml")):
   lines=path.read_text("utf-8").splitlines()
   for i,line in enumerate(lines):
    if not re.match(r"^\s*group\s*:",line) or "mrx-telegram-personal-account" not in line:
     continue
    checked+=1
    indent=len(line)-len(line.lstrip())
    block=[]
    for following in lines[i+1:]:
     if not following.strip() or following.lstrip().startswith("#"):
      continue
     if len(following)-len(following.lstrip())<indent:
      break
     block.append(following.strip())
    with self.subTest(workflow=path.name,line=i+1):
     self.assertIn("cancel-in-progress: false",block)
     self.assertIn("queue: max",block)
  self.assertGreater(checked,0)

if __name__=="__main__":unittest.main()
