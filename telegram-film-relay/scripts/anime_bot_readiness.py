"""Read-only production readiness report for a dedicated CineX Anime Bot V2.

No publication, no getUpdates consumption, no personal Telegram session and
no changing chat permissions. Optional Bot API calls only verify configured
identity, webhook status and channel administrator access.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

from film_relay.anime_bot_transport import AnimeBotTransport
from film_relay.anime_bot_matching import (
    select_bot_anime_batches, associate_anime_messages
)
from film_relay.anime_bot_migration import migrate_legacy_catalogue


def _valid_id(value: str) -> bool:
    return str(value).startswith("-100") and str(value)[1:].isdigit()


def local_diagnostics(env=None):
    env = os.environ if env is None else env
    source_values = [
        x.strip() for x in env.get("ANIME_AUTHORIZED_SOURCE_IDS", "")
            .replace(",", " ").split() if x.strip()
    ]
    destination_values = [
        env.get("ANIME_PRIVATE_CHANNEL", "").strip(),
        env.get("ANIME_PUBLIC_CHANNEL_ID", "").strip(),
    ]
    blockers = []
    if not source_values:
        blockers.append("sources_not_allowlisted")
    elif len(set(source_values)) != len(source_values) or not all(
            _valid_id(x) for x in source_values):
        blockers.append("source_id_format_or_duplicates")
    if not all(_valid_id(x) for x in destination_values) or (
            destination_values[0] == destination_values[1]):
        blockers.append("numeric_destinations_missing")
    if set(source_values) & set(destination_values):
        blockers.append("source_destination_overlap")
    token = env.get("CINEX_ANIME_SOURCE_BOT_TOKEN", "")
    if not token or ":" not in token:
        blockers.append("dedicated_bot_missing")
    if not str(env.get("CINEX_ANIME_EXPECTED_BOT_ID", "")).isdigit():
        blockers.append("bot_identity_not_attested")
    if env.get("ANIME_RIGHTS_ATTESTED", "").lower() != "true":
        blockers.append("source_rights_not_attested")
    if env.get("CINEX_ANIME_PRIVATE_PERSISTENCE_ATTESTED") != "true":
        blockers.append("private_durable_storage_not_attested")
    state_path = env.get("CINEX_ANIME_BOT_STATE_PATH", "")
    if not state_path or not Path(state_path).is_absolute() or state_path.startswith(
            ("/tmp/", "/var/tmp/", "/home/runner/work/")):
        blockers.append("private_persistent_path_missing")
    if env.get("CINEX_ANIME_LEGACY_RELAY_DISABLED") != "true":
        blockers.append("legacy_relay_still_active")
    if env.get("CINEX_ANIME_CUTOVER_VERIFIED") != "true":
        blockers.append("cutover_not_verified")
    if env.get("CINEX_ANIME_UNIFIED_LIBRARY_RECONCILED") != "true":
        blockers.append("unified_download_library_not_reconciled")
    return {
        "ready_to_publish": not blockers, "blockers": blockers,
        "authorized_sources_count": len(source_values),
        "private_and_public_ids_configured": all(
            _valid_id(x) for x in destination_values),
    }


async def remote_read_only(env=None):
    env = os.environ if env is None else env
    report = local_diagnostics(env)
    if not env.get("CINEX_ANIME_SOURCE_BOT_TOKEN", ""):
        report["live_bot_checks"] = "skipped_token_not_configured"
        return report
    bot = AnimeBotTransport(env["CINEX_ANIME_SOURCE_BOT_TOKEN"])
    try:
        identity = await bot.identity()
        expected = env.get("CINEX_ANIME_EXPECTED_BOT_ID", "")
        if str(identity.id) != expected:
            report["blockers"].append("dedicated_bot_identity_mismatch")
        # Never consume getUpdates here: doing so would acknowledge messages.
        webhook = await bot.call("getWebhookInfo")
        if webhook.get("url"):
            report["blockers"].append("bot_token_has_other_webhook")
        sources = [x for x in env.get("ANIME_AUTHORIZED_SOURCE_IDS", "").replace(
            ",", " ").split() if _valid_id(x)]
        private = env.get("ANIME_PRIVATE_CHANNEL", "")
        public = env.get("ANIME_PUBLIC_CHANNEL_ID", "")
        if all(_valid_id(c) for c in (private, public)) and sources:
            await bot.assert_permissions(sources, private, public)
            report["live_bot_checks"] = "permissions_validated"
        else:
            report["live_bot_checks"] = "skipped_source_or_destination_ids"
    except Exception as exc:
        # Never include sensitive Telegram error descriptions in public logs.
        report["blockers"].append("bot_api_readiness_failed")
        report["live_bot_checks"] = "failed_" + type(exc).__name__
    report["ready_to_publish"] = not report["blockers"]
    return report


def summarize_legacy(catalogue_path: str):
    path = Path(catalogue_path)
    if not path.is_file():
        return {"available": False}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("active_batch"):
        # An unfinished legacy series must be resumed by its original
        # publisher before cutting over; never import partial receipts.
        batch = data["active_batch"]
        return {"available": True, "migration_blocked": True,
                "reason": "legacy_active_batch_unfinished",
                "pending_episode_count": len(batch.get("episodes", []))
                    if isinstance(batch, dict) and
                       isinstance(batch.get("episodes"), list) else None}
    state = {"schema_version": 1, "series": {}}
    _, review = migrate_legacy_catalogue(state, data)
    return {
        "available": True,
        "importable_series": review["imported_series"],
        "legacy_private_episodes": review["imported_private_episodes"],
        "legacy_public_pairs": review["imported_public_pairs"],
        "unverified_public_episodes": review["legacy_unverified_episodes"],
        "identity_collisions": len(review["collisions"]),
        "requires_review_count": len(review["requires_review"]),
    }


def main():
    try:
        report = asyncio.run(remote_read_only())
    except Exception as exc:
        # Report the stage, never the exception message (may contain tokens).
        print(json.dumps({
            "ready_to_publish": False,
            "blockers": ["remote_readiness_unavailable"],
            "failure_stage": "remote_read_only",
            "failure_type": type(exc).__name__,
        }, sort_keys=True, ensure_ascii=False))
        return 2
    try:
        report["legacy_catalogue"] = summarize_legacy(
            os.environ.get("CINEX_ANIME_LEGACY_CATALOGUE",
                           "state/anime_catalog.json"))
    except Exception as exc:
        report.setdefault("blockers", []).append("legacy_catalogue_audit_failed")
        report["ready_to_publish"] = False
        report["legacy_catalogue"] = {"available": False,
                                      "failure_stage": "legacy_catalogue",
                                      "failure_type": type(exc).__name__}
        print(json.dumps(report, sort_keys=True, ensure_ascii=False))
        return 2
    if not report["legacy_catalogue"].get("available"):
        report.setdefault("blockers", []).append("legacy_catalogue_missing")
        report["ready_to_publish"] = False
    if report["legacy_catalogue"].get("migration_blocked"):
        report.setdefault("blockers", []).append("legacy_active_batch_unfinished")
        report["ready_to_publish"] = False
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    # Missing external configuration is an explicit blocker in the JSON,
    # not permission to publish or a misleading successful live check.
    return 0


if __name__ == "__main__":
    sys.exit(main())
