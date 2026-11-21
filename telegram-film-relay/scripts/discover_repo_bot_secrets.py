"""Inventory ALL Telegram Bot API credentials available as GitHub Actions secrets.

This runs before any owner-user Telegram session, in a dedicated step.
The GitHub secrets JSON is NEVER written to disk or printed. Only a sanitized,
0600-permission manifest of verified BOT IDENTITIES (no tokens) is persisted.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

from scripts.provision_private_stock import bot_identity

# BotFather token shape, not a broad '*TOKEN*' name filter. This catches bots
# saved under unexpected names without calling getMe using non-Telegram secrets.
BOTFATHER = re.compile(r"^[0-9]{6,15}:[A-Za-z0-9_-]{20,160}$")
SECRET_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
BOT_USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")
RADAR_USERNAME = "cineradarfr_bot"
# Explicit S03 identity check: do not grant a publisher token to an unknown bot.
PUBLISHER_KEY = "CINEX_PUBLISH_BOT_TOKEN"


def _priority(name: str) -> tuple[int, str]:
    special = {
        "CINEX_RADAR_BOT_TOKEN": 0,
        "TELEGRAM_BOT_TOKEN": 1,
        PUBLISHER_KEY: 2,
    }
    return special.get(name, 3), name


def discover_all(secrets: dict, *, expected_publisher="", identify=bot_identity):
    if not isinstance(secrets, dict) or len(secrets) > 2000:
        raise ValueError("invalid_secret_bundle")
    publisher = expected_publisher.lstrip("@").casefold()
    verified, invalid = [], []
    seen = set()
    matching = 0
    for name in sorted(secrets, key=_priority):
        value = secrets[name]
        if not isinstance(name, str) or not SECRET_NAME.fullmatch(name):
            continue
        if not isinstance(value, str) or not BOTFATHER.fullmatch(value.strip()):
            continue
        matching += 1
        try:
            response = identify(value.strip())
            username = str(response.get("username") or "")
            bot_id = response.get("id")
            if (response.get("is_bot") is not True
                or type(bot_id) is not int or bot_id <= 0
                or not BOT_USERNAME.fullmatch(username)):
                raise ValueError("unverified_telegram_bot")
            if name == PUBLISHER_KEY and (
                not publisher or username.casefold() != publisher
            ):
                raise ValueError("publisher_identity_mismatch")
            if name == "CINEX_RADAR_BOT_TOKEN" and username.casefold() != RADAR_USERNAME:
                raise ValueError("radar_identity_mismatch")
            if bot_id not in seen:
                verified.append({
                    "id": bot_id,
                    "username": username,
                    "label": name,
                })
                seen.add(bot_id)
        except Exception:
            # No token/URL/exception details printed or persisted.
            invalid.append(name)
    if not any(b["username"].casefold() == RADAR_USERNAME for b in verified):
        raise RuntimeError("required_radar_identity_not_verified")
    return {
        "version": 1,
        "verified_bots": verified,
        "invalid_secret_labels": sorted(set(invalid)),
        "matching_credential_count": matching,
        "distinct_verified_bot_count": len(verified),
    }


def write_private_manifest(path: str, manifest: dict) -> None:
    # Reject overwrite, symlinks and accidental public permissions.
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(manifest, stream, ensure_ascii=True, separators=(",", ":"))
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    raw = os.environ.get("CINEX_GITHUB_SECRET_BUNDLE_JSON")
    if not raw:
        raise RuntimeError("repo_secrets_bundle_missing")
    data = json.loads(raw)
    manifest = discover_all(
        data,
        expected_publisher=os.environ.get("CINEX_PUBLISH_BOT_USERNAME", ""),
    )
    write_private_manifest(args.manifest, manifest)
    print(
        "CINEX_ALL_GITHUB_BOTS_VERIFIED",
        "bot_secret_values_detected", manifest["matching_credential_count"],
        "distinct_bots", manifest["distinct_verified_bot_count"],
        "unverified", len(manifest["invalid_secret_labels"]),
        "credential_values_logged", False,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Never print exception messages: they could contain token-bearing URLs.
        print("CINEX_ALL_GITHUB_BOTS_INVENTORY_ERROR", type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)
