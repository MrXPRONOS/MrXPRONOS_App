#!/usr/bin/env python3
"""Read-only CinéX bot identity and permission preflight.

Never logs Telegram tokens, channel IDs, invitation links or subscriber IDs.
Never calls mutating Telegram methods or uses a personal Telegram session.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from audit_series_bots import BotAPI, parse_channel_ids
from publish_individual_series_bot import d1

REPORT = Path("cinex-bot-permissions-report.json")
EXCESS = (
    "can_promote_members", "can_change_info", "can_restrict_members",
    "can_delete_messages", "can_manage_video_chats", "can_post_stories",
    "can_edit_stories", "can_delete_stories",
)
DESTINATIONS = frozenset(("series_main", "series_rescue", "films_main", "films_rescue"))
SENSITIVE_DESTINATIONS = DESTINATIONS  # Existing callers/tests
SOURCE_CATEGORIES = frozenset(("franchise_source",))
BOT_TOKENS = (
    ("publisher", "CINEX_PUBLISH_BOT_TOKEN"),
    ("legacy_football", "ALT_FOOTBALL_NEWS_BOT_TOKEN"),
    ("radar", "CINEX_RADAR_BOT_TOKEN"),
    ("secondary", "ALT_TELEGRAM_BOT_TOKEN"),
    ("desir", "ALT_DESIR_BOT_TOKEN"),
    ("action", "ALT_ACTION_BOT_TOKEN"),
    ("anime", "ALT_ANIME_BOT_TOKEN"),
    ("series", "ALT_SERIES_BOT_TOKEN"),
)
USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


def channel_targets():
    sources = parse_channel_ids(os.getenv("CINEX_SERIES_CHANNEL_IDS", ""))
    targets = [
        ("series_main", "@seriesvf_cinex"),
        ("series_rescue", "-1003822435811"),
        ("films_main", "@CineXFilms_vf"),
        ("franchise_source", "@fastandfuriousvffr"),
    ]
    try:
        rows = d1(
            "SELECT rescue_chat_id FROM cine_classic_rescue_config WHERE LOWER(public_handle)=?",
            ["@cinexfilms_vf"],
        )
        if len(rows) == 1 and re.fullmatch(r"-100[0-9]{6,}", str(rows[0].get("rescue_chat_id", ""))):
            targets.append(("films_rescue", str(rows[0]["rescue_chat_id"])))
    except RuntimeError:
        print("PERMISSIONS_RESCUE_D1_UNAVAILABLE: films rescue omitted")
    for i, source in enumerate(sources, 1):
        targets.append((f"series_source_{i:02d}", source))
    return targets


def inspect_permission(member: dict, *, destination: bool):
    status = str(member.get("status") or "unknown")
    if status not in ("administrator", "creator"):
        return {"access": status, "can_publish": False, "dangerous": []}
    sensitive = sorted(x for x in EXCESS if member.get(x) is True)
    return {
        "access": status,
        "can_publish": (status == "creator" or bool(member.get("can_post_messages"))) if destination else None,
        "dangerous": sensitive,
    }


def expected_username(value: str):
    value = (value or "").strip().lstrip("@")
    if not value:
        return None
    if not USERNAME.fullmatch(value):
        raise ValueError("CINEX_PUBLISH_BOT_USERNAME invalid")
    return value.lower()


def audit_permissions(bot_candidates, targets, *, publisher_username="", expected_series_count=11):
    """Each checked identity is bound to its own token. No cross-bot substitutions.

    A dedicated publisher is ready only if the configured public username
    matches, all four destinations allow posting, and all indexed sources
    permit source access. A missing target never counts as verified.
    """
    expected = expected_username(publisher_username)
    categories = [category for category, _ in targets]
    required = set(categories)
    expected_categories = set(DESTINATIONS)
    expected_categories.add("franchise_source")
    if not isinstance(expected_series_count, int) or not 1 <= expected_series_count <= 50:
        raise ValueError("Expected series source count must be between 1 and 50")
    expected_categories.update(f"series_source_{i:02d}" for i in range(1, expected_series_count + 1))
    report = {
        "bot_count": 0, "channel_categories": len(targets),
        "checks": [], "manual_review_count": 0, "unreachable_count": 0,
        "publisher": {
            "dedicated_secret_present": False, "expected_username_configured": expected is not None,
            "identity": "not_configured", "destinations_verified": False,
            "source_access_verified": False, "ready": False,
            "missing_categories": sorted(expected_categories - required),
        },
    }
    seen = set()
    for label, token in bot_candidates:
        token = (token or "").strip()
        if label == "publisher" and token:
            report["publisher"]["dedicated_secret_present"] = True
        if not token:
            continue
        if token in seen:
            report["checks"].append({"bot_label": label, "category": "identity", "access": "duplicate_secret"})
            if label == "publisher":
                report["publisher"]["identity"] = "duplicate_secret"
            continue
        seen.add(token)
        try:
            bot = BotAPI(token)
            who = bot.call("getMe", {})
            if who.get("is_bot") is not True:
                raise ValueError("Not a Telegram bot")
            user_id = who["id"]
            if type(user_id) is not int or user_id <= 0:
                raise ValueError("Invalid bot identity")
            username = str(who.get("username") or "").lower()
            if label == "publisher":
                report["publisher"]["identity"] = (
                    "verified" if expected and username == expected
                    else "mismatch" if expected
                    else "expected_username_missing"
                )
        except (RuntimeError, TypeError, ValueError, KeyError):
            report["unreachable_count"] += 1
            report["checks"].append({"bot_label": label, "category": "identity", "access": "unavailable"})
            if label == "publisher":
                report["publisher"]["identity"] = "unavailable"
            continue
        report["bot_count"] += 1
        verified = set()
        source_ok = set()
        for category, chat in targets:
            try:
                rights = bot.call("getChatMember", {"chat_id": chat, "user_id": user_id})
                info = inspect_permission(rights, destination=category in DESTINATIONS)
                entry = {"bot_label": label, "category": category, **info}
                if info["dangerous"]:
                    report["manual_review_count"] += 1
                if category in DESTINATIONS:
                    entry["publisher_rights_missing"] = info["can_publish"] is False
                    if info["can_publish"] is True:
                        verified.add(category)
                elif info["access"] in ("administrator", "creator"):
                    source_ok.add(category)
                report["checks"].append(entry)
            except (RuntimeError, TypeError, KeyError, ValueError):
                report["unreachable_count"] += 1
                report["checks"].append({"bot_label": label, "category": category, "access": "unavailable"})
        if label == "publisher":
            report["publisher"]["destinations_verified"] = DESTINATIONS.issubset(verified)
            sources = {x for x in expected_categories if x not in DESTINATIONS}
            report["publisher"]["source_access_verified"] = sources.issubset(source_ok)
            report["publisher"]["ready"] = bool(
                report["publisher"]["identity"] == "verified"
                and not report["publisher"]["missing_categories"]
                and report["publisher"]["destinations_verified"]
                and report["publisher"]["source_access_verified"]
            )
    return report


def main():
    candidates = [(label, os.getenv(name, "")) for label, name in BOT_TOKENS]
    targets = channel_targets()
    report = audit_permissions(
        candidates, targets,
        publisher_username=os.getenv("CINEX_PUBLISH_BOT_USERNAME", ""),
        expected_series_count=int(os.getenv("CINEX_EXPECTED_SERIES_SOURCE_COUNT", "11")),
    )
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("CINEX_BOT_RIGHTS_SUMMARY", json.dumps(
        {k: v for k, v in report.items() if k != "checks"}, ensure_ascii=False))
    for check in report["checks"]:
        print("CINEX_BOT_RIGHTS", check["bot_label"], check["category"],
              check["access"], "excess", ",".join(check.get("dangerous", [])) or "-")
    # Diagnostic exit code remains 0: missing deployment secrets should never
    # accidentally break other working publication workflows.
    if not report["publisher"]["ready"]:
        print("CINEX_PUBLISHER_PREFLIGHT_INCOMPLETE: read-only diagnosis, no Telegram changes")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        REPORT.write_text(json.dumps({"status": "unavailable", "reason": type(error).__name__}),
                          encoding="utf-8")
        print("CINEX_BOT_RIGHTS_AUDIT_UNAVAILABLE", type(error).__name__, file=sys.stderr)
        sys.exit(1)
