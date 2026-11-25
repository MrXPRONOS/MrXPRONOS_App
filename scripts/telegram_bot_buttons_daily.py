#!/usr/bin/env python3
"""Daily button-first Telegram bot dispatcher.

Runs one approved EXISTING bot publisher per daily slot. Does not use MTProto.
A preview never calls Telegram, Supabase, or uploads files.
"""
from __future__ import annotations

import argparse
import importlib
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SLOTS = {
    "0 6 * * *": "weekday",
    "30 6 * * *": "xpvip",
    "0 7 * * *": "bonus",
    "30 7 * * *": "guide",
}
PUBLISHERS = {
    "weekday": "send_day_based_bookmaker_promos.py",
    "xpvip": "send_daily_partner_promo.py",
    "bonus": "send_daily_bookmaker_bonus_ads.py",
    "guide": "send_daily_bookmaker_guide.py",
}


def selected_campaign(event_schedule="", manual_campaign=""):
    event_schedule = (event_schedule or "").strip()
    manual_campaign = (manual_campaign or "").strip()
    if event_schedule and manual_campaign:
        raise ValueError("Cron and manual campaign cannot be combined")
    if event_schedule:
        if event_schedule not in SLOTS:
            raise ValueError("Unknown scheduled slot, no publication")
        return SLOTS[event_schedule]
    if manual_campaign not in PUBLISHERS:
        raise ValueError("Explicit manual campaign required")
    return manual_campaign


def assert_buttons(markup, label):
    if not isinstance(markup, dict) or not isinstance(markup.get("inline_keyboard"), list):
        raise ValueError(f"{label}: real inline keyboard required")
    count = 0
    for row in markup["inline_keyboard"]:
        if not isinstance(row, list) or not row:
            raise ValueError(f"{label}: invalid keyboard row")
        for entry in row:
            if not isinstance(entry, dict) or not str(entry.get("text", "")).strip():
                raise ValueError(f"{label}: missing button caption")
            url = str(entry.get("url", "")).strip()
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError(f"{label}: HTTPS URL button required")
            count += 1
    if count < 1:
        raise ValueError(f"{label}: empty inline keyboard")
    return count


def validate_templates():
    """Import existing campaigns and verify actual button payloads offline."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    xp = importlib.import_module("send_daily_partner_promo")
    day = importlib.import_module("send_day_based_bookmaker_promos")
    bonus = importlib.import_module("send_daily_bookmaker_bonus_ads")
    guide = importlib.import_module("send_daily_bookmaker_guide")
    checks = {"xpvip": 0, "weekday": 0, "bonus": 0, "guide": 0}
    checks["xpvip"] += assert_buttons(xp.keyboard(xp.IMAGE_PATH), "xpvip")
    for promo in day.PROMOS:
        if day.partner(promo.bookmaker) is None:
            continue
        checks["weekday"] += assert_buttons(day.keyboard_for(promo), promo.image)
    for key, offer in bonus.BOOKMAKERS.items():
        checks["bonus"] += assert_buttons(bonus.keyboard(offer), key)
    for key, offer in guide.PARTNERS.items():
        checks["guide"] += assert_buttons(guide.single_keyboard(offer), key)
    if not all(checks.values()):
        raise ValueError("Some promotion templates lost their buttons")
    return checks


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule", default="", help="Exact GitHub cron that fired")
    parser.add_argument("--campaign", default="", choices=("", *PUBLISHERS.keys()))
    parser.add_argument("--execute", action="store_true", help="Explicitly post via Bot API")
    args = parser.parse_args(argv)
    campaign = selected_campaign(args.schedule, args.campaign)
    buttons = validate_templates()
    print("BUTTON_PREFLIGHT_OK", campaign, "template_buttons", buttons)
    if not args.execute:
        print("PREVIEW_ONLY; no Telegram or Supabase API call")
        return 0
    if os.environ.get("TG_BOT_BUTTONS_DAILY_ENABLED") != "true":
        raise RuntimeError("New bot scheduler is not enabled")
    if not all((os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID"),
                os.environ.get("TELEGRAM_CHAT_ID_SECONDARY"),
                os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))):
        raise RuntimeError("Missing production bot or idempotency credentials")
    env = os.environ.copy()
    # No date/bookmaker override in production; always use today's approved rotation.
    env["FORCE_WEEKDAY"] = ""
    env["BOOKMAKER_FORCE_KEY"] = ""
    env["BOOKMAKER_OVERRIDE"] = "auto"
    env["DRY_RUN"] = "false"
    cmd = [sys.executable, str(SCRIPTS / PUBLISHERS[campaign])]
    result = subprocess.run(cmd, cwd=ROOT, env=env, check=False)
    if result.returncode:
        raise RuntimeError(f"Bot publisher {campaign} failed with exit {result.returncode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
