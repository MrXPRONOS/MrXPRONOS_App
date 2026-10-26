"""Actu Foot V2 operator backup/restore CLI. Never print plaintext or secrets."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
from scripts.actu_foot_v2_store import (
    COLLECTIONS, CollectionVault, VaultError, collection_path, decrypt,
    restore_backup, verify_audit,
)

def snapshot(root: Path, *, branch: str = "main", strict: bool = True) -> dict:
    if branch != "main":
        raise VaultError("Backup must come from approved main branch")
    root.mkdir(parents=True, exist_ok=True)
    index = {"format": "actufoot-v2-backup-v2", "collections": {}}
    for collection in COLLECTIONS:
        vault = CollectionVault(collection, branch=branch)
        response = vault.session.get(vault.url, headers=vault.headers,
                                     params={"ref": branch}, timeout=20)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        metadata = response.json()
        blob = base64.b64decode("".join(metadata["content"].split()), validate=True)
        records, header = decrypt(collection, blob.decode("utf-8"))
        if collection == "audit":
            verify_audit(records)
        target = root / (collection + ".aes.json")
        target.write_bytes(blob)
        os.chmod(target, 0o600)
        index["collections"][collection] = {
            "filename": target.name,
            "sha256": hashlib.sha256(blob).hexdigest(),
            "generation": header["generation"],
            "key_version": header["key_version"],
            "record_count": len(records),
            "source_sha": metadata["sha"],
        }
    if strict and not index["collections"]:
        raise VaultError("No encrypted collection available: backup aborted")
    (root / "manifest.json").write_text(json.dumps(index, sort_keys=True), encoding="utf-8")
    return index


def verify_directory(root: Path, *, require_records: bool = True) -> dict:
    index = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if index.get("format") != "actufoot-v2-backup-v2":
        raise VaultError("Unsupported backup manifest")
    collections = index.get("collections")
    if not isinstance(collections, dict) or (require_records and not collections):
        raise VaultError("Backup manifest has no collections")
    for name, meta in collections.items():
        if name not in COLLECTIONS or meta.get("filename") != name + ".aes.json":
            raise VaultError("Invalid backup collection entry")
        blob = (root / meta["filename"]).read_bytes()
        if hashlib.sha256(blob).hexdigest() != meta.get("sha256"):
            raise VaultError("Backup ciphertext digest mismatch")
        records, header = decrypt(name, blob.decode("utf-8"))
        if name == "audit":
            verify_audit(records)
        if (header["generation"] != meta["generation"]
                or header["key_version"] != meta["key_version"]
                or len(records) != meta["record_count"]):
            raise VaultError("Backup manifest mismatch")
    return index


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--operation", choices=("backup", "verify", "restore", "rotate", "recover-artifact"), required=True)
    cli.add_argument("--directory", default="/tmp/actufoot-v2-backup")
    cli.add_argument("--collection", choices=COLLECTIONS)
    cli.add_argument("--expected-sha", default="")
    cli.add_argument("--minimum-generation", type=int, default=0)
    cli.add_argument("--target-version", type=int, default=0)
    cli.add_argument("--confirm", default="")
    cli.add_argument("--artifact-id", type=int, default=0)
    args = cli.parse_args()
    root = Path(args.directory)
    if args.operation == "recover-artifact":
        from scripts.actu_foot_v2_artifact_recovery import fetch_artifact
        result = fetch_artifact(args.artifact_id, root)
        print("VERIFIED_ARTIFACT_READY", result["artifact_id"], len(result["collections"]))
    elif args.operation == "backup":
        result = snapshot(root)
        print("ENCRYPTED_BACKUP_OK", len(result["collections"]))
    elif args.operation == "verify":
        result = verify_directory(root)
        print("ENCRYPTED_BACKUP_VERIFIED", len(result["collections"]))
    elif args.operation == "restore":
        if args.confirm != "RESTORE_ENCRYPTED_V2" or not args.collection:
            raise VaultError("Explicit restore acknowledgment and collection required")
        verify_directory(root)
        payload = (root / (args.collection + ".aes.json")).read_text(encoding="utf-8")
        result = restore_backup(CollectionVault(args.collection, branch="main"), payload,
                                expected_sha=args.expected_sha, confirm=True,
                                minimum_generation=args.minimum_generation)
        print("RESTORE_COMPLETE", args.collection, bool(result))
    else:
        if args.confirm != "ROTATE_ENCRYPTED_V2" or not args.collection or args.target_version <= 1:
            raise VaultError("Explicit rotation acknowledgment and new key version required")
        result = CollectionVault(args.collection, branch="main").rotate(args.target_version)
        print("ROTATION_COMPLETE", args.collection, bool(result))


if __name__ == "__main__":
    main()
