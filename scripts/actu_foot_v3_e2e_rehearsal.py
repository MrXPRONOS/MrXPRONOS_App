"""Real Cloudflare KV end-to-end rehearsal of V3 compaction, in local memory only.

Uses a fresh throwaway AES key and a synthetic in-memory Git store. Never
writes any fixture or secret into production Git collections or D1 receipts.
The remote rehearsal namespace expires automatically.
"""
from __future__ import annotations
import base64
import json
import os
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from scripts.actu_foot_github_vault import VaultError
from scripts.actu_foot_v2_store import collection_path, encrypt, verify_audit
from scripts.actu_foot_v3_archive import archive_path, compact_month
from scripts.actu_foot_v3_cloud_archive import CloudArchive, recover_inventory
from scripts.actu_foot_v3_service import SnapshotReader, audit_receipts, inventory
from tests_football_channel.test_actu_foot_v3_complete import MemoryAtomic, fixture


def rehearsal():
    if os.getenv("GITHUB_EVENT_NAME") not in {"push", "schedule", "workflow_dispatch"}:
        raise VaultError("V3 E2E only runs inside the trusted GitHub workflow")
    if os.getenv("GITHUB_REF") != "refs/heads/main":
        raise VaultError("V3 E2E must run on main")
    # Never reuse the live key: this test's encrypted data is entirely synthetic.
    os.environ["ACTU_FOOT_V2_KEY_B64_V2"] = base64.b64encode(secrets.token_bytes(32)).decode("ascii")

    store = MemoryAtomic()
    archived = fixture(1, 1)
    active = fixture(1, 11)
    old_scheduled = fixture(2, 1)
    old_scheduled["state"] = "scheduled"
    original = {"archived": archived, "active": active, "not_finished": old_scheduled}
    store.files[collection_path("matches")] = encrypt("matches", original, key_version=2, generation=2)
    store.files[collection_path("audit")] = encrypt("audit", {}, key_version=2, generation=2)
    cutoff = datetime(2026, 4, 1, tzinfo=timezone.utc)
    before = dict(store.files)
    try:
        compact_month(store, "matches", field="kickoff_utc", cutoff=cutoff,
                      durable_copy=lambda *_: "incorrect-digest")
    except VaultError:
        pass
    else:
        raise VaultError("Refused backup should prevent live compaction")
    if before != store.files:
        raise VaultError("Failed external verification changed local live data")

    cloud = CloudArchive(rehearsal=True)
    committed = compact_month(store, "matches", field="kickoff_utc", cutoff=cutoff,
                              durable_copy=cloud.persist)
    if committed["moved"] != 1 or committed["partitions"] != 1 or not committed["commit"]:
        raise VaultError("Independent compaction did not commit one record")
    head, _ = store.head()
    remaining = store.load_collection("matches", head).data
    if set(remaining) != {"active", "not_finished"}:
        raise VaultError("Compaction removed an active or unfinished match")
    entries = store.load_collection("audit", head).data
    verify_audit(entries)
    receipts = audit_receipts(entries)
    path = archive_path("matches", "2026-01")
    if set(receipts) != {path}:
        raise VaultError("Missing authenticated archive receipt")

    store.list_archives = lambda name, _: sorted(
        p for p in store.files if "/archive/" + name + "/" in p)
    if inventory(store, head) != receipts:
        raise VaultError("Archive inventory does not match hash-linked audit")
    reader = SnapshotReader(store)
    reader.refresh()
    if reader.query("matches")["count"] != 2 or reader.query("matches", archive=path)["count"] != 1:
        raise VaultError("Live and archive query indexes disagree")
    with tempfile.TemporaryDirectory(prefix="v3-e2e-") as temp:
        result = recover_inventory(receipts, Path(temp) / "recovered", cloud)
        if result["verified"] != 1 or result["remaining"] != 0:
            raise VaultError("Remote archive recovery incomplete")
        restored = (Path(temp) / "recovered" / "matches" / "2026-01.aes.json")
        if not restored.exists() or restored.read_text(encoding="utf-8") != store.files[path]:
            raise VaultError("Recovered ciphertext differs from verified archive")
    return {
        "synthetic_records_archived": 1,
        "synthetic_active_records_preserved": 2,
        "independent_cloudflare_copy": "readback_verified",
        "refused_backup_did_not_prune": True,
        "isolated_recovery": "verified",
        "audit_receipts": len(receipts),
        "git_production_mutations": 0,
        "live_keys_used": False,
    }


if __name__ == "__main__":
    print("V3_FULL_CYCLE_REHEARSAL", json.dumps(rehearsal(), sort_keys=True))
