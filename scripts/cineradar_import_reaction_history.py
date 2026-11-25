#!/usr/bin/env python3
"""One-time, read-only historical reaction migration from D1 to encrypted GitHub.

No tables are deleted or modified in D1. Never print signed URLs or SQL rows.
Do not run while any legacy D1 reaction job is enabled.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time

import requests

from scripts.cineradar_reaction_store import ReactionVault, LocalReactionDB, pack
from scripts.actu_foot_github_vault import VaultError

TABLES = (
    "channel_reaction_posts", "channel_reaction_jobs",
    "channel_reaction_extra_jobs", "channel_reaction_extra_bot_activation",
    "channel_reaction_terminal_posts",
)
DB_ID = "fa8b5009-bc1a-4a6e-b143-7a487c7297a5"


def export_reactions(session, account_id, token, *, polls=20):
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{DB_ID}/export"
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    options = {
        "output_format": "polling",
        "dump_options": {"tables": list(TABLES), "compatibility": "sqlite3_cli_only"},
    }
    bookmark = None
    for _ in range(polls):
        payload = dict(options)
        if bookmark:
            payload["current_bookmark"] = bookmark
        response = session.post(url, headers=headers, json=payload, timeout=55)
        response.raise_for_status()
        outer = response.json()
        result = outer.get("result") or {}
        if outer.get("success") is not True or result.get("success") is not True:
            raise RuntimeError("D1 historical export rejected")
        if result.get("status") == "complete":
            signed = (result.get("result") or {}).get("signed_url")
            if not signed or not signed.startswith("https://"):
                raise RuntimeError("D1 export completed without download link")
            # Signed URL is deliberately never printed, stored or persisted.
            downloaded = session.get(signed, timeout=55)
            downloaded.raise_for_status()
            if len(downloaded.content) > 30_000_000:
                raise RuntimeError("D1 reaction history export unexpectedly large")
            return downloaded.text
        if result.get("status") not in ("active", "pending"):
            raise RuntimeError("D1 reaction history export failed")
        bookmark = result.get("at_bookmark")
        if not bookmark:
            raise RuntimeError("D1 export missing continuation bookmark")
        time.sleep(2)
    raise RuntimeError("D1 export polling timed out")


def import_history(sql):
    db = sqlite3.connect(":memory:")
    try:
        db.executescript(sql)
        # The snapshot includes only the five reaction tables, not the rest of CineRadar.
        LocalReactionDB(db)
        pack(db, observer_offset=None)  # Validates schema, FK and size.
        return db
    except Exception:
        db.close()
        raise


def main():
    vault = ReactionVault(branch="main")
    # Fail closed if an encrypted record exists. Never reset or overwrite history.
    prior = vault.read(allow_new=True)
    if prior.sha is not None:
        from scripts.cineradar_reaction_store import unpack
        db, _ = unpack(prior.data)
        try:
            print("CINERADAR_REACTION_HISTORY_PRESENT_VALIDATED")
        finally:
            db.close()
        return 0
    token = os.getenv("CLOUDFLARE_API_TOKEN", "") or os.getenv("CF_API_TOKEN", "")
    account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    if not token or not account:
        raise RuntimeError("Historical import requires one-time Cloudflare export credentials")
    sql = export_reactions(requests.Session(), account, token)
    db = import_history(sql)
    try:
        packed = pack(db, observer_offset=None)
        vault.write(packed, expected_sha=None,
                    message="data(cineradar): encrypted D1 reaction history import")
        summary = {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in TABLES}
        print("CINERADAR_REACTION_HISTORY_IMPORTED", summary)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except VaultError as exc:
        print("CINERADAR_HISTORY_IMPORT_REJECTED:", str(exc), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print("CINERADAR_HISTORY_IMPORT_FAILED:", type(exc).__name__, file=sys.stderr)
        sys.exit(1)
